from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from muclegal.evidence import verify_manifest
from muclegal.fetch import FetchFailure, FetchPolicy, HttpFetcher
from muclegal.live import LiveMonitorWorkflow, LiveWorkflowResult, changed_excerpts
from muclegal.ui import TERMINAL_RUN_STATUSES, create_app


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
        self.assertTrue(manifest_valid)

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


class LiveUiTests(unittest.TestCase):
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

        self.assertIn("Pipeline gegen öffentliche URL testen", page.text)
        self.assertIn("Pipeline Test Harness", page.text)
        self.assertEqual("baseline_created", baseline["status"])
        self.assertEqual("unchanged", unchanged["status"])
        self.assertEqual("completed", completed["status"])
        self.assertTrue(completed["result_available"])
        self.assertIn("Anthropic-Gateway", result_page.text)
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


if __name__ == "__main__":
    unittest.main()
