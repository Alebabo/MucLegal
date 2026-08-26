from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from muclegal.decathlon_demo import (
    BASELINE_HTML_PATH,
    CURRENT_DOCUMENT_PATH,
    DEMO_BASELINE_ID,
    DEMO_CURRENT_ID,
    DEMO_FIXTURE_REVISION,
    DEMO_NOTICE,
)
from muclegal.evidence import sha256_file
from muclegal.monitoring_cases import MonitoringCaseRepository
from muclegal.ui import create_app


def test_local_decathlon_demo_replays_manual_baseline_and_difference_flow() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repository = MonitoringCaseRepository(
            root / "reviews.sqlite3", root / "case-intake"
        )
        app = create_app(
            root / "latest-case.json",
            root / "reviews.sqlite3",
            anthropic_ready=False,
            monitoring_cases=repository,
        )
        with TestClient(app) as client:
            page = client.get("/beweis-labor")
            prepared = client.post("/api/v1/demo/decathlon")
            payload = prepared.json()
            baseline = client.get(f"/api/v1/cases/{DEMO_BASELINE_ID}")
            attached = client.post(
                f"/api/v1/cases/{payload['monitoring_case_id']}/baseline-evidence",
                json={"evidence_case_id": DEMO_BASELINE_ID},
            )
            prepared_again = client.post("/api/v1/demo/decathlon")
            current = client.get(f"/api/v1/cases/{DEMO_CURRENT_ID}")
            compared = client.post(
                f"/api/v1/cases/{payload['monitoring_case_id']}/evidence-comparisons",
                json={"evidence_case_id": DEMO_CURRENT_ID},
            )
            download = client.get(f"/api/v1/cases/{DEMO_CURRENT_ID}/download")

        current_pdf = root / "bundles" / DEMO_CURRENT_ID / "capture" / "agb" / "source.pdf"
        current_text = (
            root / "bundles" / DEMO_CURRENT_ID / "capture" / "agb" / "normalized-text.txt"
        ).read_text(encoding="utf-8")
        baseline_text = (
            root / "bundles" / DEMO_BASELINE_ID / "capture" / "agb" / "normalized-text.txt"
        ).read_text(encoding="utf-8")
        current_pdf_bytes = current_pdf.read_bytes()
        current_pdf_sha256 = sha256_file(current_pdf)
        current_pdf_page_count = len(PdfReader(current_pdf).pages)
        current_record = json.loads(
            (root / "bundles" / DEMO_CURRENT_ID / "case.json").read_text(
                encoding="utf-8"
            )
        )

    assert prepared.status_code == 200
    assert payload["demo_only"] is True
    assert payload["baseline_attached"] is False
    assert payload["next_case_id"] == DEMO_BASELINE_ID
    assert 'id="decathlon-demo"' in page.text
    assert "keine Live-Beweise" not in page.text
    assert "Bereitet zwei eingefrorene Vergleichsstände" not in page.text
    assert "Erzeugt ausschließlich klar gekennzeichnete lokale Demo-Snapshots" not in page.text
    assert "SYNTHETISCHE DEMO · KEIN LIVE-BEWEIS" not in page.text
    assert DEMO_NOTICE not in page.text
    assert "Synthetisches Demo-Paket herunterladen" not in page.text

    assert baseline.status_code == 200
    assert baseline.json()["demo_only"] is True
    assert baseline.json()["demo_notice"] == DEMO_NOTICE
    assert baseline.json()["demo_next_case_id"] == DEMO_CURRENT_ID
    assert "Webarchiv" in baseline.json()["capture_galleries"]["agb"]["title"]
    assert baseline.json()["capture_galleries"]["agb"]["title"] == "Webarchiv · 08.10.2024"
    assert "Teillieferungen sind jedoch, nach vorherigem Hinweis" in baseline_text
    assert "Du stellst decathlon.de von allen Ansprüchen Dritter frei" in baseline_text
    assert BASELINE_HTML_PATH.read_bytes().lstrip().startswith(b"<html")

    assert attached.status_code == 201
    assert attached.json()["baseline_evidence"]["demo_only"] is True
    assert prepared_again.json()["baseline_attached"] is True
    assert prepared_again.json()["next_case_id"] == DEMO_CURRENT_ID

    assert current.status_code == 200
    assert current.json()["demo_only"] is True
    assert current.json()["evidence_suitability"] == "synthetische_demo"
    assert current.json()["capture_galleries"]["agb"]["title"] == "PDF · Stand 20.07.2026"
    assert current.json()["capture_galleries"]["agb"]["document_urls"]
    assert current_pdf_bytes.startswith(b"%PDF-")
    assert current_pdf_sha256 == sha256_file(CURRENT_DOCUMENT_PATH)
    assert current_pdf_page_count == 14
    assert "Teillieferungen berechtigt" in current_text
    assert "auf einer von dir schuldhaft" in current_text
    assert "begangenen Rechtsverletzung beruhen" in current_text
    assert current_record["demo_fixture_revision"] == DEMO_FIXTURE_REVISION

    assert compared.status_code == 201
    comparison = compared.json()["comparison"]
    assert comparison["status"] == "technische_aenderung_erkannt"
    assert comparison["demo_only"] is True
    assert comparison["demo_notice"] == DEMO_NOTICE
    assert comparison["differences"]
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
