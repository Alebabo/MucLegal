from __future__ import annotations

import html
import json
import re
import shutil
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader

from muclegal.evidence import create_manifest, sha256_file, verify_manifest
from muclegal.monitoring_cases import MonitoringCaseRepository
from muclegal.normalize import normalize_plain_text


DEMO_FALL_ID = "VZ-DECATHLON-GESAMTBEWEIS-2026"
DEMO_BASELINE_ID = "demo-decathlon-webarchiv-20241008"
DEMO_CURRENT_ID = "demo-decathlon-pdf-20260720"
DEMO_NOTICE = "Technischer Referenzdatensatz (demo_only=true)."
DEMO_FIXTURE_REVISION = "decathlon-agb-webarchive-20241008-vs-pdf-20260720-v1"
DEMO_BASELINE_URL = (
    "https://web.archive.org/web/20241008191055/"
    "https://www.decathlon.de/AGB_lp-P7ELHE"
)
DEMO_CURRENT_URL = (
    "https://www.decathlon.de/c/legal/"
    "allgemeine-geschaeftsbedingungen-agb-webshop_917fe9ac-dc2d-4705-a58b-63c393960b57"
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "decathlon_demo"
BASELINE_TEXT_PATH = FIXTURE_ROOT / "agb-webarchiv-2024-10-08.txt"
BASELINE_HTML_PATH = FIXTURE_ROOT / "agb-webarchiv-2024-10-08.html"
BASELINE_DOCUMENT_PATH = FIXTURE_ROOT / "agb-webarchiv-2024-10-08.pdf"
CURRENT_DOCUMENT_PATH = FIXTURE_ROOT / "agb-webshop-verbraucher-2026-07-20.pdf"

_PDF_GLYPH_TRANSLATION = str.maketrans(
    {
        "\ue09d": "+",
        "\ue081": "(",
        "\ue082": ")",
        "\ue088": "-",
        "\ue0a4": "*",
    }
)


def prepare_decathlon_demo(
    store_root: str | Path,
    monitoring_cases: MonitoringCaseRepository,
) -> dict:
    """Prepare the fixed Decathlon Wayback-to-PDF comparison workflow."""

    root = Path(store_root).resolve()
    baseline_text = BASELINE_TEXT_PATH.read_text(encoding="utf-8")
    current_text = _extract_pdf_text(CURRENT_DOCUMENT_PATH)
    baseline = ensure_demo_bundle(
        root,
        DEMO_BASELINE_ID,
        url=DEMO_BASELINE_URL,
        text=baseline_text,
        title="Webarchiv · 08.10.2024",
        next_case_id=DEMO_CURRENT_ID,
        document_path=BASELINE_DOCUMENT_PATH,
        raw_html_path=BASELINE_HTML_PATH,
        source_kind="webarchive_snapshot",
    )
    current = ensure_demo_bundle(
        root,
        DEMO_CURRENT_ID,
        url=DEMO_CURRENT_URL,
        text=current_text,
        title="PDF · Stand 20.07.2026",
        document_path=CURRENT_DOCUMENT_PATH,
        source_kind="uploaded_pdf_fixture",
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


def ensure_demo_bundle(
    store_root: Path,
    case_id: str,
    *,
    url: str,
    text: str,
    title: str,
    next_case_id: str | None = None,
    fall_id: str = DEMO_FALL_ID,
    notice: str = DEMO_NOTICE,
    document_path: Path | None = None,
    raw_html_path: Path | None = None,
    source_kind: str = "fixed_text_fixture",
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
        if record.get("demo_fixture_revision") != DEMO_FIXTURE_REVISION:
            raise RuntimeError(f"Bestehendes Demo-Paket hat einen veralteten Quellenstand: {target}")
        verification = verify_manifest(
            record.get("artifacts", {}).get("manifest", ""),
            expected_manifest_sha256=record.get("evidence", {}).get("manifest_sha256"),
            require_digest_file=True,
        )
        if not verification.valid:
            raise RuntimeError("Vorhandenes Demo-Paket ist nicht manifestgültig.")
        return {
            "case_id": case_id,
            "manifest_sha256": verification.manifest_sha256,
            "captured_at": record["erkannt_am"],
        }

    temporary = bundle_root / f".{case_id}.{uuid.uuid4().hex}.tmp"
    try:
        role = temporary / "capture" / "agb"
        role.mkdir(parents=True)
        normalized = role / "normalized-text.txt"
        raw_html = role / "raw.html"
        preview = role / "preview.png"
        document = role / "source.pdf" if document_path is not None else None
        capture_index = role / "index.json"
        transparency = temporary / "capture_transparency.yaml"
        interactions = temporary / "screenshot_interactions.json"
        notice_path = temporary / "DEMO_ONLY.txt"

        normalized.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
        if raw_html_path is not None:
            shutil.copyfile(raw_html_path, raw_html)
        else:
            raw_html.write_text(
                "<!doctype html><html lang=\"de\"><meta charset=\"utf-8\">"
                f"<title>{html.escape(title)}</title><main><h1>{html.escape(title)}</h1>"
                f"<pre>{html.escape(text.strip())}</pre></main></html>",
                encoding="utf-8",
                newline="\n",
            )
        if document is not None and document_path is not None:
            shutil.copyfile(document_path, document)
        _write_demo_preview(preview, title, text)
        source_path = raw_html_path or document_path
        source_sha256 = (
            sha256_file(source_path) if source_path is not None else sha256_file(normalized)
        )
        transparency.write_text(
            f"capture_type: {source_kind}\n"
            "live_fetch: false\n"
            "browser_capture: false\n"
            f"source_url: {url}\n"
            f"source_sha256: {source_sha256}\n"
            "robots_txt: nicht_anwendbar_fester_quellenstand\n"
            "legal_assessment: false\n",
            encoding="utf-8",
            newline="\n",
        )
        interactions.write_text("[]\n", encoding="utf-8", newline="\n")
        notice_path.write_text(notice + "\n", encoding="utf-8", newline="\n")
        capture_files = {
            "normalized_text": "normalized-text.txt",
            "raw_html": "raw.html",
            "preview": "preview.png",
        }
        if document is not None:
            capture_files["document"] = "source.pdf"
        capture_index.write_text(
            json.dumps(
                {
                    "version": 1,
                    "role": "agb",
                    "title": title,
                    "capture_type": source_kind,
                    "live_fetch": False,
                    "source": {
                        "url": url,
                        "sha256": source_sha256,
                        "kind": source_kind,
                    },
                    "files": capture_files,
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
        if document is not None:
            manifested["agb_pdf"] = document
        manifest = create_manifest(manifested, temporary, notice=notice)
        temporary.rename(target)

        def final_path(path: Path) -> str:
            return str(target / path.relative_to(temporary))

        captured_at = datetime.now(timezone.utc).isoformat()
        record = {
            "url": url,
            "requested_url": url,
            "captured_url": url,
            "erkannt_am": captured_at,
            "fall_id": fall_id,
            "demo_only": True,
            "demo_notice": notice,
            "demo_fixture_revision": DEMO_FIXTURE_REVISION,
            "demo_next_case_id": next_case_id,
            "god_mode": False,
            "evidence_suitability": "synthetische_demo",
            "evidence_suitability_notice": notice,
            "capture_completeness": "vollstaendig_erfasst",
            "snapshot_sha256": sha256_file(target / "capture" / "agb" / "normalized-text.txt"),
            "warnings": [notice],
            "assessment": {
                "ergebnis": "nicht_bewertet",
                "confidence": 0.0,
            },
            "technical_result": {
                "code": source_kind,
                "label": title,
                "meaning": notice,
                "next_action": "Fest hinterlegten Quellenstand technisch vergleichen.",
                "tone": "warning",
                "what_was_found": "Fest hinterlegter AGB-Quellenstand wurde geladen.",
            },
            "capture_transparency": {
                "robots_txt": "nicht_anwendbar_fester_quellenstand",
                "capture_type": source_kind,
                "live_fetch": False,
                "source_url": url,
                "source_sha256": source_sha256,
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
                    "mode": source_kind,
                    "capture_completeness": "vollstaendig_erfasst",
                    "index": "capture/agb/index.json",
                    "preview": "capture/agb/preview.png",
                    "tiles": [],
                    "originals": ["capture/agb/preview.png"],
                    "documents": (["capture/agb/source.pdf"] if document is not None else []),
                    "raw_html": "capture/agb/raw.html",
                }
            },
            "evidence": {
                "manifest_sha256": manifest.manifest_sha256,
                "screenshot_status": "synthetische_demo",
                "screenshot_sha256": sha256_file(target / "capture" / "agb" / "preview.png"),
                "warc_status": "nicht_anwendbar_synthetische_demo",
                "timestamp_status": "nicht_anwendbar_synthetische_demo",
                "source_sha256": source_sha256,
            },
        }
        if document is not None:
            record["artifacts"]["agb_pdf"] = final_path(document)
            record["evidence"]["agb_pdf_sha256"] = sha256_file(
                target / "capture" / "agb" / "source.pdf"
            )
        case_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
        return {
            "case_id": case_id,
            "manifest_sha256": manifest.manifest_sha256,
            "captured_at": captured_at,
        }
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _write_demo_preview(path: Path, title: str, text: str) -> None:
    image = Image.new("RGB", (1200, 900), "#f7f3ea")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 118), fill="#291f16")
    draw.text((54, 42), title, fill="#ffffff")
    y = 154
    for paragraph in text.strip().split("\n"):
        if not paragraph.strip():
            y += 24
            continue
        for line in textwrap.wrap(paragraph, width=108):
            draw.text((54, y), line, fill="#291f16")
            y += 24
        y += 10
    image.save(path, format="PNG")


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted or not reader.pages:
        raise RuntimeError(f"Fest hinterlegte Decathlon-PDF ist nicht lesbar: {path}")
    pages: list[str] = []
    for page in reader.pages:
        extracted = (page.extract_text(extraction_mode="layout") or "").translate(
            _PDF_GLYPH_TRANSLATION
        )
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in extracted.splitlines()]
        pages.append("\n".join(lines))
    text = normalize_plain_text("\n\n".join(pages))
    if len(re.sub(r"\s+", "", text)) < 1_000:
        raise RuntimeError(f"Fest hinterlegte Decathlon-PDF enthält zu wenig Text: {path}")
    return text


def _case_payload() -> dict:
    return {
        "fall_id": DEMO_FALL_ID,
        "domain": "www.decathlon.de",
        "source_url": "https://www.decathlon.de/AGB_lp-P7ELHE",
        "violation_type": "klausel",
        "description": (
            "Fest hinterlegter Decathlon-AGB-Vergleich zwischen dem Webarchiv-Stand "
            "vom 08.10.2024 und dem PDF-Stand vom 20.07.2026."
        ),
        "tenor_element": (
            "Teillieferungs- und Freistellungsklauseln werden im archivierten und im "
            "aktuellen AGB-Stand technisch gegenübergestellt."
        ),
        "monitoring_target": (
            "Die AGB-PDF vom 20.07.2026 technisch gegen den Webarchiv-Ausgangsstand "
            "vom 08.10.2024 vergleichen. Keine juristische Bewertung."
        ),
        "relevant_page_types": ["AGB"],
        "target_urls": [DEMO_CURRENT_URL],
        "nicht_umfasst": ["Sämtliche Aussagen über einen tatsächlichen Live-Seitenstand."],
        "clause_text": BASELINE_TEXT_PATH.read_text(encoding="utf-8").strip(),
        "element_label": None,
        "element_labels": [],
        "element_function": None,
        "element_error": None,
        "allowed_subdomains": [],
    }
