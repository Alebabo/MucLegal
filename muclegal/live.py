from __future__ import annotations

import difflib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from muclegal.evidence import (
    OpenSslTsaClient,
    build_pdf_report,
    capture_warc,
    create_manifest,
    verify_manifest,
)
from muclegal.evidence.wayback import record_wayback_unavailable
from muclegal.fetch import FetchPolicy, HttpFetcher
from muclegal.llm import AnthropicAnalyzer, analyze_and_store
from muclegal.llm.analyzer import build_model_input
from muclegal.normalize import NormalizationConfig
from muclegal.pipeline import check_url
from muclegal.storage import SnapshotRepository


ProgressCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class LiveWorkflowResult:
    status: str
    message: str
    case_path: str | None = None
    step_states: dict[str, str] | None = None


def changed_excerpts(before: str, after: str, *, context_lines: int = 2, max_chars: int = 6000) -> tuple[str, str]:
    """Build small, deterministic before/after excerpts without sending raw HTML."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    before_parts: list[str] = []
    after_parts: list[str] = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_from = max(0, old_start - context_lines)
        old_to = min(len(before_lines), old_end + context_lines)
        new_from = max(0, new_start - context_lines)
        new_to = min(len(after_lines), new_end + context_lines)
        before_parts.append("\n".join(before_lines[old_from:old_to]))
        after_parts.append("\n".join(after_lines[new_from:new_to]))
    before_excerpt = "\n[…]\n".join(part for part in before_parts if part).strip()
    after_excerpt = "\n[…]\n".join(part for part in after_parts if part).strip()
    if not before_excerpt and not after_excerpt:
        raise ValueError("Für die Modellprüfung wurde keine geänderte Passage gefunden.")
    return _truncate_excerpt(before_excerpt, max_chars), _truncate_excerpt(after_excerpt, max_chars)


def _truncate_excerpt(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 20].rstrip() + "\n[… gekürzt …]"


class LiveMonitorWorkflow:
    def __init__(
        self,
        store: str | Path,
        tenor_path: str | Path,
        *,
        config: NormalizationConfig | None = None,
        fetcher: HttpFetcher | None = None,
        analyzer_factory: Callable[[], Any] = AnthropicAnalyzer,
        warc_capturer: Callable[..., Any] = capture_warc,
        tsa_client: OpenSslTsaClient | None = None,
        report_builder: Callable[[dict[str, Any], str | Path], str] = build_pdf_report,
    ) -> None:
        self.store = Path(store).resolve()
        self.store.mkdir(parents=True, exist_ok=True)
        self.tenor_path = Path(tenor_path).resolve()
        self.tenor = json.loads(self.tenor_path.read_text(encoding="utf-8"))
        self.config = config or NormalizationConfig()
        self.repository = SnapshotRepository(self.store / "snapshots")
        self.fetcher = fetcher or HttpFetcher(
            FetchPolicy(timeout_seconds=10, max_attempts=2, require_public_network=True)
        )
        self.analyzer_factory = analyzer_factory
        self.warc_capturer = warc_capturer
        self.tsa_client = tsa_client or OpenSslTsaClient()
        self.report_builder = report_builder

    @property
    def latest_case_path(self) -> Path:
        return self.store / "latest-case.json"

    def run(self, url: str, progress: ProgressCallback | None = None) -> LiveWorkflowResult:
        progress = progress or (lambda _step, _message: None)
        progress("fetch", "Öffentliche Webseite und robots.txt werden geprüft und abgerufen.")
        outcome = check_url(url, self.config, self.repository, self.fetcher)
        progress("normalize", "Der Seiteninhalt wurde konservativ normalisiert und gehasht.")
        progress("compare", "Der normalisierte Seitenstand wird mit der Baseline verglichen.")
        if outcome.status == "baseline_created":
            return LiveWorkflowResult(
                "baseline_created",
                "Baseline gespeichert. Erst eine spätere Änderung startet die Anthropic-Prüfung.",
                step_states=_terminal_steps("compare", skipped_after=True),
            )
        if outcome.status == "unchanged":
            return LiveWorkflowResult(
                "unchanged",
                "Keine relevante Änderung erkannt; Anthropic wurde nicht aufgerufen.",
                step_states=_terminal_steps("compare", skipped_after=True),
            )
        if not outcome.diff_path or not outcome.previous_normalized_text_path:
            raise RuntimeError("Änderung erkannt, aber der Vorher-/Nachher-Vergleich ist unvollständig.")

        before_text = Path(outcome.previous_normalized_text_path).read_text(encoding="utf-8")
        after_text = Path(outcome.normalized_text_path).read_text(encoding="utf-8")
        before_excerpt, after_excerpt = changed_excerpts(before_text, after_text)
        snapshot = self.repository.snapshot_artifacts(outcome.snapshot_id)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        bundle = self.store / "bundles" / f"{stamp}-{uuid.uuid4().hex[:8]}"
        artifacts_dir = bundle / "artifacts"
        analysis_dir = bundle / "analysis"
        capture_dir = bundle / "capture"
        artifacts_dir.mkdir(parents=True, exist_ok=False)

        progress("anthropic", "Anthropic prüft die geänderte Passage gegen den Demo-Tenor.")
        model_input = build_model_input(
            self.tenor,
            before_excerpt,
            after_excerpt,
            {
                "fall_id": self.tenor["fall_id"],
                "url": outcome.url,
                "erkannt_am": snapshot.fetched_at,
                "snapshot_sha256": snapshot.normalized_sha256,
            },
        )
        analysis = analyze_and_store(model_input, self.analyzer_factory(), analysis_dir)
        if not analysis.valid or analysis.assessment is None:
            raise RuntimeError(f"Anthropic-Antwort wurde sicher verworfen: {analysis.validation_error}")

        progress("warc", "Die lokale WARC-/CDX-Beweisspur wird erzeugt.")
        source_artifacts = {
            "raw_html": Path(snapshot.raw_html_path),
            "response_headers": Path(snapshot.response_headers_path),
            "normalized_text": Path(snapshot.normalized_text_path),
            "previous_normalized_text": Path(outcome.previous_normalized_text_path),
            "diff": Path(outcome.diff_path),
            "model_input": Path(analysis.input_path),
            "model_output": Path(analysis.output_path),
        }
        bundled_artifacts: dict[str, Path] = {}
        for label, source in source_artifacts.items():
            destination = artifacts_dir / f"{label}{source.suffix}"
            shutil.copy2(source, destination)
            bundled_artifacts[label] = destination

        warnings: list[str] = []
        warc_status = "valide (warcio check)"
        try:
            warc = self.warc_capturer(outcome.url, capture_dir)
            bundled_artifacts["warc"] = Path(warc.warc_path)
            bundled_artifacts["cdx"] = Path(warc.cdx_path)
        except Exception as exc:
            warc_status = f"unvollständig: {type(exc).__name__}: {exc}"
            warnings.append("WARC konnte nicht vollständig erzeugt oder validiert werden.")
            warc_status_path = bundle / "warc-status.json"
            _write_json(warc_status_path, {"status": "failed", "message": warc_status})
            bundled_artifacts["warc_status"] = warc_status_path

        wayback = record_wayback_unavailable(bundle)
        bundled_artifacts["wayback_status"] = bundle / "wayback-status.json"
        progress("manifest", "Das Hash-Manifest wird erzeugt und unmittelbar verifiziert.")
        manifest = create_manifest(bundled_artifacts, bundle)
        verification = verify_manifest(manifest.manifest_path)
        if not verification.valid:
            raise RuntimeError(f"Manifestprüfung fehlgeschlagen: {verification.errors}")
        progress("timestamp", "RFC-3161-Zeitstempel und technischer PDF-Bericht werden erzeugt.")
        timestamp = self.tsa_client.timestamp_digest(manifest.manifest_sha256, bundle / "timestamp")
        if timestamp.status != "verified":
            warnings.append("RFC-3161-Zeitstempel ist noch offen.")

        report_data = {
            "fall_id": self.tenor["fall_id"],
            "url": outcome.url,
            "erkannt_am": snapshot.fetched_at,
            "vorher": before_excerpt,
            "nachher": after_excerpt,
            "assessment": analysis.assessment.to_dict(),
            "evidence": {
                "warc_status": warc_status,
                "manifest_sha256": manifest.manifest_sha256,
                "chain_head_sha256": manifest.chain_head_sha256,
                "timestamp_status": timestamp.status,
                "wayback_status": wayback.status,
            },
        }
        report_path = Path(self.report_builder(report_data, bundle / "pruefbericht.pdf"))
        case_record = {
            **report_data,
            "analysis_mode": analysis.mode,
            "schema_valid": True,
            "snapshot_sha256": snapshot.normalized_sha256,
            "previous_snapshot_sha256": outcome.previous_sha256,
            "freigabe_durch_mensch": None,
            "warnings": warnings,
            "artifacts": {
                **{label: str(path) for label, path in bundled_artifacts.items()},
                "manifest": manifest.manifest_path,
                "manifest_digest": manifest.digest_path,
                "timestamp_query": timestamp.query_path,
                "timestamp_response": timestamp.response_path,
                "report": str(report_path),
            },
        }
        case_path = bundle / "case.json"
        _write_json(case_path, case_record)
        self.latest_case_path.write_text(
            case_path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
        )
        status = "completed_with_warnings" if warnings else "completed"
        message = "Prüfung und Beweispaket abgeschlossen."
        if warnings:
            message = "Prüfung abgeschlossen; einzelne Beweisschritte sind offen."
        step_states = {step: "success" for step in PIPELINE_STEPS}
        if "WARC konnte nicht vollständig erzeugt oder validiert werden." in warnings:
            step_states["warc"] = "warning"
        if timestamp.status != "verified":
            step_states["timestamp"] = "warning"
        return LiveWorkflowResult(status, message, str(self.latest_case_path), step_states)


PIPELINE_STEPS = ("fetch", "normalize", "compare", "anthropic", "warc", "manifest", "timestamp")


def _terminal_steps(last_success: str, *, skipped_after: bool = False) -> dict[str, str]:
    states: dict[str, str] = {}
    reached_last = False
    for step in PIPELINE_STEPS:
        states[step] = "skipped" if reached_last and skipped_after else "success"
        if step == last_success:
            reached_last = True
    return states


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
