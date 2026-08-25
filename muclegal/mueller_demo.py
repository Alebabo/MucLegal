from __future__ import annotations

import hashlib
from pathlib import Path

from muclegal.decathlon_demo import ensure_demo_bundle
from muclegal.monitoring_cases import MonitoringCaseRepository


DEMO_FALL_ID = "VZ-MUELLER-CLICK-COLLECT-2025"
DEMO_BASELINE_ID = "demo-mueller-agb-alt"
DEMO_CURRENT_URL = "https://www.mueller.de/unternehmen/agb/"
DEMO_SOURCE_URL = "https://www.landesrecht-bw.de/bsbw/document/NJRE001626589"
DEMO_NOTICE = (
    "HISTORISCHER DEMO-REFERENZTEXT: Die beanstandete Klauselkombination ist dem "
    "rechtskräftigen Urteil des OLG Stuttgart vom 25.11.2025 (6 UKl 1/25) "
    "entnommen. Dieser synthetisch gesetzte Referenzstand ist kein archivierter "
    "Live-Screenshot der früheren Müller-Website."
)

BASELINE_TEXT = """Historischer Demo-Referenzstand · OLG Stuttgart, 25.11.2025, 6 UKl 1/25

Teil 2 · Lieferung in die Filiale

Sie übermitteln sodann ein Angebot zum Abschluss eines Kaufvertrages durch
Anklicken der Schaltfläche „JETZT RESERVIEREN“.

Ein Kaufvertrag kommt nur zustande, wenn Sie die Artikel in der Filiale
entgegennehmen und bezahlen.

Gerichtlich beanstandete Kombination: Die AGB bezeichneten bereits den Klick
auf „JETZT RESERVIEREN“ als Vertragsangebot, erklärten zugleich aber, ein
Kaufvertrag komme nur durch Entgegennahme und Bezahlung in der Filiale zustande.

Quelle der historischen Formulierungen und Konstellation:
OLG Stuttgart, Urteil vom 25.11.2025, Az. 6 UKl 1/25 (rechtskräftig).
"""


def prepare_mueller_demo(
    store_root: str | Path,
    monitoring_cases: MonitoringCaseRepository,
) -> dict:
    """Create the historic Müller case with an attached, labelled demo baseline."""

    root = Path(store_root).resolve()
    baseline = ensure_demo_bundle(
        root,
        DEMO_BASELINE_ID,
        url=DEMO_CURRENT_URL,
        text=BASELINE_TEXT,
        title="Müller-AGB · historischer Demo-Referenzstand",
        fall_id=DEMO_FALL_ID,
        notice=DEMO_NOTICE,
    )

    candidates = [case for case in monitoring_cases.list() if case.fall_id == DEMO_FALL_ID]
    monitoring_case = candidates[0] if candidates else monitoring_cases.create(_case_payload())
    if monitoring_case.baseline_evidence is None:
        normalized_text = BASELINE_TEXT.strip()
        monitoring_case = monitoring_cases.attach_baseline_evidence(
            monitoring_case.case_id,
            {
                "evidence_case_id": DEMO_BASELINE_ID,
                "requested_url": DEMO_CURRENT_URL,
                "captured_url": DEMO_CURRENT_URL,
                "captured_at": baseline["captured_at"],
                "manifest_sha256": baseline["manifest_sha256"],
                "documents": [
                    {
                        "role": "agb",
                        "text": normalized_text,
                        "sha256": hashlib.sha256(
                            normalized_text.encode("utf-8")
                        ).hexdigest(),
                    }
                ],
                "grey_mode": False,
                "demo_only": True,
                "demo_notice": DEMO_NOTICE,
            },
        )

    return {
        "demo_only": True,
        "demo_notice": DEMO_NOTICE,
        "fall_id": monitoring_case.fall_id,
        "monitoring_case_id": monitoring_case.case_id,
        "baseline_evidence_case_id": DEMO_BASELINE_ID,
        "baseline_attached": True,
        "current_url": DEMO_CURRENT_URL,
        "judgment_url": DEMO_SOURCE_URL,
        "next_step": (
            "Aktuelle Müller-AGB im BeweisLab erfassen und den Scan anschließend "
            "dem automatisch ausgewählten Fall zuordnen und vergleichen."
        ),
    }


def _case_payload() -> dict:
    return {
        "fall_id": DEMO_FALL_ID,
        "domain": "www.mueller.de",
        "source_url": DEMO_CURRENT_URL,
        "violation_type": "klausel",
        "description": (
            "Historischer Müller-Click-&-Collect-Fall nach dem rechtskräftigen "
            "Urteil des OLG Stuttgart vom 25.11.2025 (6 UKl 1/25). Der frühere "
            "Klauselstand wird transparent als synthetischer Referenztext geführt."
        ),
        "tenor_element": (
            "Es ist zu unterlassen, in AGB für die Lieferung in eine Filiale zu "
            "erklären, der Kunde übermittle durch Anklicken von „JETZT RESERVIEREN“ "
            "ein Angebot zum Abschluss eines Kaufvertrages, wenn zugleich geregelt "
            "wird, der Kaufvertrag komme nur durch Entgegennahme und Bezahlung in "
            "der Filiale zustande."
        ),
        "monitoring_target": (
            "Technisch prüfen, ob die aktuelle AGB-Fassung für Click & Collect "
            "weiterhin die gerichtlich beanstandete Kombination enthält. Die "
            "rechtliche Einordnung bleibt der menschlichen Prüfung vorbehalten."
        ),
        "relevant_page_types": ["AGB"],
        "target_urls": [DEMO_CURRENT_URL],
        "nicht_umfasst": [
            "Der Kauf-Button für eine Lieferung an die Kundenadresse außerhalb des reinen Filialabholungsablaufs.",
            "Eine Reservierungsbestätigung, die ausdrücklich noch keine Vertragsannahme darstellt.",
        ],
        "clause_text": BASELINE_TEXT.strip(),
        "element_label": None,
        "element_labels": [],
        "element_function": None,
        "element_error": None,
        "allowed_subdomains": [],
    }
