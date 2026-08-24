from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from muclegal.domain_monitor import CaseDomainMonitor, ScanPolicy
from muclegal.evidence import create_manifest
from muclegal.fetch import DomInspectionCapture, FetchFailure, FetchResult
from muclegal.live import LiveMonitorWorkflow
from muclegal.monitoring_cases import MonitoringCaseError, MonitoringCaseRepository
from muclegal.ui import TERMINAL_RUN_STATUSES, create_app


ROOT = Path(__file__).resolve().parents[1]
CLAUSE = "Die Rücksendekosten trägt stets der Verbraucher."


class FakeFetcher:
    def __init__(self, pages: dict[str, bytes], blocked: set[str] | None = None) -> None:
        self.pages = pages
        self.blocked = blocked or set()

    def fetch(self, url: str) -> FetchResult:
        if url in self.blocked:
            raise FetchFailure("robots_disallowed", "robots.txt untersagt den Abruf.", manual_review=True)
        body = self.pages.get(url)
        if body is None:
            raise FetchFailure("http_error", "HTTP 404", status_code=404)
        content_type = "application/xml" if url.endswith("sitemap.xml") else "text/html; charset=utf-8"
        return FetchResult(
            requested_url=url,
            final_url=url,
            fetched_at="2026-08-20T10:00:00+00:00",
            status_code=200,
            headers=(("Content-Type", content_type),),
            redirect_chain=(),
            body=body,
            decoded_html=body.decode("utf-8"),
        )


class BrowserFallbackFetcher(FakeFetcher):
    def __init__(
        self,
        pages: dict[str, bytes],
        *,
        protected: set[str],
        browser_pages: dict[str, bytes],
    ) -> None:
        super().__init__(pages)
        self.protected = protected
        self.browser_pages = browser_pages
        self.last_browser_capture = None
        self._capture_root: Path | None = None

    def fetch(self, url: str) -> FetchResult:
        if url in self.protected:
            raise FetchFailure(
                "protected_or_login_page",
                "Abruf abgebrochen: HTTP-Zugriffsschutz (Status 403).",
                status_code=403,
                manual_review=True,
            )
        return super().fetch(url)

    @contextmanager
    def capture_session(self, output_root: str | Path):
        self._capture_root = Path(output_root) / "synthetic-browser-run"
        self._capture_root.mkdir(parents=True, exist_ok=False)
        try:
            yield self
        finally:
            self._capture_root = None

    def fetch_in_browser(self, url: str) -> FetchResult:
        body = self.browser_pages.get(url)
        if self._capture_root is None:
            raise FetchFailure(
                "protected_or_login_page",
                "Browser-Prüfversuch blieb geschützt.",
                status_code=403,
                manual_review=True,
            )
        artifact_root = self._capture_root / f"{len(list(self._capture_root.iterdir())) + 1:02d}-main"
        artifact_root.mkdir()
        if body is None:
            challenge = (
                b'<html><body><iframe src="https://geo.captcha-delivery.com/interstitial/" '
                b'title="DataDome Device Check"></iframe></body></html>'
            )
            (artifact_root / "raw.html").write_bytes(challenge)
            self.last_browser_capture = SimpleNamespace(
                artifact_directory=str(artifact_root),
                capture_completeness="durch_seitenschutz_begrenzt",
                screenshot=None,
            )
            raise FetchFailure(
                "protected_or_login_page",
                "Browser-Prüfversuch blieb durch CAPTCHA geschützt.",
                status_code=200,
                manual_review=True,
            )
        (artifact_root / "raw.html").write_bytes(body)
        (artifact_root / "screenshot-full-page.png").write_bytes(b"synthetic-png")
        self.last_browser_capture = SimpleNamespace(
            artifact_directory=str(artifact_root),
            capture_completeness="vollstaendig_erfasst",
            screenshot=SimpleNamespace(path=str(artifact_root / "screenshot-full-page.png")),
        )
        return FetchResult(
            requested_url=url,
            final_url=url,
            fetched_at="2026-08-24T21:00:00+00:00",
            status_code=200,
            headers=(("Content-Type", "text/html; charset=utf-8"),),
            redirect_chain=(),
            body=body,
            decoded_html=body.decode("utf-8"),
            fetch_mode="browser_review",
        )

    def capture_screenshot(self, url: str, destination: str | Path):
        del url
        destination = Path(destination)
        destination.write_bytes(b"synthetic-protection-png")
        return SimpleNamespace(path=str(destination))


def clause_payload() -> dict:
    return {
        "fall_id": "VZ-TEST-1",
        "domain": "example.test",
        "source_url": "https://example.test/agb",
        "violation_type": "klausel",
        "description": "Bereits durch die Verbraucherzentrale geprüfte AGB-Klausel.",
        "tenor_element": "Verwendung der beanstandeten Rücksendekostenklausel",
        "monitoring_target": "Beanstandete Klausel darf nicht weiter verwendet werden.",
        "relevant_page_types": ["AGB"],
        "clause_text": CLAUSE,
        "element_label": None,
        "element_function": None,
        "element_error": None,
        "allowed_subdomains": [],
    }


def element_payload() -> dict:
    return {
        "fall_id": "VZ-TEST-2",
        "domain": "example.test",
        "source_url": "https://example.test/vertrag",
        "violation_type": "element",
        "description": "Kündigungsbutton fehlt.",
        "tenor_element": "Ständig verfügbare Kündigungsschaltfläche",
        "monitoring_target": "Verträge hier kündigen",
        "relevant_page_types": ["Startseite", "Vertragsabschluss"],
        "clause_text": None,
        "element_label": "Verträge hier kündigen",
        "element_function": "Öffnet den öffentlichen Kündigungsprozess",
        "element_error": "fehlt",
        "allowed_subdomains": [],
    }


class MonitoringCaseTests(unittest.TestCase):
    def test_manually_attached_baseline_turns_first_run_into_comparison(self) -> None:
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            "https://example.test/agb": (
                f"<html><body><main><h1>AGB</h1><p>{CLAUSE}</p></main></body></html>"
            ).encode(),
        }
        baseline_text = f"Allgemeine Geschäftsbedingungen\n{CLAUSE}"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.create(clause_payload())
            case = repository.attach_baseline_evidence(case.case_id, {
                "evidence_case_id": "evidence-baseline-1",
                "requested_url": "https://example.test/agb",
                "captured_url": "https://example.test/agb",
                "captured_at": "2026-08-24T10:00:00+00:00",
                "manifest_sha256": "a" * 64,
                "documents": [{
                    "role": "agb",
                    "text": baseline_text,
                    "sha256": hashlib.sha256(baseline_text.encode()).hexdigest(),
                }],
            })
            case = repository.review(case.case_id, "freigegeben")
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=FakeFetcher(pages),
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)

        self.assertEqual("unveraendert_fortbestehend", result.status)
        self.assertEqual(
            "evidence-baseline-1",
            result.reported_initial_violation["baseline_evidence"]["evidence_case_id"],
        )
        self.assertTrue(any(item["baseline_similarity"] == 1.0 for item in result.document_findings))
        self.assertNotIn("documents", case.to_dict()["baseline_evidence"])

    def test_legacy_case_rows_get_source_url_as_default_profile_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "cases.sqlite3"
            repository = MonitoringCaseRepository(database, Path(directory) / "intake")
            created = repository.create(clause_payload())
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    "UPDATE monitoring_cases SET relevant_page_types_json = ? WHERE case_id = ?",
                    ('["AGB"]', created.case_id),
                )
                connection.commit()
            finally:
                connection.close()

            loaded = repository.get(created.case_id)

        self.assertEqual((created.source_url,), loaded.target_urls)
        self.assertEqual(("AGB",), loaded.relevant_page_types)

    def test_case_profile_persists_required_urls_variants_and_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = MonitoringCaseRepository(
                Path(directory) / "cases.sqlite3", Path(directory) / "intake"
            )
            record = repository.create({
                **element_payload(),
                "target_urls": [
                    "https://example.test/",
                    "https://example.test/policies/terms-of-service",
                ],
                "element_labels": ["Abo kündigen", "Abonnement beenden"],
                "nicht_umfasst": ["Ein freiwilliger Supportlink ohne Kündigungsfunktion."],
            })

        self.assertEqual(
            (
                "https://example.test/vertrag",
                "https://example.test/",
                "https://example.test/policies/terms-of-service",
            ),
            record.target_urls,
        )
        self.assertIn("Verträge hier kündigen", record.element_labels)
        self.assertIn("Abo kündigen", record.element_labels)
        self.assertEqual(1, len(record.nicht_umfasst))

    def test_unlinked_required_terms_page_is_still_monitored(self) -> None:
        terms_url = "https://example.test/policies/terms-of-service"
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            "https://example.test/": b"<html><body><main>Shop ohne AGB-Link</main></body></html>",
            terms_url: (
                f"<html><body><main><h1>AGB</h1><p>{CLAUSE}</p></main></body></html>"
            ).encode(),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.create({
                **clause_payload(),
                "source_url": "https://example.test/",
                "target_urls": ["https://example.test/", terms_url],
            })
            case = repository.review(case.case_id, "freigegeben")
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=FakeFetcher(pages),
                policy=ScanPolicy(max_urls=10, max_seconds=5),
            ).run(case)

        self.assertIn(terms_url, result.coverage["captured_required_target_urls"])
        self.assertEqual([], result.coverage["missing_required_target_urls"])
        self.assertTrue(any(item["url"] == terms_url for item in result.document_findings))
        self.assertTrue(any(item["reported_clause_exact"] for item in result.document_findings))

    def test_required_protected_target_uses_transparent_browser_fallback(self) -> None:
        event_url = "https://example.test/event"
        home_url = "https://example.test/"
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            home_url: b"<html><body><main>Ticketmarkt</main></body></html>",
        }
        browser_pages = {
            event_url: b"<html><body><main>Oeffentliche Veranstaltungsseite</main></body></html>",
        }

        def no_match(url: str, destination: Path, **kwargs) -> DomInspectionCapture:
            del url, kwargs
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("{}", encoding="utf-8")
            screenshot = destination.with_suffix(".png")
            screenshot.write_bytes(b"png")
            return DomInspectionCapture(
                str(destination), str(screenshot), "0" * 64, (), (), (),
                "kein_passender_navigationspfad", (),
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.create({
                **element_payload(),
                "source_url": event_url,
                "target_urls": [event_url, home_url],
            })
            case = repository.review(case.case_id, "freigegeben")
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=BrowserFallbackFetcher(
                    pages,
                    protected={event_url},
                    browser_pages=browser_pages,
                ),
                dom_inspector=no_match,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)
            manifest = json.loads(Path(result.artifacts["manifest"]).read_text(encoding="utf-8"))

        self.assertEqual("referenzzustand_dokumentiert", result.status)
        self.assertTrue(result.coverage["complete_within_scope"])
        self.assertIn(event_url, result.coverage["captured_required_target_urls"])
        self.assertEqual([], result.coverage["blocked_urls"])
        self.assertEqual("captured", result.coverage["browser_fallbacks"][0]["browser_status"])
        self.assertEqual("browser_review", result.coverage["browser_fallbacks"][0]["browser_fetch_mode"])
        self.assertTrue(
            any(
                item["path"].endswith("screenshot-full-page.png")
                for item in manifest["artifacts"]
            )
        )

    def test_failed_required_dom_inspection_keeps_coverage_incomplete(self) -> None:
        event_url = "https://example.test/event"
        home_url = "https://example.test/"
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            event_url: b"<html><body><main>Veranstaltung</main></body></html>",
            home_url: b"<html><body><main>Ticketmarkt</main></body></html>",
        }

        def partial_inspection(url: str, destination: Path, **kwargs) -> DomInspectionCapture:
            del kwargs
            if url == event_url:
                raise RuntimeError("synthetischer Browserabbruch")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("{}", encoding="utf-8")
            screenshot = destination.with_suffix(".png")
            screenshot.write_bytes(b"png")
            return DomInspectionCapture(
                str(destination), str(screenshot), "0" * 64, (), (), (),
                "kein_passender_navigationspfad", (),
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.create({
                **element_payload(),
                "source_url": event_url,
                "target_urls": [event_url, home_url],
            })
            case = repository.review(case.case_id, "freigegeben")
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=FakeFetcher(pages),
                dom_inspector=partial_inspection,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)

        self.assertEqual("pruefung_unvollstaendig", result.status)
        self.assertFalse(result.coverage["complete_within_scope"])
        self.assertEqual([event_url], result.coverage["missing_dom_target_urls"])
        self.assertTrue(result.coverage["dom_inspection_incomplete"])

    def test_failed_browser_fallback_manifests_a_protection_image(self) -> None:
        event_url = "https://example.test/event"
        pages = {"https://example.test/sitemap.xml": b"<urlset/>"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.review(
                repository.create({
                    **element_payload(),
                    "source_url": event_url,
                    "target_urls": [event_url],
                }).case_id,
                "freigegeben",
            )
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=BrowserFallbackFetcher(
                    pages,
                    protected={event_url},
                    browser_pages={},
                ),
                dom_inspector=lambda *args, **kwargs: None,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)
            manifest = json.loads(Path(result.artifacts["manifest"]).read_text(encoding="utf-8"))

        self.assertEqual("pruefung_unvollstaendig", result.status)
        fallback = result.coverage["browser_fallbacks"][0]
        self.assertEqual("failed", fallback["browser_status"])
        self.assertIsNone(fallback["screenshot_error"])
        self.assertTrue(str(fallback["screenshot_path"]).endswith("screenshot-full-page.png"))
        self.assertTrue(
            any(
                item["path"].endswith("screenshot-full-page.png")
                for item in manifest["artifacts"]
            )
        )

    def test_button_label_variants_are_forwarded_to_dom_inspection(self) -> None:
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            "https://example.test/vertrag": b"<html><body><main>Vertrag</main></body></html>",
        }
        received: list[tuple[str, ...]] = []

        def inspect(url: str, destination: Path, **kwargs) -> DomInspectionCapture:
            del url
            received.append(tuple(kwargs["labels"]))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("{}", encoding="utf-8")
            screenshot = destination.with_suffix(".png")
            screenshot.write_bytes(b"png")
            match = {
                "accessible_name": "Abo kündigen",
                "visible": True,
                "disabled": False,
                "obscured": False,
                "href": "https://example.test/kuendigen",
            }
            return DomInspectionCapture(
                str(destination), str(screenshot), "0" * 64, (match,), (match,), (),
                "gleichurspruengliches_ziel_dokumentiert", (),
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.create({
                **element_payload(),
                "element_labels": ["Abo kündigen", "Abonnement beenden"],
            })
            case = repository.review(case.case_id, "freigegeben")
            CaseDomainMonitor(
                root / "monitor",
                fetcher=FakeFetcher(pages),
                dom_inspector=inspect,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)

        self.assertTrue(received)
        self.assertIn("Abo kündigen", received[0])
        self.assertIn("Abonnement beenden", received[0])

    def test_case_intake_rejects_schemeless_url_and_unrelated_allowed_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = MonitoringCaseRepository(
                Path(directory) / "cases.sqlite3", Path(directory) / "intake"
            )
            schemeless = {**clause_payload(), "source_url": "example.test/agb"}
            unrelated = {**clause_payload(), "allowed_subdomains": ["attacker.test"]}
            invalid_port = {
                **clause_payload(), "source_url": "https://example.test:not-a-port/agb"
            }
            domain_with_path = {**clause_payload(), "domain": "example.test/unexpected"}

            with self.assertRaisesRegex(MonitoringCaseError, "vollständige"):
                repository.create(schemeless)
            with self.assertRaisesRegex(MonitoringCaseError, "echte Subdomains"):
                repository.create(unrelated)
            with self.assertRaisesRegex(MonitoringCaseError, "gültigen Port"):
                repository.create(invalid_port)
            with self.assertRaises(MonitoringCaseError):
                repository.create(domain_with_path)

    def test_screenshot_is_evidence_and_cannot_replace_required_fields(self) -> None:
        screenshot = {
            "filename": "beleg.png",
            "media_type": "image/png",
            "data_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nsynthetic").decode(),
        }
        with tempfile.TemporaryDirectory() as directory:
            repository = MonitoringCaseRepository(
                Path(directory) / "cases.sqlite3", Path(directory) / "intake"
            )
            with self.assertRaises(MonitoringCaseError):
                repository.create({"fall_id": "VZ-1"}, screenshot)
            record = repository.create(clause_payload(), screenshot)

        self.assertEqual("verbraucherzentrale", record.erstverstoss_festgestellt_durch)
        self.assertIsNotNone(record.screenshot_sha256)
        self.assertEqual("weitere_pruefung", record.decision)

    def test_api_requires_human_approval_and_case_id(self) -> None:
        pages = {
            "https://example.test/sitemap.xml": (
                b"<urlset><url><loc>https://example.test/agb</loc></url></urlset>"
            ),
            "https://example.test/agb": (
                f"<html><body><main><h1>AGB</h1><p>{CLAUSE}</p></main></body></html>"
            ).encode(),
        }
        fetcher = FakeFetcher(pages)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = MonitoringCaseRepository(root / "reviews.sqlite3", root / "intake")
            workflow = LiveMonitorWorkflow(root / "live", ROOT / "fixtures" / "tenor.json", fetcher=fetcher)
            monitor = CaseDomainMonitor(
                root / "domain", fetcher=fetcher, policy=ScanPolicy(max_urls=5, max_seconds=5)
            )
            app = create_app(
                workflow.latest_case_path,
                root / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=False,
                monitoring_cases=cases,
                domain_monitor=monitor,
            )
            request_payload = {**clause_payload(), "screenshot": None}
            with TestClient(app) as client:
                created = client.post("/api/v1/cases", json=request_payload)
                case_id = created.json()["case_id"]
                before_review = client.post("/api/v1/runs", json={"case_id": case_id})
                raw_url = client.post("/api/v1/runs", json={"url": "https://example.test/agb"})
                reviewed = client.post(
                    f"/api/v1/cases/{case_id}/review", json={"decision": "freigegeben"}
                )
                started = client.post("/api/v1/runs", json={"case_id": case_id})
                first = _poll(client, started.json()["run_id"])
                second_start = client.post("/api/v1/runs", json={"case_id": case_id})
                second = _poll(client, second_start.json()["run_id"])

        self.assertEqual(201, created.status_code)
        self.assertEqual(403, before_review.status_code)
        self.assertEqual(422, raw_url.status_code)
        self.assertEqual("freigegeben", reviewed.json()["decision"])
        self.assertEqual("referenzzustand_dokumentiert", first["status"])
        self.assertFalse(first["monitoring_result"]["reported_initial_violation"]["system_detected"])
        self.assertEqual("verbraucherzentrale", first["monitoring_result"]["reported_initial_violation"]["erstverstoss_festgestellt_durch"])
        self.assertEqual("unveraendert_fortbestehend", second["status"])
        self.assertIsNone(second["monitoring_result"]["freigabe_durch_mensch"])
        self.assertEqual("skipped", second["steps"]["anthropic"])
        self.assertEqual("success", second["steps"]["warc"])
        self.assertEqual("success", second["steps"]["manifest"])
        self.assertEqual("skipped", second["steps"]["timestamp"])

    def test_api_attaches_only_regular_manifest_valid_same_domain_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live_root = root / "live"
            cases = MonitoringCaseRepository(root / "reviews.sqlite3", root / "intake")
            workflow = LiveMonitorWorkflow(
                live_root, ROOT / "fixtures" / "tenor.json", fetcher=FakeFetcher({})
            )
            app = create_app(
                workflow.latest_case_path,
                root / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=False,
                monitoring_cases=cases,
            )
            regular_id = _write_baseline_bundle(live_root, "evidence-regular", god_mode=False)
            grey_id = _write_baseline_bundle(live_root, "god-evidence-grey", god_mode=True)
            wayback_id = _write_baseline_bundle(
                live_root,
                "evidence-wayback",
                god_mode=False,
                url=(
                    "https://web.archive.org/web/20241008191055/"
                    "https://www.decathlon.de/AGB_lp-P7ELHE"
                ),
            )
            spoofed_wayback_id = _write_baseline_bundle(
                live_root,
                "evidence-wayback-userinfo",
                god_mode=False,
                url=(
                    "https://web.archive.org/web/20241008191055/"
                    "https://attacker.test@www.decathlon.de/AGB_lp-P7ELHE"
                ),
            )
            with TestClient(app) as client:
                created = client.post(
                    "/api/v1/cases", json={**clause_payload(), "screenshot": None}
                ).json()
                regular = client.post(
                    f"/api/v1/cases/{created['case_id']}/baseline-evidence",
                    json={"evidence_case_id": regular_id},
                )
                grey = client.post(
                    f"/api/v1/cases/{created['case_id']}/baseline-evidence",
                    json={"evidence_case_id": grey_id},
                )
                decathlon = client.post(
                    "/api/v1/cases",
                    json={
                        **clause_payload(),
                        "fall_id": "VZ-DECATHLON-WAYBACK",
                        "domain": "www.decathlon.de",
                        "source_url": "https://www.decathlon.de/AGB_lp-P7ELHE",
                        "screenshot": None,
                    },
                ).json()
                wayback = client.post(
                    f"/api/v1/cases/{decathlon['case_id']}/baseline-evidence",
                    json={"evidence_case_id": wayback_id},
                )
                spoofed_wayback = client.post(
                    f"/api/v1/cases/{decathlon['case_id']}/baseline-evidence",
                    json={"evidence_case_id": spoofed_wayback_id},
                )

        self.assertEqual(201, regular.status_code)
        self.assertEqual(regular_id, regular.json()["baseline_evidence"]["evidence_case_id"])
        self.assertEqual(422, grey.status_code)
        self.assertIn("Grey-Mode", grey.json()["detail"])
        self.assertEqual(201, wayback.status_code)
        self.assertEqual(
            wayback_id, wayback.json()["baseline_evidence"]["evidence_case_id"]
        )
        self.assertEqual(422, spoofed_wayback.status_code)
        self.assertIn("Domain", spoofed_wayback.json()["detail"])

    def test_missing_element_is_only_reported_with_complete_coverage(self) -> None:
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            "https://example.test/vertrag": b"<html><body><a href='/agb'>AGB</a></body></html>",
            "https://example.test/agb": b"<html><body><p>Bedingungen</p></body></html>",
        }

        def no_match(url: str, destination: Path, **kwargs) -> DomInspectionCapture:
            del url, kwargs
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("{}", encoding="utf-8")
            screenshot = destination.with_suffix(".png")
            screenshot.write_bytes(b"png")
            return DomInspectionCapture(
                str(destination), str(screenshot), "0" * 64, (), (), (),
                "kein_passender_navigationspfad", (),
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.create(element_payload())
            case = repository.review(case.case_id, "freigegeben")
            complete = CaseDomainMonitor(
                root / "complete", fetcher=FakeFetcher(pages), dom_inspector=no_match,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)
            required_case = repository.review(
                repository.create({
                    **element_payload(),
                    "fall_id": "VZ-TEST-2-REQUIRED",
                    "target_urls": ["https://example.test/agb"],
                }).case_id,
                "freigegeben",
            )
            incomplete = CaseDomainMonitor(
                root / "incomplete",
                fetcher=FakeFetcher(pages, blocked={"https://example.test/agb"}),
                dom_inspector=no_match,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(required_case)

        self.assertEqual("referenzzustand_dokumentiert", complete.status)
        self.assertTrue(complete.coverage["complete_within_scope"])
        self.assertEqual("nicht_gefunden_im_pruefumfang", complete.element_findings[0]["state"])
        self.assertEqual("pruefung_unvollstaendig", incomplete.status)
        self.assertFalse(incomplete.coverage["complete_within_scope"])

    def test_blocked_optional_discovery_does_not_invalidate_required_profile(self) -> None:
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            "https://example.test/agb": (
                f"<html><body><p>{CLAUSE}</p><a href='/shop'>Shop</a></body></html>"
            ).encode(),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.review(
                repository.create(clause_payload()).case_id,
                "freigegeben",
            )
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=FakeFetcher(pages, blocked={"https://example.test/shop"}),
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)

        self.assertEqual("referenzzustand_dokumentiert", result.status)
        self.assertTrue(result.coverage["complete_within_scope"])
        optional_failure = next(
            item for item in result.coverage["skipped_urls"]
            if item["url"] == "https://example.test/shop"
        )
        self.assertFalse(optional_failure["required_by_case_profile"])

    def test_missing_dom_inspector_makes_element_coverage_incomplete(self) -> None:
        pages = {
            "https://example.test/sitemap.xml": b"<urlset/>",
            "https://example.test/vertrag": b"<html><body><main>Vertrag</main></body></html>",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = MonitoringCaseRepository(root / "cases.sqlite3", root / "intake")
            case = repository.review(
                repository.create(element_payload()).case_id, "freigegeben"
            )
            result = CaseDomainMonitor(
                root / "monitor",
                fetcher=FakeFetcher(pages),
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)

        self.assertEqual("pruefung_unvollstaendig", result.status)
        self.assertFalse(result.coverage["complete_within_scope"])
        self.assertTrue(result.coverage["dom_inspection_incomplete"])


def _poll(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        response = client.get(f"/api/v1/runs/{run_id}").json()
        if response["status"] in TERMINAL_RUN_STATUSES:
            return response
        time.sleep(0.01)
    raise AssertionError("Fallbezogener Lauf wurde nicht rechtzeitig beendet.")


def _write_baseline_bundle(
    root: Path, case_id: str, *, god_mode: bool, url: str = "https://example.test/agb"
) -> str:
    bundle_parent = root / ("god-mode-bundles" if god_mode else "bundles")
    bundle = bundle_parent / case_id
    role = bundle / "capture" / "agb"
    role.mkdir(parents=True)
    text = f"Allgemeine Geschäftsbedingungen\n{CLAUSE}"
    normalized = role / "normalized-text.txt"
    normalized.write_text(text, encoding="utf-8")
    index = role / "index.json"
    index.write_text("{}", encoding="utf-8")
    manifest = create_manifest(
        {"normalized_text": normalized, "capture_index": index}, bundle
    )
    record = {
        "url": url,
        "requested_url": url,
        "captured_url": url,
        "erkannt_am": "2026-08-24T10:00:00+00:00",
        "god_mode": god_mode,
        "evidence_suitability": "regulaer",
        "snapshot_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "capture_completeness": "vollstaendig_erfasst",
        "warnings": [],
        "assessment": {},
        "evidence": {"manifest_sha256": manifest.manifest_sha256},
        "artifacts": {
            "manifest": manifest.manifest_path,
            "normalized_text": str(normalized),
        },
        "capture_galleries": {"agb": {"index": "capture/agb/index.json"}},
    }
    (bundle / "case.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )
    return case_id


if __name__ == "__main__":
    unittest.main()
