from __future__ import annotations

import json
import io
import hashlib
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
from muclegal.fetch.playwright import (
    _capture_html_evidence_image,
    _capture_validated_screenshots,
    _cookie_rejection_action,
)
from muclegal.live import (
    LiveMonitorWorkflow,
    LiveWorkflowResult,
    _bundle_browser_capture_artifacts,
    _capture_transparency,
    _discover_legal_pages,
    _legal_subpage_candidates,
    _mark_god_mode_bundle,
    _select_legal_content_url,
    _select_legal_link,
    changed_excerpts,
)
from muclegal.normalize import NormalizationError
from muclegal.ui import CaseArchive, TERMINAL_RUN_STATUSES, create_app


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class _LiveHandler(BaseHTTPRequestHandler):
    page = (FIXTURES / "baseline.html").read_bytes()
    robots_status = 200
    robots_body = b"User-agent: *\nAllow: /\n"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/robots.txt":
            body = type(self).robots_body
            status = type(self).robots_status
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
        _LiveHandler.robots_status = 200
        _LiveHandler.robots_body = b"User-agent: *\nAllow: /\n"
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
    def test_shrinking_page_keeps_valid_tiles_instead_of_raising_clip_error(self) -> None:
        from PIL import Image
        from playwright.sync_api import Error as PlaywrightError

        class ShrinkingPage:
            def __init__(self) -> None:
                self.height_reads = 0

            def evaluate(self, expression: str):
                if "scrollHeight" in expression:
                    self.height_reads += 1
                    return 5_000 if self.height_reads <= 3 else 1_000
                if "scrollWidth" in expression:
                    return 1_440
                return None

            def wait_for_timeout(self, _milliseconds: int) -> None:
                return None

            def screenshot(self, *, path: str, full_page: bool, type: str, clip=None) -> None:
                del type
                if full_page:
                    raise PlaywrightError("Full-page screenshot failed")
                assert clip is not None
                Image.new("RGB", (int(clip["width"]), int(clip["height"])), "blue").save(
                    path, "PNG"
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = _capture_validated_screenshots(ShrinkingPage(), root, [])
            index = json.loads((root / "screenshot-index.json").read_text(encoding="utf-8"))

        self.assertEqual("teilweise_erfasst", capture.capture_completeness)
        self.assertEqual(1, len(capture.tile_paths))
        self.assertTrue(index["tile_errors"])
        self.assertEqual(1_000, index["reached_height_css_px"])

    def test_shopify_legal_paths_are_discovered_without_footer_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_path = root / "shopify.html"
            output_path = root / "legal-pages.json"
            html_path.write_text(
                "<html><head><script src='https://cdn.shopify.com/store.js'></script></head>"
                "<body><main>Shop ohne Rechtstextlinks</main></body></html>",
                encoding="utf-8",
            )

            _discover_legal_pages(
                html_path,
                "https://www.ankerkraut.de/",
                output_path,
            )
            legal_pages = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://www.ankerkraut.de/policies/terms-of-service",
            legal_pages["agb"][0]["url"],
        )
        self.assertEqual("known_shopify_public_path", legal_pages["agb"][0]["source"])
        self.assertEqual(
            "https://www.ankerkraut.de/policies/privacy-policy",
            legal_pages["datenschutz"][0]["url"],
        )

    def test_known_site_legal_paths_are_always_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_path = root / "page.html"
            html_path.write_text(
                "<html><body><main>Öffentliche Seite</main></body></html>",
                encoding="utf-8",
            )

            temu_path = root / "temu-legal-pages.json"
            _discover_legal_pages(html_path, "https://www.temu.com/", temu_path)
            temu = json.loads(temu_path.read_text(encoding="utf-8"))

            adidas_path = root / "adidas-legal-pages.json"
            _discover_legal_pages(html_path, "https://www.adidas.de/", adidas_path)
            adidas = json.loads(adidas_path.read_text(encoding="utf-8"))

        self.assertEqual(
            "https://www.temu.com/de/terms-of-use.html", temu["agb"][0]["url"]
        )
        self.assertEqual(
            "https://www.temu.com/de/privacy-policy.html",
            temu["datenschutz"][0]["url"],
        )
        self.assertEqual("known_site_public_path", temu["agb"][0]["source"])
        self.assertEqual(
            "https://www.adidas.de/terms_and_conditions", adidas["agb"][0]["url"]
        )
        self.assertEqual("known_site_public_path", adidas["agb"][0]["source"])

    def test_failure_discovery_keeps_one_agb_and_privacy_fallback_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_path = root / "page.html"
            html_path.write_text(
                "<html><body><main>Erreichbare Rechtstext-Unterseite</main></body></html>",
                encoding="utf-8",
            )
            output_path = root / "legal-pages.json"
            _discover_legal_pages(
                html_path,
                "https://shop.example/terms",
                output_path,
                fallback_source_url="https://shop.example/",
            )
            legal_pages = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual("https://shop.example/terms-of-use.html", legal_pages["agb"][0]["url"])
        self.assertEqual(
            "https://shop.example/privacy-policy.html",
            legal_pages["datenschutz"][0]["url"],
        )
        self.assertEqual("fallback_public_path", legal_pages["agb"][0]["source"])
        self.assertEqual(
            "fallback_public_path", legal_pages["datenschutz"][0]["source"]
        )

    def test_empty_main_creates_terminal_result_instead_of_normalization_exception(self) -> None:
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.page = b"<html><body><main></main></body></html>"
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )

            result = workflow.run(server.url, capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            run_result = json.loads(
                Path(case["artifacts"]["run_result"]).read_text(encoding="utf-8")
            )
            protection = json.loads(
                Path(case["artifacts"]["protection_report"]).read_text(encoding="utf-8")
            )

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("nicht_erfassbar", case["technical_result"]["code"])
        self.assertEqual("normalization_error", run_result["failure_code"])
        self.assertTrue(
            any("terms" in url or url.endswith("/agb") for url in protection["checked_subpages"])
        )
        self.assertTrue(
            any(
                "privacy" in url or url.endswith("/datenschutz")
                for url in protection["checked_subpages"]
            )
        )

    def test_robots_disallow_creates_terminal_refusal_record(self) -> None:
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.robots_body = b"User-agent: *\nDisallow: /\n"
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )

            result = workflow.run(server.url, capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("nicht_erfassbar", case["technical_result"]["code"])
        self.assertEqual(
            "geprueft_abruf_untersagt",
            case["capture_transparency"]["robots_txt"],
        )
        self.assertIn("nicht automatisiert abrufen", case["technical_result"]["next_action"])

    def test_private_url_creates_terminal_result_record_without_stacktrace(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=HttpFetcher(
                    FetchPolicy(require_public_network=True, max_attempts=1)
                ),
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )

            result = workflow.run(
                "http://127.0.0.1/private", capture_baseline=True
            )
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("nicht_erfassbar", case["technical_result"]["code"])
        self.assertEqual("URL nicht erfassbar", case["technical_result"]["label"])
        self.assertNotIn("FetchFailure", result.message)

    def test_invalid_url_creates_terminal_result_record(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )

            result = workflow.run("keine-url", capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("nicht_erfassbar", case["technical_result"]["code"])
        self.assertIn("HTTP(S)-URL", case["technical_result"]["what_was_found"])

    def test_second_normalization_error_preserves_browser_state_as_hint_package(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            role_root = root / "browser-state"
            role_root.mkdir()
            raw_html = "<html><body><main></main></body></html>"
            (role_root / "raw.html").write_text(raw_html, encoding="utf-8")
            (role_root / "dom-initial.html").write_text(raw_html, encoding="utf-8")
            (role_root / "normalized-text.txt").write_text("", encoding="utf-8")
            image_path = role_root / "screenshot-full-page.png"
            Image.new("RGB", (320, 180), "white").save(image_path, "PNG")
            Image.new("RGB", (160, 90), "white").save(
                role_root / "screenshot-preview.webp", "WEBP"
            )
            (role_root / "screenshot-index.json").write_text(
                json.dumps({
                    "mode": "full_page",
                    "capture_completeness": "teilweise_erfasst",
                    "full_page_attempt": {"path": "screenshot-full-page.png"},
                    "tiles": [],
                }),
                encoding="utf-8",
            )
            (role_root / "resource-metrics.json").write_text(
                json.dumps({"failure_phase": "normalization", "request_count": 3}),
                encoding="utf-8",
            )
            screenshot = SimpleNamespace(
                path=str(image_path),
                sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                size_bytes=image_path.stat().st_size,
                capture_state="site_connectivity_error",
                state_reason="Der Browser zeigte No connection.",
                interactions=(),
                artifact_directory=str(role_root),
                capture_completeness="teilweise_erfasst",
            )
            rendered = FetchResult(
                requested_url="https://www.temu.com/",
                final_url="https://www.temu.com/",
                fetched_at="2026-08-21T10:00:00Z",
                status_code=200,
                headers=(),
                redirect_chain=(),
                body=raw_html.encode(),
                decoded_html=raw_html,
                fetch_mode="browser_review",
                browser_metadata={
                    "user_agent": "MucLegal-Test",
                    "navigator_webdriver": True,
                    "request_count": 3,
                },
            )
            fetcher = local_fetcher()

            def browser_fetch(_url: str) -> FetchResult:
                fetcher.last_browser_capture = SimpleNamespace(
                    fetch_result=rendered,
                    screenshot=screenshot,
                    artifact_directory=str(role_root),
                )
                return rendered

            workflow = LiveMonitorWorkflow(
                root,
                FIXTURES / "tenor.json",
                fetcher=fetcher,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            with patch("muclegal.live.check_url") as checked:
                checked.side_effect = [
                    NormalizationError("Die konfigurierte Extraktion ergab keinen relevanten Text."),
                    NormalizationError("Die konfigurierte Extraktion ergab keinen relevanten Text."),
                ]
                with patch.object(fetcher, "fetch_in_browser", side_effect=browser_fetch):
                    result = workflow.run(
                        "https://www.temu.com/",
                        capture_baseline=True,
                        browser_mode=True,
                    )

            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            run_result = json.loads(
                Path(case["artifacts"]["run_result"]).read_text(encoding="utf-8")
            )
            protection = json.loads(
                Path(case["artifacts"]["protection_report"]).read_text(encoding="utf-8")
            )

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("hinweis", case["technical_result"]["code"])
        self.assertEqual("technisch_fehlgeschlagen", case["capture_completeness"])
        self.assertIn("requested", case["capture_galleries"])
        self.assertEqual("normalization_error", run_result["failure_code"])
        self.assertIn("NormalizationError", protection["technical_error"])
        self.assertEqual(
            [
                "https://www.temu.com/de/terms-of-use.html",
                "https://www.temu.com/de/privacy-policy.html",
            ],
            protection["checked_subpages"][:2],
        )
        self.assertNotIn("NormalizationError", result.message)

    def test_god_mode_failure_still_starts_public_legal_page_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            fallback_result = LiveWorkflowResult(
                "completed_with_warnings", "Rechtstext-Fallback abgeschlossen."
            )
            with patch.object(
                workflow,
                "_run_impl",
                side_effect=NormalizationError(
                    "Die konfigurierte Extraktion ergab keinen relevanten Text."
                ),
            ), patch.object(
                workflow,
                "_try_public_legal_subpages",
                return_value=fallback_result,
            ) as fallback:
                result = workflow.run(
                    "https://www.temu.com/",
                    capture_baseline=True,
                    browser_mode=True,
                    god_mode=True,
                )

        self.assertIs(fallback_result, result)
        self.assertEqual("https://www.temu.com/", fallback.call_args.args[0])
        self.assertTrue(fallback.call_args.kwargs["god_mode"])
        self.assertEqual("leerer_browserzustand", fallback.call_args.kwargs["failure_kind"])
        self.assertEqual("normalization_error", fallback.call_args.kwargs["failure_code"])

    def test_authorized_god_mode_is_separate_marked_and_ignores_robots(self) -> None:
        from PIL import Image

        def fake_editorial_builder(**kwargs):
            output_directory = Path(kwargs["output_directory"])
            output_directory.mkdir(parents=True, exist_ok=True)
            summary = output_directory.parent / "god-mode-editorial-summary.md"
            usage = output_directory.parent / "god-mode-ai-usage.json"
            summary.write_text(
                "GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR\n\n"
                "Redaktionelle Testzusammenfassung",
                encoding="utf-8",
            )
            usage.write_text(
                json.dumps({"total_api_calls": 0, "total_estimated_cost_usd": 0.0}),
                encoding="utf-8",
            )
            return SimpleNamespace(
                status="generated",
                artifacts={
                    "god_mode_editorial_summary": summary,
                    "god_mode_ai_usage": usage,
                },
                page_results=(),
                total_estimated_cost_usd=0.0,
            )

        def fake_screenshot(url: str, destination: str | Path):
            del url
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (640, 360), "white").save(path, "PNG")
            return SimpleNamespace(
                path=str(path),
                sha256="1" * 64,
                size_bytes=path.stat().st_size,
                capture_state="page_content",
                state_reason=None,
                interactions=(),
                artifact_directory=None,
            )

        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.robots_body = b"User-agent: *\nDisallow: /\n"
            root = Path(output)
            workflow = LiveMonitorWorkflow(
                root,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
                screenshot_capturer=fake_screenshot,
                god_mode_editorial_builder=fake_editorial_builder,
            )
            result = workflow.run(
                server.url,
                capture_baseline=True,
                browser_mode=True,
                god_mode=True,
            )
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            bundle_path = Path(case["artifacts"]["manifest"]).parent
            manifest = json.loads(Path(case["artifacts"]["manifest"]).read_text(encoding="utf-8"))
            normalized = Path(case["artifacts"]["normalized_text"]).read_text(encoding="utf-8")
            authorization = json.loads(
                Path(case["artifacts"]["god_mode_authorization"]).read_text(encoding="utf-8")
            )
            ai_usage = json.loads(
                Path(case["artifacts"]["god_mode_ai_usage"]).read_text(encoding="utf-8")
            )
            editorial_summary = Path(
                case["artifacts"]["god_mode_editorial_summary"]
            ).read_text(encoding="utf-8")
            with Image.open(case["artifacts"]["screenshot"]) as image:
                banner_pixel = image.convert("RGB").getpixel((1, 1))
            archive = CaseArchive(root)
            regular_cases = archive.list()
            god_cases = archive.list_god_mode()
            regular_latest_exists = workflow.latest_case_path.exists()
            god_latest_exists = workflow.latest_god_mode_case_path.exists()

        self.assertIn("god-mode-bundles", str(bundle_path))
        self.assertTrue(bundle_path.name.startswith("god-"))
        self.assertTrue(case["god_mode"])
        self.assertEqual("nicht_juristisch_verwertbar", case["evidence_suitability"])
        self.assertEqual("god_mode_ausdruecklich_ignoriert", case["capture_transparency"]["robots_txt"])
        self.assertTrue(normalized.startswith("GOD MODE"))
        self.assertIn("GOD MODE", manifest["notice"])
        self.assertTrue(authorization["activated"])
        self.assertIn("optionale_openai_redaktionelle_textanalyse", authorization["enabled_functions"])
        self.assertEqual(0, ai_usage["total_api_calls"])
        self.assertIn("Redaktionelle Testzusammenfassung", editorial_summary)
        self.assertTrue(
            any(
                item["label"] == "god_mode_editorial_summary"
                for item in manifest["artifacts"]
            )
        )
        self.assertLess(banner_pixel[1], 40)
        self.assertEqual([], regular_cases)
        self.assertEqual(1, len(god_cases))
        self.assertFalse(regular_latest_exists)
        self.assertTrue(god_latest_exists)

    def test_god_mode_cannot_enter_the_legal_analysis_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            workflow = LiveMonitorWorkflow(
                Path(output),
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )

            with self.assertRaisesRegex(
                ValueError,
                "ausschließlich für die technische BeweisLab-Erfassung",
            ):
                workflow.run("https://example.com", god_mode=True)

        self.assertFalse(workflow.latest_case_path.exists())
        self.assertFalse(workflow.latest_god_mode_case_path.exists())

    def test_god_mode_without_openai_key_is_a_visible_non_blocking_warning(self) -> None:
        from PIL import Image

        def fake_screenshot(url: str, destination: str | Path):
            del url
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40, 40), "white").save(path, format="PNG")
            return SimpleNamespace(
                path=str(path),
                sha256="1" * 64,
                size_bytes=path.stat().st_size,
                capture_state="page_content",
                state_reason=None,
                interactions=(),
                artifact_directory=None,
            )

        def skipped_editorial_builder(**kwargs):
            output_directory = Path(kwargs["output_directory"])
            output_directory.mkdir(parents=True, exist_ok=True)
            usage = output_directory.parent / "god-mode-ai-usage.json"
            usage.write_text(
                json.dumps({"configured": False, "total_api_calls": 0}),
                encoding="utf-8",
            )
            return SimpleNamespace(
                status="skipped_no_api_key",
                artifacts={"god_mode_ai_usage": usage},
                page_results=(),
                total_estimated_cost_usd=0.0,
            )

        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            workflow = LiveMonitorWorkflow(
                Path(output),
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
                screenshot_capturer=fake_screenshot,
                god_mode_editorial_builder=skipped_editorial_builder,
            )
            result = workflow.run(
                server.url,
                capture_baseline=True,
                browser_mode=True,
                god_mode=True,
            )

        self.assertEqual("completed_with_warnings", result.status)
        self.assertIn("OPENAI_API_KEY", result.message)
        self.assertEqual("skipped", result.step_states["anthropic"])

    def test_unchecked_robots_marks_case_manifest_zip_and_ui_as_not_evidence_suitable(self) -> None:
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.robots_status = 503
            root = Path(output)
            workflow = LiveMonitorWorkflow(
                root,
                FIXTURES / "tenor.json",
                fetcher=local_fetcher(),
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
            )
            result = workflow.run(server.url, capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            bundle = Path(case["artifacts"]["manifest"]).parent
            case_id = bundle.name
            app = create_app(
                workflow.latest_case_path,
                root / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                detail = client.get(f"/api/cases/{case_id}").json()
                page = client.get("/beweis-labor").text
                package_response = client.get(f"/api/v1/cases/{case_id}/download")
            with zipfile.ZipFile(io.BytesIO(package_response.content)) as package:
                package_names = package.namelist()
                notice = package.read("artifacts/NICHT_BEWEISGEEIGNET.txt").decode("utf-8")
            manifest_valid = verify_manifest(case["artifacts"]["manifest"]).valid

        self.assertEqual("completed_with_warnings", result.status)
        self.assertEqual("ungeprueft", case["capture_transparency"]["robots_txt"])
        self.assertEqual("nicht_beweisgeeignet", case["evidence_suitability"])
        self.assertEqual("nicht_beweisgeeignet", detail["evidence_suitability"])
        self.assertIn("NICHT BEWEISGEEIGNET", result.message)
        self.assertIn("NICHT_BEWEISGEEIGNET.txt", " ".join(package_names))
        self.assertIn("NICHT BEWEISGEEIGNET", notice)
        self.assertIn('id="evidence-warning"', page)
        self.assertIn("evidence_suitability", page)
        self.assertTrue(manifest_valid)

    def test_agb_hub_resolves_to_concrete_clause_page(self) -> None:
        hub = """<html><main><h1>Allgemeine Liefer- und Zahlungsbedingungen</h1>
          <a href='/terms/agb-online-shop'>Allgemeine Liefer- und Zahlungsbedingungen Online-Shop</a>
          <a href='/terms/agb-gift-card.pdf'>AGB Geschenkkarte PDF</a>
        </main><footer><a href='/agb'>AGB</a></footer></html>"""

        resolved, selection = _select_legal_content_url(
            hub,
            "https://shop.test/agb",
            "agb",
        )

        self.assertEqual("https://shop.test/terms/agb-online-shop", resolved)
        self.assertEqual("klauselseite_aus_rechtstextübersicht", selection)

    def test_concrete_agb_clause_page_is_not_followed_again(self) -> None:
        clause = "Für diesen Vertrag gelten die nachstehenden Bedingungen. " * 25
        page = f"""<html><main><h1>AGB Online-Shop</h1>
          <p>1. Geltung {clause}</p><p>2. Vertragsschluss {clause}</p>
          <p>3. Zahlung und Lieferung {clause}</p>
        </main><footer><a href='/agb'>AGB</a></footer></html>"""

        resolved, selection = _select_legal_content_url(
            page,
            "https://shop.test/agb-online-shop",
            "agb",
        )

        self.assertEqual("https://shop.test/agb-online-shop", resolved)
        self.assertEqual("direkter_rechtstext", selection)

    def test_browserless_html_evidence_image_is_labeled_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            artifact_root = Path(output) / "captured-page"
            artifact_root.mkdir()
            destination = artifact_root / "screenshot-full-page.png"
            capture = _capture_html_evidence_image(
                "<html><head><title>IKEA Test</title></head><body>"
                "<h1>Allgemeine Geschäftsbedingungen</h1>"
                "<p>Gespeicherter öffentlicher Inhalt.</p></body></html>",
                "https://www.ikea.com/de/de/customer-service/terms-conditions/",
                destination,
                protection=None,
                fallback_reason="Page.set_content: browser has been closed",
                browser_error="Target page, context or browser has been closed",
                artifact_directory=artifact_root,
            )

            from PIL import Image

            with Image.open(destination) as image:
                dimensions = image.size
            raw_html_saved = (artifact_root / "raw.html").is_file()
            normalized_content = (artifact_root / "normalized-text.txt").read_text(
                encoding="utf-8"
            )
            screenshot_index_saved = (artifact_root / "screenshot-index.json").is_file()
            preview_saved = (artifact_root / "screenshot-preview.webp").is_file()

        self.assertEqual("http_snapshot_visualized", capture.capture_state)
        self.assertIn("keine pixelgetreue Live-Browser-Aufnahme", capture.state_reason)
        self.assertGreater(capture.size_bytes, 5_000)
        self.assertEqual(1440, dimensions[0])
        self.assertGreaterEqual(dimensions[1], 900)
        self.assertEqual(str(artifact_root.resolve()), capture.artifact_directory)
        self.assertTrue(raw_html_saved)
        self.assertIn("Gespeicherter öffentlicher Inhalt", normalized_content)
        self.assertTrue(screenshot_index_saved)
        self.assertTrue(preview_saved)

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

    def test_god_mode_uses_stored_browser_dom_when_regular_screenshot_is_missing(self) -> None:
        fetcher = HttpFetcher(
            FetchPolicy(respect_robots=True, require_public_network=False, max_attempts=1)
        )
        fetched = FetchResult(
            requested_url="https://authorized.example",
            final_url="https://authorized.example/final",
            fetched_at="2026-08-21T00:00:00+00:00",
            status_code=200,
            headers=(),
            redirect_chain=(),
            body=b"<html><main>Schutzseite</main></html>",
            decoded_html="<html><main>Schutzseite</main></html>",
            fetch_mode="browser_review",
        )
        fallback_capture = SimpleNamespace(capture_state="http_snapshot_rendered")
        with tempfile.TemporaryDirectory() as output, fetcher.god_mode_session(), patch(
            "muclegal.fetch.playwright._capture_html_evidence_image",
            return_value=fallback_capture,
        ) as fallback:
            target_root = Path(output) / "target"
            target_root.mkdir()
            fetcher._capture_controller = SimpleNamespace(
                capture_target=lambda _url, role: SimpleNamespace(
                    fetch_result=fetched,
                    screenshot=None,
                    failure_phase="initialzustand_sichern",
                    artifact_directory=str(target_root),
                )
            )
            captured = fetcher.capture_screenshot(
                "https://authorized.example", Path(output) / "god-mode.png"
            )

        self.assertIs(captured, fallback_capture)
        self.assertEqual("<html><main>Schutzseite</main></html>", fallback.call_args.args[0])
        self.assertIn("God Mode", fallback.call_args.kwargs["fallback_reason"])
        self.assertEqual(target_root, fallback.call_args.args[2].parent)
        self.assertEqual(target_root, fallback.call_args.kwargs["artifact_directory"])

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
            fetcher = local_fetcher()
            fetcher._record_robots_check(
                url="https://shop.test/robots.txt",
                status="ungeprueft",
                reason="robots.txt konnte nicht verlässlich geprüft werden (HTTP 503).",
            )
            workflow = LiveMonitorWorkflow(
                root,
                FIXTURES / "tenor.json",
                fetcher=fetcher,
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
        self.assertEqual("nicht_beweisgeeignet", case["evidence_suitability"])
        self.assertEqual("ungeprueft", case["capture_transparency"]["robots_txt"])
        self.assertIn("Nicht als Beleg verwendbar", result.message)
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

    def test_every_captured_page_bundles_html_text_and_screenshot(self) -> None:
        from PIL import Image
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            bundle = root / "bundle"
            artifacts = bundle / "artifacts"
            source_root = root / "source-agb"
            source_root.mkdir(parents=True)
            (source_root / "request.json").write_text(
                json.dumps(
                    {
                        "requested_url": "https://shop.test/agb",
                        "final_url": "https://shop.test/agb-online",
                    }
                ),
                encoding="utf-8",
            )
            (source_root / "raw.html").write_text(
                "<html><body>AGB Rohstand</body></html>", encoding="utf-8"
            )
            (source_root / "normalized-text.txt").write_text(
                "AGB Rohstand", encoding="utf-8"
            )
            screenshot = source_root / "screenshot-full-page.png"
            Image.new("RGB", (200, 300), "white").save(screenshot)
            (source_root / "screenshot-preview.webp").write_bytes(screenshot.read_bytes())
            (source_root / "screenshot-index.json").write_text(
                json.dumps(
                    {
                        "mode": "full_page",
                        "capture_completeness": "vollstaendig_erfasst",
                        "full_page_attempt": {"path": screenshot.name},
                        "tiles": [],
                    }
                ),
                encoding="utf-8",
            )
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with (source_root / "expanded-legal-print.pdf").open("wb") as handle:
                writer.write(handle)
            capture = SimpleNamespace(
                artifact_directory=str(source_root),
                path=str(screenshot),
                capture_completeness="vollstaendig_erfasst",
            )
            bundled = {}
            completeness, galleries, _ = _bundle_browser_capture_artifacts(
                bundle=bundle,
                artifacts_dir=artifacts,
                bundled_artifacts=bundled,
                role_captures={"main": capture, "agb": capture},
                legal_screenshot_statuses={},
                protection_type=None,
                requested_url="https://shop.test/",
                captured_url="https://shop.test/agb-online",
                browser_run_root=None,
            )
            _mark_god_mode_bundle(bundle)
            index = json.loads(
                Path(bundled["page_artifacts_index"]).read_text(encoding="utf-8")
            )
            from pypdf import PdfReader

            god_pdf_text = "\n".join(
                page.extract_text() or ""
                for page in PdfReader(
                    bundle / index["pages"]["agb"]["document_files"][0]["path"]
                ).pages
            )
            for collection in (
                "raw_html_files",
                "normalized_text_files",
                "screenshot_files",
                "document_files",
            ):
                for item in index["pages"]["agb"][collection]:
                    actual = hashlib.sha256((bundle / item["path"]).read_bytes()).hexdigest()
                    self.assertEqual(actual, item["sha256"])

        page = index["pages"]["agb"]
        self.assertEqual("vollstaendig_erfasst", completeness)
        self.assertTrue(index["all_required_artifacts_complete"])
        self.assertTrue(page["required_artifacts_complete"])
        self.assertTrue(page["raw_html_files"])
        self.assertTrue(page["normalized_text_files"])
        self.assertTrue(page["screenshot_files"])
        self.assertTrue(page["document_files"])
        self.assertIn("GOD MODE", god_pdf_text)
        self.assertEqual("https://shop.test/agb-online", page["captured_url"])
        self.assertTrue(galleries["agb"]["page_artifacts_complete"])

    def test_real_browser_bundle_has_three_artifact_groups_for_main_and_legal_pages(self) -> None:
        page = b"""<!doctype html><html><main><h1>Shop</h1><p>Oeffentlicher Inhalt.</p></main>
          <footer><a href='/agb'>AGB</a><a href='/privacy'>Datenschutz</a></footer></html>"""
        with tempfile.TemporaryDirectory() as output, LiveServer() as server:
            _LiveHandler.page = page
            fetcher = local_fetcher()
            workflow = LiveMonitorWorkflow(
                output,
                FIXTURES / "tenor.json",
                fetcher=fetcher,
                warc_capturer=fake_warc,
                tsa_client=FakeTsaClient(),
                report_builder=fake_report,
                screenshot_capturer=fetcher.capture_screenshot,
            )
            result = workflow.run(server.url, capture_baseline=True)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            page_index = json.loads(
                Path(case["artifacts"]["page_artifacts_index"]).read_text(encoding="utf-8")
            )

        self.assertEqual({"main", "agb", "privacy"}, set(page_index["pages"]))
        for role in ("main", "agb", "privacy"):
            captured = page_index["pages"][role]
            self.assertTrue(captured["required_artifacts_complete"], role)
            self.assertTrue(captured["raw_html_files"], role)
            self.assertTrue(captured["normalized_text_files"], role)
            self.assertTrue(captured["screenshot_files"], role)
            if role in {"agb", "privacy"}:
                self.assertTrue(captured["document_files"], role)

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
    def test_evidence_lab_authorization_checkbox_starts_explicit_god_mode(self) -> None:
        class GodModeWorkflow:
            tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))

            def run(
                self, url, progress, *, capture_baseline=False, browser_mode=False, god_mode=False
            ):
                self.received = (url, capture_baseline, browser_mode, god_mode)
                progress("fetch", "God Mode protokolliert")
                return LiveWorkflowResult("protected", "GOD MODE – NUR DEMONSTRATION")

        with tempfile.TemporaryDirectory() as output:
            workflow = GodModeWorkflow()
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
                    json={
                        "url": "https://authorized.example/",
                        "verification_mode": False,
                        "god_mode_authorized": True,
                    },
                ).json()
                completed = poll(client, started["run_id"])

        self.assertIn('id="god-mode-authorized" type="checkbox"', page.text)
        self.assertIn("Autorisiert (God Mode)", page.text)
        self.assertTrue(started["god_mode_authorized"])
        self.assertTrue(started["verification_mode"])
        self.assertEqual(
            ("https://authorized.example/", True, True, True), workflow.received
        )
        self.assertIn("GOD MODE", completed["message"])

    def test_evidence_lab_groups_primary_artifacts_and_exposes_text_per_page(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            case_id = "capture-pages"
            bundle = root / "bundles" / case_id
            roles = bundle / "artifacts" / "roles"
            galleries = {}
            for role, content in (
                ("main", "Text der Hauptseite"),
                ("agb", "Text der AGB-Seite"),
                ("privacy", "Text der Datenschutz-Seite"),
            ):
                role_dir = roles / role
                role_dir.mkdir(parents=True)
                (role_dir / "screenshot-index.json").write_text("{}", encoding="utf-8")
                (role_dir / "normalized-text.txt").write_text(content, encoding="utf-8")
                (role_dir / "raw.html").write_text(
                    f"<html><body>{content}</body></html>", encoding="utf-8"
                )
                galleries[role] = {
                    "index": f"artifacts/roles/{role}/screenshot-index.json",
                    "preview": f"artifacts/roles/{role}/screenshot-preview.webp",
                    "raw_html": f"artifacts/roles/{role}/raw.html",
                    "originals": [],
                    "tiles": [],
                }
                if role in {"agb", "privacy"}:
                    (role_dir / "expanded-legal-print.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
                    galleries[role]["documents"] = [
                        f"artifacts/roles/{role}/expanded-legal-print.pdf"
                    ]
            record = {
                "url": "https://shop.test/",
                "erkannt_am": "2026-08-20T10:00:00Z",
                "evidence": {},
                "assessment": {"ergebnis": "nicht_bewertet", "confidence": 0.0},
                "artifacts": {},
                "capture_galleries": galleries,
            }
            (bundle / "case.json").write_text(json.dumps(record), encoding="utf-8")
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                page = client.get("/beweis-labor")
                detail = client.get(f"/api/cases/{case_id}").json()
                main = client.get(
                    f"/api/v1/cases/{case_id}/capture/main/normalized-text"
                )
                privacy = client.get(
                    f"/api/v1/cases/{case_id}/capture/privacy/normalized-text"
                )
                agb_html = client.get(
                    f"/api/v1/cases/{case_id}/capture/agb/raw-html"
                )
                privacy_pdf = client.get(
                    f"/api/v1/cases/{case_id}/capture/privacy/documents/0"
                )

        self.assertIn('createMenuPill("Screenshots"', page.text)
        self.assertIn('createDirectPill("Datenschutz-Screenshot"', page.text)
        self.assertIn('createDirectPill("AGB-Screenshot"', page.text)
        self.assertIn('createMenuPill("Normalisierter Text"', page.text)
        self.assertIn('createMenuPill("Technische Details"', page.text)
        self.assertIn('createMenuPill("Druckfassungen"', page.text)
        self.assertEqual("Hauptseite", detail["capture_galleries"]["main"]["title"])
        self.assertTrue(
            detail["capture_galleries"]["agb"]["normalized_text_url"].endswith(
                "/capture/agb/normalized-text"
            )
        )
        self.assertEqual("Text der Hauptseite", main.text)
        self.assertEqual("Text der Datenschutz-Seite", privacy.text)
        self.assertIn("Text der AGB-Seite", agb_html.text)
        self.assertTrue(detail["capture_galleries"]["agb"]["raw_html_url"].endswith("/raw-html"))
        self.assertEqual(200, privacy_pdf.status_code)
        self.assertEqual("application/pdf", privacy_pdf.headers["content-type"])
        self.assertIn("inline", privacy_pdf.headers["content-disposition"])
        self.assertNotIn("attachment", privacy_pdf.headers["content-disposition"])
        self.assertEqual("SAMEORIGIN", privacy_pdf.headers["x-frame-options"])
        self.assertIn(
            "frame-ancestors 'self'",
            privacy_pdf.headers["content-security-policy"],
        )
        self.assertTrue(detail["capture_galleries"]["privacy"]["document_urls"])

    def test_evidence_lab_selects_newest_fallback_case_by_requested_url(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            records = (
                (
                    "older-root-case",
                    {
                        "url": "https://www.temu.com/",
                        "erkannt_am": "2026-08-21T09:00:00Z",
                    },
                ),
                (
                    "newer-legal-fallback",
                    {
                        "url": "https://www.temu.com/de/terms-of-use.html",
                        "requested_url": "https://www.temu.com/",
                        "captured_url": "https://www.temu.com/de/terms-of-use.html",
                        "erkannt_am": "2026-08-21T15:50:00Z",
                    },
                ),
            )
            for case_id, values in records:
                bundle = root / "bundles" / case_id
                bundle.mkdir(parents=True)
                record = {
                    **values,
                    "evidence": {},
                    "assessment": {"ergebnis": "nicht_bewertet", "confidence": 0.0},
                    "artifacts": {},
                }
                (bundle / "case.json").write_text(json.dumps(record), encoding="utf-8")
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                anthropic_ready=False,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                page = client.get("/beweis-labor")
                cases = client.get("/api/cases").json()["cases"]

        self.assertEqual("newer-legal-fallback", cases[0]["case_id"])
        self.assertEqual("https://www.temu.com/", cases[0]["requested_url"])
        self.assertEqual(
            "https://www.temu.com/de/terms-of-use.html",
            cases[0]["captured_url"],
        )
        self.assertIn(
            "list.find(entry=>entry.requested_url===expectedUrl)",
            page.text,
        )
        self.assertLess(
            page.text.index("entry.requested_url===expectedUrl"),
            page.text.index("entry.url===expectedUrl"),
        )
        self.assertIn("input.value=data.requested_url||data.url", page.text)
        self.assertIn(
            'new URLSearchParams(window.location.search).get("case_id")',
            page.text,
        )
        self.assertIn(
            "api(`/api/cases/${encodeURIComponent(caseId)}`)",
            page.text,
        )

    def test_automatic_verification_is_enabled_by_default_in_lab_and_can_be_disabled(self) -> None:
        class VerificationWorkflow:
            tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))

            def run(self, url, progress, *, capture_baseline=False, browser_mode=False):
                self.browser_modes = getattr(self, "browser_modes", []) + [browser_mode]
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
                disabled = client.post(
                    "/api/v1/evidence-runs",
                    json={"url": "https://example.org", "verification_mode": False},
                ).json()
                for _ in range(100):
                    disabled_result = client.get(
                        f"/api/v1/evidence-runs/{disabled['run_id']}"
                    ).json()
                    if disabled_result["status"] in TERMINAL_RUN_STATUSES:
                        break
                    time.sleep(0.01)

        self.assertIn('id="verification-mode" type="checkbox" checked', page.text)
        self.assertIn("Automatische Überprüfung", page.text)
        self.assertNotIn("Grau-Modus", page.text)
        self.assertIn("keine Tarntechniken", page.text)
        self.assertTrue(started["verification_mode"])
        self.assertFalse(disabled["verification_mode"])
        self.assertEqual([True, False], workflow.browser_modes)

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
        self.assertIn('anthropic:"KI-Analyse"', page.text)
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
        self.assertEqual("https://www.temu.com/de/terms-of-use.html", candidates[0])
        self.assertIn("https://www.temu.com/de/privacy-policy.html", candidates)
        self.assertIn("https://www.temu.com/de-en/privacy-policy.html", candidates)
        self.assertIn("https://www.temu.com/policies/terms-of-service", candidates)
        self.assertIn("https://www.temu.com/policies/privacy-policy", candidates)
        self.assertTrue(all(url.startswith("https://www.temu.com/") for url in candidates))

        root_candidates = _legal_subpage_candidates("https://www.temu.com/")
        self.assertEqual(
            "https://www.temu.com/de/terms-of-use.html", root_candidates[0]
        )
        self.assertEqual(
            "https://www.temu.com/de/privacy-policy.html", root_candidates[1]
        )

        adidas_candidates = _legal_subpage_candidates("https://www.adidas.de/")
        self.assertEqual(
            "https://www.adidas.de/terms_and_conditions", adidas_candidates[0]
        )


if __name__ == "__main__":
    unittest.main()
