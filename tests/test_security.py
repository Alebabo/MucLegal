from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from muclegal.ui import create_app


def write_case(root: Path) -> tuple[Path, str]:
    case_id = "20260819T120000000000Z-security"
    bundle = root / "bundles" / case_id
    artifact = bundle / "artifacts" / "raw.html"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("<script>document.body.dataset.pwned='1'</script>", encoding="utf-8")
    record = {
        "fall_id": "SEC-001",
        "url": "https://example.org",
        "erkannt_am": "2026-08-19T12:00:00Z",
        "assessment": {"ergebnis": "unklar", "confidence": 0.1},
        "evidence": {
            "manifest_sha256": "a" * 64,
            "warc_status": "nicht erzeugt",
            "timestamp_status": "pending",
        },
        "artifacts": {"raw_html": str(artifact)},
        "warnings": [],
    }
    case_path = bundle / "case.json"
    case_path.write_text(json.dumps(record), encoding="utf-8")
    latest = root / "latest-case.json"
    latest.write_text(json.dumps(record), encoding="utf-8")
    return latest, case_id


class UiSecurityTests(unittest.TestCase):
    def test_security_headers_and_host_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            latest, _ = write_case(root)
            app = create_app(latest, root / "reviews.sqlite3")
            with TestClient(app) as client:
                page = client.get("/")
                hostile_host = client.get("/", headers={"Host": "attacker.example"})
        self.assertEqual("nosniff", page.headers["x-content-type-options"])
        content_security_policy = page.headers["content-security-policy"]
        self.assertIn("frame-ancestors 'none'", content_security_policy)
        self.assertIn(
            "img-src 'self' data: https://*.public.blob.vercel-storage.com",
            content_security_policy,
        )
        self.assertIn(
            "frame-src 'self' https://*.public.blob.vercel-storage.com",
            content_security_policy,
        )
        self.assertEqual(400, hostile_host.status_code)

    def test_raw_html_download_is_inert_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            latest, case_id = write_case(root)
            app = create_app(latest, root / "reviews.sqlite3")
            with TestClient(app) as client:
                response = client.get(f"/artifact/{case_id}/raw_html")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("<script>", response.text)

    def test_run_api_rejects_excessive_and_unknown_input(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            latest, _ = write_case(root)
            app = create_app(latest, root / "reviews.sqlite3")
            with TestClient(app) as client:
                excessive = client.post("/api/runs", json={"url": "https://" + "a" * 3000})
                extra = client.post(
                    "/api/runs",
                    json={"url": "https://example.org", "api_key": "must-not-be-accepted"},
                )
        self.assertEqual(422, excessive.status_code)
        self.assertEqual(422, extra.status_code)

    def test_cross_origin_state_change_and_large_body_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            latest, _ = write_case(root)
            app = create_app(latest, root / "reviews.sqlite3")
            with TestClient(app) as client:
                cross_origin = client.post(
                    "/review",
                    content="decision=freigegeben",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://attacker.example",
                    },
                )
                large = client.post(
                    "/review",
                    content="decision=" + "x" * 70_000,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        self.assertEqual(403, cross_origin.status_code)
        self.assertEqual(413, large.status_code)


if __name__ == "__main__":
    unittest.main()
