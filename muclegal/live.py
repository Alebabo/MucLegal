from __future__ import annotations

import difflib
import io
import json
import re
import shutil
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit
from contextlib import nullcontext

from lxml import html as lxml_html
from pypdf import PdfReader

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
from muclegal.fetch import FetchFailure, FetchPolicy, HttpFetcher, ScreenshotCapture
from muclegal.llm import AnthropicAnalyzer, analyze_and_store
from muclegal.llm import (
    CLAUSE_PROMPT_VERSION,
    DeterministicClauseAnalyzer,
    analyze_clause_pairs_and_store,
)
from muclegal.llm.analyzer import build_model_input
from muclegal.normalize import NormalizationConfig, NormalizationError, split_clauses
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

    def run(
        self,
        url: str,
        progress: ProgressCallback | None = None,
        *,
        capture_baseline: bool = False,
        allow_protected_fallback: bool = True,
        browser_mode: bool = False,
        blocked_source_url: str | None = None,
        blocked_source_type: str | None = None,
        requested_page_screenshot: ScreenshotCapture | None = None,
    ) -> LiveWorkflowResult:
        session = nullcontext()
        if (
            capture_baseline
            and self.screenshot_capturer is not None
            and hasattr(self.fetcher, "capture_session")
        ):
            session = self.fetcher.capture_session(self.store / "capture-runs")
        with session:
            return self._run_impl(
                url,
                progress,
                capture_baseline=capture_baseline,
                allow_protected_fallback=allow_protected_fallback,
                browser_mode=browser_mode,
                blocked_source_url=blocked_source_url,
                blocked_source_type=blocked_source_type,
                requested_page_screenshot=requested_page_screenshot,
            )

    def _run_impl(
        self,
        url: str,
        progress: ProgressCallback | None = None,
        *,
        capture_baseline: bool = False,
        allow_protected_fallback: bool = True,
        browser_mode: bool = False,
        blocked_source_url: str | None = None,
        blocked_source_type: str | None = None,
        requested_page_screenshot: ScreenshotCapture | None = None,
    ) -> LiveWorkflowResult:
        progress = progress or (lambda _step, _message: None)
        protection_type = blocked_source_type
        requested_url = blocked_source_url or url
        progress("fetch", "Öffentliche Webseite und robots.txt werden geprüft und abgerufen.")
        protection_notice: str | None = None
        try:
            outcome = check_url(url, self.config, self.repository, self.fetcher)
        except NormalizationError:
            if not (capture_baseline and browser_mode):
                raise
            progress(
                "browser",
                "Der direkte Abruf enthielt nur eine JavaScript-Hülle; die öffentliche Seite wird einmalig im Browser gerendert.",
            )
            try:
                rendered = self.fetcher.fetch_in_browser(url)
            except FetchFailure as exc:
                if allow_protected_fallback and exc.code == "protected_or_login_page":
                    protection_type = str(exc).removeprefix("Abruf abgebrochen: ")
                    return self._try_public_legal_subpages(
                        url,
                        protection_type,
                        progress,
                        browser_mode=True,
                        blocked_source_url=blocked_source_url or url,
                        blocked_source_type=blocked_source_type or protection_type,
                    )
                raise
            outcome = check_url(
                url,
                self.config,
                self.repository,
                self.fetcher,
                fetched=rendered,
            )
        except FetchFailure as exc:
            if (
                capture_baseline
                and exc.code == "protected_or_login_page"
            ):
                protection_type = str(exc).removeprefix("Abruf abgebrochen: ")
                blocked_source_url = blocked_source_url or url
                blocked_source_type = blocked_source_type or protection_type
                if browser_mode:
                    progress(
                        "browser",
                        "Seitenschutz erkannt: Der Überprüfungsmodus wird automatisch aktiviert und die öffentliche Seite einmalig in einem echten Browser mit JavaScript geladen.",
                    )
                    try:
                        rendered = self.fetcher.fetch_in_browser(url)
                        outcome = check_url(
                            url,
                            self.config,
                            self.repository,
                            self.fetcher,
                            fetched=rendered,
                        )
                        protection_notice = (
                            f"SEITENSCHUTZ ERKANNT: {protection_type} "
                            "Die Seite konnte im aktivierten Überprüfungsmodus browsergestützt erfasst werden."
                        )
                    except (FetchFailure, ValueError):
                        if allow_protected_fallback:
                            return self._try_public_legal_subpages(
                                url, protection_type, progress, browser_mode=True,
                                blocked_source_url=blocked_source_url,
                                blocked_source_type=blocked_source_type,
                            )
                        raise
                elif allow_protected_fallback:
                    return self._try_public_legal_subpages(
                        url, protection_type, progress, browser_mode=False,
                        blocked_source_url=blocked_source_url,
                        blocked_source_type=blocked_source_type,
                    )
                else:
                    raise
            else:
                raise
        progress("normalize", "Der Seiteninhalt wurde konservativ normalisiert und gehasht.")
        snapshot = self.repository.snapshot_artifacts(outcome.snapshot_id)
        progress("legal_pages", "Die Seite wird nach AGB und Datenschutzerklärung durchsucht.")
        legal_pages_path = _discover_legal_pages(
            snapshot.raw_html_path,
            outcome.url,
            Path(snapshot.raw_html_path).parent / "legal-pages.json",
        )
        screenshot: ScreenshotCapture | None = None
        screenshot_error: str | None = None
        legal_page_screenshots: dict[str, ScreenshotCapture] = {}
        legal_screenshot_statuses: dict[str, dict[str, str]] = {}

        def capture_primary_screenshot() -> None:
            nonlocal screenshot, screenshot_error
            if self.screenshot_capturer is None:
                return
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

        if capture_baseline and self.screenshot_capturer is not None:
            if blocked_source_url is None:
                legal_page_screenshots, legal_screenshot_statuses = self._capture_legal_screenshots(
                    legal_pages_path,
                    Path(snapshot.raw_html_path).parent,
                    progress,
                    primary_url=outcome.url,
                    primary_screenshot=None,
                )
                capture_primary_screenshot()
            else:
                capture_primary_screenshot()
                legal_page_screenshots, legal_screenshot_statuses = self._capture_legal_screenshots(
                    legal_pages_path,
                    Path(snapshot.raw_html_path).parent,
                    progress,
                    primary_url=outcome.url,
                    primary_screenshot=screenshot,
                )
        else:
            capture_primary_screenshot()
        progress("compare", "Der normalisierte Seitenstand wird mit der Baseline verglichen.")
        if capture_baseline:
            result = self._capture_baseline_evidence(
                outcome=outcome,
                snapshot=snapshot,
                screenshot=screenshot,
                screenshot_error=screenshot_error,
                legal_pages_path=legal_pages_path,
                progress=progress,
                browser_mode_used=outcome.fetch_mode == "browser_review",
                requested_url=blocked_source_url or url,
                protection_type=blocked_source_type,
                requested_page_screenshot=requested_page_screenshot,
                legal_page_screenshots=legal_page_screenshots,
                legal_screenshot_statuses=legal_screenshot_statuses,
            )
            if protection_notice:
                return LiveWorkflowResult(
                    result.status,
                    protection_notice,
                    result.case_path,
                    result.step_states,
                )
            return result
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
            "legal_pages": legal_pages_path,
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

        role_captures = {
            "main": screenshot,
            "requested": requested_page_screenshot,
            "agb": (legal_page_screenshots or {}).get("agb_screenshot"),
            "privacy": (legal_page_screenshots or {}).get("privacy_screenshot"),
        }
        capture_index_entries: list[dict[str, Any]] = []
        capture_galleries: dict[str, dict[str, Any]] = {}
        copied_directories: dict[str, str] = {}
        metric_documents: list[dict[str, Any]] = []
        for role, capture in role_captures.items():
            if capture is None or not getattr(capture, "artifact_directory", None):
                continue
            source_root = Path(capture.artifact_directory).resolve()
            source_key = str(source_root)
            effective_role = copied_directories.get(source_key, role)
            if source_key not in copied_directories:
                role_root = artifacts_dir / "roles" / role
                shutil.copytree(source_root, role_root)
                copied_directories[source_key] = role
                for path in sorted(role_root.rglob("*")):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(bundle).as_posix()
                    label = f"capture_{role}_{path.relative_to(role_root).as_posix()}"
                    bundled_artifacts[label] = path
                    capture_index_entries.append(
                        {
                            "role": role,
                            "path": relative,
                            "sha256": sha256_file(path),
                            "size_bytes": path.stat().st_size,
                            "kind": "original" if path.name != "screenshot-preview.webp" else "derived_preview",
                            "derived_from": (
                                f"artifacts/roles/{role}/screenshot-index.json"
                                if path.name == "screenshot-preview.webp" else None
                            ),
                        }
                    )
                metrics_path = role_root / "resource-metrics.json"
                if metrics_path.is_file():
                    metric_documents.append(json.loads(metrics_path.read_text(encoding="utf-8")))
            role_root = artifacts_dir / "roles" / effective_role
            screenshot_index = role_root / "screenshot-index.json"
            if screenshot_index.is_file():
                index_data = json.loads(screenshot_index.read_text(encoding="utf-8"))
                capture_galleries[role] = {
                    "source_role": effective_role,
                    "preview": f"artifacts/roles/{effective_role}/screenshot-preview.webp",
                    "index": f"artifacts/roles/{effective_role}/screenshot-index.json",
                    "mode": index_data.get("mode"),
                    "capture_completeness": index_data.get("capture_completeness"),
                    "tiles": [
                        f"artifacts/roles/{effective_role}/{item['path']}"
                        for item in index_data.get("tiles", [])
                    ],
                }

        capture_states = [
            getattr(capture, "capture_completeness", "vollstaendig_erfasst")
            for capture in role_captures.values()
            if capture is not None
        ]
        if protection_type:
            capture_completeness = "durch_seitenschutz_begrenzt"
        elif screenshot is None:
            capture_completeness = "teilweise_erfasst"
        elif "teilweise_erfasst" in capture_states or any(
            status.get("status") in {"failed", "warning"}
            for status in (legal_screenshot_statuses or {}).values()
        ):
            capture_completeness = "teilweise_erfasst"
        else:
            capture_completeness = "vollstaendig_erfasst"
        capture_index_path = artifacts_dir / "capture-index.json"
        _write_json(
            capture_index_path,
            {
                "version": 1,
                "capture_completeness": capture_completeness,
                "sources": capture_galleries,
                "artifacts": capture_index_entries,
            },
        )
        bundled_artifacts["capture_index"] = capture_index_path
        metrics_path = artifacts_dir / "capture-metrics.json"
        _write_json(
            metrics_path,
            {
                "version": 1,
                "targets": metric_documents,
                "browser_run_root": getattr(self.fetcher, "last_capture_run_root", None),
                "warc_size_bytes": {"value": "pending", "reason": "Manifestbildung folgt."},
                "zip_size_bytes": {"value": "not_available", "reason": "ZIP wird beim Download erzeugt."},
            },
        )
        bundled_artifacts["capture_metrics"] = metrics_path
        run_result_path = artifacts_dir / "run-result.json"
        _write_json(
            run_result_path,
            {
                "status": capture_completeness,
                "requested_url": requested_url or outcome.url,
                "captured_url": outcome.url,
                "protection_type": protection_type,
                "failure_phase": next(
                    (
                        document.get("failure_phase")
                        for document in metric_documents
                        if document.get("failure_phase")
                    ),
                    None,
                ),
                "available_intermediate_artifacts": [item["path"] for item in capture_index_entries],
            },
        )
        bundled_artifacts["run_result"] = run_result_path

        warnings: list[str] = []
        if screenshot_error:
            warnings.append(f"Screenshot konnte nicht erzeugt werden: {screenshot_error}")
        if screenshot is not None and getattr(screenshot, "capture_state", "page_content") == "page_content_truncated":
            warnings.append(
                getattr(screenshot, "state_reason", None)
                or "Der Hauptseiten-Screenshot wurde aus technischen Gründen gekürzt."
            )
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

        metrics_document = json.loads(metrics_path.read_text(encoding="utf-8"))
        if "warc" in bundled_artifacts and bundled_artifacts["warc"].is_file():
            metrics_document["warc_size_bytes"] = bundled_artifacts["warc"].stat().st_size
        else:
            metrics_document["warc_size_bytes"] = {
                "value": "not_available",
                "reason": warc_status,
            }
        _write_json(metrics_path, metrics_document)

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
                "screenshot_status": (
                    "captured_truncated"
                    if screenshot is not None
                    and getattr(screenshot, "capture_state", "page_content") == "page_content_truncated"
                    else ("captured" if screenshot else "failed")
                ),
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

    def _capture_legal_screenshots(
        self,
        legal_pages_path: Path,
        output_directory: Path,
        progress: ProgressCallback,
        *,
        primary_url: str,
        primary_screenshot: ScreenshotCapture | None,
    ) -> tuple[dict[str, ScreenshotCapture], dict[str, dict[str, str]]]:
        legal_pages = json.loads(legal_pages_path.read_text(encoding="utf-8"))
        capture_selections: dict[str, dict[str, str]] = legal_pages.setdefault(
            "screenshot_captures", {}
        )
        captures: dict[str, ScreenshotCapture] = {}
        statuses: dict[str, dict[str, str]] = {}
        categories = (
            ("agb", "agb_screenshot", "AGB"),
            ("datenschutz", "privacy_screenshot", "Datenschutzerklärung"),
        )
        for category, label, title in categories:
            links = legal_pages.get(category, [])
            if not links:
                statuses[label] = {
                    "status": "not_applicable",
                    "reason": f"Kein öffentlicher Link für {title} im gespeicherten HTML gefunden.",
                }
                continue
            selected_link = _select_legal_link(links, category)
            discovered_url = str(selected_link["url"])
            target_url = discovered_url
            selection = "direkter_rechtstext"
            candidate_record: dict[str, Any] = {
                "discovered_url": discovered_url,
                "captured_url": None,
                "redirect_chain": [],
                "document_type": category,
                "link_source": selected_link.get("source", "saved_html_link"),
                "http_status": None,
                "visible_characters": 0,
                "heading_count": 0,
                "clause_count": 0,
                "selection_score": None,
                "exclusion_reason": None,
            }
            try:
                legal_page = self.fetcher.fetch(discovered_url)
                content_type = next(
                    (
                        value
                        for name, value in legal_page.headers
                        if name.casefold() == "content-type"
                    ),
                    "",
                ).casefold()
                is_pdf = "application/pdf" in content_type or urlsplit(
                    legal_page.final_url
                ).path.casefold().endswith(".pdf")
                if is_pdf:
                    original_pdf = output_directory / f"{category}-original.pdf"
                    original_pdf.write_bytes(legal_page.body)
                    reader = PdfReader(io.BytesIO(legal_page.body))
                    page_texts = [page.extract_text() or "" for page in reader.pages]
                    extracted_pdf = output_directory / f"{category}-pdf-text.txt"
                    extracted_pdf.write_text("\n\n".join(page_texts), encoding="utf-8")
                    legal_pages.setdefault("pdf_artifacts", {})[category] = {
                        "original_path": str(original_pdf),
                        "original_sha256": sha256_file(original_pdf),
                        "extracted_text_path": str(extracted_pdf),
                        "extracted_text_sha256": sha256_file(extracted_pdf),
                        "page_count": len(page_texts),
                        "pages_with_text": sum(bool(text.strip()) for text in page_texts),
                        "extracted_characters": sum(len(text) for text in page_texts),
                    }
                    target_url = legal_page.final_url
                    selection = "pdf_rechtstext_original_und_seitenweise_extrahiert"
                    visible = "\n\n".join(page_texts)
                    headings = []
                    clauses = split_clauses(visible)
                else:
                    target_url, selection = _select_legal_content_url(
                        legal_page.decoded_html,
                        legal_page.final_url,
                        category,
                    )
                    document = lxml_html.fromstring(legal_page.decoded_html)
                    visible = "\n".join(
                        line.strip() for line in document.text_content().splitlines() if line.strip()
                    )
                    headings = document.xpath("//h1 | //h2 | //h3 | //h4 | //h5 | //h6")
                    clauses = split_clauses(visible)
                candidate_record.update(
                    {
                        "captured_url": target_url,
                        "redirect_chain": list(legal_page.redirect_chain),
                        "http_status": legal_page.status_code,
                        "visible_characters": len(visible),
                        "heading_count": len(headings),
                        "clause_count": len(clauses),
                        "selection_score": (
                            len(visible) + len(headings) * 250 + len(clauses) * 100
                        ),
                        "selection_method": selection,
                    }
                )
            except Exception as exc:
                selection = f"auflösung_fehlgeschlagen:{type(exc).__name__}"
                candidate_record["exclusion_reason"] = f"{type(exc).__name__}: {exc}"
            legal_pages.setdefault("candidates", []).append(candidate_record)
            capture_selections[category] = {
                "discovered_url": discovered_url,
                "captured_url": target_url,
                "selection": selection,
            }
            if target_url != discovered_url:
                progress(
                    "legal_pages",
                    f"{title}-Übersicht erkannt; die konkrete Klauselseite wird geöffnet.",
                )
            else:
                progress("legal_pages", f"{title} wird für einen eigenen Screenshot geöffnet.")
            try:
                if primary_screenshot is not None and _same_document_url(target_url, primary_url):
                    capture = primary_screenshot
                else:
                    capture = self.screenshot_capturer(
                        target_url,
                        output_directory / f"{label}.png",
                    )
                quality_warning = _legal_capture_warning(category, selection, capture)
                if quality_warning:
                    try:
                        capture = replace(
                            capture,
                            capture_state="page_content_truncated",
                            state_reason=quality_warning,
                            capture_completeness="teilweise_erfasst",
                        )
                    except TypeError:
                        capture.capture_state = "page_content_truncated"
                        capture.state_reason = quality_warning
                        capture.capture_completeness = "teilweise_erfasst"
                captures[label] = capture
                if getattr(capture, "capture_state", "page_content") == "page_content":
                    statuses[label] = {
                        "status": "available",
                        "reason": (
                            f"Öffentlicher {title}-Klauseltext unter {target_url} aufgenommen."
                            if category == "agb"
                            else f"Öffentliche {title} unter {target_url} aufgenommen."
                        ),
                    }
                else:
                    statuses[label] = {
                        "status": "warning",
                        "reason": getattr(capture, "state_reason", None)
                        or f"{title} zeigte einen Fehlerzustand.",
                    }
            except Exception as exc:
                statuses[label] = {
                    "status": "failed",
                    "reason": f"{title}-Screenshot nicht erzeugt: {type(exc).__name__}: {exc}",
                }
        _write_json(legal_pages_path, legal_pages)
        return captures, statuses

    def _capture_baseline_evidence(
        self,
        *,
        outcome: Any,
        snapshot: Any,
        screenshot: ScreenshotCapture | None,
        screenshot_error: str | None,
        legal_pages_path: Path,
        progress: ProgressCallback,
        browser_mode_used: bool = False,
        requested_url: str | None = None,
        protection_type: str | None = None,
        requested_page_screenshot: ScreenshotCapture | None = None,
        legal_page_screenshots: dict[str, ScreenshotCapture] | None = None,
        legal_screenshot_statuses: dict[str, dict[str, str]] | None = None,
    ) -> LiveWorkflowResult:
        """Create a technical first-capture bundle without an LLM assessment."""
        captured_role = _legal_role_for_url(outcome.url) if protection_type else "main"
        if captured_role in {"agb", "privacy"} and screenshot is not None:
            role_label = "agb_screenshot" if captured_role == "agb" else "privacy_screenshot"
            legal_page_screenshots = dict(legal_page_screenshots or {})
            legal_page_screenshots.setdefault(role_label, screenshot)
            legal_screenshot_statuses = dict(legal_screenshot_statuses or {})
            legal_screenshot_statuses.setdefault(
                role_label,
                {
                    "status": "available",
                    "reason": "Öffentlich erreichbarer Rechtstext als Ersatzquelle erfasst.",
                },
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        bundle = self.store / "bundles" / f"{stamp}-{uuid.uuid4().hex[:8]}"
        artifacts_dir = bundle / "artifacts"
        capture_dir = bundle / "capture"
        artifacts_dir.mkdir(parents=True, exist_ok=False)

        progress("warc", "Die lokale WARC-/CDX-Beweisspur wird erzeugt.")
        source_artifacts = {
            "raw_html": Path(snapshot.raw_html_path),
            "response_headers": Path(snapshot.response_headers_path),
            "normalized_text": Path(snapshot.normalized_text_path),
            "legal_pages": legal_pages_path,
        }
        legal_pages_document = json.loads(legal_pages_path.read_text(encoding="utf-8"))
        for role, pdf in legal_pages_document.get("pdf_artifacts", {}).items():
            source_artifacts[f"{role}_pdf_original"] = Path(pdf["original_path"])
            source_artifacts[f"{role}_pdf_text"] = Path(pdf["extracted_text_path"])
        if outcome.previous_normalized_text_path:
            source_artifacts["previous_normalized_text"] = Path(
                outcome.previous_normalized_text_path
            )
        if outcome.diff_path:
            source_artifacts["diff"] = Path(outcome.diff_path)
        if screenshot is not None:
            source_artifacts["screenshot"] = Path(screenshot.path)
        if requested_page_screenshot is not None:
            source_artifacts["requested_page_screenshot"] = Path(
                requested_page_screenshot.path
            )
        for label, capture in (legal_page_screenshots or {}).items():
            source_artifacts[label] = Path(capture.path)
        bundled_artifacts: dict[str, Path] = {}
        for label, source in source_artifacts.items():
            destination = artifacts_dir / f"{label}{source.suffix}"
            shutil.copy2(source, destination)
            bundled_artifacts[label] = destination

        (
            capture_completeness,
            capture_galleries,
            metrics_path,
        ) = _bundle_browser_capture_artifacts(
            bundle=bundle,
            artifacts_dir=artifacts_dir,
            bundled_artifacts=bundled_artifacts,
            role_captures={
                "main": screenshot if captured_role == "main" else None,
                "requested": requested_page_screenshot,
                "agb": (
                    screenshot if captured_role == "agb"
                    else (legal_page_screenshots or {}).get("agb_screenshot")
                ),
                "privacy": (
                    screenshot if captured_role == "privacy"
                    else (legal_page_screenshots or {}).get("privacy_screenshot")
                ),
            },
            legal_screenshot_statuses=legal_screenshot_statuses or {},
            protection_type=protection_type,
            requested_url=requested_url or outcome.url,
            captured_url=outcome.url,
            browser_run_root=getattr(self.fetcher, "last_capture_run_root", None),
        )

        capture_transparency = _capture_transparency(
            outcome=outcome,
            configured_user_agent=self.fetcher.policy.user_agent,
            requested_url=requested_url or outcome.url,
            protection_type=protection_type,
            browser_capture=screenshot,
        )
        transparency_path = artifacts_dir / "capture_transparency.yaml"
        _write_simple_yaml(transparency_path, capture_transparency)
        bundled_artifacts["capture_transparency"] = transparency_path

        screenshot_interactions = {
            label: list(getattr(capture, "interactions", ()) or ())
            for label, capture in {
                "screenshot": screenshot,
                "requested_page_screenshot": requested_page_screenshot,
                **(legal_page_screenshots or {}),
            }.items()
            if capture is not None
        }
        interactions_path = artifacts_dir / "screenshot_interactions.json"
        _write_json(
            interactions_path,
            {
                "policy": "nur_eindeutige_datensparsame_cookie_auswahl",
                "allowed_actions": [
                    "nur_notwendige_cookies",
                    "optionale_cookies_abgelehnt",
                    "alle_optionalen_cookies_abgelehnt",
                    "ohne_optionale_zustimmung_fortgefahren",
                ],
                "screenshots": screenshot_interactions,
            },
        )
        bundled_artifacts["screenshot_interactions"] = interactions_path

        warnings: list[str] = []
        if screenshot_error:
            warnings.append(f"Screenshot konnte nicht erzeugt werden: {screenshot_error}")
        if screenshot is not None and getattr(
            screenshot, "capture_state", "page_content"
        ) != "page_content":
            warnings.append(
                getattr(screenshot, "state_reason", None)
                or "Der Hauptseiten-Screenshot zeigt einen technisch abweichenden Zustand."
            )
        for label, status in (legal_screenshot_statuses or {}).items():
            if status.get("status") in {"failed", "warning"}:
                warnings.append(status.get("reason") or f"{label} konnte nicht aufgenommen werden.")
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
                warnings.append("WARC und primärer Snapshot enthalten unterschiedliche Antwortbytes.")
        except Exception as exc:
            warc_status = f"unvollständig: {type(exc).__name__}: {exc}"
            capture_relation = "warc_unavailable"
            warnings.append("WARC konnte nicht vollständig erzeugt oder validiert werden.")
            warc_status_path = bundle / "warc-status.json"
            _write_json(warc_status_path, {"status": "failed", "message": warc_status})
            bundled_artifacts["warc_status"] = warc_status_path

        metrics_document = json.loads(metrics_path.read_text(encoding="utf-8"))
        if "warc" in bundled_artifacts and bundled_artifacts["warc"].is_file():
            metrics_document["warc_size_bytes"] = bundled_artifacts["warc"].stat().st_size
        else:
            metrics_document["warc_size_bytes"] = {
                "value": "not_available",
                "reason": warc_status,
            }
        _write_json(metrics_path, metrics_document)

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

        assessment = {
            "ergebnis": "nicht_bewertet",
            "confidence": 0.0,
            "begruendung": "Technische Beweiserfassung ohne juristische Bewertung.",
            "tatsachenbasis": ["Aktuell abgerufener öffentlicher Seitenzustand"],
            "staerkstes_gegenargument": "Die technische Aufnahme enthält keine juristische Bewertung.",
            "unsicherheit": "Keine Kerngleichheitsprüfung in diesem BeweisLab-Lauf.",
        }
        before_text = (
            Path(outcome.previous_normalized_text_path).read_text(encoding="utf-8")[:1800]
            if outcome.previous_normalized_text_path
            else "Kein Vorherzustand – technische Erstaufnahme."
        )
        report_data = {
            "fall_id": self.tenor["fall_id"],
            "url": outcome.url,
            "erkannt_am": snapshot.fetched_at,
            "vorher": before_text,
            "nachher": Path(snapshot.normalized_text_path).read_text(encoding="utf-8")[:1800],
            "assessment": assessment,
            "legacy_assessment": assessment,
            "clause_findings": [],
            "clause_schema_valid": False,
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
                "requested_page_screenshot_status": (
                    (
                        "protected_error_state"
                        if getattr(requested_page_screenshot, "capture_state", "page_content")
                        in {
                            "site_connectivity_error",
                            "protected_http_snapshot_rendered",
                            "protected_http_snapshot_visualized",
                        }
                        else "captured"
                    )
                    if requested_page_screenshot else "not_applicable"
                ),
                "requested_page_screenshot_sha256": (
                    requested_page_screenshot.sha256 if requested_page_screenshot else None
                ),
                "requested_page_screenshot_reason": (
                    getattr(requested_page_screenshot, "state_reason", None)
                    if requested_page_screenshot else None
                ),
                "agb_screenshot_sha256": (
                    legal_page_screenshots["agb_screenshot"].sha256
                    if legal_page_screenshots and "agb_screenshot" in legal_page_screenshots
                    else None
                ),
                "privacy_screenshot_sha256": (
                    legal_page_screenshots["privacy_screenshot"].sha256
                    if legal_page_screenshots and "privacy_screenshot" in legal_page_screenshots
                    else None
                ),
            },
        }
        report_path = Path(self.report_builder(report_data, bundle / "pruefbericht.pdf"))
        case_record = {
            **report_data,
            "tenor": self.tenor,
            "capture_mode": "browser_review" if browser_mode_used else "technical_evidence",
            "capture_completeness": capture_completeness,
            "capture_galleries": capture_galleries,
            "capture_method_note": (
                "Öffentlicher Seitenzustand mit Chromium und ausgeführtem JavaScript erfasst; "
                "ausschließlich eindeutig datensparsame Cookie-Auswahl vor Screenshots; "
                "kein CAPTCHA-Lösen und keine Stealth-Technik."
                if browser_mode_used
                else "Konservativer direkter HTTP-Abruf; Screenshots dürfen ausschließlich "
                "eindeutig datensparsame Cookie-Auswahlen verwenden."
            ),
            "requested_url": requested_url or outcome.url,
            "blocked_url": requested_url if protection_type else None,
            "protection_type": protection_type,
            "captured_url": outcome.url,
            "capture_transparency": capture_transparency,
            "analysis_mode": "capture_only",
            "schema_valid": True,
            "snapshot_sha256": snapshot.normalized_sha256,
            "previous_snapshot_sha256": outcome.previous_sha256,
            "freigabe_durch_mensch": None,
            "warnings": warnings,
            "artifact_statuses": {
                **(legal_screenshot_statuses or {}),
                **({
                    "screenshot": {
                        "status": "warning",
                        "reason": getattr(screenshot, "state_reason", None)
                        or "Der Hauptseiten-Screenshot wurde aus technischen Gründen gekürzt.",
                    }
                } if screenshot is not None
                    and getattr(screenshot, "capture_state", "page_content") != "page_content"
                    else {}),
            },
            "not_applicable_artifacts": [
                *([] if outcome.previous_normalized_text_path else ["previous_normalized_text"]),
                *([] if outcome.diff_path else ["diff"]),
                "model_input", "model_output", "clause_model_input", "clause_model_output",
            ],
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
        message = "Technische Beweiserfassung abgeschlossen."
        if warnings:
            message = "Beweiserfassung abgeschlossen; einzelne Beweiselemente sind offen."
        states = {step: "success" for step in PIPELINE_STEPS}
        states["anthropic"] = "skipped"
        if screenshot_error:
            states["screenshot"] = "warning"
        if "WARC konnte nicht vollständig erzeugt oder validiert werden." in warnings:
            states["warc"] = "warning"
        if timestamp.status != "verified":
            states["timestamp"] = "warning"
        return LiveWorkflowResult(status, message, str(self.latest_case_path), states)

    def _try_public_legal_subpages(
        self,
        protected_url: str,
        protection_type: str,
        progress: ProgressCallback,
        browser_mode: bool,
        blocked_source_url: str,
        blocked_source_type: str,
    ) -> LiveWorkflowResult:
        progress(
            "legal_pages",
            f"Seitenschutz erkannt ({protection_type}) Direkt öffentliche AGB- und Datenschutzseiten werden einzeln geprüft.",
        )
        protected_screenshot: ScreenshotCapture | None = None
        if self.screenshot_capturer is not None:
            progress(
                "screenshot",
                "Der sichtbare Zustand der eingegebenen Hauptseite wird getrennt festgehalten.",
            )
            protected_path = (
                self.store
                / "protected-captures"
                / uuid.uuid4().hex
                / "requested-page.png"
            )
            try:
                protected_screenshot = self.screenshot_capturer(
                    protected_url, protected_path
                )
            except Exception as exc:
                progress(
                    "screenshot",
                    f"Die eingegebene Hauptseite konnte nicht fotografiert werden: {type(exc).__name__}: {exc}",
                )
        failures: list[str] = []
        candidates = _legal_subpage_candidates(protected_url)
        progress(
            "legal_pages",
            f"{len(candidates)} bekannte AGB- und Datenschutzpfade werden nacheinander geprüft.",
        )
        for candidate in candidates:
            def candidate_progress(step: str, message: str) -> None:
                if step not in {"fetch", "browser", "legal_pages"}:
                    progress(step, message)
            try:
                result = self.run(
                    candidate,
                    candidate_progress,
                    capture_baseline=True,
                    allow_protected_fallback=False,
                    browser_mode=browser_mode,
                    blocked_source_url=blocked_source_url,
                    blocked_source_type=blocked_source_type,
                    requested_page_screenshot=protected_screenshot,
                )
                progress("legal_pages", f"Öffentliche Rechtstext-Unterseite erfasst: {candidate}")
                return LiveWorkflowResult(
                    result.status,
                    "SEITENSCHUTZ ERKANNT: Die Hauptseite war geschützt. "
                    f"{protection_type} "
                    f"Als Ersatz wurde diese öffentlich erreichbare Rechtstext-Unterseite erfasst: {candidate}",
                    result.case_path,
                    result.step_states,
                )
            except Exception as exc:
                failures.append(f"{candidate}: {type(exc).__name__}: {exc}")
        return self._capture_protection_evidence(
            protected_url=protected_url,
            protection_type=protection_type,
            browser_mode=browser_mode,
            protected_screenshot=protected_screenshot,
            candidates=candidates,
            failures=failures,
            progress=progress,
        )

    def _capture_protection_evidence(
        self,
        *,
        protected_url: str,
        protection_type: str,
        browser_mode: bool,
        protected_screenshot: ScreenshotCapture | None,
        candidates: list[str],
        failures: list[str],
        progress: ProgressCallback,
    ) -> LiveWorkflowResult:
        """Create a reviewable package even when every public target remains protected."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        bundle = self.store / "bundles" / f"{stamp}-{uuid.uuid4().hex[:8]}"
        artifacts_dir = bundle / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=False)

        protection_path = artifacts_dir / "protection_report.json"
        _write_json(
            protection_path,
            {
                "requested_url": protected_url,
                "protection_type": protection_type,
                "verification_mode": browser_mode,
                "result": "manual_capture_required",
                "checked_subpages": candidates,
                "failed_subpages": failures,
            },
        )
        bundled_artifacts: dict[str, Path] = {"protection_report": protection_path}
        if protected_screenshot is not None:
            screenshot_path = artifacts_dir / "requested_page_screenshot.png"
            shutil.copy2(protected_screenshot.path, screenshot_path)
            bundled_artifacts["requested_page_screenshot"] = screenshot_path

        (
            capture_completeness,
            capture_galleries,
            capture_metrics_path,
        ) = _bundle_browser_capture_artifacts(
            bundle=bundle,
            artifacts_dir=artifacts_dir,
            bundled_artifacts=bundled_artifacts,
            role_captures={"main": None, "requested": protected_screenshot},
            legal_screenshot_statuses={},
            protection_type=protection_type,
            requested_url=protected_url,
            captured_url=protected_url,
            browser_run_root=getattr(self.fetcher, "last_capture_run_root", None),
        )
        protection_metrics = json.loads(capture_metrics_path.read_text(encoding="utf-8"))
        protection_metrics["warc_size_bytes"] = {
            "value": "not_available",
            "reason": "Kein dahinterliegender Seiteninhalt für WARC erfasst.",
        }
        _write_json(capture_metrics_path, protection_metrics)

        transparency_path = artifacts_dir / "capture_transparency.yaml"
        _write_simple_yaml(
            transparency_path,
            {
                "erfassungsmodus": (
                    "browsergestuetzter_schutzbefund" if browser_mode
                    else "direkter_http_schutzbefund"
                ),
                "user_agent": self.fetcher.policy.user_agent,
                "navigator.webdriver": None,
                "automation_flags": [],
                "proxy": "keiner",
                "context": "frisch_pro_screenshot",
                "storage_state": "keiner",
                "profilverzeichnis": "keines",
                "robots_txt": "geprueft_abruf_erlaubt",
                "angefragte_url": protected_url,
                "seitenschutz": protection_type,
                "tatsaechlich_erfasste_url": None,
                "gepruefte_rechtstext_unterseiten": len(candidates),
                "herkunft": "eigene_infrastruktur_ohne_proxy",
            },
        )
        bundled_artifacts["capture_transparency"] = transparency_path

        interactions_path = artifacts_dir / "screenshot_interactions.json"
        _write_json(
            interactions_path,
            {
                "policy": "nur_eindeutige_datensparsame_cookie_auswahl",
                "screenshots": {
                    "requested_page_screenshot": list(
                        getattr(protected_screenshot, "interactions", ()) or ()
                    ) if protected_screenshot else []
                },
            },
        )
        bundled_artifacts["screenshot_interactions"] = interactions_path

        wayback = self.wayback_client.save(protected_url, bundle)
        bundled_artifacts["wayback_status"] = bundle / "wayback-status.json"
        progress("manifest", "Der Schutzbefund wird in einem Hash-Manifest gesichert.")
        manifest = create_manifest(bundled_artifacts, bundle)
        verification = verify_manifest(manifest.manifest_path)
        if not verification.valid:
            raise RuntimeError(f"Manifestprüfung fehlgeschlagen: {verification.errors}")
        progress("timestamp", "Der Schutzbefund erhält einen RFC-3161-Zeitstempelversuch.")
        timestamp = self.tsa_client.timestamp_digest(
            manifest.manifest_sha256, bundle / "timestamp"
        )

        assessment = {
            "ergebnis": "nicht_bewertet",
            "confidence": 0.0,
            "begruendung": "Seitenschutz verhinderte eine inhaltliche Erfassung.",
            "tatsachenbasis": [
                protection_type,
                f"{len(candidates)} direkte Rechtstext-Unterseiten geprüft.",
            ],
            "staerkstes_gegenargument": (
                "Der Schutzbefund belegt nicht den dahinterliegenden Seiteninhalt."
            ),
            "unsicherheit": "Manuelle Beweissicherung erforderlich.",
            "freigabe_durch_mensch": None,
        }
        evidence = {
            "warc_status": "nicht_erzeugt_wegen_seitenschutz",
            "manifest_sha256": manifest.manifest_sha256,
            "chain_head_sha256": manifest.chain_head_sha256,
            "timestamp_status": timestamp.status,
            "wayback_status": wayback.status,
            "wayback_url": wayback.url,
            "capture_relation": "protected_page_only",
            "snapshot_payload_sha256": None,
            "warc_payload_sha256": None,
            "screenshot_status": "protected_error_state" if protected_screenshot else "failed",
            "screenshot_sha256": protected_screenshot.sha256 if protected_screenshot else None,
            "screenshot_path": protected_screenshot.path if protected_screenshot else None,
            "requested_page_screenshot_status": (
                "protected_error_state" if protected_screenshot else "failed"
            ),
            "requested_page_screenshot_sha256": (
                protected_screenshot.sha256 if protected_screenshot else None
            ),
            "requested_page_screenshot_reason": (
                getattr(protected_screenshot, "state_reason", None)
                if protected_screenshot else protection_type
            ),
        }
        report_data = {
            "fall_id": self.tenor["fall_id"],
            "url": protected_url,
            "erkannt_am": datetime.now(timezone.utc).isoformat(),
            "vorher": "Kein Vorherzustand.",
            "nachher": "Inhalt wegen Seitenschutz nicht erfasst.",
            "assessment": assessment,
            "evidence": evidence,
        }
        report_path = Path(self.report_builder(report_data, bundle / "pruefbericht.pdf"))
        warnings = [
            f"SEITENSCHUTZ ERKANNT: {protection_type}",
            f"{len(failures)} Rechtstext-Unterseiten konnten nicht erfasst werden.",
        ]
        if timestamp.status != "verified":
            warnings.append("RFC-3161-Zeitstempel ist noch offen.")
        case_record = {
            **report_data,
            "tenor": self.tenor,
            "capture_mode": "protected_review",
            "capture_completeness": capture_completeness,
            "capture_galleries": capture_galleries,
            "requested_url": protected_url,
            "blocked_url": protected_url,
            "protection_type": protection_type,
            "captured_url": None,
            "analysis_mode": "capture_only",
            "schema_valid": True,
            "clause_schema_valid": False,
            "clause_findings": [],
            "snapshot_sha256": None,
            "previous_snapshot_sha256": None,
            "freigabe_durch_mensch": None,
            "warnings": warnings,
            "artifact_statuses": {
                "requested_page_screenshot": {
                    "status": "warning" if protected_screenshot else "failed",
                    "reason": (
                        getattr(protected_screenshot, "state_reason", None)
                        if protected_screenshot else "Schutzseite konnte nicht fotografiert werden."
                    ) or protection_type,
                },
                "warc": {
                    "status": "not_applicable",
                    "reason": "Kein dahinterliegender Seiteninhalt wurde abgerufen.",
                },
            },
            "not_applicable_artifacts": [
                "raw_html", "response_headers", "normalized_text", "legal_pages",
                "previous_normalized_text", "diff", "model_input", "model_output",
                "clause_model_input", "clause_model_output", "screenshot",
                "agb_screenshot", "privacy_screenshot", "warc", "cdx", "warc_status",
            ],
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
        states = {step: "skipped" for step in PIPELINE_STEPS}
        states.update({"fetch": "warning", "screenshot": "warning", "manifest": "success"})
        states["timestamp"] = "success" if timestamp.status == "verified" else "warning"
        return LiveWorkflowResult(
            "completed_with_warnings",
            f"SEITENSCHUTZ ERKANNT: {protection_type} Ein Schutzbefund mit Screenshot "
            f"und {len(failures)} geprüften Rechtstext-Unterseiten wurde gesichert. "
            "Der dahinterliegende Seiteninhalt wurde nicht erfasst; manuelle Beweissicherung erforderlich.",
            str(self.latest_case_path),
            states,
        )


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


def _capture_transparency(
    *,
    outcome: Any,
    configured_user_agent: str,
    requested_url: str,
    protection_type: str | None,
    browser_capture: ScreenshotCapture | None = None,
) -> dict[str, Any]:
    metadata = dict(outcome.browser_metadata or {})
    artifact_directory = getattr(browser_capture, "artifact_directory", None)
    if browser_capture is not None and artifact_directory:
        metadata_path = Path(artifact_directory) / "browser-metadata.json"
        if metadata_path.is_file():
            metadata.update(json.loads(metadata_path.read_text(encoding="utf-8")))
    browser_based = outcome.fetch_mode == "browser_review" or browser_capture is not None
    return {
        "erfassungsmodus": "browsergestuetzt" if browser_based else "direkter_http_abruf",
        "user_agent": metadata.get("user_agent", configured_user_agent),
        "navigator.webdriver": metadata.get("navigator_webdriver") if browser_based else None,
        "chromium_version": metadata.get("browser_version") if browser_based else None,
        "launch_args": metadata.get("launch_args", []),
        "automation_flags": metadata.get("automation_flags", []),
        "proxy": metadata.get("proxy", "keiner"),
        "context": metadata.get("context", "nicht_anwendbar"),
        "storage_state": metadata.get("storage_state", "keiner"),
        "profilverzeichnis": metadata.get("profilverzeichnis", "keines"),
        "robots_txt": metadata.get("robots_txt", "geprueft_abruf_erlaubt"),
        "angefragte_url": requested_url,
        "seitenschutz": protection_type or "keiner_erkannt",
        "tatsaechlich_erfasste_url": outcome.url,
        "browser_document_requests": metadata.get("document_request_count", 0),
        "browser_requests_gesamt": metadata.get("request_count", 0),
        "browser_abbruchphase": metadata.get("failure_phase"),
        "parallelitaet": "seriell_maximal_ein_aktiver_prueflauf",
        "herkunft": "eigene_infrastruktur_ohne_proxy",
    }


def _write_simple_yaml(path: Path, values: dict[str, Any]) -> None:
    lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, list):
            rendered = "[]" if not value else json.dumps(value, ensure_ascii=False)
        elif value is None:
            rendered = "null"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value), ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _discover_legal_pages(raw_html_path: str | Path, source_url: str, output_path: Path) -> Path:
    """Find linked legal pages in the captured HTML without following click paths."""
    document = lxml_html.fromstring(Path(raw_html_path).read_bytes())
    categories = {
        "agb": ("agb", "allgemeine geschäftsbedingungen", "terms and conditions"),
        "datenschutz": ("datenschutz", "datenschutzerklärung", "privacy policy", "privacy"),
    }
    findings: dict[str, list[dict[str, Any]]] = {key: [] for key in categories}
    seen: dict[str, set[str]] = {key: set() for key in categories}
    source_host = (urlsplit(source_url).hostname or "").lower()
    for anchor in document.xpath("//a[@href]"):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        label = " ".join(anchor.text_content().split()).strip()
        absolute_url = urljoin(source_url, href)
        parsed = urlsplit(absolute_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        haystack = f"{label} {parsed.path}".casefold()
        for category, needles in categories.items():
            if any(needle in haystack for needle in needles) and absolute_url not in seen[category]:
                seen[category].add(absolute_url)
                findings[category].append({
                    "label": label or absolute_url,
                    "url": absolute_url,
                    "same_domain": (parsed.hostname or "").lower() == source_host,
                    "document_type": category,
                    "source": "anchor_in_saved_html",
                })
    payload = {
        "source_url": source_url,
        "method": "Linksuche im gespeicherten HTML; keine Klickpfade aufgerufen.",
        "agb": findings["agb"][:20],
        "datenschutz": findings["datenschutz"][:20],
    }
    _write_json(output_path, payload)
    return output_path


def _legal_subpage_candidates(source_url: str) -> list[str]:
    parsed = urlsplit(source_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    segments = [segment for segment in parsed.path.split("/") if segment]
    locale = segments[0] if segments and len(segments[0]) in {2, 5} else None
    paths: list[str] = []
    if locale:
        paths.extend([
            f"/{locale}/terms-of-use.html",
            f"/{locale}/privacy-policy.html",
            f"/{locale}/privacy-and-cookie-policy.html",
            f"/{locale}/agb",
            f"/{locale}/datenschutz",
        ])
        if locale == "de":
            paths.append("/de-en/privacy-policy.html")
    paths.extend([
        "/terms-of-use.html", "/terms", "/agb", "/agb.html",
        "/privacy-policy.html", "/privacy-and-cookie-policy.html", "/datenschutz",
        "/policies/terms-of-service", "/policies/privacy-policy",
    ])
    return list(dict.fromkeys(urljoin(origin, path) for path in paths))


def _same_document_url(left: str, right: str) -> bool:
    def normalized(value: str) -> tuple[str, str, str, str]:
        parsed = urlsplit(value)
        path = parsed.path.rstrip("/") or "/"
        return parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query

    return normalized(left) == normalized(right)


def _legal_role_for_url(url: str) -> str:
    path = urlsplit(url).path.casefold()
    if any(marker in path for marker in ("privacy", "datenschutz")):
        return "privacy"
    if any(marker in path for marker in ("terms", "agb", "geschaeftsbeding")):
        return "agb"
    return "main"


def _legal_capture_warning(
    category: str, selection: str, capture: ScreenshotCapture
) -> str | None:
    if "übersicht_ohne_auflösbare_klauselseite" in selection:
        return "Die gefundene Rechtstextübersicht ließ sich nicht auf eine konkrete Klauselseite auflösen."
    artifact_directory = getattr(capture, "artifact_directory", None)
    if not artifact_directory:
        return None
    normalized = Path(artifact_directory) / "normalized-text.txt"
    clauses = Path(artifact_directory) / "clauses.json"
    if not normalized.is_file() or not clauses.is_file():
        return "Gerenderter Rechtstext und Klauseldatei sind nicht vollständig vorhanden."
    characters = len(normalized.read_text(encoding="utf-8"))
    clause_count = len(json.loads(clauses.read_text(encoding="utf-8")).get("clauses", []))
    minimum_characters = 1_500 if category == "datenschutz" else 1_000
    if characters < minimum_characters or clause_count < 5:
        return (
            f"Gerenderter Rechtstext ist mit {characters} Zeichen und {clause_count} Klauseln "
            "zu dünn für einen vollständigen Klauselbeweis."
        )
    return None


def _select_legal_link(links: list[dict[str, Any]], category: str) -> dict[str, Any]:
    def score(item: dict[str, Any]) -> tuple[int, int]:
        label = str(item.get("label", "")).lower()
        url = str(item.get("url", "")).lower()
        value = 20 if item.get("same_domain") else 0
        if category == "agb":
            if label.strip() == "agb":
                value += 35
            if "allgemeine geschäftsbedingungen" in label:
                value += 30
            if "/terms" in url or "/agb" in url:
                value += 12
        else:
            if label.strip() in {"datenschutz", "datenschutzerklärung", "datenschutzhinweise"}:
                value += 35
            if "datenschutzerklärung" in label:
                value += 28
            if " shop" in f" {label}" or url.rstrip("/").endswith("/shop"):
                value += 22
            if "datenschutz" in label or "privacy" in url:
                value += 12
            if any(term in label or term in url for term in (
                "mymediamarkt", "terminvereinbarung", "newsletter", "gewinnspiel", "karriere"
            )):
                value -= 25
        return value, -len(url)

    return max(links, key=score)


def _select_legal_content_url(html: str, source_url: str, category: str) -> tuple[str, str]:
    """Resolve a legal hub to a same-site page containing the actual legal text."""
    try:
        document = lxml_html.fromstring(html)
    except (ValueError, TypeError):
        return source_url, "nicht_lesbare_rechtstextseite"
    if _contains_legal_body(document, category):
        return source_url, "direkter_rechtstext"

    source = urlsplit(source_url)
    source_host = (source.hostname or "").casefold()
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for anchor in document.xpath("//main//a[@href] | //article//a[@href]"):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute_url = urljoin(source_url, href)
        parsed = urlsplit(absolute_url)
        if (
            parsed.scheme not in {"http", "https"}
            or (parsed.hostname or "").casefold() != source_host
            or _same_document_url(absolute_url, source_url)
            or absolute_url in seen
        ):
            continue
        seen.add(absolute_url)
        label = " ".join(anchor.text_content().split()).casefold()
        haystack = f"{label} {parsed.path.casefold()}"
        score = 0
        if category == "agb":
            if not any(term in haystack for term in (
                "agb", "geschäftsbeding", "geschaeftsbeding", "lieferbeding",
                "zahlungsbeding", "terms-condition", "terms_condition",
            )):
                continue
            if "online-shop" in haystack or "online shop" in haystack:
                score += 90
            if "allgemeine liefer" in haystack:
                score += 70
            if "geschäftsbeding" in haystack or "geschaeftsbeding" in haystack:
                score += 45
            if "lieferbeding" in haystack or "zahlungsbeding" in haystack:
                score += 35
            if parsed.path.casefold().endswith(".pdf"):
                score -= 20
        else:
            if not any(term in haystack for term in (
                "datenschutz", "privacy", "datenschutzhinweis", "datenverarbeitung",
            )):
                continue
            if "datenschutzerklärung" in label or "datenschutzerklaerung" in label:
                score += 80
            if "privacy policy" in label:
                score += 70
            if parsed.path.casefold().endswith(".pdf"):
                score -= 20
        score += 20 if label else 0
        candidates.append((score, absolute_url))
    if not candidates:
        return source_url, "übersicht_ohne_auflösbare_klauselseite"
    candidates.sort(key=lambda item: (item[0], -len(item[1])), reverse=True)
    return candidates[0][1], "klauselseite_aus_rechtstextübersicht"


def _contains_legal_body(document: Any, category: str) -> bool:
    roots = document.xpath("//main | //article")
    root = max(roots, key=lambda node: len(" ".join(node.text_content().split())), default=document)
    lines = [" ".join(value.split()) for value in root.text_content().splitlines()]
    lines = [value for value in lines if value]
    text = "\n".join(lines)
    folded = text.casefold()
    if category == "agb":
        numbered_clauses = sum(
            bool(re.match(r"^\d+(?:\.\d+)*\.?\s+[a-zäöüß]", line.casefold()))
            for line in lines
        )
        legal_terms = sum(
            term in folded
            for term in ("geltung", "vertrag", "zahlung", "liefer", "haftung", "widerruf")
        )
        return numbered_clauses >= 2 and legal_terms >= 2 and len(text) >= 1_000
    privacy_terms = sum(
        term in folded
        for term in (
            "personenbezogene daten", "datenverarbeitung", "verantwortliche",
            "rechtsgrundlage", "speicherdauer", "betroffenenrechte",
        )
    )
    return privacy_terms >= 2 and len(text) >= 1_500


def _bundle_browser_capture_artifacts(
    *,
    bundle: Path,
    artifacts_dir: Path,
    bundled_artifacts: dict[str, Path],
    role_captures: dict[str, ScreenshotCapture | None],
    legal_screenshot_statuses: dict[str, dict[str, str]],
    protection_type: str | None,
    requested_url: str,
    captured_url: str,
    browser_run_root: str | None,
) -> tuple[str, dict[str, dict[str, Any]], Path]:
    entries: list[dict[str, Any]] = []
    galleries: dict[str, dict[str, Any]] = {}
    metric_documents: list[dict[str, Any]] = []
    copied_directories: dict[str, str] = {}
    for role, capture in role_captures.items():
        if capture is None or not getattr(capture, "artifact_directory", None):
            continue
        source_root = Path(capture.artifact_directory).resolve()
        source_key = str(source_root)
        effective_role = copied_directories.get(source_key, role)
        if source_key not in copied_directories:
            role_root = artifacts_dir / "roles" / role
            shutil.copytree(source_root, role_root)
            copied_directories[source_key] = role
            for path in sorted(role_root.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(bundle).as_posix()
                relative_in_role = path.relative_to(role_root).as_posix()
                label = f"capture_{role}_{relative_in_role}"
                bundled_artifacts[label] = path
                entries.append(
                    {
                        "role": role,
                        "path": relative,
                        "sha256": sha256_file(path),
                        "size_bytes": path.stat().st_size,
                        "kind": (
                            "derived_preview"
                            if path.name == "screenshot-preview.webp" else "original"
                        ),
                        "derived_from": (
                            f"artifacts/roles/{role}/screenshot-index.json"
                            if path.name == "screenshot-preview.webp" else None
                        ),
                    }
                )
            resource_metrics = role_root / "resource-metrics.json"
            if resource_metrics.is_file():
                metric_documents.append(
                    json.loads(resource_metrics.read_text(encoding="utf-8"))
                )
        role_root = artifacts_dir / "roles" / effective_role
        screenshot_index = role_root / "screenshot-index.json"
        if screenshot_index.is_file():
            index_data = json.loads(screenshot_index.read_text(encoding="utf-8"))
            galleries[role] = {
                "source_role": effective_role,
                "preview": f"artifacts/roles/{effective_role}/screenshot-preview.webp",
                "index": f"artifacts/roles/{effective_role}/screenshot-index.json",
                "mode": index_data.get("mode"),
                "capture_completeness": index_data.get("capture_completeness"),
                "tiles": [
                    f"artifacts/roles/{effective_role}/{item['path']}"
                    for item in index_data.get("tiles", [])
                ],
                "originals": (
                    [f"artifacts/roles/{effective_role}/screenshot-full-page.png"]
                    if index_data.get("full_page_attempt", {}).get("path")
                    else []
                ),
            }
    states = [
        getattr(capture, "capture_completeness", "vollstaendig_erfasst")
        for capture in role_captures.values()
        if capture is not None
    ]
    if protection_type:
        completeness = "durch_seitenschutz_begrenzt"
    elif role_captures.get("main") is None:
        completeness = "teilweise_erfasst"
    elif "teilweise_erfasst" in states or any(
        status.get("status") in {"failed", "warning"}
        for status in legal_screenshot_statuses.values()
    ):
        completeness = "teilweise_erfasst"
    else:
        completeness = "vollstaendig_erfasst"
    capture_index = artifacts_dir / "capture-index.json"
    _write_json(
        capture_index,
        {
            "version": 1,
            "capture_completeness": completeness,
            "sources": galleries,
            "artifacts": entries,
        },
    )
    bundled_artifacts["capture_index"] = capture_index
    metrics_path = artifacts_dir / "capture-metrics.json"
    _write_json(
        metrics_path,
        {
            "version": 1,
            "targets": metric_documents,
            "browser_run_root": browser_run_root,
            "warc_size_bytes": {"value": "pending", "reason": "WARC folgt."},
            "zip_size_bytes": {
                "value": "not_available",
                "reason": "ZIP wird erst beim lokalen Download erzeugt.",
            },
        },
    )
    bundled_artifacts["capture_metrics"] = metrics_path
    run_result = artifacts_dir / "run-result.json"
    _write_json(
        run_result,
        {
            "status": completeness,
            "requested_url": requested_url,
            "captured_url": captured_url,
            "protection_type": protection_type,
            "failure_phase": next(
                (
                    document.get("failure_phase")
                    for document in metric_documents
                    if document.get("failure_phase")
                ),
                None,
            ),
            "available_intermediate_artifacts": [item["path"] for item in entries],
        },
    )
    bundled_artifacts["run_result"] = run_result
    return completeness, galleries, metrics_path


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
