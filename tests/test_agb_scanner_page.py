from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from muclegal import agb_scan
from muclegal.ui import create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(agb_scan._api_module(), "STEP_DELAY_SECONDS", 0)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        app = create_app(root / "latest-case.json", root / "reviews.sqlite3", anthropic_ready=False)
        with TestClient(app) as test_client:
            yield test_client


def test_beweislab_tab_serves_slim_scanner_with_evidence_enabled(client) -> None:
    page = client.get("/beweis-labor")
    assert page.status_code == 200
    html = page.text
    assert '<body data-evidence="on">' in html
    assert 'id="scan-form"' in html and 'id="evidence-button"' in html
    for asset in ("style.css", "design.css", "app.js", "evidence.js", "muclegal-logo.png"):
        assert f'="/beweis-labor/{asset}"' in html
        assert client.get(f"/beweis-labor/{asset}").status_code == 200
    assert client.get("/beweis-labor/fonts/manrope.css").headers["content-type"].startswith("text/css")
    assert client.get("/beweis-labor/fonts/manrope-0.woff2").status_code == 200


@pytest.mark.parametrize("name", ["scan.py", "data/mueller.json", "fonts/../scan.py", "api/index.py"])
def test_scanner_sources_are_not_exposed(client, name) -> None:
    assert client.get(f"/beweis-labor/{name}").status_code == 404


def test_classic_beweislab_remains_available(client) -> None:
    page = client.get("/beweis-labor/klassisch")
    assert page.status_code == 200
    assert 'id="run-form"' in page.text


def test_scan_api_streams_saved_comparison(client) -> None:
    response = client.post("/api/scan", json={"example": "mueller", "language": "de"})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert [e["step"] for e in events if e["type"] == "progress"][0] == 0
    result = events[-1]
    assert result["type"] == "result" and result["changed"] > 0
    assert "web.archive.org" in result["before"]["url"]


def test_scan_api_rejects_invalid_payload(client) -> None:
    assert client.post("/api/scan", content=b"[]").status_code == 400
    events = [
        json.loads(line)
        for line in client.post("/api/scan", json={"example": "x"}).text.splitlines()
        if line.strip()
    ]
    assert events[-1] == {"type": "error", "message": "Unbekanntes Beispiel."}
