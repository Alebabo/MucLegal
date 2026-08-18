from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


RESULTS = {"kerngleich_umfasst", "nicht_umfasst", "unklar"}
SOURCE_STATUSES = {"verifiziert", "nicht_verifiziert"}
REQUIRED_KEYS = {
    "ergebnis",
    "begruendung",
    "tatsachenbasis",
    "rechtsquellen",
    "staerkstes_gegenargument",
    "unsicherheit",
    "confidence",
    "freigabe_durch_mensch",
}

ASSESSMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ergebnis": {"type": "string", "enum": sorted(RESULTS)},
        "begruendung": {"type": "string"},
        "tatsachenbasis": {"type": "array", "items": {"type": "string"}},
        "rechtsquellen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fundstelle": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(SOURCE_STATUSES)},
                },
                "required": ["fundstelle", "status"],
            },
        },
        "staerkstes_gegenargument": {"type": "string"},
        "unsicherheit": {"type": "string"},
        "confidence": {"type": "number"},
        "freigabe_durch_mensch": {"type": "null"},
    },
    "required": sorted(REQUIRED_KEYS),
}


class AssessmentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LegalSource:
    fundstelle: str
    status: str


@dataclass(frozen=True)
class LegalAssessment:
    ergebnis: str
    begruendung: str
    tatsachenbasis: tuple[str, ...]
    rechtsquellen: tuple[LegalSource, ...]
    staerkstes_gegenargument: str
    unsicherheit: str
    confidence: float
    freigabe_durch_mensch: None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["tatsachenbasis"] = list(self.tatsachenbasis)
        value["rechtsquellen"] = [asdict(item) for item in self.rechtsquellen]
        return value


def validate_assessment(value: Any) -> LegalAssessment:
    if not isinstance(value, dict):
        raise AssessmentValidationError("Modellantwort muss ein JSON-Objekt sein.")
    actual_keys = set(value)
    if actual_keys != REQUIRED_KEYS:
        raise AssessmentValidationError(
            f"Schemafelder weichen ab; fehlen={sorted(REQUIRED_KEYS - actual_keys)}, "
            f"zusätzlich={sorted(actual_keys - REQUIRED_KEYS)}."
        )
    if value["ergebnis"] not in RESULTS:
        raise AssessmentValidationError("Unzulässiges Ergebnis.")
    for field in ("begruendung", "staerkstes_gegenargument", "unsicherheit"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise AssessmentValidationError(f"{field} muss ein nichtleerer Text sein.")
    facts = value["tatsachenbasis"]
    if not isinstance(facts, list) or not facts or not all(
        isinstance(item, str) and item.strip() for item in facts
    ):
        raise AssessmentValidationError("tatsachenbasis muss eine nichtleere Textliste sein.")
    sources = value["rechtsquellen"]
    if not isinstance(sources, list):
        raise AssessmentValidationError("rechtsquellen muss eine Liste sein.")
    validated_sources: list[LegalSource] = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"fundstelle", "status"}:
            raise AssessmentValidationError("Jede Rechtsquelle benötigt genau fundstelle und status.")
        if not isinstance(source["fundstelle"], str) or not source["fundstelle"].strip():
            raise AssessmentValidationError("Leere Fundstelle ist unzulässig.")
        if source["status"] not in SOURCE_STATUSES:
            raise AssessmentValidationError("Unzulässiger Rechtsquellenstatus.")
        validated_sources.append(LegalSource(source["fundstelle"], source["status"]))
    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise AssessmentValidationError("confidence muss eine Zahl sein.")
    if not 0 <= float(confidence) <= 1:
        raise AssessmentValidationError("confidence muss zwischen 0 und 1 liegen.")
    if value["freigabe_durch_mensch"] is not None:
        raise AssessmentValidationError("Modellantwort darf keine menschliche Freigabe setzen.")
    return LegalAssessment(
        ergebnis=value["ergebnis"],
        begruendung=value["begruendung"].strip(),
        tatsachenbasis=tuple(item.strip() for item in facts),
        rechtsquellen=tuple(validated_sources),
        staerkstes_gegenargument=value["staerkstes_gegenargument"].strip(),
        unsicherheit=value["unsicherheit"].strip(),
        confidence=float(confidence),
    )

