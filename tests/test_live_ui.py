from __future__ import annotations

import json
import io
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from muclegal.evidence import verify_manifest
from muclegal.fetch import (
    FetchFailure,
    FetchPolicy,
    FetchResult,
    HttpFetcher,
    ScreenshotCaptureError,
)
from muclegal.fetch.playwright import _capture_html_evidence_image, _cookie_rejection_action
from muclegal.live import (
    LiveMonitorWorkflow,
    LiveWorkflowResult,
    _capture_transparency,
    _legal_subpage_candidates,
    _select_legal_link,
    changed_excerpts,
)
from muclegal.ui import CaseArchive, TERMINAL_RUN_STATUSES, create_app


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class _LiveHandler(BaseHTTPRequestHandler):
    page = (FIXTURES / "baseline.html").read_bytes()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\n"
            status = 200
            content_type = "text/plain; charset=utf-8"
        else:
            body = type(self).page
            status = 200
            content_type = "text/html; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class LiveServer:
    def __enter__(self):
        _LiveHandler.page = (FIXTURES / "baseline.html").read_bytes()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _LiveHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/page"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class RecordingAnalyzer:
    mode = "test_live"
    model = "test-model"

    def __init__(self, response_name: str = "llm-output-kerngleich.json") -> None:
        self.calls: list[dict] = []
        self.response_name = response_name

    def analyze(self, model_input: dict):
        self.calls.append(model_input)
        return json.loads((FIXTURES / self.response_name).read_text(encoding="utf-8"))


class FakeTsaClient:
    def __init__(self, status: str = "verified") -> None:
        self.status = status

    def timestamp_digest(self, digest_hex: str, output_directory: str | Path):
        del digest_hex
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        query = output / "manifest.tsq"
        query.write_bytes(b"query")
        return SimpleNamespace(status=self.status, query_path=str(query), response_path=None)


def fake_warc(url: str, output_directory: str | Path):
    del url
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    warc = output / "capture.warc.gz"
    cdx = output / "capture.cdx"
    warc.write_bytes(b"warc")
    cdx.write_text("cdx", encoding="utf-8")
    return SimpleNamespace(warc_path=str(warc), cdx_path=str(cdx))


def mismatched_warc(url: str, output_directory: str | Path):
    result = fake_warc(url, output_directory)
    return SimpleNamespace(
        warc_path=result.warc_path,
        cdx_path=result.cdx_path,
        response_payload_sha256="0" * 64,
    )


def fake_report(report: dict, output_path: str | Path) -> str:
    self_contained = Path(output_path)
    self_contained.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return str(self_contained)


def local_fetcher() -> HttpFetcher:
    return HttpFetcher(
        FetchPolicy(
            timeout_seconds=2,
            max_attempts=1,
            retry_backoff_seconds=0,
            require_public_network=False,
        )
    )


def poll(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] in TERMINAL_RUN_STATUSES:
            return result
        time.sleep(0.01)
    raise AssertionError("Prüflauf wurde nicht rechtzeitig beendet.")


class LiveWorkflowTests(unittest.TestCase):
    def test_browserless_html_evidence_image_is_labeled_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            destination = Path(output) / "evidence.png"
            capture = _capture_html_evidence_image(
                "<html><head><title>IKEA Test</title></head><body>"
                "<h1>Allgemeine Geschäftsbedingungen</h1>"
                "<p>Gespeicherter öffentlicher Inhalt.</p></body></html>",
                "https://www.ikea.com/de/de/customer-service/terms-conditions/",
                destination,
                protection=None,
                fallback_reason="Page.set_content: browser has been closed",
                browser_error="Target page, context or browser has been closed",
            )

            from PIL import Image

            with Image.open(destination) as image:
                dimensions = image.size

        self.assertEqual("http_snapshot_visualized", capture.capture_state)
        self.assertIn("keine pixelgetreue Live-Browser-Aufnahme", capture.state_reason)
        self.assertGreater(capture.size_bytes, 5_000)
        self.assertEqual(1440, dimensions[0])
        self.assertGreaterEqual(dimensions[1], 900)

    def test_browser_termination_uses_labeled_http_snapshot_fallback(self) -> None:
        fetcher = HttpFetcher(
            FetchPolicy(respect_robots=False, require_public_network=False, max_attempts=1)
        )
        fetched = FetchResult(
            requested_url="https://example.org",
            final_url="https://example.org/final",
            fetched_at="2026-08-20T12:00:00+00:00",
            status_code=200,
            headers=(),
            redirect_chain=(),
            body=b"<html><main>Gespeichert</main></html>",
            decoded_html="<html><main>Gespeichert</main></html>",
        )
        fallback_capture = SimpleNamespace(capture_state="http_snapshot_rendered")
        with tempfile.TemporaryDirectory() as output, patch(
            "muclegal.fetch.playwright.capture_page_screenshot",
            side_effect=ScreenshotCaptureError(
                "Page.goto: Target page, context or browser has been closed"
            ),
        ), patch(
            "muclegal.fetch.playwright.capture_html_screenshot",
            return_value=fallback_capture,
        ) as fallback, patch.object(fetcher, "fetch", return_value=fetched):
            captured = fetcher.capture_screenshot(
                "https://example.org", Path(output) / "fallback.png"
            )

        self.assertIs(captured, fallback_capture)
        self.assertEqual("<html><main>Gespeichert</main></html>", fallback.call_args.args[0])
        self.assertEqual("https://example.org/final", fallback.call_args.args[1])

    def test_all_protected_targets_still_create_reviewable_evidence_package(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            screenshot = root / "challenge.png"
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\nchallenge")
            capture = SimpleNamespace(
                path=str(screenshot),
                sha256="7" * 64,
                size_bytes=screenshot.stat().st_size,
                capture_state="protected_http_snapshot_rendered",
                state_reason="Gespeicherte Schutzseite ohne JavaScript gerendert.",
                interactions=(),
            )
            workflow = LiveMonitorWorkflow(
                root,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            result = workflow._capture_protection_evidence(
                protected_url="https://shop.test/",
                protection_type="Art des Seitenschutzes: JavaScript-Challenge.",
                browser_mode=True,
                protected_screenshot=capture,
                candidates=["https://shop.test/agb", "https://shop.test/privacy"],
                failures=["agb: blockiert", "privacy: blockiert"],
                progress=lambda _step, _message: None,
            )
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            manifest_valid = verify_manifest(case["artifacts"]["manifest"]).valid
            detail = CaseArchive(root).detail(
                Path(case["artifacts"]["manifest"]).parent.name
            )

        artifacts = {item["label"]: item for item in detail["artifacts"]}
        self.assertEqual("completed_with_warnings", result.status)
        self.assertTrue(manifest_valid)
        self.assertTrue(artifacts["protection_report"]["available"])
        self.assertEqual("warning", artifacts["requested_page_screenshot"]["status"])
        self.assertIsNone(case["captured_url"])

    def test_browser_transparency_records_non_stealth_runtime_values(self) -> None:
        outcome = SimpleNamespace(
            fetch_mode="browser_review",
            url="https://example.org/terms",
            browser_metadata={
                "user_agent": "MucLegal-Monitor/0.1 (+https://example.org/contact)",
                "navigator_webdriver": True,
                "automation_flags": [],
                "proxy": "keiner",
                "context": "frisch_pro_lauf",
                "robots_txt": "geprueft_abruf_erlaubt",
                "document_request_count": 1,
            },
        )
        transparency = _capture_transparency(
            outcome=outcome,
            configured_user_agent="unused",
            requested_url="https://example.org",
            protection_type="Art des Seitenschutzes: JavaScript-Challenge.",
        )

        self.assertTrue(transparency["navigator.webdriver"])
        self.assertEqual([], transparency["automation_flags"])
        self.assertEqual("keiner", transparency["proxy"])
        self.assertEqual("https://example.org", transparency["angefragte_url"])
        self.assertEqual(
            "https://example.org/terms", transparency["tatsaechlich_erfasste_url"]
        )

    def test_general_privacy_link_is_preferred_over_special_program(self) -> None:
        links = [
            {"label": "Datenschutzhinweise myMediaMarkt/myMediaMarkt+", "url": "https://shop.test/privacy/member", "same_domain": True},
            {"label": "Datenschutzhinweise Shop", "url": "https://shop.test/privacy/shop", "same_domain": True},
            {"label": "Datenschutzhinweise Terminvereinbarung", "url": "https://shop.test/privacy/terminvereinbarung", "same_domain": True},
        ]
        selected = _select_legal_link(links, "datenschutz")
        self.assertEqual("Datenschutzhinweise Shop", selected["label"])

    def test_changed_excerpts_only_contains_relevant_text(self) -> None:
        before, after = changed_excerpts("Kopf\nAlt\nFuß", "Kopf\nNeu\nFuß", context_lines=0)
        self.assertEqual("Alt", before)
        self.assertEqual("Neu", after)

    def test_private_target_is_rejected_before_network_fetch(self) -> None:
        fetcher = HttpFetcher(FetchPolicy(require_public_network=True, max_attempts=1))
        with self.assertRaises(FetchFailure) as caught:
            fetcher.fetch("http://127.0.0.1/private")
        self.assertEqual("non_public_target", caught.exception.code)
        self.assertTrue(caught.exception.manual_review)

    def test_baseline_unchanged_and_changed_live_flow(self) -> None:
        analyzer = RecordingAnalyzer()
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            baseline = workflow.run(server.url)
            unchanged = workflow.run(server.url)
            self.assertEqual("baseline_created", baseline.status)
            self.assertEqual("unchanged", unchanged.status)
            self.assertEqual([], analyzer.calls)

            _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
            changed = workflow.run(server.url)
            case = json.loads(Path(changed.case_path).read_text(encoding="utf-8"))
            manifest_valid = verify_manifest(case["artifacts"]["manifest"]).valid

        self.assertEqual("completed", changed.status)
        self.assertEqual(1, len(analyzer.calls))
        sent = analyzer.calls[0]
        self.assertNotIn("raw_html", json.dumps(sent))
        self.assertIn("20 % Rabatt", sent["aenderung"]["vorher"])
        self.assertIn("30 % Rabatt", sent["aenderung"]["nachher"])
        self.assertIsNone(case["assessment"]["freigabe_durch_mensch"])
        self.assertTrue(case["clause_findings"])
        self.assertIn(
            case["clause_findings"][0]["classification"],
            {"beseitigt", "kerngleich", "neuer_sachverhalt", "unsicher"},
        )
        self.assertTrue(manifest_valid)

    def test_capture_baseline_adds_agb_and_privacy_screenshots(self) -> None:
        captured_urls: list[str] = []

        def fake_screenshot(url: str, destination: str | Path):
            captured_urls.append(url)
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + url.encode("utf-8"))
            return SimpleNamespace(
                path=str(path),
                sha256="1" * 64,
                size_bytes=path.stat().st_size,
                capture_state="page_content",
                state_reason=None,
                interactions=(
                    {
                        "type": "cookie_banner",
                        "action": "alle_optionalen_cookies_abgelehnt",
                        "button_text": "Alle ablehnen",
                    },
                ),
            )

        page = b"""<html><main><h1>Shop</h1></main><footer>
          <a href='/agb'>Allgemeine Geschaeftsbedingungen</a>
          <a href='/privacy'>Datenschutzerklaerung</a>
        </footer></html>"""
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.page = page
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
                screenshot_capturer=fake_screenshot,
            )
            result = workflow.run(server.url, capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            manifest_valid = verify_manifest(case["artifacts"]["manifest"]).valid
            detail = CaseArchive(output).detail(Path(case["artifacts"]["manifest"]).parent.name)
            interactions = json.loads(
                Path(case["artifacts"]["screenshot_interactions"]).read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(f"{server.url.rsplit('/', 1)[0]}/agb", captured_urls)
        self.assertIn(f"{server.url.rsplit('/', 1)[0]}/privacy", captured_urls)
        self.assertIn("agb_screenshot", case["artifacts"])
        self.assertIn("privacy_screenshot", case["artifacts"])
        self.assertEqual(
            interactions["screenshots"]["agb_screenshot"][0]["button_text"],
            "Alle ablehnen",
        )
        self.assertTrue(manifest_valid)
        artifacts = {item["label"]: item for item in detail["artifacts"]}
        self.assertTrue(artifacts["agb_screenshot"]["available"])
        self.assertTrue(artifacts["privacy_screenshot"]["available"])

    def test_cookie_rejection_action_never_accepts_consent(self) -> None:
        self.assertEqual(
            _cookie_rejection_action("Alle ablehnen", "Wir verwenden Cookies"),
            "alle_optionalen_cookies_abgelehnt",
        )
        self.assertEqual(
            _cookie_rejection_action("Ablehnen", "Cookie-Einwilligung"),
            "optionale_cookies_abgelehnt",
        )
        self.assertIsNone(_cookie_rejection_action("Ablehnen", "Newsletter bestellen"))
        self.assertIsNone(_cookie_rejection_action("Alle akzeptieren", "Cookie-Banner"))

    def test_warc_failure_keeps_result_and_marks_warning(self) -> None:
        analyzer = RecordingAnalyzer()

        def failing_warc(*args, **kwargs):
            del args, kwargs
            raise RuntimeError("WARC-Werkzeug fehlt")

        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                warc_capturer=failing_warc,
                tsa_client=FakeTsaClient(status="pending"),
                report_builder=fake_report,
            )
            workflow.run(server.url)
            _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
            result = workflow.run(server.url)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            warc_status_exists = Path(case["artifacts"]["warc_status"]).is_file()

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("warning", result.step_states["warc"])
        self.assertEqual("warning", result.step_states["timestamp"])
        self.assertIn("unvollständig", case["evidence"]["warc_status"])
        self.assertEqual("pending", case["evidence"]["timestamp_status"])
        self.assertTrue(warc_status_exists)

    def test_capture_baseline_creates_legal_page_artifact_without_llm(self) -> None:
        analyzer = RecordingAnalyzer()
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.page = b"""<html><body><main>Start</main><footer>
                <a href='/agb'>Allgemeine Geschaeftsbedingungen</a>
                <a href='/datenschutz'>Datenschutzerklaerung</a>
                </footer></body></html>"""
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            result = workflow.run(server.url, capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            legal_pages = json.loads(
                Path(case["artifacts"]["legal_pages"]).read_text(encoding="utf-8")
            )
            transparency = Path(case["artifacts"]["capture_transparency"]).read_text(
                encoding="utf-8"
            )

        self.assertEqual("completed", result.status)
        self.assertEqual("capture_only", case["analysis_mode"])
        self.assertEqual([], analyzer.calls)
        self.assertEqual("http", legal_pages["agb"][0]["url"].split(":", 1)[0])
        self.assertTrue(legal_pages["agb"][0]["url"].endswith("/agb"))
        self.assertTrue(legal_pages["datenschutz"][0]["url"].endswith("/datenschutz"))
        self.assertIn('erfassungsmodus: "direkter_http_abruf"', transparency)
        self.assertIn("automation_flags: []", transparency)
        self.assertIn("model_output", case["not_applicable_artifacts"])

    def test_mismatched_warc_is_never_presented_as_identical_capture(self) -> None:
        analyzer = RecordingAnalyzer()
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                warc_capturer=mismatched_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            workflow.run(server.url)
            _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
            result = workflow.run(server.url)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("separate_recapture_mismatch", case["evidence"]["capture_relation"])
        self.assertIn("unterschiedliche Antwortbytes", " ".join(case["warnings"]))

    def test_default_primary_warc_is_bound_to_saved_snapshot(self) -> None:
        analyzer = RecordingAnalyzer()
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            workflow.run(server.url)
            _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
            result = workflow.run(server.url)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
        self.assertEqual("completed", result.status)
        self.assertEqual("exact_payload", case["evidence"]["capture_relation"])
        self.assertEqual(
            case["evidence"]["snapshot_payload_sha256"],
            case["evidence"]["warc_payload_sha256"],
        )


class LiveUiTests(unittest.TestCase):
    def test_verification_mode_is_explicit_and_forwarded_only_when_enabled(self) -> None:
        class VerificationWorkflow:
            tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))

            def run(self, url, progress, *, capture_baseline=False, browser_mode=False):
                self.browser_mode = browser_mode
                progress("browser", "Browsermodus geprüft")
                return LiveWorkflowResult("protected", "SEITENSCHUTZ ERKANNT")

        with tempfile.TemporaryDirectory() as output:
            workflow = VerificationWorkflow()
            app = create_app(
                Path(output) / "latest-case.json",
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                page = client.get("/beweis-labor")
                started = client.post(
                    "/api/v1/evidence-runs",
                    json={"url": "https://example.org", "verification_mode": True},
                ).json()
                for _ in range(100):
                    result = client.get(
                        f"/api/v1/evidence-runs/{started['run_id']}"
                    ).json()
                    if result["status"] in TERMINAL_RUN_STATUSES:
                        break
                    time.sleep(0.01)

        self.assertIn('id="verification-mode"', page.text)
        self.assertIn("Überprüfungsmodus", page.text)
        self.assertNotIn("Grau-Modus", page.text)
        self.assertIn("keine Tarntechniken", page.text)
        self.assertTrue(started["verification_mode"])
        self.assertTrue(workflow.browser_mode)

    def test_missing_key_disables_form_and_rejects_api(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=RecordingAnalyzer,
                tsa_client=FakeTsaClient(),
            )
            app = create_app(
                workflow.latest_case_path,
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                page = client.get("/")
                response = client.post("/api/runs", json={"url": "https://example.org"})
        self.assertEqual(200, page.status_code)
        self.assertIn("ANTHROPIC_API_KEY", page.text)
        self.assertIn("disabled", page.text)
        self.assertEqual(503, response.status_code)

    def test_polling_api_runs_baseline_unchanged_and_changed(self) -> None:
        analyzer = RecordingAnalyzer()
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            app = create_app(
                workflow.latest_case_path,
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=True,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                page = client.get("/")
                first = client.post("/api/runs", json={"url": server.url})
                baseline = poll(client, first.json()["run_id"])
                second = client.post("/api/runs", json={"url": server.url})
                unchanged = poll(client, second.json()["run_id"])
                _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
                third = client.post("/api/runs", json={"url": server.url})
                completed = poll(client, third.json()["run_id"])
                result_page = client.get("/")

        self.assertIn("Umsetzung auf öffentlicher URL überwachen", page.text)
        self.assertIn("Unterlassungs- und Umsetzungsmonitor", page.text)
        self.assertEqual("baseline_created", baseline["status"])
        self.assertEqual("unchanged", unchanged["status"])
        self.assertEqual("completed", completed["status"])
        self.assertTrue(completed["result_available"])
        self.assertIn("Juristische Vorprüfung", result_page.text)
        self.assertEqual(1, len(analyzer.calls))

    def test_run_api_exposes_granular_skipped_and_success_states(self) -> None:
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(output, FIXTURES / "tenor.json", fetcher=local_fetcher())
            app = create_app(
                workflow.latest_case_path,
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=True,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                response = client.post("/api/runs", json={"url": server.url})
                baseline = poll(client, response.json()["run_id"])

        self.assertEqual("success", baseline["steps"]["fetch"])
        self.assertEqual("success", baseline["steps"]["normalize"])
        self.assertEqual("success", baseline["steps"]["compare"])
        self.assertEqual("skipped", baseline["steps"]["anthropic"])
        self.assertEqual("skipped", baseline["steps"]["timestamp"])

    def test_case_history_preview_and_artifact_path_safety(self) -> None:
        analyzer = RecordingAnalyzer()
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=lambda: analyzer,
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            workflow.run(server.url)
            _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
            workflow.run(server.url)
            _LiveHandler.page = (FIXTURES / "baseline.html").read_bytes()
            workflow.run(server.url)
            app = create_app(
                workflow.latest_case_path,
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=True,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                listed = client.get("/api/cases")
                case_id = listed.json()["cases"][0]["case_id"]
                detail = client.get(f"/api/cases/{case_id}")
                download = client.get(f"/api/v1/cases/{case_id}/download")
                preview = client.get(f"/api/cases/{case_id}/preview/raw_html")
                binary_preview = client.get(f"/api/cases/{case_id}/preview/warc")
                traversal = client.get("/api/cases/%2E%2E")

                bundle_case = Path(output) / "bundles" / case_id / "case.json"
                record = json.loads(bundle_case.read_text(encoding="utf-8"))
                record["artifacts"]["raw_html"] = str(FIXTURES / "baseline.html")
                bundle_case.write_text(json.dumps(record), encoding="utf-8")
                outside = client.get(f"/artifact/{case_id}/raw_html")

        self.assertEqual(200, listed.status_code)
        self.assertEqual(2, len(listed.json()["cases"]))
        self.assertEqual(
            sorted((item["erkannt_am"] for item in listed.json()["cases"]), reverse=True),
            [item["erkannt_am"] for item in listed.json()["cases"]],
        )
        self.assertEqual(1, len({item["url"] for item in listed.json()["cases"]}))
        self.assertNotIn("assessment", listed.text)
        self.assertEqual(200, detail.status_code)
        self.assertEqual(200, download.status_code)
        self.assertEqual("application/zip", download.headers["content-type"])
        with zipfile.ZipFile(io.BytesIO(download.content)) as package:
            self.assertIn("case.json", package.namelist())
            self.assertTrue(any(name.startswith("artefakte/raw_html") for name in package.namelist()))
        self.assertNotIn("begruendung", detail.text)
        self.assertIn("<html", preview.json()["content"].lower())
        self.assertEqual(415, binary_preview.status_code)
        self.assertEqual(404, traversal.status_code)
        self.assertEqual(404, outside.status_code)

    def test_invalid_anthropic_output_is_not_published_as_result(self) -> None:
        class InvalidAnalyzer:
            mode = "test_invalid"
            model = "test-model"

            def analyze(self, model_input):
                del model_input
                return {"ergebnis": "kerngleich_umfasst"}

        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                analyzer_factory=InvalidAnalyzer,
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            app = create_app(
                workflow.latest_case_path,
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=True,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                first = client.post("/api/runs", json={"url": server.url})
                poll(client, first.json()["run_id"])
                _LiveHandler.page = (FIXTURES / "legal-change.html").read_bytes()
                second = client.post("/api/runs", json={"url": server.url})
                failed = poll(client, second.json()["run_id"])

            saved_invalid_outputs = list(Path(output).glob("bundles/*/analysis/model-output.json"))
            latest_case_exists = workflow.latest_case_path.exists()

        self.assertEqual("failed", failed["status"])
        self.assertIn("sicher verworfen", failed["message"])
        self.assertFalse(failed["result_available"])
        self.assertFalse(latest_case_exists)
        self.assertEqual(1, len(saved_invalid_outputs))

    def test_single_active_run_is_enforced(self) -> None:
        started = threading.Event()
        release = threading.Event()

        class BlockingWorkflow:
            tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))

            def run(self, url, progress):
                del url
                progress("fetch", "läuft")
                started.set()
                release.wait(timeout=2)
                return LiveWorkflowResult("unchanged", "fertig")

        with tempfile.TemporaryDirectory() as output:
            app = create_app(
                Path(output) / "latest-case.json",
                Path(output) / "reviews.sqlite3",
                workflow=BlockingWorkflow(),
                anthropic_ready=True,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                first = client.post("/api/runs", json={"url": "https://example.org"})
                self.assertTrue(started.wait(timeout=1))
                second = client.post("/api/runs", json={"url": "https://example.org"})
                release.set()
                poll(client, first.json()["run_id"])
        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)

    def test_evidence_lab_exposes_direct_url_run_and_audit_log(self) -> None:
        class AuditWorkflow:
            tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))

            def run(self, url, progress, *, capture_baseline=False):
                self.url = url
                self.capture_baseline = capture_baseline
                progress("fetch", "robots.txt geprüft und Seite abgerufen")
                progress("normalize", "flüchtige Inhalte entfernt")
                progress("compare", "SHA-256 mit Referenz verglichen")
                return LiveWorkflowResult(
                    "unchanged",
                    "Keine relevante Änderung erkannt.",
                    step_states={
                        "fetch": "success", "normalize": "success",
                        "screenshot": "skipped", "compare": "success",
                        "anthropic": "skipped", "warc": "skipped",
                        "manifest": "skipped", "timestamp": "skipped",
                    },
                )

        with tempfile.TemporaryDirectory() as output:
            workflow = AuditWorkflow()
            app = create_app(
                Path(output) / "latest-case.json",
                Path(output) / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                page = client.get("/beweis-labor")
                started = client.post(
                    "/api/v1/evidence-runs", json={"url": "https://example.org/angebote"}
                )
                run_id = started.json()["run_id"]
                for _ in range(100):
                    result = client.get(f"/api/v1/evidence-runs/{run_id}").json()
                    if result["status"] in TERMINAL_RUN_STATUSES:
                        break
                    time.sleep(0.01)

        self.assertEqual(200, page.status_code)
        self.assertNotIn("Eine URL. Eine nachvollziehbare Beweisspur.", page.text)
        self.assertIn("Prüfverlauf", page.text)
        self.assertNotIn("ANTHROPIC_API_KEY", page.text)
        self.assertNotIn("Anthropic wurde nicht aufgerufen", page.text)
        self.assertIn("Beweispaket herunterladen", page.text)
        self.assertIn("SEITENSCHUTZ ERKANNT", page.text)
        self.assertEqual(202, started.status_code)
        self.assertEqual("https://example.org/angebote", workflow.url)
        self.assertTrue(workflow.capture_baseline)
        self.assertEqual("unchanged", result["status"])
        self.assertEqual(
            ["queued", "fetch", "normalize", "compare", "compare"],
            [event["step"] for event in result["audit_log"]],
        )

    def test_evidence_lab_stream_reports_real_backend_progress(self) -> None:
        class StreamingWorkflow:
            tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))

            def run(self, url, progress, *, capture_baseline=False):
                del url, capture_baseline
                progress("fetch", "Seite wird abgerufen")
                progress("normalize", "Inhalt wird aufbereitet")
                return LiveWorkflowResult(
                    "unchanged",
                    "Keine relevante Änderung erkannt.",
                    step_states={
                        "fetch": "success", "normalize": "success",
                        "screenshot": "skipped", "compare": "success",
                        "anthropic": "skipped", "warc": "skipped",
                        "manifest": "skipped", "timestamp": "skipped",
                    },
                )

        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                workflow=StreamingWorkflow(),
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/evidence-runs/stream",
                    json={"url": "https://example.org/"},
                )

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        messages = [json.loads(line) for line in response.text.splitlines() if line]
        self.assertEqual("run", messages[0]["type"])
        self.assertEqual("complete", messages[-1]["type"])
        observed_steps = {
            event["step"]
            for message in messages
            for event in message["run"].get("audit_log", [])
        }
        self.assertIn("fetch", observed_steps)
        self.assertIn("normalize", observed_steps)

    def test_legal_fallback_candidates_keep_origin_and_locale(self) -> None:
        candidates = _legal_subpage_candidates("https://www.temu.com/de")
        self.assertIn("https://www.temu.com/de/terms-of-use.html", candidates)
        self.assertIn("https://www.temu.com/de/privacy-policy.html", candidates)
        self.assertIn("https://www.temu.com/de-en/privacy-policy.html", candidates)
        self.assertTrue(all(url.startswith("https://www.temu.com/") for url in candidates))


if __name__ == "__main__":
    unittest.main()
