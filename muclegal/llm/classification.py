from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from muclegal.normalize.core import normalize_plain_text


CLASSIFICATIONS = {"beseitigt", "kerngleich", "neuer_sachverhalt", "unsicher"}
CONFIDENCE_LEVELS = {"hoch", "mittel", "niedrig"}
REQUIRED_FIELDS = {
    "classification",
    "tenor_element_id",
    "confidence",
    "evidence_quote",
    "reasoning",
}

CLAUSE_CLASSIFICATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "classification": {"type": "string", "enum": sorted(CLASSIFICATIONS)},
        "tenor_element_id": {"type": "string"},
        "confidence": {"type": "string", "enum": sorted(CONFIDENCE_LEVELS)},
        "evidence_quote": {"type": "string", "minLength": 1},
        "reasoning": {"type": "string", "minLength": 1},
    },
    "required": sorted(REQUIRED_FIELDS),
}


@dataclass(frozen=True)
class ClauseClassification:
    classification: str
    tenor_element_id: str | None
    confidence: str
    evidence_quote: str | None
    reasoning: str
    validation_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_clause_classification(
    value: Any,
    tenor_elements: list[dict[str, Any]],
    old_clause: str | None,
    new_clause: str | None,
) -> ClauseClassification:
    """Validate a model result and fail closed to the first-class `unsicher` result."""
    error = _validation_error(value, tenor_elements, old_clause, new_clause)
    if error:
        return ClauseClassification(
            classification="unsicher",
            tenor_element_id=None,
            confidence="niedrig",
            evidence_quote=None,
            reasoning=f"Automatische Validierung fehlgeschlagen: {error}",
            validation_error=error,
        )
    return ClauseClassification(
        classification=value["classification"],
        tenor_element_id=value["tenor_element_id"],
        confidence=value["confidence"],
        evidence_quote=value["evidence_quote"],
        reasoning=value["reasoning"].strip(),
    )


def _validation_error(
    value: Any,
    tenor_elements: list[dict[str, Any]],
    old_clause: str | None,
    new_clause: str | None,
) -> str | None:
    if not isinstance(value, dict) or set(value) != REQUIRED_FIELDS:
        return "Antwort entspricht nicht dem Klassifikationsschema."
    if value["classification"] not in CLASSIFICATIONS:
        return "Unzulässige Klassifikation."
    if value["confidence"] not in CONFIDENCE_LEVELS:
        return "Unzulässige Konfidenz."
    if not isinstance(value["reasoning"], str) or not value["reasoning"].strip():
        return "Begründung fehlt."
    element_ids = {
        item.get("id") for item in tenor_elements if isinstance(item, dict) and item.get("id")
    }
    if value["tenor_element_id"] not in element_ids:
        return "Tenor-Element existiert nicht."
    quote = value["evidence_quote"]
    if not isinstance(quote, str) or not quote.strip():
        return "Wörtliches Belegzitat fehlt."
    normalized_quote = normalize_plain_text(quote).strip()
    sources = [normalize_plain_text(item).strip() for item in (old_clause, new_clause) if item]
    if not normalized_quote or not any(normalized_quote in source for source in sources):
        return "Belegzitat kommt im alten oder neuen Klauseltext nicht wörtlich vor."
    return None
