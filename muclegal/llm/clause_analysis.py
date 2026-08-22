from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from muclegal.clause_diff import ClausePair
from muclegal.llm.analyzer import MAX_OUTPUT_TOKENS, PREFILTER_MODEL
from muclegal.llm.classification import (
    CLAUSE_CLASSIFICATION_JSON_SCHEMA,
    ClauseClassification,
    validate_clause_classification,
)
from muclegal.llm.schema import LegalAssessment, LegalSource


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "classify_v1.md"
CLAUSE_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").strip()
CLAUSE_PROMPT_VERSION = "classify_v1"
CLAUSE_PROMPT_SHA256 = hashlib.sha256(CLAUSE_PROMPT.encode("utf-8")).hexdigest()


class ClauseAnalyzer(Protocol):
    mode: str
    model: str

    def analyze(self, model_input: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class ClassifiedClausePair:
    previous_ordinal: int | None
    current_ordinal: int | None
    previous_text: str | None
    current_text: str | None
    similarity: float
    result: ClauseClassification

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_ordinal": self.previous_ordinal,
            "current_ordinal": self.current_ordinal,
            "previous_text": self.previous_text,
            "current_text": self.current_text,
            "similarity": round(self.similarity, 4),
            **self.result.to_dict(),
        }


@dataclass(frozen=True)
class ClauseAnalysisRun:
    valid: bool
    mode: str
    model: str
    findings: tuple[ClassifiedClausePair, ...]
    assessment: LegalAssessment
    input_path: str
    output_path: str


def tenor_elements_from_tenor(tenor: dict[str, Any]) -> list[dict[str, Any]]:
    elements = [
        {
            "id": "TENOR-KERN",
            "typ": "verbotener_kern",
            "text": tenor.get("verbotene_praxis") or tenor["tenor"],
        }
    ]
    elements.extend(
        {"id": f"KERNGLEICH-{index}", "typ": "kerngleich_umfasst", "text": text}
        for index, text in enumerate(tenor.get("kerngleich_umfasst", []), start=1)
    )
    elements.extend(
        {"id": f"NICHT-ERFASST-{index}", "typ": "nicht_erfasst", "text": text}
        for index, text in enumerate(tenor.get("nicht_umfasst", []), start=1)
    )
    return elements


def build_clause_input(
    tenor: dict[str, Any], pair: ClausePair, tenor_elements: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "fall_id": tenor["fall_id"],
        "tenor": tenor["tenor"],
        "verbotene_praxis": tenor.get("verbotene_praxis", ""),
        "tenor_elements": tenor_elements,
        "altes_klauselstueck": pair.previous.text if pair.previous else None,
        "neues_klauselstueck": pair.current.text if pair.current else None,
    }


class AnthropicClauseAnalyzer:
    mode = "live_anthropic_clause_pairs"
    model = PREFILTER_MODEL

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
            system=CLAUSE_PROMPT,
            messages=[{
                "role": "user",
                "content": json.dumps(model_input, ensure_ascii=False, sort_keys=True),
            }],
            output_config={
                "format": {"type": "json_schema", "schema": CLAUSE_CLASSIFICATION_JSON_SCHEMA}
            },
        )
        if response.stop_reason != "end_turn":
            raise RuntimeError(
                "Anthropic-Klauselantwort wurde nicht regulär beendet "
                f"(stop_reason={response.stop_reason!r})."
            )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        if len(text_blocks) != 1:
            raise RuntimeError("Anthropic lieferte keine eindeutige Klauselklassifikation.")
        return json.loads(text_blocks[0])


class DeterministicClauseAnalyzer:
    mode = "deterministic_clause_demo"
    model = "kein-modell"

    def analyze(self, model_input: dict[str, Any]) -> dict[str, Any]:
        old = model_input.get("altes_klauselstueck")
        new = model_input.get("neues_klauselstueck")
        elements = model_input["tenor_elements"]
        if new is None:
            return _result("beseitigt", elements[0]["id"], old, "Die frühere Klausel fehlt im aktuellen Stand.")

        lowered = new.casefold()
        excluded = next(
            (
                item for item in elements
                if item["typ"] == "nicht_erfasst"
                and _matches_excluded_case(lowered, item["text"].casefold())
            ),
            None,
        )
        if excluded:
            return _result(
                "neuer_sachverhalt",
                excluded["id"],
                new,
                "Die neue Klausel beschreibt einen ausdrücklich nicht erfassten Gegenfall.",
            )

        covered = next(
            (
                item for item in elements
                if item["typ"] == "kerngleich_umfasst"
                and _matches_covered_case(lowered, item["text"].casefold())
            ),
            None,
        )
        if covered:
            return _result(
                "kerngleich",
                covered["id"],
                new,
                "Andere Formulierung, aber derselbe vom Tenor erfasste Wirkungsmechanismus.",
            )
        return _result(
            "unsicher",
            elements[0]["id"],
            new,
            "Die deterministische Demo kann die neue Klausel nicht sicher dem Tenor zuordnen.",
            confidence="niedrig",
        )


def analyze_clause_pairs_and_store(
    tenor: dict[str, Any],
    pairs: tuple[ClausePair, ...],
    analyzer: ClauseAnalyzer,
    output_directory: str | Path,
) -> ClauseAnalysisRun:
    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    input_path = output_directory / "clause-model-input.json"
    output_path = output_directory / "clause-model-output.json"
    metadata_path = output_directory / "clause-analysis-metadata.json"
    elements = tenor_elements_from_tenor(tenor)
    inputs: list[dict[str, Any]] = []
    findings: list[ClassifiedClausePair] = []
    for pair in pairs:
        model_input = build_clause_input(tenor, pair, elements)
        inputs.append(model_input)
        try:
            raw = analyzer.analyze(model_input)
        except Exception as exc:
            raw = {
                "classification": "unsicher",
                "tenor_element_id": elements[0]["id"],
                "confidence": "niedrig",
                "evidence_quote": _short_quote(
                    pair.current.text if pair.current else pair.previous.text
                ),
                "reasoning": f"Modellaufruf fehlgeschlagen: {type(exc).__name__}: {exc}",
            }
        validated = validate_clause_classification(
            raw,
            elements,
            pair.previous.text if pair.previous else None,
            pair.current.text if pair.current else None,
        )
        findings.append(
            ClassifiedClausePair(
                previous_ordinal=pair.previous.ordinal if pair.previous else None,
                current_ordinal=pair.current.ordinal if pair.current else None,
                previous_text=pair.previous.text if pair.previous else None,
                current_text=pair.current.text if pair.current else None,
                similarity=pair.similarity,
                result=validated,
            )
        )
    assessment = aggregate_clause_findings(tenor, tuple(findings))
    valid = all(item.result.validation_error is None for item in findings)
    input_payload = {
        "prompt_version": CLAUSE_PROMPT_VERSION,
        "prompt_sha256": CLAUSE_PROMPT_SHA256,
        "pairs": inputs,
    }
    output_payload = {
        "schema_valid": valid,
        "classifications": [item.to_dict() for item in findings],
        "aggregate_assessment": assessment.to_dict(),
    }
    _write_json(input_path, input_payload)
    _write_json(output_path, output_payload)
    _write_json(metadata_path, {
        "mode": analyzer.mode,
        "model": analyzer.model,
        "prompt_version": CLAUSE_PROMPT_VERSION,
        "prompt_sha256": CLAUSE_PROMPT_SHA256,
        "schema_valid": valid,
        "pair_count": len(findings),
    })
    return ClauseAnalysisRun(
        valid=valid,
        mode=analyzer.mode,
        model=analyzer.model,
        findings=tuple(findings),
        assessment=assessment,
        input_path=str(input_path),
        output_path=str(output_path),
    )


def aggregate_clause_findings(
    tenor: dict[str, Any], findings: tuple[ClassifiedClausePair, ...]
) -> LegalAssessment:
    classes = [item.result.classification for item in findings]
    if "kerngleich" in classes:
        result = "kerngleich_umfasst"
    elif "unsicher" in classes or not classes:
        result = "unklar"
    else:
        result = "nicht_umfasst"
    levels = {"hoch": 0.9, "mittel": 0.7, "niedrig": 0.4}
    confidence = min((levels[item.result.confidence] for item in findings), default=0.4)
    facts = tuple(
        f"{item.result.classification}: {item.result.evidence_quote}"
        for item in findings
        if item.result.evidence_quote
    ) or ("Keine belastbare geänderte Klausel ermittelt.",)
    reasoning = " ".join(item.result.reasoning for item in findings)
    sources = tuple(
        LegalSource(str(source), "nicht_verifiziert")
        for source in tenor.get("rechtsgrundlage", [])
    )
    return LegalAssessment(
        ergebnis=result,
        begruendung=reasoning or "Klauselscharfe Vorprüfung ohne abschließende Rechtsentscheidung.",
        tatsachenbasis=facts,
        rechtsquellen=sources,
        staerkstes_gegenargument=(
            "Die tatsächlichen Umstände können von der textlichen Klauselwirkung abweichen."
        ),
        unsicherheit="Jede Klauselklassifikation muss durch einen Menschen freigegeben werden.",
        confidence=confidence,
    )


def _matches_excluded_case(value: str, excluded_text: str) -> bool:
    has_date = bool(
        re.search(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b", value)
    )
    has_terms = "belegbar" in excluded_text or "enddatum" in excluded_text
    return has_date and has_terms


def _matches_covered_case(value: str, covered_text: str) -> bool:
    if "countdown" in covered_text:
        return "countdown" in value or (":" in value and any(char.isdigit() for char in value))
    if "restmengen" in covered_text:
        return any(term in value for term in ("nur noch", "stück", "verfügbar", "lager"))
    if "nur heute" in covered_text:
        return "nur heute" in value
    return covered_text in value


def _result(
    classification: str,
    element_id: str,
    source: str | None,
    reasoning: str,
    *,
    confidence: str = "hoch",
) -> dict[str, Any]:
    return {
        "classification": classification,
        "tenor_element_id": element_id,
        "confidence": confidence,
        "evidence_quote": _short_quote(source),
        "reasoning": reasoning,
    }


def _short_quote(value: str | None, max_chars: int = 240) -> str:
    if not value:
        return "Kein aktueller Klauseltext vorhanden."
    return value[:max_chars]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
