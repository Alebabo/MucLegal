from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from muclegal.fetch import FetchFailure, FetchPolicy, HttpFetcher
from muclegal.fetch.http import _detect_block_page
from muclegal.normalize import NormalizationConfig, NormalizationError, VolatileRule, normalize_html
from muclegal.pipeline import check_url
from muclegal.storage import SnapshotRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class _FixtureHandler(BaseHTTPRequestHandler):
    fixture_name = "baseline.html"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /denied\nAllow: /\n"
            content_type = "text/plain; charset=utf-8"
            status = 200
        elif self.path == "/page":
            body = (FIXTURES / type(self).fixture_name).read_bytes()
            content_type = "text/html; charset=utf-8"
            status = 200
        elif self.path == "/login":
            body = b'<html><form><input type="password"></form></html>'
            content_type = "text/html; charset=utf-8"
            status = 200
        elif self.path == "/captcha":
            body = b'<html><main><div class="g-recaptcha">Verify you are human</div></main></html>'
            content_type = "text/html; charset=utf-8"
            status = 200
        elif self.path == "/slow":
            time.sleep(0.2)
            body = b"<html><main>Zu spaet</main></html>"
            content_type = "text/html; charset=utf-8"
            status = 200
        else:
            body = b"not found"
            content_type = "text/plain; charset=utf-8"
            status = 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class FixtureServer:
    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def load_config() -> NormalizationConfig:
    data = json.loads((FIXTURES / "demo-profile.json").read_text(encoding="utf-8"))
    return NormalizationConfig.from_dict(data)


class NormalizationAcceptanceTests(unittest.TestCase):
    def test_identical_html_is_byte_stable(self) -> None:
        source = (FIXTURES / "baseline.html").read_bytes()
        first = normalize_html(source, load_config())
        second = normalize_html(source, load_config())
        self.assertEqual(first.text.encode("utf-8"), second.text.encode("utf-8"))
        self.assertEqual(first.sha256, second.sha256)

    def test_changed_countdown_keeps_same_hash(self) -> None:
        baseline = normalize_html((FIXTURES / "baseline.html").read_bytes(), load_config())
        changed = normalize_html((FIXTURES / "countdown-changed.html").read_bytes(), load_config())
        self.assertEqual(baseline.text, changed.text)
        self.assertEqual(baseline.sha256, changed.sha256)
        self.assertIn("[COUNTDOWN]", baseline.text)

    def test_added_cookie_banner_keeps_same_hash_when_selector_is_configured(self) -> None:
        config = NormalizationConfig(
            include_selector="main",
            remove_selectors=(".cookie-banner",),
        )
        baseline = normalize_html(
            b"<html><main><h1>Angebot</h1><p>Nur heute 20 % Rabatt.</p></main></html>",
            config,
        )
        changed = normalize_html(
            b'<html><main><div class="cookie-banner">Cookies akzeptieren</div>'
            b"<h1>Angebot</h1><p>Nur heute 20 % Rabatt.</p></main></html>",
            config,
        )
        self.assertEqual(baseline.text, changed.text)
        self.assertEqual(baseline.sha256, changed.sha256)

    def test_legal_statement_changes_hash(self) -> None:
        baseline = normalize_html((FIXTURES / "baseline.html").read_bytes(), load_config())
        changed = normalize_html((FIXTURES / "legal-change.html").read_bytes(), load_config())
        self.assertNotEqual(baseline.sha256, changed.sha256)
        self.assertIn("20 % Rabatt", baseline.text)
        self.assertIn("30 % Rabatt", changed.text)

    def test_include_selector_must_match_exactly_once(self) -> None:
        for source in (
            b"<html><body><p>Kein Hauptinhalt</p></body></html>",
            b"<html><main>Eins</main><main>Zwei</main></html>",
        ):
            with self.subTest(source=source):
                with self.assertRaises(NormalizationError):
                    normalize_html(source, NormalizationConfig(include_selector="main"))

    def test_configured_session_value_is_replaced_but_claim_remains(self) -> None:
        config = NormalizationConfig(
            include_selector="main",
            volatile_rules=(VolatileRule(".session", "[SESSION]"),),
        )
        first = normalize_html(
            b'<main><h1>Angebot</h1><p>Nur heute 20 Prozent Rabatt auf alle Moebel.</p>'
            b'<p class="session">abc-123</p><p>Lieferung in zwei Werktagen.</p></main>', config
        )
        second = normalize_html(
            b'<main><h1>Angebot</h1><p>Nur heute 20 Prozent Rabatt auf alle Moebel.</p>'
            b'<p class="session">xyz-999</p><p>Lieferung in zwei Werktagen.</p></main>', config
        )
        self.assertEqual(first.sha256, second.sha256)
        self.assertIn("Nur heute", first.text)
        self.assertIn("[SESSION]", first.text)


class PipelineAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        _FixtureHandler.fixture_name = "baseline.html"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SnapshotRepository(self.temp_dir.name)
        self.fetcher = HttpFetcher(
            FetchPolicy(timeout_seconds=2, max_attempts=1, retry_backoff_seconds=0)
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_invalid_port_is_rejected_before_network_access(self) -> None:
        with self.assertRaises(FetchFailure) as caught:
            self.fetcher.fetch("https://example.test:not-a-port/page")

        self.assertEqual("invalid_url", caught.exception.code)

    def test_fetch_compare_and_diff_golden_path(self) -> None:
        with FixtureServer() as server:
            url = server.base_url + "/page"
            _FixtureHandler.fixture_name = "baseline.html"
            first = check_url(url, load_config(), self.repository, self.fetcher)
            second = check_url(url, load_config(), self.repository, self.fetcher)
            _FixtureHandler.fixture_name = "countdown-changed.html"
            noise = check_url(url, load_config(), self.repository, self.fetcher)
            _FixtureHandler.fixture_name = "legal-change.html"
            legal = check_url(url, load_config(), self.repository, self.fetcher)

        self.assertEqual("baseline_created", first.status)
        self.assertEqual("unchanged", second.status)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual("unchanged", noise.status)
        self.assertFalse(noise.needs_review)
        self.assertEqual("changed", legal.status)
        self.assertTrue(legal.needs_review)
        self.assertIsNotNone(legal.diff_path)
        diff = Path(legal.diff_path).read_text(encoding="utf-8")
        self.assertIn("-Nur heute 20 % Rabatt", diff)
        self.assertIn("+Nur heute 30 % Rabatt", diff)

        connection = sqlite3.connect(self.repository.database_path)
        try:
            rows = connection.execute(
                "SELECT raw_html_path, response_headers_path, normalized_text_path FROM snapshots"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(4, len(rows))
        for row in rows:
            for artifact in row:
                self.assertTrue(Path(artifact).is_file())

    def test_login_page_is_saved_as_manual_failure_not_snapshot(self) -> None:
        with FixtureServer() as server:
            url = server.base_url + "/login"
            with self.assertRaises(FetchFailure) as caught:
                check_url(url, load_config(), self.repository, self.fetcher)
        self.assertTrue(caught.exception.manual_review)
        connection = sqlite3.connect(self.repository.database_path)
        try:
            attempts = connection.execute(
                "SELECT outcome, error_code, manual_review FROM fetch_attempts"
            ).fetchall()
            snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual([("failure", "protected_or_login_page", 1)], attempts)
        self.assertEqual(0, snapshot_count)
        self.assertEqual(0, snapshot_count)

    def test_http_error_is_recorded_without_snapshot(self) -> None:
        with FixtureServer() as server:
            url = server.base_url + "/missing"
            with self.assertRaises(FetchFailure) as caught:
                check_url(url, load_config(), self.repository, self.fetcher)
        self.assertEqual(404, caught.exception.status_code)
        connection = sqlite3.connect(self.repository.database_path)
        try:
            attempt = connection.execute(
                "SELECT outcome, status_code, error_code FROM fetch_attempts"
            ).fetchone()
            snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(("failure", 404, "http_error"), attempt)
        self.assertEqual(0, snapshot_count)

    def test_timeout_is_recorded_without_snapshot(self) -> None:
        timeout_fetcher = HttpFetcher(
            FetchPolicy(timeout_seconds=0.05, max_attempts=1, retry_backoff_seconds=0)
        )
        with FixtureServer() as server:
            with self.assertRaises(FetchFailure) as caught:
                check_url(
                    server.base_url + "/slow",
                    load_config(),
                    self.repository,
                    timeout_fetcher,
                )
        self.assertEqual("network_error", caught.exception.code)
        connection = sqlite3.connect(self.repository.database_path)
        try:
            attempts = connection.execute(
                "SELECT outcome, error_code FROM fetch_attempts"
            ).fetchall()
            snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual([("failure", "network_error")], attempts)
        self.assertEqual(0, snapshot_count)

    def test_captcha_page_is_saved_as_manual_failure_not_snapshot(self) -> None:
        with FixtureServer() as server:
            with self.assertRaises(FetchFailure) as caught:
                check_url(
                    server.base_url + "/captcha",
                    load_config(),
                    self.repository,
                    self.fetcher,
                )
        self.assertEqual("protected_or_login_page", caught.exception.code)
        self.assertTrue(caught.exception.manual_review)
        connection = sqlite3.connect(self.repository.database_path)
        try:
            attempts = connection.execute(
                "SELECT outcome, error_code, manual_review FROM fetch_attempts"
            ).fetchall()
            snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual([("failure", "protected_or_login_page", 1)], attempts)

    def test_javascript_challenge_is_classified_as_protected(self) -> None:
        page = (
            "<html><script src='https://static.kwcdn.com/upload-static/assets/chl/js/x.js'>"
            "</script><script>window.challenge('token')</script></html>"
        )
        self.assertIn("Seitenschutz", _detect_block_page(page))

    def test_dormant_shopify_captcha_script_is_not_a_block_page(self) -> None:
        page = """
        <html><body><main><h1>Öffentlicher Shop</h1></main>
        <script id="captcha-bootstrap">
          const fields = ['g-recaptcha-response', 'h-captcha-response'];
          const source = 'storefront-forms-hcaptcha/example.js';
        </script></body></html>
        """
        self.assertIsNone(_detect_block_page(page))

    def test_privacy_policy_that_explains_captcha_is_not_a_block_page(self) -> None:
        page = """
        <html><main><h1>Datenschutzerklärung</h1>
        <p>Wir verwenden den CAPTCHA-Dienst Google reCAPTCHA zum Schutz von Formularen.</p>
        </main></html>
        """
        self.assertIsNone(_detect_block_page(page))

    def test_robots_disallow_stops_before_page_fetch(self) -> None:
        with FixtureServer() as server:
            with self.assertRaises(FetchFailure) as caught:
                check_url(server.base_url + "/denied", load_config(), self.repository, self.fetcher)
        self.assertEqual("robots_disallowed", caught.exception.code)
        self.assertTrue(caught.exception.manual_review)

    def test_single_cli_command_runs_without_llm_or_ui(self) -> None:
        with FixtureServer() as server:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "muclegal",
                    "check",
                    "--url",
                    server.base_url + "/page",
                    "--profile",
                    str(FIXTURES / "demo-profile.json"),
                    "--store",
                    self.temp_dir.name,
                    "--attempts",
                    "1",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("baseline_created", result["status"])
        self.assertFalse(result["needs_review"])


if __name__ == "__main__":
    unittest.main()
