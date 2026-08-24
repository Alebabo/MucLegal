from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from muclegal.tenor_pdf import TenorPdfError, extract_tenor_pdf_text
from muclegal.ui import create_app


def _text_pdf(*pages: str) -> bytes:
    stream = BytesIO()
    document = canvas.Canvas(stream)
    for index, text in enumerate(pages):
        if index:
            document.showPage()
        document.drawString(72, 760, text)
    document.save()
    return stream.getvalue()


def test_extracts_contract_text_page_by_page() -> None:
    result = extract_tenor_pdf_text(
        _text_pdf(
            "Vertrag der Synthetischen Beispiel GmbH mit Verbrauchern",
            "Klausel: Die Kuendigung ist nur schriftlich per Brief moeglich.",
        ),
        filename="vertrag.pdf",
    )

    assert result.page_count == 2
    assert result.extracted_pages == 2
    assert "[Seite 1]" in result.text
    assert "[Seite 2]" in result.text
    assert "Kuendigung ist nur schriftlich" in result.text
    assert result.truncated is False


def test_rejects_pdf_without_machine_readable_text() -> None:
    with BytesIO() as stream:
        document = canvas.Canvas(stream)
        document.showPage()
        document.save()
        data = stream.getvalue()

    try:
        extract_tenor_pdf_text(data, filename="scan.pdf")
    except TenorPdfError as exc:
        assert "OCR" in str(exc)
    else:
        raise AssertionError("Eine PDF ohne Text muss sichtbar abgelehnt werden.")


def test_tenor_pdf_api_returns_text_for_follow_up_questions(tmp_path: Path) -> None:
    app = create_app(tmp_path / "latest-case.json", tmp_path / "reviews.sqlite3")
    data = _text_pdf(
        "Vertrag zwischen der Synthetischen Beispiel GmbH und Verbrauchern. "
        "Die Laufzeit verlaengert sich automatisch um ein Jahr."
    ) + b"\n%" + (b"synthetic-padding" * 5_000)
    assert len(data) > 64 * 1024

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tenor-pdf-text",
            content=data,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": quote("Verbrauchervertrag 2026.pdf"),
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "Verbrauchervertrag 2026.pdf"
    assert payload["page_count"] == 1
    assert "verlaengert sich automatisch" in payload["text"]


def test_tenor_pdf_api_rejects_non_pdf_body(tmp_path: Path) -> None:
    app = create_app(tmp_path / "latest-case.json", tmp_path / "reviews.sqlite3")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tenor-pdf-text",
            content=b"kein pdf",
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 422
    assert "gültige PDF" in response.json()["detail"]
