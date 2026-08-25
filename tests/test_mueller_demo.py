from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from muclegal.decathlon_demo import ensure_demo_bundle
from muclegal.monitoring_cases import MonitoringCaseRepository
from muclegal.mueller_demo import (
    BASELINE_TEXT,
    DEMO_BASELINE_ID,
    DEMO_CURRENT_URL,
    DEMO_FALL_ID,
    DEMO_NOTICE,
)
from muclegal.ui import create_app


CURRENT_TEXT = """Allgemeine Geschäftsbedingungen · Teil 2 Lieferung in die Filiale

Nach Ihrer Bestellung erhalten Sie eine Reservierungsbestätigung. Diese stellt
noch keine Annahme Ihres Angebots dar.

Ein Kaufvertrag kommt nur zustande, wenn Sie die Artikel in der Filiale
entgegennehmen und bezahlen.
"""


def test_mueller_demo_prepares_attached_baseline_for_live_agb_comparison() -> None:
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
            prepared = client.post("/api/v1/demo/mueller")
            prepared_again = client.post("/api/v1/demo/mueller")
            payload = prepared.json()
            monitoring_case = client.get(
                f"/api/v1/monitoring-cases/{payload['monitoring_case_id']}"
            )
            baseline = client.get(f"/api/v1/cases/{DEMO_BASELINE_ID}")

            current_id = "demo-mueller-agb-aktuell"
            ensure_demo_bundle(
                root,
                current_id,
                url=DEMO_CURRENT_URL,
                text=CURRENT_TEXT,
                title="Müller-AGB · aktueller Teststand",
                fall_id=DEMO_FALL_ID,
                notice=DEMO_NOTICE,
            )
            compared = client.post(
                f"/api/v1/cases/{payload['monitoring_case_id']}/evidence-comparisons",
                json={"evidence_case_id": current_id},
            )

    assert page.status_code == 200
    assert 'id="mueller-demo"' in page.text
    assert "/api/v1/demo/mueller" in page.text
    assert prepared.status_code == 200
    assert prepared_again.status_code == 200
    assert payload["fall_id"] == DEMO_FALL_ID
    assert payload["current_url"] == DEMO_CURRENT_URL
    assert payload["baseline_attached"] is True
    assert prepared_again.json()["monitoring_case_id"] == payload["monitoring_case_id"]

    case_payload = monitoring_case.json()
    assert case_payload["baseline_evidence"]["evidence_case_id"] == DEMO_BASELINE_ID
    assert case_payload["baseline_evidence"]["demo_only"] is True
    assert "JETZT RESERVIEREN" in case_payload["clause_text"]
    assert case_payload["clause_text"] == BASELINE_TEXT.strip()

    assert baseline.status_code == 200
    assert baseline.json()["demo_only"] is True
    assert baseline.json()["demo_notice"] == DEMO_NOTICE

    assert compared.status_code == 201
    comparison = compared.json()["comparison"]
    assert comparison["status"] == "technische_aenderung_erkannt"
    assert comparison["compared_role"] == "agb"
    assert comparison["demo_only"] is True
    assert comparison["differences"]
