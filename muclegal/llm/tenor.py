from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from muclegal.llm.analyzer import MAX_OUTPUT_TOKENS, SONNET_MODEL


TENOR_PROMPT_VERSION = "2026-08-19-tenor-draft-1"
TENOR_SYSTEM_PROMPT = """Du erstellst ausschließlich einen prüfbedürftigen Entwurf für
einen deutschen Unterlassungstenor. Du triffst keine abschließende Rechtsentscheidung.

Arbeitsregeln:
1. Binde den Entwurf eng an die belegten Tatsachen im Input.
2. Formuliere das rechtlich Charakteristische, nicht bloß einzelne Wörter.
3. Nenne kerngleiche Varianten und besonders die nicht umfassten Gegenfälle.
4. Übernimm nur Rechtsgrundlagen aus dem Input; erfinde keine Fundstellen.
5. Nenne offene Tatsachen- oder Rechtsfragen ausdrücklich.
6. freigabe_durch_mensch bleibt immer null.

Antworte ausschließlich im vorgegebenen JSON-Schema."""
TENOR_PROMPT_SHA256 = hashlib.sha256(TENOR_SYSTEM_PROMPT.encode("utf-8")).hexdigest()

TENOR_DRAFT_KEYS = {
    "fall_id",
    "schuldner",
    "entwurf",
    "charakteristischer_kern",
    "kerngleich_umfasst",
    "nicht_umfasst",
    "rechtsgrundlagen",
    "offene_fragen",
    "freigabe_durch_mensch",
}

TENOR_DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fall_id": {"type": "string"},
        "schuldner": {"type": "string"},
        "entwurf": {"type": "string"},
        "charakteristischer_kern": {"type": "string"},
        "kerngleich_umfasst": {
            "type": "array",
            "items": {"type": "string"},
        },
        "nicht_umfasst": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rechtsgrundlagen": {
            "type": "array",
            "items": {"type": "string"},
        },
        "offene_fragen": {
            "type": "array",
            "items": {"type": "string"},
        },
        "freigabe_durch_mensch": {"type": "null"},
    },
    "required": sorted(TENOR_DRAFT_KEYS),
}


class TenorDraftValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TenorDraft:
    fall_id: str
    schuldner: str
    entwurf: str
    charakteristischer_kern: str
    kerngleich_umfasst: tuple[str, ...]
    nicht_umfasst: tuple[str, ...]
    rechtsgrundlagen: tuple[str, ...]
    offene_fragen: tuple[str, ...]
    freigabe_durch_mensch: None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for field in (
            "kerngleich_umfasst",
            "nicht_umfasst",
            "rechtsgrundlagen",
            "offene_fragen",
        ):
            value[field] = list(value[field])
        return value

    def to_monitoring_tenor(self) -> dict[str, Any]:
        return {
            "fall_id": self.fall_id,
            "schuldner": self.schuldner,
            "tenor": self.entwurf,
            "verbotene_praxis": self.charakteristischer_kern,
            "kerngleich_umfasst": list(self.kerngleich_umfasst),
            "nicht_umfasst": list(self.nicht_umfasst),
            "rechtsgrundlage": list(self.rechtsgrundlagen),
            "kanaele": [],
        }


def build_tenor_input(
    *,
    fall_id: str,
    schuldner: str,
    fundstelle: str,
    beschreibung: str,
    rechtsgrundlagen: list[str],
) -> dict[str, Any]:
    fields = {
        "fall_id": fall_id.strip(),
        "schuldner": schuldner.strip(),
        "fundstelle": fundstelle.strip(),
        "beschreibung": beschreibung.strip(),
    }
    if any(not value for value in fields.values()):
        raise ValueError("Fall-ID, Schuldner, Fundstelle und Beschreibung sind erforderlich.")
    if any(len(value) > 4000 for value in fields.values()):
        raise ValueError("Ein Eingabefeld überschreitet die zulässige Länge.")
    legal_bases = [item.strip() for item in rechtsgrundlagen if item.strip()]
    if not legal_bases:
        raise ValueError("Mindestens eine belegte Rechtsgrundlage ist erforderlich.")
    return {**fields, "rechtsgrundlagen": legal_bases}


def validate_tenor_draft(value: Any, *, allowed_legal_bases: list[str]) -> TenorDraft:
    if not isinstance(value, dict) or set(value) != TENOR_DRAFT_KEYS:
        raise TenorDraftValidationError("Tenor-Entwurf weicht vom erwarteten Schema ab.")
    for field in ("fall_id", "schuldner", "entwurf", "charakteristischer_kern"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise TenorDraftValidationError(f"{field} muss ein nichtleerer Text sein.")
    lists: dict[str, tuple[str, ...]] = {}
    for field in (
        "kerngleich_umfasst",
        "nicht_umfasst",
        "rechtsgrundlagen",
        "offene_fragen",
    ):
        raw = value[field]
        if not isinstance(raw, list) or not all(
            isinstance(item, str) and item.strip() for item in raw
        ):
            raise TenorDraftValidationError(f"{field} muss eine Liste nichtleerer Texte sein.")
        if field in {"kerngleich_umfasst", "nicht_umfasst", "rechtsgrundlagen"} and not raw:
            raise TenorDraftValidationError(f"{field} darf nicht leer sein.")
        lists[field] = tuple(item.strip() for item in raw)
    allowed = set(allowed_legal_bases)
    if not set(lists["rechtsgrundlagen"]).issubset(allowed):
        raise TenorDraftValidationError("Der Entwurf enthält eine nicht belegte Rechtsgrundlage.")
    if value["freigabe_durch_mensch"] is not None:
        raise TenorDraftValidationError("Das Modell darf den Tenor nicht menschlich freigeben.")
    return TenorDraft(
        fall_id=value["fall_id"].strip(),
        schuldner=value["schuldner"].strip(),
        entwurf=value["entwurf"].strip(),
        charakteristischer_kern=value["charakteristischer_kern"].strip(),
        kerngleich_umfasst=lists["kerngleich_umfasst"],
        nicht_umfasst=lists["nicht_umfasst"],
        rechtsgrundlagen=lists["rechtsgrundlagen"],
        offene_fragen=lists["offene_fragen"],
    )


class TenorAnalyzer(Protocol):
    mode: str
    model: str

    def analyze(self, model_input: dict[str, Any]) -> Any: ...


class DeterministicTenorAnalyzer:
    mode = "deterministic_demo"
    model = "kein-modell"

    def analyze(self, model_input: dict[str, Any]) -> dict[str, Any]:
        description = model_input["beschreibung"].rstrip(". ")
        return {
            "fall_id": model_input["fall_id"],
            "schuldner": model_input["schuldner"],
            "entwurf": (
                "Es wird untersagt, im geschäftlichen Verkehr gegenüber Verbraucherinnen "
                f"und Verbrauchern {description}, sofern die tatsächlichen Voraussetzungen "
                "hierfür nicht nachweisbar vorliegen."
            ),
            "charakteristischer_kern": description,
            "kerngleich_umfasst": [
                "sinngleiche Darstellung mit gleicher irreführender Wirkung",
            ],
            "nicht_umfasst": [
                "nachweisbar zutreffende Darstellung mit realem tatsächlichem Hintergrund",
            ],
            "rechtsgrundlagen": list(model_input["rechtsgrundlagen"]),
            "offene_fragen": [
                "Tatsächliche Umstände und Reichweite sind vor Freigabe juristisch zu prüfen.",
            ],
            "freigabe_durch_mensch": None,
        }


class AnthropicTenorAnalyzer:
    mode = "live_anthropic"
    model = SONNET_MODEL

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("Live-Modus benötigt `pip install -e .[demo]`.") from exc
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, model_input: dict[str, Any]) -> Any:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=TENOR_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": json.dumps(model_input, ensure_ascii=False, sort_keys=True),
            }],
            output_config={
                "format": {"type": "json_schema", "schema": TENOR_DRAFT_JSON_SCHEMA}
            },
        )
        if response.stop_reason != "end_turn":
            raise RuntimeError(
                "Anthropic-Tenorantwort wurde nicht regulär beendet "
                f"(stop_reason={response.stop_reason!r})."
            )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        if len(text_blocks) != 1:
            raise RuntimeError("Anthropic lieferte keinen eindeutigen strukturierten Tenorentwurf.")
        return json.loads(text_blocks[0])


def create_tenor_draft(
    model_input: dict[str, Any], analyzer: TenorAnalyzer
) -> tuple[TenorDraft, str, str]:
    raw = analyzer.analyze(model_input)
    draft = validate_tenor_draft(
        raw,
        allowed_legal_bases=list(model_input["rechtsgrundlagen"]),
    )
    return draft, analyzer.mode, analyzer.model
