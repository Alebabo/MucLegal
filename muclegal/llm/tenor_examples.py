from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal


ViolationBranch = Literal["A", "B", "C"]

UE_EXAMPLE_REFERENCE_VERSION = "ue-examples-2026-08-25-v1"
UE_EXAMPLE_SOURCE_PATH = Path(__file__).resolve().parents[2] / "reference" / "ue_examples.json"
MAX_SELECTED_UE_EXAMPLES = 3

_BANNED_COURT_FORMULAS = (
    "die beklagte wird verurteilt",
    "der beklagten wird untersagt",
    "es wird untersagt",
    "ordnungsgeld",
    "ordnungshaft",
)
_TOKEN_RE = re.compile(r"[a-zäöüß0-9]{4,}", re.IGNORECASE)


class UEExampleValidationError(ValueError):
    pass


def _tokens(value: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(value)}


def _validate_record(record: Any) -> dict[str, Any]:
    required = {
        "id",
        "label",
        "source_url",
        "court_case",
        "branch",
        "fallgruppe",
        "original_tenor",
        "ue_style_example",
        "source_verified",
        "case_reference_match",
        "prompt_eligible",
        "verification_history",
        "quarantine_reason",
    }
    allowed = required | {"primary_verification_url"}
    if (
        not isinstance(record, dict)
        or not required.issubset(record)
        or not set(record).issubset(allowed)
    ):
        raise UEExampleValidationError("UE-Beispielregister enthält einen ungültigen Eintrag.")
    for field in ("id", "label", "source_url", "court_case", "fallgruppe"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise UEExampleValidationError(f"{field} muss im UE-Beispielregister gesetzt sein.")
    if record["branch"] not in {"A", "B", "C"}:
        raise UEExampleValidationError("UE-Beispielregister enthält einen unbekannten Ast.")
    for field in ("source_verified", "case_reference_match", "prompt_eligible"):
        if not isinstance(record[field], bool):
            raise UEExampleValidationError(f"{field} muss ein Wahrheitswert sein.")
    if not isinstance(record["verification_history"], list) or not all(
        isinstance(item, str) and item.strip() for item in record["verification_history"]
    ):
        raise UEExampleValidationError("verification_history muss nichtleere Texte enthalten.")
    if not isinstance(record["quarantine_reason"], str):
        raise UEExampleValidationError("quarantine_reason muss Text sein.")
    if not isinstance(record["original_tenor"], str) or not isinstance(
        record["ue_style_example"], str
    ):
        raise UEExampleValidationError("Tenor und UE-Stilbeispiel müssen Texte sein.")

    if record["prompt_eligible"]:
        if not record["source_verified"] or not record["case_reference_match"]:
            raise UEExampleValidationError(
                "Nur quellen- und aktenzeichengeprüfte Beispiele dürfen prompt_eligible sein."
            )
        example = record["ue_style_example"].strip()
        if not example.startswith("…es zu unterlassen,"):
            raise UEExampleValidationError("Ein freigegebenes UE-Beispiel hat keine UE-Formel.")
        lowered = example.casefold()
        if any(formula in lowered for formula in _BANNED_COURT_FORMULAS):
            raise UEExampleValidationError("Gerichtliche Formeln dürfen nicht in Modellbeispiele.")
        if record["quarantine_reason"].strip():
            raise UEExampleValidationError("Freigegebene Beispiele dürfen nicht quarantänisiert sein.")
        primary_url = record.get("primary_verification_url", "")
        if not isinstance(primary_url, str) or not primary_url.startswith(
            "https://www.gesetze-bayern.de/Content/Document/"
        ):
            raise UEExampleValidationError(
                "Ein freigegebenes Beispiel benötigt eine maschinenlesbare Primärquelle."
            )
    return record


def load_ue_examples(path: Path = UE_EXAMPLE_SOURCE_PATH) -> tuple[dict[str, Any], ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UEExampleValidationError("UE-Beispielregister ist nicht lesbar.") from exc
    if not isinstance(payload, dict) or set(payload) != {"version", "source_documents", "examples"}:
        raise UEExampleValidationError("UE-Beispielregister hat eine ungültige Wurzelstruktur.")
    if payload["version"] != UE_EXAMPLE_REFERENCE_VERSION:
        raise UEExampleValidationError("UE-Beispielregister hat eine unerwartete Version.")
    if not isinstance(payload["source_documents"], list) or len(payload["source_documents"]) != 2:
        raise UEExampleValidationError("Beide bereitgestellten Google-Dokumente müssen belegt sein.")
    if not isinstance(payload["examples"], list) or len(payload["examples"]) < 51:
        raise UEExampleValidationError("Das Inventar muss 49 Links und zwei Volltextbeispiele enthalten.")
    records = tuple(_validate_record(item) for item in payload["examples"])
    ids = [item["id"] for item in records]
    if len(ids) != len(set(ids)):
        raise UEExampleValidationError("UE-Beispiel-IDs müssen eindeutig sein.")
    fingerprints = [
        (
            item["source_url"].strip().casefold(),
            item["court_case"].strip().casefold(),
            item["original_tenor"].strip().casefold(),
        )
        for item in records
    ]
    if len(fingerprints) != len(set(fingerprints)):
        raise UEExampleValidationError(
            "Doppelte Quellen-/Tenorkombination im UE-Beispielregister."
        )
    return records


def select_ue_examples(
    *,
    branch: ViolationBranch,
    fallgruppe: str,
    text: str,
    limit: int = MAX_SELECTED_UE_EXAMPLES,
) -> list[dict[str, str]]:
    if branch not in {"A", "B", "C"}:
        raise ValueError("Unbekannter Verstoßast.")
    if not 0 <= limit <= MAX_SELECTED_UE_EXAMPLES:
        raise ValueError("Es dürfen höchstens drei UE-Beispiele ausgewählt werden.")
    query_tokens = _tokens(f"{fallgruppe} {text}")
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for record in load_ue_examples():
        if not record["prompt_eligible"] or record["branch"] != branch:
            continue
        score = 20
        if record["fallgruppe"] == fallgruppe:
            score += 15
        score += len(query_tokens & _tokens(f"{record['label']} {record['fallgruppe']}"))
        candidates.append((score, record["id"], record))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "source_id": record["id"],
            "gericht_az": record["court_case"],
            "ast": record["branch"],
            "fallgruppe": record["fallgruppe"],
            "ue_stilbeispiel": record["ue_style_example"].strip(),
        }
        for _, _, record in candidates[:limit]
    ]


def eligible_source_ids() -> tuple[str, ...]:
    return tuple(record["id"] for record in load_ue_examples() if record["prompt_eligible"])
