from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from muclegal.llm import AnthropicAnalyzer, OfflineAnalyzer, analyze_and_store
from muclegal.llm.analyzer import Analyzer, build_model_input
from muclegal.llm.prompt import PROMPT_SHA256, PROMPT_VERSION
from muclegal.llm.schema import RESULTS


_SAFE_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_METRIC_NAMES = (
    "schema_valid_rate",
    "result_accuracy",
    "human_release_null_rate",
    "reasoning_rate",
    "counterargument_rate",
)


class ExpectedFixtureAnalyzer:
    """Deterministic expected response for an inline synthetic eval case."""

    mode = "offline_expected_fixture"
    model = "fixture-kein-modell"

    def __init__(self, case: dict[str, Any], tenor: dict[str, Any]) -> None:
        self.case = case
        self.tenor = tenor

    def analyze(self, model_input: dict[str, Any]) -> dict[str, Any]:
        del model_input
        return {
            "ergebnis": self.case["expected_result"],
            "begruendung": self.case["expected_reason"],
            "tatsachenbasis": [self.case["input"]["nachher"]],
            "rechtsquellen": [
                {"fundstelle": source, "status": "nicht_verifiziert"}
                for source in self.tenor.get("rechtsgrundlage", [])
            ],
            "staerkstes_gegenargument": self.case["strongest_counterargument"],
            "unsicherheit": self.case.get(
                "uncertainty", "Die tatsächlichen Umstände sind menschlich zu verifizieren."
            ),
            "confidence": float(self.case.get("fixture_confidence", 0.7)),
            "freigabe_durch_mensch": None,
        }


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    expected_result: str
    actual_result: str | None
    schema_valid: bool
    result_correct: bool
    human_release_null: bool
    has_reasoning: bool
    has_counterargument: bool
    passed: bool
    duration_ms: int
    validation_error: str | None
    model_output_path: str


@dataclass(frozen=True)
class EvalReport:
    suite_name: str
    suite_version: int
    mode: str
    model: str
    created_at: str
    prompt_version: str
    prompt_sha256: str
    metrics: dict[str, float]
    gates: dict[str, float]
    gate_results: dict[str, bool]
    passed: bool
    confusion_matrix: dict[str, dict[str, int]]
    cases: tuple[EvalCaseResult, ...]
    json_path: str
    markdown_path: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["cases"] = [asdict(case) for case in self.cases]
        return value


def run_evaluation(
    suite_path: str | Path,
    output_directory: str | Path,
    *,
    live: bool = False,
    live_analyzer: Analyzer | None = None,
) -> EvalReport:
    suite_path = Path(suite_path).resolve()
    suite_root = suite_path.parent
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    _validate_suite(suite)
    tenor = _read_json_below(suite_root, suite["tenor_path"])
    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    shared_analyzer = live_analyzer or (AnthropicAnalyzer() if live else None)

    case_results: list[EvalCaseResult] = []
    confusion: dict[str, dict[str, int]] = {
        expected: {actual: 0 for actual in (*sorted(RESULTS), "invalid")}
        for expected in sorted(RESULTS)
    }
    for case in suite["cases"]:
        case_id = case["id"]
        case_input = (
            case["input"]
            if isinstance(case.get("input"), dict)
            else _read_json_below(suite_root, case["input_path"])
        )
        model_input = build_model_input(
            tenor,
            case_input["vorher"],
            case_input["nachher"],
            case_input["belegte_metadaten"],
        )
        analyzer = shared_analyzer or _offline_analyzer(suite_root, case, tenor)
        started = time.perf_counter()
        run = analyze_and_store(model_input, analyzer, output_directory / "cases" / case_id)
        duration_ms = round((time.perf_counter() - started) * 1000)
        assessment = run.assessment
        actual_result = assessment.ergebnis if assessment else None
        expected_result = case["expected_result"]
        schema_valid = run.valid
        result_correct = actual_result == expected_result
        human_release_null = bool(assessment and assessment.freigabe_durch_mensch is None)
        has_reasoning = bool(assessment and assessment.begruendung.strip())
        has_counterargument = bool(
            assessment and assessment.staerkstes_gegenargument.strip()
        )
        passed = all(
            (
                schema_valid,
                result_correct,
                human_release_null,
                has_reasoning,
                has_counterargument,
            )
        )
        confusion[expected_result][actual_result or "invalid"] += 1
        case_results.append(
            EvalCaseResult(
                case_id=case_id,
                expected_result=expected_result,
                actual_result=actual_result,
                schema_valid=schema_valid,
                result_correct=result_correct,
                human_release_null=human_release_null,
                has_reasoning=has_reasoning,
                has_counterargument=has_counterargument,
                passed=passed,
                duration_ms=duration_ms,
                validation_error=run.validation_error,
                model_output_path=run.output_path,
            )
        )

    count = len(case_results)
    metrics = {
        "schema_valid_rate": _rate(case_results, "schema_valid"),
        "result_accuracy": _rate(case_results, "result_correct"),
        "human_release_null_rate": _rate(case_results, "human_release_null"),
        "reasoning_rate": _rate(case_results, "has_reasoning"),
        "counterargument_rate": _rate(case_results, "has_counterargument"),
    }
    gates = {name: float(suite["gates"][name]) for name in _METRIC_NAMES}
    gate_results = {name: metrics[name] >= gates[name] for name in _METRIC_NAMES}
    analyzer_for_metadata = shared_analyzer or _offline_analyzer(
        suite_root, suite["cases"][0], tenor
    )
    created_at = datetime.now(timezone.utc).isoformat()
    json_path = output_directory / "eval-results.json"
    markdown_path = output_directory / "eval-report.md"
    report = EvalReport(
        suite_name=suite["name"],
        suite_version=int(suite["version"]),
        mode=analyzer_for_metadata.mode,
        model=analyzer_for_metadata.model,
        created_at=created_at,
        prompt_version=PROMPT_VERSION,
        prompt_sha256=PROMPT_SHA256,
        metrics=metrics,
        gates=gates,
        gate_results=gate_results,
        passed=count > 0 and all(gate_results.values()),
        confusion_matrix=confusion,
        cases=tuple(case_results),
        json_path=str(json_path),
        markdown_path=str(markdown_path),
    )
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(_markdown_report(report), encoding="utf-8", newline="\n")
    return report


def _validate_suite(suite: Any) -> None:
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise ValueError("Eval-Suite muss ein Objekt mit cases sein.")
    if not suite["cases"]:
        raise ValueError("Eval-Suite darf nicht leer sein.")
    if not isinstance(suite.get("gates"), dict):
        raise ValueError("Eval-Suite benötigt gates.")
    for name in _METRIC_NAMES:
        threshold = suite["gates"].get(name)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ValueError(f"Gate {name} muss eine Zahl sein.")
        if not 0 <= float(threshold) <= 1:
            raise ValueError(f"Gate {name} muss zwischen 0 und 1 liegen.")
    seen: set[str] = set()
    for case in suite["cases"]:
        case_id = case.get("id") if isinstance(case, dict) else None
        if not isinstance(case_id, str) or not _SAFE_CASE_ID.fullmatch(case_id):
            raise ValueError(f"Unzulässige Eval-Fall-ID: {case_id!r}")
        if case_id in seen:
            raise ValueError(f"Doppelte Eval-Fall-ID: {case_id}")
        seen.add(case_id)
        if case.get("expected_result") not in RESULTS:
            raise ValueError(f"Unzulässiges erwartetes Ergebnis für {case_id}.")
        if not isinstance(case.get("input"), dict):
            if not isinstance(case.get("input_path"), str) or not case["input_path"]:
                raise ValueError(f"{case_id} benötigt input oder input_path.")
        else:
            if set(case["input"]) != {"vorher", "nachher", "belegte_metadaten"}:
                raise ValueError(f"Inline-Input für {case_id} ist unvollständig.")
        if not isinstance(case.get("offline_response_path"), str):
            for field in ("expected_reason", "strongest_counterargument"):
                if not isinstance(case.get(field), str) or not case[field].strip():
                    raise ValueError(f"{case_id} benötigt {field} für das Offline-Fixture.")


def _offline_analyzer(root: Path, case: dict[str, Any], tenor: dict[str, Any]) -> Analyzer:
    response_path = case.get("offline_response_path")
    if isinstance(response_path, str):
        return OfflineAnalyzer(_resolve_below(root, response_path))
    return ExpectedFixtureAnalyzer(case, tenor)


def _resolve_below(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Eval-Pfad verlässt Suite-Verzeichnis: {relative_path}") from exc
    return path


def _read_json_below(root: Path, relative_path: str) -> Any:
    return json.loads(_resolve_below(root, relative_path).read_text(encoding="utf-8"))


def _rate(cases: list[EvalCaseResult], field: str) -> float:
    return sum(bool(getattr(case, field)) for case in cases) / len(cases)


def _markdown_report(report: EvalReport) -> str:
    status = "BESTANDEN" if report.passed else "NICHT BESTANDEN"
    lines = [
        f"# Eval-Auswertung: {report.suite_name}",
        "",
        f"**Status:** {status}",
        "",
        f"- Modus: `{report.mode}`",
        f"- Modell: `{report.model}`",
        f"- Prompt-Version: `{report.prompt_version}`",
        f"- Prompt-SHA-256: `{report.prompt_sha256}`",
        f"- Erstellt: `{report.created_at}`",
        "",
        "## Qualitäts-Gates",
        "",
        "| Metrik | Ergebnis | Gate | Status |",
        "|---|---:|---:|---|",
    ]
    for name in _METRIC_NAMES:
        gate_status = "OK" if report.gate_results[name] else "FEHLER"
        lines.append(
            f"| `{name}` | {report.metrics[name]:.1%} | {report.gates[name]:.1%} | {gate_status} |"
        )
    lines.extend(
        [
            "",
            "## Fälle",
            "",
            "| Fall | Erwartet | Tatsächlich | Schema | Ergebnis | Dauer |",
            "|---|---|---|---|---|---:|",
        ]
    )
    for case in report.cases:
        lines.append(
            f"| `{case.case_id}` | `{case.expected_result}` | "
            f"`{case.actual_result or 'invalid'}` | "
            f"{'OK' if case.schema_valid else 'FEHLER'} | "
            f"{'OK' if case.passed else 'FEHLER'} | {case.duration_ms} ms |"
        )
    lines.extend(
        [
            "",
            "> Diese Auswertung misst eine juristische Vorprüfung, keine abschließende Rechtsentscheidung.",
            "> Die menschliche Freigabe muss in jeder Modellantwort null bleiben.",
            "",
        ]
    )
    return "\n".join(lines)

