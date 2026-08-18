from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def build_pdf_report(report: dict[str, Any], output_path: str | Path) -> str:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("PDF-Erzeugung benötigt `pip install -e .[demo]`.") from exc

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    navy = colors.HexColor("#132238")
    teal = colors.HexColor("#007A78")
    pale = colors.HexColor("#E9F5F3")
    amber = colors.HexColor("#B76600")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleCustom", parent=styles["Title"], textColor=navy, fontSize=22, leading=26))
    styles.add(ParagraphStyle("H2Custom", parent=styles["Heading2"], textColor=teal, fontSize=13, leading=16, spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT))
    styles.add(ParagraphStyle("SmallCustom", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#4B5563")))
    styles.add(ParagraphStyle("Warning", parent=styles["BodyText"], fontSize=9.5, leading=13, textColor=amber, backColor=colors.HexColor("#FFF4E5"), borderPadding=7))

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="MucLegal Prüfbericht",
        author="MucLegal",
    )

    def paragraph(value: Any, style: str = "BodyCustom"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    assessment = report["assessment"]
    evidence = report["evidence"]
    story = [
        Paragraph("MucLegal Prüfbericht", styles["TitleCustom"]),
        paragraph("Synthetischer Demonstrationsfall - keine abschließende Rechtsentscheidung", "Warning"),
        Spacer(1, 6 * mm),
        Table(
            [
                [paragraph("Fall", "SmallCustom"), paragraph(report["fall_id"])],
                [paragraph("URL", "SmallCustom"), paragraph(report["url"])],
                [paragraph("Erkannt am", "SmallCustom"), paragraph(report["erkannt_am"])],
                [paragraph("Status", "SmallCustom"), paragraph("Menschliche Freigabe ausstehend")],
            ],
            colWidths=[35 * mm, 132 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), pale),
                    ("TEXTCOLOR", (0, 0), (0, -1), navy),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CAD5E1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Paragraph("Festgestellte Änderung", styles["H2Custom"]),
        Table(
            [
                [paragraph("Vorher", "SmallCustom"), paragraph(report["vorher"])],
                [paragraph("Nachher", "SmallCustom"), paragraph(report["nachher"])],
            ],
            colWidths=[35 * mm, 132 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CAD5E1")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F7FA")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Paragraph("Automatische juristische Vorprüfung", styles["H2Custom"]),
        KeepTogether(
            [
                paragraph(f"Ergebnis: {assessment['ergebnis']} ({assessment['confidence']:.0%} Confidence)"),
                Spacer(1, 2 * mm),
                paragraph(assessment["begruendung"]),
            ]
        ),
        Paragraph("Tatsachenbasis", styles["H2Custom"]),
        *[paragraph(f"• {item}") for item in assessment["tatsachenbasis"]],
        Paragraph("Stärkstes Gegenargument", styles["H2Custom"]),
        paragraph(assessment["staerkstes_gegenargument"]),
        Paragraph("Unsicherheit", styles["H2Custom"]),
        paragraph(assessment["unsicherheit"]),
        Paragraph("Beweiskette", styles["H2Custom"]),
        Table(
            [
                [paragraph("WARC", "SmallCustom"), paragraph(evidence["warc_status"])],
                [paragraph("Manifest", "SmallCustom"), paragraph(evidence["manifest_sha256"])],
                [paragraph("Hashkette", "SmallCustom"), paragraph(evidence["chain_head_sha256"])],
                [paragraph("RFC 3161", "SmallCustom"), paragraph(evidence["timestamp_status"])],
                [paragraph("Wayback", "SmallCustom"), paragraph(evidence["wayback_status"])],
            ],
            colWidths=[35 * mm, 132 * mm],
            repeatRows=0,
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CAD5E1")),
                    ("BACKGROUND", (0, 0), (0, -1), pale),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Die Modellbewertung ist eine Entscheidungshilfe. freigabe_durch_mensch bleibt null, "
            "bis eine berechtigte Person im Prüfschritt entscheidet.",
            "Warning",
        ),
    ]

    def footer(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        canvas.setStrokeColor(teal)
        canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#4B5563"))
        canvas.drawString(18 * mm, 8.5 * mm, "MucLegal - synthetischer Demonstrationsfall")
        canvas.drawRightString(192 * mm, 8.5 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return str(output_path)
