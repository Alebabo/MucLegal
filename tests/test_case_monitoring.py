from __future__ import annotations

import base64
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from muclegal.domain_monitor import CaseDomainMonitor, ScanPolicy
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
            incomplete = CaseDomainMonitor(
                root / "incomplete",
                fetcher=FakeFetcher(pages, blocked={"https://example.test/agb"}),
                dom_inspector=no_match,
                policy=ScanPolicy(max_urls=5, max_seconds=5),
            ).run(case)

        self.assertEqual("referenzzustand_dokumentiert", complete.status)
        self.assertTrue(complete.coverage["complete_within_scope"])
        self.assertEqual("nicht_gefunden_im_pruefumfang", complete.element_findings[0]["state"])
        self.assertEqual("pruefung_unvollstaendig", incomplete.status)
        self.assertFalse(incomplete.coverage["complete_within_scope"])

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


if __name__ == "__main__":
    unittest.main()
