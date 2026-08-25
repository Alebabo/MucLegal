from __future__ import annotations

import html
import json
import shutil
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from muclegal.evidence import create_manifest, sha256_file, verify_manifest
from muclegal.monitoring_cases import MonitoringCaseRepository


DEMO_FALL_ID = "VZ-DECATHLON-GESAMTBEWEIS-2026"
DEMO_BASELINE_ID = "demo-decathlon-webarchiv"
DEMO_CURRENT_ID = "demo-decathlon-aktuell"
DEMO_NOTICE = (
    "SYNTHETISCHE DEMO: Dieser eingefrorene Snapshot dient ausschließlich der "
    "Vorführung des Zuordnungs- und Vergleichsablaufs. Er ist kein Live-Beweis und "
    "darf nicht als Nachweis eines tatsächlichen Decathlon-Seitenstands verwendet werden."
)
DEMO_BASELINE_URL = (
    "https://web.archive.org/web/20241008191055/"
    "https://www.decathlon.de/AGB_lp-P7ELHE"
)
DEMO_CURRENT_URL = (
    "https://www.decathlon.de/c/legal/"
    "allgemeine-geschaeftsbedingungen-agb-webshop_917fe9ac-dc2d-4705-a58b-63c393960b57"
)

BASELINE_TEXT = """SYNTHETISCHE DEMO-FASSUNG · Webarchiv-Ausgangsstand Oktober 2024

Teillieferungen sind jedoch, nach vorherigem Hinweis, möglich, sofern eine Komplettlieferung nicht durchgeführt werden kann.

Du stellst decathlon.de von allen Ansprüchen Dritter frei, die decathlon.de aus oder im Zusammenhang mit den von dir hochgeladenen, bearbeiteten oder erstellten Motiven entstehen.
"""

CURRENT_TEXT = """SYNTHETISCHE DEMO-FASSUNG · Aktueller Vergleichsstand Juli 2026

Teillieferungen erfolgen nur, soweit sie für dich zumutbar sind, keine zusätzlichen Versandkosten entstehen und deine gesetzlichen Rechte gewahrt bleiben.

Eine Freistellung gilt nur für Ansprüche aufgrund einer von dir schuldhaft begangenen Rechtsverletzung. Sie gilt nicht, soweit DECATHLON eine gebotene Entfernung schuldhaft versäumt hat.
"""


def prepare_decathlon_demo(
    store_root: str | Path,
    monitoring_cases: MonitoringCaseRepository,
) -> dict:
    """Prepare a local-only, unmistakably synthetic replay of the real UI workflow."""

    root = Path(store_root).resolve()
    baseline = _ensure_demo_bundle(
        root,
        DEMO_BASELINE_ID,
        url=DEMO_BASELINE_URL,
        text=BASELINE_TEXT,
        title="Webarchiv · synthetischer Demo-Ausgangsstand",
        next_case_id=DEMO_CURRENT_ID,
    )
    current = _ensure_demo_bundle(
        root,
        DEMO_CURRENT_ID,
        url=DEMO_CURRENT_URL,
        text=CURRENT_TEXT,
        title="Aktuell · synthetischer Demo-Vergleichsstand",
    )

    candidates = [case for case in monitoring_cases.list() if case.fall_id == DEMO_FALL_ID]
    monitoring_case = candidates[0] if candidates else monitoring_cases.create(_case_payload())
    baseline_attached = monitoring_case.baseline_evidence is not None
    next_case_id = current["case_id"] if baseline_attached else baseline["case_id"]
    return {
        "demo_only": True,
        "demo_notice": DEMO_NOTICE,
        "fall_id": monitoring_case.fall_id,
        "monitoring_case_id": monitoring_case.case_id,
        "baseline_evidence_case_id": baseline["case_id"],
        "current_evidence_case_id": current["case_id"],
        "baseline_attached": baseline_attached,
        "next_case_id": next_case_id,
        "next_step": (
            "Aktuellen Demo-Snapshot manuell zuordnen und vergleichen."
            if baseline_attached
            else "Webarchiv-Demo-Ausgangsstand manuell als Ausgangsbeweis zuordnen."
        ),
    }


def _ensure_demo_bundle(
    store_root: Path,
    case_id: str,
    *,
    url: str,
    text: str,
    title: str,
    next_case_id: str | None = None,
) -> dict:
    bundle_root = store_root / "bundles"
    bundle_root.mkdir(parents=True, exist_ok=True)
    target = bundle_root / case_id
    case_path = target / "case.json"
    if target.exists():
        if not case_path.is_file():
            raise RuntimeError(f"Demo-Paket ist unvollständig: {target}")
        record = json.loads(case_path.read_text(encoding="utf-8"))
        if record.get("demo_only") is not True:
            raise RuntimeError(f"Bestehendes Paket ist nicht als Demo gekennzeichnet: {target}")
        verification = verify_manifest(
            record.get("artifacts", {}).get("manifest", ""),
            expected_manifest_sha256=record.get("evidence", {}).get("manifest_sha256"),
            require_digest_file=True,
        )
        if not verification.valid:
            raise RuntimeError("Vorhandenes Decathlon-Demo-Paket ist nicht manifestgültig.")
        return {"case_id": case_id, "manifest_sha256": verification.manifest_sha256}

    temporary = bundle_root / f".{case_id}.{uuid.uuid4().hex}.tmp"
    try:
        role = temporary / "capture" / "agb"
        role.mkdir(parents=True)
        normalized = role / "normalized-text.txt"
        raw_html = role / "raw.html"
        preview = role / "preview.png"
        capture_index = role / "index.json"
        transparency = temporary / "capture_transparency.yaml"
        interactions = temporary / "screenshot_interactions.json"
        notice_path = temporary / "DEMO_ONLY.txt"

        normalized.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
        raw_html.write_text(
            "<!doctype html><html lang=\"de\"><meta charset=\"utf-8\">"
            f"<title>{html.escape(title)}</title><main><h1>{html.escape(title)}</h1>"
            f"<p><strong>{html.escape(DEMO_NOTICE)}</strong></p>"
            f"<pre>{html.escape(text.strip())}</pre></main></html>",
            encoding="utf-8",
            newline="\n",
        )
        _write_demo_preview(preview, title, text)
        transparency.write_text(
            "capture_type: synthetische_demo\n"
            "live_fetch: false\n"
            "browser_capture: false\n"
            "robots_txt: nicht_anwendbar_synthetische_demo\n"
            "legal_assessment: false\n",
            encoding="utf-8",
            newline="\n",
        )
        interactions.write_text("[]\n", encoding="utf-8", newline="\n")
        notice_path.write_text(DEMO_NOTICE + "\n", encoding="utf-8", newline="\n")
        capture_index.write_text(
            json.dumps(
                {
                    "version": 1,
                    "role": "agb",
                    "title": title,
                    "capture_type": "synthetische_demo",
                    "live_fetch": False,
                    "files": {
                        "normalized_text": "normalized-text.txt",
                        "raw_html": "raw.html",
                        "preview": "preview.png",
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
            newline="\n",
        )
        manifested = {
            "agb_screenshot": preview,
            "capture_index": capture_index,
            "capture_transparency": transparency,
            "demo_notice": notice_path,
            "normalized_text": normalized,
            "raw_html": raw_html,
            "screenshot_interactions": interactions,
        }
        manifest = create_manifest(manifested, temporary, notice=DEMO_NOTICE)
        temporary.rename(target)

        def final_path(path: Path) -> str:
            return str(target / path.relative_to(temporary))

        captured_at = datetime.now(timezone.utc).isoformat()
        record = {
            "url": url,
            "requested_url": url,
            "captured_url": url,
            "erkannt_am": captured_at,
            "fall_id": DEMO_FALL_ID,
            "demo_only": True,
            "demo_notice": DEMO_NOTICE,
            "demo_next_case_id": next_case_id,
            "god_mode": False,
            "evidence_suitability": "synthetische_demo",
            "evidence_suitability_notice": DEMO_NOTICE,
            "capture_completeness": "vollstaendig_erfasst",
            "snapshot_sha256": sha256_file(target / "capture" / "agb" / "normalized-text.txt"),
            "warnings": [DEMO_NOTICE],
            "assessment": {
                "ergebnis": "nicht_bewertet",
                "confidence": 0.0,
            },
            "technical_result": {
                "code": "synthetische_demo",
                "label": "Synthetischer Demo-Snapshot",
                "meaning": DEMO_NOTICE,
                "next_action": "Nur den lokalen UI-Ablauf vorführen.",
                "tone": "warning",
                "what_was_found": "Kein Live-Befund; eingefrorene synthetische Demo-Daten.",
            },
            "capture_transparency": {
                "robots_txt": "nicht_anwendbar_synthetische_demo",
                "capture_type": "synthetische_demo",
                "live_fetch": False,
            },
            "artifacts": {
                "agb_screenshot": final_path(preview),
                "capture_index": final_path(capture_index),
                "capture_transparency": final_path(transparency),
                "normalized_text": final_path(normalized),
                "raw_html": final_path(raw_html),
                "screenshot_interactions": final_path(interactions),
                "manifest": str(target / Path(manifest.manifest_path).name),
                "manifest_digest": str(target / Path(manifest.digest_path).name),
            },
            "capture_galleries": {
                "agb": {
                    "title": title,
                    "mode": "synthetische_demo",
                    "capture_completeness": "vollstaendig_erfasst",
                    "index": "capture/agb/index.json",
                    "preview": "capture/agb/preview.png",
                    "tiles": [],
                    "originals": ["capture/agb/preview.png"],
                    "documents": [],
                    "raw_html": "capture/agb/raw.html",
                }
            },
            "evidence": {
                "manifest_sha256": manifest.manifest_sha256,
                "screenshot_status": "synthetische_demo",
                "screenshot_sha256": sha256_file(target / "capture" / "agb" / "preview.png"),
                "warc_status": "nicht_anwendbar_synthetische_demo",
                "timestamp_status": "nicht_anwendbar_synthetische_demo",
            },
        }
        case_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
        return {"case_id": case_id, "manifest_sha256": manifest.manifest_sha256}
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _write_demo_preview(path: Path, title: str, text: str) -> None:
    image = Image.new("RGB", (1200, 900), "#f7f3ea")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 118), fill="#291f16")
    draw.text((54, 38), "SYNTHETISCHE DEMO · KEIN LIVE-BEWEIS", fill="#ffffff")
    draw.text((54, 154), title, fill="#291f16")
    y = 210
    for paragraph in text.strip().split("\n"):
        if not paragraph.strip():
            y += 24
            continue
        for line in textwrap.wrap(paragraph, width=108):
            draw.text((54, y), line, fill="#291f16")
            y += 24
        y += 10
    draw.rectangle((44, 790, 1156, 856), outline="#a85d00", width=3)
    draw.text((62, 812), "Nur zur Vorführung des lokalen Zuordnungs- und Vergleichsablaufs.", fill="#7a4300")
    image.save(path, format="PNG")


def _case_payload() -> dict:
    return {
        "fall_id": DEMO_FALL_ID,
        "domain": "www.decathlon.de",
        "source_url": "https://www.decathlon.de/AGB_lp-P7ELHE",
        "violation_type": "klausel",
        "description": (
            "Klar gekennzeichneter synthetischer Decathlon-Demofall für die lokale "
            "Vorführung der manuellen Beweiszuordnung und technischen Differenzanzeige."
        ),
        "tenor_element": (
            "Synthetischer Demo-Tenor: Teillieferungs- und Freistellungsklauseln werden "
            "ausschließlich zur Vorführung des technischen Vergleichs gegenübergestellt."
        ),
        "monitoring_target": (
            "Synthetischen aktuellen Demo-Snapshot technisch gegen den eingefrorenen "
            "Webarchiv-Demo-Ausgangsstand vergleichen. Keine juristische Bewertung."
        ),
        "relevant_page_types": ["AGB"],
        "target_urls": [DEMO_CURRENT_URL],
        "nicht_umfasst": ["Sämtliche Aussagen über einen tatsächlichen Live-Seitenstand."],
        "clause_text": BASELINE_TEXT.strip(),
        "element_label": None,
        "element_labels": [],
        "element_function": None,
        "element_error": None,
        "allowed_subdomains": [],
    }
