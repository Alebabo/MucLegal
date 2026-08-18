from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pypdf import PdfReader

from muclegal.evidence import (
    OpenSslTsaClient,
    build_pdf_report,
    capture_warc,
    create_manifest,
    verify_manifest,
)


class _StaticHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\n"
            content_type = "text/plain"
        else:
            body = b"<!doctype html><html><body><main>Beweisinhalt</main></body></html>"
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class EvidenceTests(unittest.TestCase):
    def test_wget_warc_is_validated_by_warcio(self) -> None:
        server = ThreadingHTTPServer(("0.0.0.0", 0), _StaticHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as output:
                result = capture_warc(f"http://127.0.0.1:{server.server_port}/page", output)
                self.assertTrue(Path(result.warc_path).is_file())
                self.assertTrue(Path(result.cdx_path).is_file())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_manifest_hash_chain_can_be_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            first = root / "raw.html"
            second = root / "normalized.txt"
            first.write_bytes(b"<p>Original</p>")
            second.write_text("Original\n", encoding="utf-8")
            manifest = create_manifest({"raw_html": first, "normalized_text": second}, root)
            verification = verify_manifest(manifest.manifest_path)
            self.assertTrue(verification.valid, verification.errors)
            second.write_text("Manipuliert\n", encoding="utf-8")
            verification = verify_manifest(manifest.manifest_path)
            self.assertFalse(verification.valid)
            self.assertTrue(any("Hash weicht ab" in error for error in verification.errors))

    def test_tsa_outage_leaves_query_and_pending_status(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            result = OpenSslTsaClient(
                tsa_url="http://127.0.0.1:1/tsr",
                timeout_seconds=0.1,
                max_attempts=1,
            ).timestamp_digest("a" * 64, output)
            self.assertEqual("pending", result.status)
            self.assertTrue(Path(result.query_path).is_file())
            self.assertTrue((Path(output) / "tsa-status.json").is_file())

    def test_pdf_report_is_readable_and_has_human_release_warning(self) -> None:
        assessment = json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures/llm-output-kerngleich.json").read_text(
                encoding="utf-8"
            )
        )
        report = {
            "fall_id": "VZ-2024-0417",
            "url": "https://example.org/angebote",
            "erkannt_am": "2026-08-19T08:00:00Z",
            "vorher": "Dauerhaft günstig.",
            "nachher": "Nur noch 3 Stück verfügbar.",
            "assessment": assessment,
            "evidence": {
                "warc_status": "valide",
                "manifest_sha256": "a" * 64,
                "chain_head_sha256": "b" * 64,
                "timestamp_status": "verified",
                "wayback_status": "not_requested",
            },
        }
        with tempfile.TemporaryDirectory() as output:
            path = Path(output) / "report.pdf"
            build_pdf_report(report, path)
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("MucLegal Prüfbericht", text)
        self.assertIn("Menschliche Freigabe ausstehend", text)
        self.assertIn("keine abschließende Rechtsentscheidung", text)


if __name__ == "__main__":
    unittest.main()
