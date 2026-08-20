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
    capture_snapshot_warc,
    create_manifest,
    verify_manifest,
    sha256_file,
)
from muclegal.evidence.wayback import WaybackClient
from muclegal.llm.tenor import TenorDraft
from muclegal.fetch import FetchPolicy, HttpFetcher, ScreenshotCapture
from muclegal.llm import AnthropicAnalyzer, analyze_and_store
from muclegal.llm import (
    CLAUSE_PROMPT_VERSION,
    DeterministicClauseAnalyzer,
    analyze_clause_pairs_and_store,
)
from muclegal.llm.analyzer import build_model_input
from muclegal.normalize import NormalizationConfig, split_clauses
from muclegal.clause_diff import pair_clause_changes
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
        clause_analyzer_factory: Callable[[], Any] = DeterministicClauseAnalyzer,
        warc_capturer: Callable[..., Any] | None = None,
        tsa_client: OpenSslTsaClient | None = None,
        report_builder: Callable[[dict[str, Any], str | Path], str] = build_pdf_report,
        wayback_client: WaybackClient | None = None,
        screenshot_capturer: Callable[[str, Path], ScreenshotCapture] | None = None,
    ) -> None:
        self.store = Path(store).resolve()
        self.store.mkdir(parents=True, exist_ok=True)
        approved_tenor_path = self.store / "approved-tenor.json"
        self.tenor_path = (
            approved_tenor_path if approved_tenor_path.is_file() else Path(tenor_path).resolve()
        )
        self.tenor = json.loads(self.tenor_path.read_text(encoding="utf-8"))
        self.config = config or NormalizationConfig()
        self.repository = SnapshotRepository(self.store / "snapshots")
        self.fetcher = fetcher or HttpFetcher(
            FetchPolicy(timeout_seconds=10, max_attempts=2, require_public_network=True)
        )
        self.analyzer_factory = analyzer_factory
        self.clause_analyzer_factory = clause_analyzer_factory
        self.warc_capturer = warc_capturer
        self.tsa_client = tsa_client or OpenSslTsaClient()
        self.report_builder = report_builder
        self.wayback_client = wayback_client or WaybackClient()
        self.screenshot_capturer = screenshot_capturer

    def use_approved_tenor(self, draft: TenorDraft) -> Path:
        """Persist a human-approved draft and make it the next run's monitoring tenor."""
        tenor = draft.to_monitoring_tenor()
        path = self.store / "approved-tenor.json"
        _write_json(path, tenor)
        self.tenor = tenor
        self.tenor_path = path
        return path

    @property
    def latest_case_path(self) -> Path:
        return self.store / "latest-case.json"

    def run(self, url: str, progress: ProgressCallback | None = None) -> LiveWorkflowResult:
        progress = progress or (lambda _step, _message: None)
        progress("fetch", "Öffentliche Webseite und robots.txt werden geprüft und abgerufen.")
        outcome = check_url(url, self.config, self.repository, self.fetcher)
        progress("normalize", "Der Seiteninhalt wurde konservativ normalisiert und gehasht.")
        snapshot = self.repository.snapshot_artifacts(outcome.snapshot_id)
        screenshot: ScreenshotCapture | None = None
        screenshot_error: str | None = None
        if self.screenshot_capturer is not None:
            progress("screenshot", "Der sichtbare Seitenzustand wird als Full-Page-PNG gespeichert.")
            screenshot_path = Path(snapshot.raw_html_path).parent / "screenshot.png"
            try:
                screenshot = self.screenshot_capturer(outcome.url, screenshot_path)
                self.repository.save_snapshot_screenshot(
                    outcome.snapshot_id,
                    path=screenshot.path,
                    sha256=screenshot.sha256,
                    size_bytes=screenshot.size_bytes,
                )
            except Exception as exc:
                screenshot_error = f"{type(exc).__name__}: {exc}"
                self.repository.save_snapshot_screenshot(
                    outcome.snapshot_id, error_message=screenshot_error
                )
        progress("compare", "Der normalisierte Seitenstand wird mit der Baseline verglichen.")
        if outcome.status == "baseline_created":
            states = _terminal_steps("compare", skipped_after=True)
            if screenshot_error:
                states["screenshot"] = "warning"
            return LiveWorkflowResult(
                "baseline_created",
                "Baseline gespeichert. Erst eine spätere Änderung startet die Anthropic-Prüfung."
                + (" Der Screenshot konnte nicht erzeugt werden." if screenshot_error else ""),
                step_states=states,
            )
        if outcome.status == "unchanged":
            states = _terminal_steps("compare", skipped_after=True)
            if screenshot_error:
                states["screenshot"] = "warning"
            return LiveWorkflowResult(
                "unchanged",
                "Keine relevante Änderung erkannt; Anthropic wurde nicht aufgerufen."
                + (" Der Screenshot konnte nicht erzeugt werden." if screenshot_error else ""),
                step_states=states,
            )
        if not outcome.diff_path or not outcome.previous_normalized_text_path:
            raise RuntimeError("Änderung erkannt, aber der Vorher-/Nachher-Vergleich ist unvollständig.")

        before_text = Path(outcome.previous_normalized_text_path).read_text(encoding="utf-8")
        after_text = Path(outcome.normalized_text_path).read_text(encoding="utf-8")
        before_excerpt, after_excerpt = changed_excerpts(before_text, after_text)
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

        clause_pairs = pair_clause_changes(split_clauses(before_text), split_clauses(after_text))
        clause_analysis = analyze_clause_pairs_and_store(
            self.tenor,
            clause_pairs,
            self.clause_analyzer_factory(),
            analysis_dir,
        )
        current_records = {
            item.ordinal: item for item in self.repository.clauses_for_snapshot(outcome.snapshot_id)
        }
        previous_records = {
            item.ordinal: item
            for item in self.repository.clauses_for_snapshot(outcome.previous_snapshot_id)
        } if outcome.previous_snapshot_id is not None else {}
        persisted_findings = []
        for finding in clause_analysis.findings:
            record = self.repository.save_finding(
                snapshot_id=outcome.snapshot_id,
                classification=finding.result,
                model=clause_analysis.model,
                prompt_version=CLAUSE_PROMPT_VERSION,
                clause_id=(
                    current_records[finding.current_ordinal].id
                    if finding.current_ordinal in current_records else None
                ),
                prev_clause_id=(
                    previous_records[finding.previous_ordinal].id
                    if finding.previous_ordinal in previous_records else None
                ),
            )
            persisted_findings.append({**finding.to_dict(), "finding_id": record.id})

        progress("warc", "Die lokale WARC-/CDX-Beweisspur wird erzeugt.")
        source_artifacts = {
            "raw_html": Path(snapshot.raw_html_path),
            "response_headers": Path(snapshot.response_headers_path),
            "normalized_text": Path(snapshot.normalized_text_path),
            "previous_normalized_text": Path(outcome.previous_normalized_text_path),
            "diff": Path(outcome.diff_path),
            "model_input": Path(analysis.input_path),
            "model_output": Path(analysis.output_path),
            "clause_model_input": Path(clause_analysis.input_path),
            "clause_model_output": Path(clause_analysis.output_path),
        }
        if screenshot is not None:
            source_artifacts["screenshot"] = Path(screenshot.path)
        bundled_artifacts: dict[str, Path] = {}
        for label, source in source_artifacts.items():
            destination = artifacts_dir / f"{label}{source.suffix}"
            shutil.copy2(source, destination)
            bundled_artifacts[label] = destination

        warnings: list[str] = []
        if screenshot_error:
            warnings.append(f"Screenshot konnte nicht erzeugt werden: {screenshot_error}")
        warc_status = "valide (warcio check)"
        snapshot_payload_sha256 = sha256_file(snapshot.raw_html_path)
        warc_payload_sha256: str | None = None
        capture_relation = "separate_recapture_unverified"
        try:
            if self.warc_capturer is None:
                warc = capture_snapshot_warc(
                    outcome.url,
                    capture_dir,
                    raw_html_path=snapshot.raw_html_path,
                    response_headers_path=snapshot.response_headers_path,
                    final_url=snapshot.final_url,
                    fetched_at=snapshot.fetched_at,
                    status_code=snapshot.status_code,
                )
            else:
                warc = self.warc_capturer(outcome.url, capture_dir)
            bundled_artifacts["warc"] = Path(warc.warc_path)
            bundled_artifacts["cdx"] = Path(warc.cdx_path)
            warc_payload_sha256 = getattr(warc, "response_payload_sha256", None)
            if warc_payload_sha256 == snapshot_payload_sha256:
                capture_relation = "exact_payload"
            elif warc_payload_sha256:
                capture_relation = "separate_recapture_mismatch"
                warnings.append(
                    "WARC und primärer Snapshot enthalten unterschiedliche Antwortbytes."
                )
        except Exception as exc:
            warc_status = f"unvollständig: {type(exc).__name__}: {exc}"
            capture_relation = "warc_unavailable"
            warnings.append("WARC konnte nicht vollständig erzeugt oder validiert werden.")
            warc_status_path = bundle / "warc-status.json"
            _write_json(warc_status_path, {"status": "failed", "message": warc_status})
            bundled_artifacts["warc_status"] = warc_status_path

        wayback = self.wayback_client.save(outcome.url, bundle)
        bundled_artifacts["wayback_status"] = bundle / "wayback-status.json"
        if wayback.status == "unavailable":
            warnings.append("Wayback Save Page Now ist nicht erreichbar.")
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
            "assessment": clause_analysis.assessment.to_dict(),
            "legacy_assessment": analysis.assessment.to_dict(),
            "clause_findings": persisted_findings,
            "clause_schema_valid": clause_analysis.valid,
            "evidence": {
                "warc_status": warc_status,
                "manifest_sha256": manifest.manifest_sha256,
                "chain_head_sha256": manifest.chain_head_sha256,
                "timestamp_status": timestamp.status,
                "wayback_status": wayback.status,
                "wayback_url": wayback.url,
                "snapshot_payload_sha256": snapshot_payload_sha256,
                "warc_payload_sha256": warc_payload_sha256,
                "capture_relation": capture_relation,
                "screenshot_status": "captured" if screenshot else "failed",
                "screenshot_sha256": screenshot.sha256 if screenshot else None,
                "screenshot_path": screenshot.path if screenshot else None,
            },
        }
        report_path = Path(self.report_builder(report_data, bundle / "pruefbericht.pdf"))
        case_record = {
            **report_data,
            "tenor": self.tenor,
            "analysis_mode": clause_analysis.mode,
            "schema_valid": clause_analysis.valid,
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
        if screenshot_error:
            step_states["screenshot"] = "warning"
        return LiveWorkflowResult(status, message, str(self.latest_case_path), step_states)


PIPELINE_STEPS = (
    "fetch", "normalize", "screenshot", "compare", "anthropic", "warc", "manifest", "timestamp"
)


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
