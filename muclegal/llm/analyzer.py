from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from muclegal.llm.prompt import PROMPT_SHA256, PROMPT_VERSION, SYSTEM_PROMPT
from muclegal.llm.schema import (
    ASSESSMENT_JSON_SCHEMA,
    AssessmentValidationError,
    LegalAssessment,
    validate_assessment,
)


SONNET_MODEL = "claude-sonnet-5"
PREFILTER_MODEL = "claude-haiku-4-5"
MAX_OUTPUT_TOKENS = 4800
ALLOWED_METADATA = {"fall_id", "url", "erkannt_am", "snapshot_sha256"}


class Analyzer(Protocol):
    mode: str
    model: str

    def analyze(self, model_input: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class AnalysisRun:
    valid: bool
    mode: str
    model: str
    assessment: LegalAssessment | None
    validation_error: str | None
    input_path: str
    output_path: str


def build_model_input(
    tenor: dict[str, Any],
    vorher: str,
    nachher: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(tenor, dict) or not tenor.get("tenor") or not tenor.get("fall_id"):
        raise ValueError("Tenor benötigt mindestens fall_id und tenor.")
    if not isinstance(vorher, str) or not isinstance(nachher, str):
        raise ValueError("Vorher- und Nachher-Ausschnitt müssen Text sein.")
    safe_metadata = {key: metadata[key] for key in ALLOWED_METADATA if key in metadata}
    return {
        "tenor": tenor,
        "aenderung": {"vorher": vorher, "nachher": nachher},
        "belegte_metadaten": safe_metadata,
    }


class OfflineAnalyzer:
    mode = "offline_fixture"
    model = "fixture-kein-modell"

    def __init__(self, response_path: str | Path) -> None:
        self.response_path = Path(response_path)

    def analyze(self, model_input: dict[str, Any]) -> Any:
        del model_input
        return json.loads(self.response_path.read_text(encoding="utf-8"))


class AnthropicAnalyzer:
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
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(model_input, ensure_ascii=False, sort_keys=True),
                }
            ],
            output_config={
                "format": {"type": "json_schema", "schema": ASSESSMENT_JSON_SCHEMA}
            },
        )
        if response.stop_reason != "end_turn":
            raise RuntimeError(
                "Anthropic-Antwort wurde nicht regulär beendet "
                f"(stop_reason={response.stop_reason!r})."
            )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        if len(text_blocks) != 1:
            raise RuntimeError("Anthropic-Antwort enthält nicht genau einen Textblock.")
        return json.loads(text_blocks[0])


def analyze_and_store(
    model_input: dict[str, Any],
    analyzer: Analyzer,
    output_directory: str | Path,
) -> AnalysisRun:
    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    input_path = output_directory / "model-input.json"
    output_path = output_directory / "model-output.json"
    metadata_path = output_directory / "analysis-metadata.json"
    input_path.write_text(
        json.dumps(model_input, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )

    call_error: str | None = None
    try:
        raw_output = analyzer.analyze(model_input)
    except Exception as exc:
        call_error = f"Modellantwort fehlt: {type(exc).__name__}: {exc}"
        raw_output = {"_error": call_error}
    output_path.write_text(
        json.dumps(raw_output, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    assessment: LegalAssessment | None = None
    validation_error: str | None = None
    if call_error:
        validation_error = call_error
    else:
        try:
            assessment = validate_assessment(raw_output)
        except AssessmentValidationError as exc:
            validation_error = str(exc)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": analyzer.mode,
        "model": analyzer.model,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "valid": assessment is not None,
        "validation_error": validation_error,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return AnalysisRun(
        valid=assessment is not None,
        mode=analyzer.mode,
        model=analyzer.model,
        assessment=assessment,
        validation_error=validation_error,
        input_path=str(input_path),
        output_path=str(output_path),
    )
