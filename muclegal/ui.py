from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import parse_qs, unquote, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from muclegal.live import PIPELINE_STEPS, LiveMonitorWorkflow
from muclegal.evidence import verify_manifest
from muclegal.evidence.suitability import classify_technical_evidence
from muclegal.domain_monitor import CaseDomainMonitor
from muclegal.monitoring_cases import (
    MonitoringCaseError,
    MonitoringCaseRepository,
)
from muclegal.llm.tenor import (
    DeterministicTenorAnalyzer,
    TenorAnalyzer,
    TenorDraft,
    build_tenor_input,
    build_tenor_strategy_input,
    create_tenor_draft,
    create_tenor_proposals,
    missing_tenor_information,
    validate_tenor_draft,
)
from muclegal.llm.tenor_questions import (
    TenorQuestionAnalyzer,
    build_tenor_question_input,
    create_tenor_question,
)
from muclegal.tenor_pdf import (
    MAX_TENOR_PDF_BYTES,
    TenorPdfError,
    extract_tenor_pdf_text,
)


DECISIONS = {"freigegeben", "abgelehnt", "weitere_pruefung"}
TERMINAL_RUN_STATUSES = {
    "baseline_created", "unchanged", "completed", "completed_with_warnings", "failed", "protected",
    "referenzzustand_dokumentiert", "unveraendert_fortbestehend", "beseitigt",
    "kerngleich_wiederaufgetreten", "neuer_sachverhalt", "unsicher",
    "pruefung_unvollstaendig",
}
MAX_TEXT_PREVIEW_BYTES = 512 * 1024
CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CAPTURE_ROLE_TITLES = {
    "main": "Hauptseite",
    "requested": "Angefragte Seite",
    "agb": "AGB-Seite",
    "privacy": "Datenschutz-Seite",
    "agb_discovered": "AGB-Übersichtsseite",
    "privacy_discovered": "Datenschutz-Übersichtsseite",
}
ARTIFACT_DEFINITIONS = {
    "evidence_suitability": ("Hinweis", "Beweiseignung", "text"),
    "god_mode_authorization": ("Abruf", "Grey-Mode-Autorisierung", "text"),
    "raw_html": ("Abruf", "Roh-HTML", "text"),
    "response_headers": ("Abruf", "Header", "text"),
    "normalized_text": ("Abruf", "Normalisierter Text", "text"),
    "legal_pages": ("Abruf", "AGB & Datenschutz", "text"),
    "capture_transparency": ("Abruf", "Erfassungstransparenz", "text"),
    "screenshot_interactions": ("Abruf", "Screenshot-Interaktionen", "text"),
    "capture_index": ("Abruf", "Erfassungsindex", "text"),
    "page_artifacts_index": ("Abruf", "Seitenartefakt-Index", "text"),
    "capture_metrics": ("Abruf", "Ressourcenmessung", "text"),
    "run_result": ("Abruf", "Laufergebnis", "text"),
    "result_assessment": ("Hinweis", "Technische Ergebnisbewertung", "text"),
    "protection_report": ("Abruf", "Seitenschutz-Bericht", "text"),
    "previous_normalized_text": ("Abruf", "Vorheriger Text", "text"),
    "diff": ("Abruf", "Diff", "text"),
    "model_input": ("Analyse", "Modellinput", "text"),
    "model_output": ("Analyse", "Validierter Modelloutput", "text"),
    "clause_model_input": ("Analyse", "Klauselpaar-Inputs", "text"),
    "clause_model_output": ("Analyse", "Vierklassen-Output", "text"),
    "requested_page_screenshot": ("Beweis", "Eingegebene Hauptseite", "image"),
    "screenshot": ("Beweis", "Erfasste Seite", "image"),
    "agb_screenshot": ("Beweis", "AGB-Klauseln", "image"),
    "privacy_screenshot": ("Beweis", "Datenschutz-Screenshot", "image"),
    "warc": ("Beweis", "WARC", "binary"),
    "cdx": ("Beweis", "CDX", "binary"),
    "warc_status": ("Beweis", "WARC-Status", "text"),
    "manifest": ("Beweis", "Manifest", "text"),
    "manifest_digest": ("Beweis", "Manifest-Digest", "text"),
    "timestamp_query": ("Beweis", "TSA-Anfrage", "binary"),
    "timestamp_response": ("Beweis", "TSA-Antwort", "binary"),
    "wayback_status": ("Beweis", "Wayback-Status", "text"),
    "report": ("Bericht", "PDF-Bericht", "pdf"),
}


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    url: str | None = Field(default=None, max_length=2048)
    case_id: str | None = Field(default=None, max_length=128)
    verification_mode: bool = False
    god_mode_authorized: bool = False


class BaselineEvidenceAttachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    evidence_case_id: str = Field(min_length=1, max_length=128)


def _evidence_subject_host(value: str) -> str | None:
    """Return the website represented by a direct URL or a Wayback replay URL."""

    parsed = urlsplit(str(value or "").strip())
    host = parsed.hostname.lower().rstrip(".") if parsed.hostname else None
    if host != "web.archive.org":
        return host
    match = re.match(r"^/web/[^/]+/(.+)$", parsed.path, flags=re.IGNORECASE)
    if not match:
        return host
    embedded = unquote(match.group(1))
    if not re.match(r"^https?://", embedded, flags=re.IGNORECASE):
        return host
    original_url = urlsplit(embedded)
    if original_url.username or original_url.password or not original_url.hostname:
        return host
    return original_url.hostname.lower().rstrip(".")


class ScreenshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    filename: str = Field(min_length=1, max_length=255)
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    data_base64: str = Field(min_length=1)


class MonitoringCaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fall_id: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=253)
    source_url: str = Field(min_length=1, max_length=2048)
    violation_type: Literal["klausel", "element"]
    description: str = Field(min_length=1, max_length=4000)
    tenor_element: str = Field(min_length=1, max_length=8000)
    monitoring_target: str = Field(min_length=1, max_length=4000)
    relevant_page_types: list[str] = Field(min_length=1, max_length=20)
    target_urls: list[str] = Field(default_factory=list, max_length=20)
    nicht_umfasst: list[str] = Field(default_factory=list, max_length=20)
    clause_text: str | None = Field(default=None, max_length=12000)
    element_label: str | None = Field(default=None, max_length=1000)
    element_labels: list[str] = Field(default_factory=list, max_length=20)
    element_function: str | None = Field(default=None, max_length=2000)
    element_error: str | None = None
    allowed_subdomains: list[str] = Field(default_factory=list, max_length=20)
    screenshot: ScreenshotInput | None = None


class TenorDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fall_id: str = Field(min_length=1, max_length=200)
    schuldner: str = Field(min_length=1, max_length=500)
    fundstelle: str | None = Field(default=None, max_length=2048)
    beschreibung: str = Field(min_length=1, max_length=4000)
    rechtsgrundlagen: list[str] = Field(default_factory=list, max_length=20)
    fallgruppe: str | None = Field(default=None, min_length=1, max_length=100)
    violation_branch: Literal["A", "B", "C"] | None = None


class TenorProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fall_id: str = Field(min_length=1, max_length=200)
    schuldner: str = Field(min_length=1, max_length=500)
    fundstelle: str | None = Field(default=None, max_length=2048)
    context: str = Field(min_length=20, max_length=60000)
    fallgruppe: str = Field(min_length=1, max_length=100)
    rechtsgrundlagen: list[str] = Field(default_factory=list, max_length=20)
    violation_branch: Literal["A", "B", "C"] | None = None


class AnsweredTenorQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    topic_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=1000)
    answer_type: Literal["yes_no", "text", "slider", "single_choice"]


class TenorQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    context: str = Field(min_length=10, max_length=60000)
    fallgruppe: str = Field(min_length=1, max_length=100)
    answered_questions: list[AnsweredTenorQuestionRequest] = Field(
        default_factory=list, max_length=8
    )


class TenorArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fall_id: str = Field(min_length=1, max_length=200)
    schuldner: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=12000)
    context: str = Field(min_length=1, max_length=60000)
    strategy: Literal["complete", "precise", "neutral"]
    model: str = Field(min_length=1, max_length=200)
    reference_version: str = Field(min_length=1, max_length=500)
    source_ids: list[str] = Field(default_factory=list, max_length=50)


@dataclass
class RunState:
    run_id: str
    url: str
    status: str = "queued"
    current_step: str = "queued"
    message: str = "Prüfung wurde eingeplant."
    result_available: bool = False
    monitoring_result: dict | None = None
    steps: dict[str, str] = field(default_factory=lambda: {step: "waiting" for step in PIPELINE_STEPS})
    audit_log: list[dict[str, str]] = field(default_factory=list)
    capture_baseline: bool = False
    verification_mode: bool = False
    god_mode_authorized: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class RunCoordinator:
    def __init__(
        self,
        workflow: LiveMonitorWorkflow,
        *,
        case_repository: MonitoringCaseRepository | None = None,
        domain_monitor: CaseDomainMonitor | None = None,
    ) -> None:
        self.workflow = workflow
        self.case_repository = case_repository
        self.domain_monitor = domain_monitor
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="muclegal-run")
        self._lock = threading.Lock()
        self._runs: dict[str, RunState] = {}
        self._active_run_id: str | None = None

    def start(
        self,
        url: str | None = None,
        *,
        case_id: str | None = None,
        direct_url: bool = False,
        verification_mode: bool = False,
        god_mode_authorized: bool = False,
        synchronous: bool = False,
    ) -> RunState:
        with self._lock:
            if self._active_run_id:
                active = self._runs[self._active_run_id]
                if active.status not in TERMINAL_RUN_STATUSES:
                    raise RuntimeError("Es läuft bereits eine Prüfung.")
            if self.case_repository is not None and not direct_url:
                if not case_id or url:
                    raise ValueError("Der Monitoringlauf erwartet ausschließlich eine freigegebene case_id.")
                try:
                    monitoring_case = self.case_repository.get(case_id)
                except KeyError as exc:
                    raise ValueError("Monitoringfall nicht gefunden.") from exc
                if not monitoring_case.approved:
                    raise PermissionError("Monitoring startet erst nach menschlicher Freigabe des Falls.")
                target_url = monitoring_case.source_url
            else:
                if case_id:
                    raise ValueError("Bei einer direkten URL-Prüfung ist keine case_id zulässig.")
                if not url:
                    raise ValueError("Eine Webadresse ist erforderlich.")
                target_url = url.strip()
            run = RunState(run_id=uuid.uuid4().hex, url=target_url)
            run.capture_baseline = direct_url
            run.god_mode_authorized = bool(god_mode_authorized and direct_url)
            run.verification_mode = bool((verification_mode or run.god_mode_authorized) and direct_url)
            run.audit_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "step": "queued",
                "state": "queued",
                "message": (
                    "Grey Mode aktiviert. Die Checkbox dokumentiert die bestätigte "
                    "Berechtigungsgrundlage; der Lauf bleibt technisch getrennt gespeichert."
                    if run.god_mode_authorized else
                    "Prüflauf angelegt; der Überprüfungsmodus wird bei tatsächlichem Seitenschutz automatisch aktiviert."
                    if run.verification_mode
                    else "Prüflauf ohne automatische Browser-Überprüfung angelegt; es wurden noch keine Beweise bewertet."
                ),
            })
            run.monitoring_result = {"case_id": case_id} if case_id else None
            self._runs[run.run_id] = run
            self._active_run_id = run.run_id
            if not synchronous:
                self._executor.submit(self._execute, run.run_id)
                return RunState(**run.to_dict())
            run_id = run.run_id
        self._execute(run_id)
        completed = self.get(run_id)
        if completed is None:
            raise RuntimeError("Prüflauf konnte nicht abgeschlossen werden.")
        return completed

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            run = self._runs.get(run_id)
            return RunState(**run.to_dict()) if run else None

    def _execute(self, run_id: str) -> None:
        def progress(step: str, message: str) -> None:
            with self._lock:
                run = self._runs[run_id]
                run.status = "running"
                run.current_step = step
                run.message = message
                if step in PIPELINE_STEPS:
                    step_index = PIPELINE_STEPS.index(step)
                    for earlier in PIPELINE_STEPS[:step_index]:
                        if run.steps[earlier] in {"waiting", "active"}:
                            run.steps[earlier] = "success"
                    run.steps[step] = "active"
                run.audit_log.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "step": step,
                    "state": "active",
                    "message": message,
                })

        with self._lock:
            url = self._runs[run_id].url
            case_id = (self._runs[run_id].monitoring_result or {}).get("case_id")
            capture_baseline = self._runs[run_id].capture_baseline
            verification_mode = self._runs[run_id].verification_mode
            god_mode_authorized = self._runs[run_id].god_mode_authorized
        try:
            if case_id and self.case_repository is not None and self.domain_monitor is not None:
                domain_result = self.domain_monitor.run(self.case_repository.get(case_id), progress)
                result = None
            else:
                domain_result = None
                if capture_baseline:
                    if god_mode_authorized:
                        result = self.workflow.run(
                            url,
                            progress,
                            capture_baseline=True,
                            browser_mode=True,
                            god_mode=True,
                        )
                    elif verification_mode:
                        result = self.workflow.run(
                            url, progress, capture_baseline=True, browser_mode=True
                        )
                    else:
                        result = self.workflow.run(url, progress, capture_baseline=True)
                else:
                    result = self.workflow.run(url, progress)
            with self._lock:
                run = self._runs[run_id]
                if domain_result is not None:
                    run.status = domain_result.status
                    run.message = f"Fallbezogenes Monitoring abgeschlossen: {domain_result.status}."
                    run.monitoring_result = domain_result.to_dict()
                    run.result_available = True
                    for step in ("fetch", "normalize", "compare"):
                        run.steps[step] = "success"
                    run.steps["screenshot"] = (
                        "success" if domain_result.element_findings else "skipped"
                    )
                    run.steps["anthropic"] = "skipped"
                    run.steps["warc"] = (
                        "warning"
                        if domain_result.artifacts.get("warc_status") == "completed_with_warnings"
                        else "success"
                    )
                    run.steps["manifest"] = (
                        "success" if domain_result.artifacts.get("manifest_sha256") else "failed"
                    )
                    run.steps["timestamp"] = "skipped"
                else:
                    assert result is not None
                    run.status = result.status
                    run.message = result.message
                    run.result_available = result.case_path is not None
                    if result.step_states:
                        run.steps = dict(result.step_states)
                reached = [step for step in PIPELINE_STEPS if run.steps[step] != "skipped"]
                run.current_step = reached[-1] if reached else "compare"
                run.audit_log.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "step": run.current_step,
                    "state": run.status,
                    "message": run.message,
                })
        except Exception as exc:
            with self._lock:
                run = self._runs[run_id]
                run.status = "failed"
                if run.current_step in PIPELINE_STEPS:
                    run.steps[run.current_step] = "failed"
                run.message = str(exc)
                run.audit_log.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "step": run.current_step,
                    "state": "failed",
                    "message": run.message,
                })
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class CaseArchive:
    def __init__(self, store_root: str | Path) -> None:
        self.store_root = Path(store_root).resolve()
        self.bundle_root = (self.store_root / "bundles").resolve()
        self.god_bundle_root = (self.store_root / "god-mode-bundles").resolve()

    def list(self) -> list[dict]:
        cases: list[dict] = []
        if not self.bundle_root.is_dir():
            return cases
        for case_path in self.bundle_root.glob("*/case.json"):
            try:
                record = self._read(case_path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            cases.append(self._summary(case_path.parent.name, record))
        return sorted(cases, key=lambda item: item["erkannt_am"], reverse=True)

    def list_god_mode(self) -> list[dict]:
        cases: list[dict] = []
        if not self.god_bundle_root.is_dir():
            return cases
        for case_path in self.god_bundle_root.glob("god-*/case.json"):
            try:
                record = self._read(case_path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            cases.append(self._summary(case_path.parent.name, record))
        return sorted(cases, key=lambda item: item["erkannt_am"], reverse=True)

    def detail(self, case_id: str) -> dict:
        case_path = self._case_path(case_id)
        record = self._read(case_path)
        summary = self._summary(case_id, record)
        artifacts: list[dict] = []
        stored = record.get("artifacts", {})
        not_applicable = set(record.get("not_applicable_artifacts", []))
        if not record.get("protection_type"):
            not_applicable.add("protection_report")
        custom_statuses = record.get("artifact_statuses", {})
        for label, (group, title, kind) in ARTIFACT_DEFINITIONS.items():
            artifact = {"label": label, "title": title, "group": group, "kind": kind,
                        "available": False, "preview_available": False, "size": None,
                        "status": "not_applicable" if label in not_applicable else "failed",
                        "status_reason": (
                            "Für eine technische Erstaufnahme ohne Vorherzustand nicht anwendbar."
                            if label in not_applicable else "Nicht erzeugt oder Datei fehlt."
                        )}
            if stored.get(label):
                try:
                    path = self._safe_artifact_path(label, record, case_path.parent)
                    artifact["available"] = True
                    artifact["status"] = "available"
                    artifact["status_reason"] = "Im lokalen Beweispaket vorhanden."
                    artifact["size"] = path.stat().st_size
                    artifact["preview_available"] = kind in {"text", "pdf", "image"}
                except HTTPException:
                    pass
            custom_status = custom_statuses.get(label)
            if isinstance(custom_status, dict):
                artifact["status"] = str(custom_status.get("status") or artifact["status"])
                artifact["status_reason"] = str(
                    custom_status.get("reason") or artifact["status_reason"]
                )
            if record.get("evidence_suitability", "regulaer") != "regulaer" and artifact["available"]:
                artifact["status"] = "warning"
                artifact["status_reason"] = (
                    record.get("evidence_suitability_notice")
                    or "Dieses Artefakt ist nicht als regulärer Beweis verwendbar."
                )
            if (
                label == "requested_page_screenshot"
                and artifact["available"]
                and record.get("evidence", {}).get("requested_page_screenshot_status")
                == "protected_error_state"
            ):
                artifact["title"] = "Schutz-/Fehlerseite"
                artifact["status"] = "warning"
                artifact["status_reason"] = (
                    record.get("evidence", {}).get("requested_page_screenshot_reason")
                    or "Die Hauptseite zeigte keinen verwertbaren Seiteninhalt."
                )
            artifacts.append(artifact)
        galleries: dict[str, dict] = {}
        for role, gallery in record.get("capture_galleries", {}).items():
            if not isinstance(role, str) or not isinstance(gallery, dict):
                continue
            tiles = gallery.get("tiles", []) if isinstance(gallery.get("tiles"), list) else []
            originals = (
                gallery.get("originals", [])
                if isinstance(gallery.get("originals"), list) else []
            )
            documents = (
                gallery.get("documents", [])
                if isinstance(gallery.get("documents"), list) else []
            )
            galleries[role] = {
                "title": CAPTURE_ROLE_TITLES.get(role, role.replace("_", " ").title()),
                "mode": gallery.get("mode"),
                "capture_completeness": gallery.get("capture_completeness"),
                "tile_count": len(tiles),
                "preview_url": f"/api/v1/cases/{case_id}/capture/{role}/preview",
                "tile_urls": [
                    f"/api/v1/cases/{case_id}/capture/{role}/tiles/{index}"
                    for index in range(len(tiles))
                ],
                "original_urls": [
                    f"/api/v1/cases/{case_id}/capture/{role}/originals/{index}"
                    for index in range(len(originals))
                ],
                "document_urls": [
                    f"/api/v1/cases/{case_id}/capture/{role}/documents/{index}"
                    for index in range(len(documents))
                ],
            }
            try:
                self.capture_normalized_text_path(case_id, role)
            except HTTPException:
                galleries[role]["normalized_text_url"] = None
            else:
                galleries[role]["normalized_text_url"] = (
                    f"/api/v1/cases/{case_id}/capture/{role}/normalized-text"
                )
            try:
                self.capture_raw_html_path(case_id, role)
            except HTTPException:
                galleries[role]["raw_html_url"] = None
            else:
                galleries[role]["raw_html_url"] = (
                    f"/api/v1/cases/{case_id}/capture/{role}/raw-html"
                )
        return {**summary, "artifacts": artifacts, "capture_galleries": galleries}

    def artifact_path(self, case_id: str, label: str) -> Path:
        case_path = self._case_path(case_id)
        return self._safe_artifact_path(
            label,
            self._read(case_path),
            case_path.parent,
        )

    def capture_gallery_path(
        self, case_id: str, role: str, kind: str, index: int | None = None
    ) -> Path:
        case_path = self._case_path(case_id)
        record = self._read(case_path)
        gallery = record.get("capture_galleries", {}).get(role)
        if not isinstance(gallery, dict):
            raise HTTPException(404, "Bildserie nicht vorhanden.")
        if kind == "preview":
            relative = gallery.get("preview")
        elif kind in {"tiles", "originals", "documents"} and index is not None:
            values = gallery.get(kind)
            if not isinstance(values, list) or index < 0 or index >= len(values):
                raise HTTPException(404, "Bild der Serie nicht vorhanden.")
            relative = values[index]
        else:
            raise HTTPException(404, "Bild der Serie nicht vorhanden.")
        if not isinstance(relative, str):
            raise HTTPException(404, "Bild der Serie nicht vorhanden.")
        path = (case_path.parent / relative).resolve()
        try:
            path.relative_to(case_path.parent.resolve())
        except ValueError as exc:
            raise HTTPException(404, "Bildpfad verlässt das Beweispaket.") from exc
        if not path.is_file():
            raise HTTPException(404, "Bilddatei fehlt.")
        return path

    def capture_normalized_text_path(self, case_id: str, role: str) -> Path:
        case_path = self._case_path(case_id)
        record = self._read(case_path)
        gallery = record.get("capture_galleries", {}).get(role)
        if not isinstance(gallery, dict):
            raise HTTPException(404, "Seitentext nicht vorhanden.")
        index_relative = gallery.get("index")
        if not isinstance(index_relative, str):
            raise HTTPException(404, "Seitentext nicht vorhanden.")
        role_directory = (case_path.parent / index_relative).resolve().parent
        path = (role_directory / "normalized-text.txt").resolve()
        try:
            role_directory.relative_to(case_path.parent.resolve())
            path.relative_to(role_directory)
        except ValueError as exc:
            raise HTTPException(404, "Textpfad verlässt das Beweispaket.") from exc
        if not path.is_file():
            raise HTTPException(404, "Seitentext fehlt.")
        return path

    def capture_raw_html_path(self, case_id: str, role: str) -> Path:
        case_path = self._case_path(case_id)
        record = self._read(case_path)
        gallery = record.get("capture_galleries", {}).get(role)
        if not isinstance(gallery, dict):
            raise HTTPException(404, "Seiten-HTML nicht vorhanden.")
        relative = gallery.get("raw_html")
        if not isinstance(relative, str):
            raise HTTPException(404, "Seiten-HTML nicht vorhanden.")
        path = (case_path.parent / relative).resolve()
        try:
            path.relative_to(case_path.parent.resolve())
        except ValueError as exc:
            raise HTTPException(404, "HTML-Pfad verlässt das Beweispaket.") from exc
        if not path.is_file():
            raise HTTPException(404, "Seiten-HTML fehlt.")
        return path

    def preview(self, case_id: str, label: str) -> str:
        definition = ARTIFACT_DEFINITIONS.get(label)
        if not definition or definition[2] != "text":
            raise HTTPException(415, "Für dieses Artefakt ist keine Textvorschau erlaubt.")
        path = self.artifact_path(case_id, label)
        with path.open("rb") as handle:
            content = handle.read(MAX_TEXT_PREVIEW_BYTES + 1)
        truncated = len(content) > MAX_TEXT_PREVIEW_BYTES
        text = content[:MAX_TEXT_PREVIEW_BYTES].decode("utf-8", errors="replace")
        if truncated:
            text += "\n\n[… Vorschau nach 512 KiB gekürzt; vollständige Datei im Beweispaket …]"
        return text

    def build_download(self, case_id: str) -> Path:
        case_path = self._case_path(case_id)
        record = self._read(case_path)
        prefix = "grey-mode-beweispaket" if record.get("god_mode") else "beweispaket"
        archive_path = case_path.parent / f"{prefix}-{case_id}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for path in sorted(case_path.parent.rglob("*")):
                if not path.is_file() or path.resolve() == archive_path.resolve():
                    continue
                relative = path.relative_to(case_path.parent)
                if ".." in relative.parts:
                    continue
                package.write(path, relative.as_posix())
            for label in ARTIFACT_DEFINITIONS:
                if not record.get("artifacts", {}).get(label):
                    continue
                try:
                    path = self._safe_artifact_path(label, record, case_path.parent)
                except HTTPException:
                    continue
                package.write(path, f"artefakte/{label}{path.suffix}")
        return archive_path

    def _case_path(self, case_id: str) -> Path:
        if not CASE_ID_PATTERN.fullmatch(case_id):
            raise HTTPException(404, "Beweislauf nicht gefunden.")
        root = self.god_bundle_root if case_id.startswith("god-") else self.bundle_root
        path = (root / case_id / "case.json").resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise HTTPException(404, "Beweislauf nicht gefunden.") from exc
        if not path.is_file():
            raise HTTPException(404, "Beweislauf nicht gefunden.")
        return path

    @staticmethod
    def _read(path: Path) -> dict:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not isinstance(record.get("url"), str):
            raise ValueError("Unvollständiges case.json")
        if not isinstance(record.get("evidence"), dict) or not isinstance(record.get("assessment"), dict):
            raise ValueError("Unvollständiges case.json")
        return record

    def _safe_artifact_path(
        self,
        label: str,
        record: dict,
        bundle_root: Path,
    ) -> Path:
        if label not in ARTIFACT_DEFINITIONS:
            raise HTTPException(404, "Artefakt nicht freigegeben.")
        path_value = record.get("artifacts", {}).get(label)
        if not path_value:
            raise HTTPException(404, "Artefakt nicht vorhanden.")
        path = Path(path_value).resolve()
        try:
            path.relative_to(bundle_root.resolve())
        except ValueError as exc:
            raise HTTPException(404, "Artefakt liegt außerhalb des Beweispakets.") from exc
        if not path.is_file():
            raise HTTPException(404, "Artefaktdatei fehlt.")
        return path

    @staticmethod
    def _summary(case_id: str, record: dict) -> dict:
        evidence = record.get("evidence", {})
        assessment = record.get("assessment", {})
        result_assessment = record.get("technical_result")
        if not isinstance(result_assessment, dict):
            result_assessment = classify_technical_evidence(
                capture_completeness=str(
                    record.get("capture_completeness") or "teilweise_erfasst"
                ),
                has_screenshot=evidence.get("screenshot_status") not in {None, "failed"},
                has_normalized_text=bool(record.get("snapshot_sha256")),
                has_raw_capture=bool(record.get("artifacts", {}).get("raw_html")),
                robots_status=record.get("capture_transparency", {}).get("robots_txt"),
                failure_kind=("schutzseite" if record.get("protection_type") else None),
                god_mode=bool(record.get("god_mode")),
            ).to_dict()
        warnings = record.get("warnings", [])
        clause_findings = record.get("clause_findings", [])
        if not isinstance(clause_findings, list):
            clause_findings = []
        class_counts: dict[str, int] = {}
        for finding in clause_findings:
            if isinstance(finding, dict) and isinstance(finding.get("classification"), str):
                label = finding["classification"]
                class_counts[label] = class_counts.get(label, 0) + 1
        return {
            "case_id": case_id,
            "url": record.get("url", ""),
            "requested_url": record.get("requested_url") or record.get("url", ""),
            "captured_url": record.get("captured_url") or record.get("url", ""),
            "erkannt_am": record.get("erkannt_am", ""), "fall_id": record.get("fall_id", ""),
            "status": "completed_with_warnings" if warnings else "completed",
            "result_code": assessment.get("ergebnis"), "confidence": assessment.get("confidence"),
            "schema_valid": record.get("schema_valid", True),
            "clause_schema_valid": record.get("clause_schema_valid", False),
            "clause_pair_count": len(clause_findings),
            "four_class_result": ", ".join(
                f"{label} ({count})" for label, count in sorted(class_counts.items())
            ) or None,
            "clause_findings": clause_findings,
            "snapshot_sha256": record.get("snapshot_sha256"),
            "previous_snapshot_sha256": record.get("previous_snapshot_sha256"),
            "manifest_sha256": evidence.get("manifest_sha256"),
            "warc_status": evidence.get("warc_status"),
            "capture_relation": evidence.get("capture_relation"),
            "snapshot_payload_sha256": evidence.get("snapshot_payload_sha256"),
            "warc_payload_sha256": evidence.get("warc_payload_sha256"),
            "screenshot_status": evidence.get("screenshot_status"),
            "screenshot_sha256": evidence.get("screenshot_sha256"),
            "timestamp_status": evidence.get("timestamp_status"),
            "capture_completeness": record.get("capture_completeness"),
            "technical_result": result_assessment,
            "warnings": warnings if isinstance(warnings, list) else [],
            "evidence_suitability": record.get("evidence_suitability", "regulaer"),
            "evidence_suitability_notice": record.get("evidence_suitability_notice"),
            "robots_txt_status": record.get("capture_transparency", {}).get("robots_txt"),
            "god_mode": bool(record.get("god_mode")),
            "god_mode_notice": record.get("god_mode_notice"),
        }

class HumanReviewRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS human_reviews (
                case_id TEXT PRIMARY KEY, decision TEXT NOT NULL, decided_at TEXT NOT NULL)""")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, case_id: str, decision: str) -> None:
        if decision not in DECISIONS:
            raise ValueError("Unzulässige menschliche Entscheidung.")
        with self._connection() as connection:
            connection.execute("""INSERT INTO human_reviews(case_id, decision, decided_at) VALUES (?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET decision=excluded.decision,
                decided_at=excluded.decided_at""",
                (case_id, decision, datetime.now(timezone.utc).isoformat()))

    def get(self, case_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT decision, decided_at FROM human_reviews WHERE case_id = ?", (case_id,)
            ).fetchone()
        return dict(row) if row else None


class TenorDraftRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS tenor_drafts (
                draft_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                model TEXT NOT NULL,
                input_json TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                decision TEXT,
                decided_at TEXT)""")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(
        self, model_input: dict, draft: TenorDraft, *, mode: str, model: str
    ) -> dict:
        record = {
            "draft_id": uuid.uuid4().hex,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "model": model,
            "input": model_input,
            "draft": draft.to_dict(),
            "decision": None,
            "decided_at": None,
        }
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO tenor_drafts(
                    draft_id, created_at, mode, model, input_json, draft_json
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record["draft_id"], record["created_at"], mode, model,
                    json.dumps(model_input, ensure_ascii=False),
                    json.dumps(record["draft"], ensure_ascii=False),
                ),
            )
        return record

    def latest(self) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM tenor_drafts ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return self._decode(row) if row else None

    def list(self, *, limit: int = 500) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM tenor_drafts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def get(self, draft_id: str) -> dict:
        if not re.fullmatch(r"[a-f0-9]{32}", draft_id):
            raise ValueError("Tenor-Entwurf nicht gefunden.")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM tenor_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Tenor-Entwurf nicht gefunden.")
        return self._decode(row)

    def decide(self, draft_id: str, decision: str) -> dict:
        if decision not in DECISIONS:
            raise ValueError("Unzulässige menschliche Entscheidung.")
        decided_at = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE tenor_drafts SET decision = ?, decided_at = ?
                WHERE draft_id = ?""",
                (decision, decided_at, draft_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Tenor-Entwurf nicht gefunden.")
        return self.get(draft_id)

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict:
        return {
            "draft_id": row["draft_id"],
            "created_at": row["created_at"],
            "mode": row["mode"],
            "model": row["model"],
            "input": json.loads(row["input_json"]),
            "draft": json.loads(row["draft_json"]),
            "decision": row["decision"],
            "decided_at": row["decided_at"],
        }


class TenorArchiveRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS tenor_archive (
                tenor_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                fall_id TEXT NOT NULL,
                schuldner TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                context TEXT NOT NULL,
                strategy TEXT NOT NULL,
                model TEXT NOT NULL,
                reference_version TEXT NOT NULL,
                source_ids_json TEXT NOT NULL)""")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, value: dict) -> dict:
        record = {
            "tenor_id": uuid.uuid4().hex,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "minimal",
            **value,
            "decision": None,
            "decided_at": None,
        }
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO tenor_archive(
                    tenor_id, created_at, fall_id, schuldner, title, text, context,
                    strategy, model, reference_version, source_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["tenor_id"],
                    record["created_at"],
                    record["fall_id"],
                    record["schuldner"],
                    record["title"],
                    record["text"],
                    record["context"],
                    record["strategy"],
                    record["model"],
                    record["reference_version"],
                    json.dumps(record["source_ids"], ensure_ascii=False),
                ),
            )
        return record

    def list(self, *, limit: int = 500) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM tenor_archive ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict:
        return {
            "tenor_id": row["tenor_id"],
            "created_at": row["created_at"],
            "source": "minimal",
            "fall_id": row["fall_id"],
            "schuldner": row["schuldner"],
            "title": row["title"],
            "text": row["text"],
            "context": row["context"],
            "strategy": row["strategy"],
            "model": row["model"],
            "reference_version": row["reference_version"],
            "source_ids": json.loads(row["source_ids_json"]),
            "decision": None,
            "decided_at": None,
        }


def create_app(case_path: str | Path, review_database: str | Path, *,
               workflow: LiveMonitorWorkflow | None = None, anthropic_ready: bool = True,
               asset_directory: str | Path | None = None,
               tenor_analyzer_factory: Callable[[], TenorAnalyzer] = DeterministicTenorAnalyzer,
               tenor_proposal_analyzer_factory: Callable[[], TenorAnalyzer] | None = None,
               tenor_question_analyzer_factory: Callable[[], TenorQuestionAnalyzer] | None = None,
               allowed_hosts: list[str] | None = None,
               monitoring_cases: MonitoringCaseRepository | None = None,
               domain_monitor: CaseDomainMonitor | None = None) -> FastAPI:
    case_path = Path(case_path).resolve()
    store_root = case_path.parent
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
    reviews = HumanReviewRepository(review_database)
    tenor_drafts = TenorDraftRepository(review_database)
    tenor_archive = TenorArchiveRepository(review_database)
    coordinator = RunCoordinator(
        workflow,
        case_repository=monitoring_cases,
        domain_monitor=domain_monitor,
    ) if workflow else None
    archive = CaseArchive(store_root)
    app = FastAPI(
        title="MucLegal Unterlassungs- und Umsetzungsmonitor",
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost", "testserver"],
    )
    app.state.run_coordinator = coordinator
    if asset_directory:
        app.mount("/static", StaticFiles(directory=Path(asset_directory).resolve()), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_length = request.headers.get("content-length")
            if request.url.path == "/api/v1/cases":
                size_limit = 14 * 1024 * 1024
            elif request.url.path == "/api/v1/tenor-pdf-text":
                size_limit = MAX_TENOR_PDF_BYTES
            else:
                size_limit = 64 * 1024
            if content_length and content_length.isdigit() and int(content_length) > size_limit:
                return JSONResponse({"detail": "Anfrage ist zu groß."}, status_code=413)
            origin = request.headers.get("origin")
            if origin:
                origin_parts = urlsplit(origin)
                if origin_parts.scheme not in {"http", "https"} or origin_parts.netloc != request.headers.get("host"):
                    return JSONResponse(
                        {"detail": "Fremde Browser-Origin ist nicht zulässig."}, status_code=403
                    )
        response = await call_next(request)
        inline_capture_document = bool(re.fullmatch(
            r"/api/v1/cases/[A-Za-z0-9][A-Za-z0-9._-]{0,127}/capture/"
            r"[A-Za-z0-9_-]+/documents/\d+",
            request.url.path,
        ))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = (
            "SAMEORIGIN" if inline_capture_document else "DENY"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "frame-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors "
            + ("'self'" if inline_capture_document else "'none'")
        )
        return response

    def load_case(*, required: bool = True) -> dict | None:
        if not case_path.is_file():
            if required:
                raise HTTPException(503, "Noch kein Prüffall erzeugt.")
            return None
        return json.loads(case_path.read_text(encoding="utf-8"))

    @app.get("/")
    async def index(request: Request):
        case = load_case(required=workflow is None)
        review_id = case.get("evidence", {}).get("manifest_sha256") if case else None
        human_review = reviews.get(review_id) if review_id else None
        return templates.TemplateResponse(request, "case.html", {
            "case": case, "human_review": human_review, "workflow_enabled": workflow is not None,
            "anthropic_ready": anthropic_ready,
            "tenor_draft": tenor_drafts.latest(),
            "active_tenor": workflow.tenor if workflow else None,
            "monitoring_cases": [item.to_dict() for item in monitoring_cases.list()] if monitoring_cases else [],
            "case_intake_enabled": monitoring_cases is not None,
            "element_errors": [
                "fehlt", "nicht_sichtbar", "nicht_leicht_zugaenglich",
                "falsches_ziel", "zusaetzliche_huerde",
            ],
        })

    @app.get("/beweis-labor")
    async def evidence_lab(request: Request):
        return templates.TemplateResponse(request, "evidence_lab.html", {
            "anthropic_ready": anthropic_ready,
        })

    def generate_tenor(payload: TenorDraftRequest) -> dict:
        values = payload.model_dump()
        fallgruppe = values.pop("fallgruppe") or "irrefuehrende_werbung"
        model_input = build_tenor_input(**values)
        model_input, _, _ = build_tenor_strategy_input(
            model_input,
            fallgruppe=fallgruppe,
            strategy="complete",
        )
        missing = missing_tenor_information(
            model_input=model_input,
            fallgruppe=fallgruppe,
        )
        if missing:
            raise ValueError(
                "Für einen bestimmten UE-Entwurf fehlen: " + ", ".join(missing)
            )
        draft, mode, model = create_tenor_draft(model_input, tenor_analyzer_factory())
        return tenor_drafts.save(model_input, draft, mode=mode, model=model)

    @app.post("/api/v1/tenor-drafts")
    @app.post("/api/tenor-drafts", include_in_schema=False)
    async def create_tenor(payload: TenorDraftRequest):
        try:
            return JSONResponse(generate_tenor(payload), status_code=201)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v1/tenor-pdf-text")
    async def extract_tenor_pdf(request: Request):
        media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type != "application/pdf":
            raise HTTPException(415, "Für die Tenorschreibhilfe ist eine PDF-Datei erforderlich.")
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_TENOR_PDF_BYTES:
                    raise HTTPException(413, "Die PDF-Datei darf höchstens 10 MB groß sein.")
            except ValueError as exc:
                raise HTTPException(400, "Ungültige Content-Length-Angabe.") from exc

        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_TENOR_PDF_BYTES:
                raise HTTPException(413, "Die PDF-Datei darf höchstens 10 MB groß sein.")

        encoded_filename = request.headers.get("x-file-name", "vertrag.pdf")
        filename = Path(unquote(encoded_filename).replace("\\", "/")).name.strip()
        if not filename or len(filename) > 255 or any(character in filename for character in "\r\n\x00"):
            raise HTTPException(422, "Ungültiger PDF-Dateiname.")
        try:
            return extract_tenor_pdf_text(bytes(data), filename=filename).to_dict()
        except TenorPdfError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v1/tenor-proposals")
    async def create_tenor_proposals_api(payload: TenorProposalRequest):
        if tenor_proposal_analyzer_factory is None:
            raise HTTPException(
                503,
                "OpenAI-Tenorhilfe ist nicht verfügbar; OPENAI_API_KEY fehlt am Server.",
            )
        model_input = build_tenor_input(
            fall_id=payload.fall_id,
            schuldner=payload.schuldner,
            fundstelle=payload.fundstelle,
            beschreibung=payload.context,
            rechtsgrundlagen=payload.rechtsgrundlagen,
            violation_branch=payload.violation_branch,
        )
        try:
            return create_tenor_proposals(
                model_input,
                tenor_proposal_analyzer_factory(),
                fallgruppe=payload.fallgruppe,
            )
        except Exception as exc:
            raw_message = str(exc)
            if "credit_balance_exhausted" in raw_message or "no credits remaining" in raw_message:
                safe_message = (
                    "Das OpenAI-API-Guthaben ist aufgebraucht. Bitte im OpenAI-Projekt "
                    "Guthaben oder ein Abrechnungslimit hinterlegen und erneut generieren."
                )
            else:
                safe_message = re.sub(
                    r"sk-[A-Za-z0-9_-]+", "[API_KEY_REDACTED]", raw_message
                )
            raise HTTPException(502, safe_message[:1_000]) from exc

    @app.post("/api/v1/tenor-archive", status_code=201)
    async def save_tenor_archive_entry(payload: TenorArchiveRequest):
        if any(not source_id.strip() or len(source_id) > 200 for source_id in payload.source_ids):
            raise HTTPException(422, "Quellenanker müssen nichtleer und höchstens 200 Zeichen lang sein.")
        return tenor_archive.save(payload.model_dump())

    @app.get("/api/v1/tenor-archive")
    async def list_tenor_archive_entries():
        minimal_entries = tenor_archive.list()
        mask_entries = [
            {
                "tenor_id": record["draft_id"],
                "created_at": record["created_at"],
                "source": "maske",
                "fall_id": record["draft"]["fall_id"],
                "schuldner": record["draft"]["schuldner"],
                "title": record["draft"]["charakteristischer_kern"],
                "text": record["draft"]["entwurf"],
                "context": record["input"]["beschreibung"],
                "strategy": record["mode"],
                "model": record["model"],
                "reference_version": "Strukturierte Tenormaske",
                "source_ids": [],
                "decision": record["decision"],
                "decided_at": record["decided_at"],
            }
            for record in tenor_drafts.list()
        ]
        entries = sorted(
            [*minimal_entries, *mask_entries],
            key=lambda item: item["created_at"],
            reverse=True,
        )
        return {"tenors": entries}

    @app.post("/api/v1/tenor-questions")
    async def create_tenor_question_api(payload: TenorQuestionRequest):
        if tenor_question_analyzer_factory is None:
            raise HTTPException(
                503,
                "OpenAI-Rückfragen sind nicht verfügbar; OPENAI_API_KEY fehlt am Server.",
            )
        try:
            model_input = build_tenor_question_input(
                context=payload.context,
                fallgruppe=payload.fallgruppe,
                answered_questions=[
                    item.model_dump() for item in payload.answered_questions
                ],
            )
            return create_tenor_question(
                model_input,
                tenor_question_analyzer_factory(),
            )
        except Exception as exc:
            raw_message = str(exc)
            if "credit_balance_exhausted" in raw_message or "no credits remaining" in raw_message:
                safe_message = (
                    "Das OpenAI-API-Guthaben ist aufgebraucht. Bitte im OpenAI-Projekt "
                    "Guthaben oder ein Abrechnungslimit hinterlegen und erneut versuchen."
                )
            else:
                safe_message = re.sub(
                    r"sk-[A-Za-z0-9_-]+", "[API_KEY_REDACTED]", raw_message
                )
            raise HTTPException(502, safe_message[:1_000]) from exc

    @app.post("/tenor-draft")
    async def create_tenor_form(request: Request):
        form = parse_qs((await request.body()).decode("utf-8"))
        try:
            payload = TenorDraftRequest(
                fall_id=form.get("fall_id", [""])[0],
                schuldner=form.get("schuldner", [""])[0],
                fundstelle=form.get("fundstelle", [""])[0],
                beschreibung=form.get("beschreibung", [""])[0],
                rechtsgrundlagen=[
                    item.strip()
                    for item in form.get("rechtsgrundlagen", [""])[0].split(",")
                    if item.strip()
                ],
            )
            generate_tenor(payload)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    def decide_tenor(draft_id: str, decision: str) -> dict:
        record = tenor_drafts.get(draft_id)
        draft: TenorDraft | None = None
        if decision == "freigegeben":
            if workflow is None:
                raise ValueError("Monitoring-Workflow ist nicht konfiguriert.")
            draft = validate_tenor_draft(
                record["draft"],
                allowed_legal_bases=record["input"]["rechtsgrundlagen"],
            )
        record = tenor_drafts.decide(draft_id, decision)
        if draft is not None:
            workflow.use_approved_tenor(draft)
        return record

    @app.post("/api/v1/tenor-drafts/{draft_id}/review")
    @app.post("/api/tenor-drafts/{draft_id}/review", include_in_schema=False)
    async def review_tenor_api(draft_id: str, request: Request):
        payload = await request.json()
        if not isinstance(payload, dict) or set(payload) != {"decision"}:
            raise HTTPException(422, "Genau eine menschliche Entscheidung wird erwartet.")
        try:
            return decide_tenor(draft_id, payload["decision"])
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/tenor-review")
    async def review_tenor_form(request: Request):
        form = parse_qs((await request.body()).decode("utf-8"))
        try:
            decide_tenor(
                form.get("draft_id", [""])[0],
                form.get("decision", [""])[0],
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/api/v1/cases")
    async def create_monitoring_case(payload: MonitoringCaseCreateRequest):
        if monitoring_cases is None:
            raise HTTPException(404, "Fallbezogene Erfassung ist nicht konfiguriert.")
        value = payload.model_dump(exclude={"screenshot"})
        screenshot = payload.screenshot.model_dump() if payload.screenshot else None
        try:
            record = monitoring_cases.create(value, screenshot)
        except MonitoringCaseError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(record.to_dict(), status_code=201)

    @app.get("/api/v1/monitoring-cases")
    async def list_monitoring_cases():
        if monitoring_cases is None:
            raise HTTPException(404, "Fallbezogene Erfassung ist nicht konfiguriert.")
        return {"cases": [item.to_dict() for item in monitoring_cases.list()]}

    @app.get("/api/v1/monitoring-cases/{case_id}")
    async def get_monitoring_case(case_id: str):
        if monitoring_cases is None:
            raise HTTPException(404, "Fallbezogene Erfassung ist nicht konfiguriert.")
        try:
            return monitoring_cases.get(case_id).to_dict()
        except KeyError as exc:
            raise HTTPException(404, "Monitoringfall nicht gefunden.") from exc

    def validated_case_evidence(monitoring_case, evidence_case_id: str) -> dict:
        """Load one regular, manifest-valid evidence bundle for the case domain."""
        try:
            evidence_detail = archive.detail(evidence_case_id)
        except HTTPException as exc:
            raise HTTPException(404, "BeweisLab-Lauf nicht gefunden.") from exc
        if evidence_detail.get("god_mode"):
            raise HTTPException(
                422,
                "Grey-Mode-Pakete bleiben von der juristischen Monitoringstrecke getrennt.",
            )
        if evidence_detail.get("evidence_suitability") != "regulaer":
            raise HTTPException(
                422,
                "Nur ein regulär geeignetes Beweispaket kann einem Fall zugeordnet werden.",
            )
        allowed_hosts = {monitoring_case.domain, *monitoring_case.allowed_subdomains}
        evidence_hosts = {
            _evidence_subject_host(str(evidence_detail.get(field) or ""))
            for field in ("requested_url", "captured_url")
        }
        if not evidence_hosts or None in evidence_hosts or not evidence_hosts.issubset(allowed_hosts):
            raise HTTPException(
                422,
                "Beweispaket und Monitoringfall müssen dieselbe freigegebene Domain betreffen.",
            )
        try:
            manifest_path = archive.artifact_path(evidence_case_id, "manifest")
        except HTTPException as exc:
            raise HTTPException(422, "Beweispaket enthält kein prüfbares Manifest.") from exc
        verification = verify_manifest(manifest_path)
        if (
            not verification.valid
            or verification.manifest_sha256 != evidence_detail.get("manifest_sha256")
        ):
            raise HTTPException(422, "Hash-Manifest des Beweispakets ist nicht gültig.")

        documents: list[dict[str, str]] = []
        text_bytes = 0
        capture_galleries = evidence_detail.get("capture_galleries", {})
        for role, gallery in capture_galleries.items():
            try:
                text_path = archive.capture_normalized_text_path(evidence_case_id, role)
            except HTTPException:
                continue
            text_bytes += text_path.stat().st_size
            if text_bytes > 2 * 1024 * 1024:
                raise HTTPException(422, "Beweispaket enthält mehr als 2 MiB Vergleichstext.")
            text = text_path.read_text(encoding="utf-8").strip()
            if text:
                documents.append({
                    "role": role,
                    "text": text,
                    "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "capture_completeness": gallery.get("capture_completeness"),
                })
        if not documents:
            try:
                text_path = archive.artifact_path(evidence_case_id, "normalized_text")
            except HTTPException as exc:
                raise HTTPException(
                    422, "Beweispaket enthält keinen normalisierten Vergleichstext."
                ) from exc
            if text_path.stat().st_size > 2 * 1024 * 1024:
                raise HTTPException(422, "Beweispaket enthält mehr als 2 MiB Vergleichstext.")
            text = text_path.read_text(encoding="utf-8").strip()
            if text:
                documents.append({
                    "role": "main",
                    "text": text,
                    "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "capture_completeness": evidence_detail.get("capture_completeness"),
                })
        if not documents:
            raise HTTPException(422, "Beweispaket enthält keinen normalisierten Vergleichstext.")
        return {
            "evidence_case_id": evidence_case_id,
            "requested_url": evidence_detail["requested_url"],
            "captured_url": evidence_detail["captured_url"],
            "captured_at": evidence_detail["erkannt_am"],
            "manifest_sha256": verification.manifest_sha256,
            "capture_completeness": evidence_detail.get("capture_completeness"),
            "documents": documents,
        }

    def primary_evidence_document(documents: list[dict]) -> dict | None:
        for preferred_role in ("main", "agb", "requested"):
            document = next(
                (item for item in documents if item.get("role") == preferred_role), None
            )
            if document is not None:
                return document
        return documents[0] if documents else None

    @app.post("/api/v1/cases/{case_id}/baseline-evidence", status_code=201)
    async def attach_case_baseline_evidence(
        case_id: str, payload: BaselineEvidenceAttachRequest
    ):
        if monitoring_cases is None:
            raise HTTPException(404, "Fallaufnahme ist nicht konfiguriert.")
        try:
            monitoring_case = monitoring_cases.get(case_id)
        except KeyError as exc:
            raise HTTPException(404, "Monitoringfall nicht gefunden.") from exc
        if monitoring_case.baseline_evidence is not None:
            raise HTTPException(
                409, "Ausgangsbeweis ist bereits vorhanden und kann nicht überschrieben werden."
            )
        evidence = validated_case_evidence(monitoring_case, payload.evidence_case_id)
        try:
            updated = monitoring_cases.attach_baseline_evidence(case_id, evidence)
        except MonitoringCaseError as exc:
            raise HTTPException(422, str(exc)) from exc
        return updated.to_dict()

    @app.post("/api/v1/cases/{case_id}/evidence-comparisons", status_code=201)
    async def compare_case_evidence(
        case_id: str, payload: BaselineEvidenceAttachRequest
    ):
        if monitoring_cases is None:
            raise HTTPException(404, "Fallaufnahme ist nicht konfiguriert.")
        try:
            monitoring_case = monitoring_cases.get(case_id)
        except KeyError as exc:
            raise HTTPException(404, "Monitoringfall nicht gefunden.") from exc
        baseline = monitoring_case.baseline_evidence
        if baseline is None:
            raise HTTPException(409, "Für diesen Fall ist noch kein Ausgangsbeweis vorhanden.")
        if baseline.get("evidence_case_id") == payload.evidence_case_id:
            raise HTTPException(422, "Ausgangsbeweis kann nicht mit sich selbst verglichen werden.")
        current = validated_case_evidence(monitoring_case, payload.evidence_case_id)
        baseline_document = primary_evidence_document(baseline.get("documents", []))
        current_document = primary_evidence_document(current.get("documents", []))
        current_incomplete = (
            current.get("capture_completeness") == "durch_seitenschutz_begrenzt"
            or (
                current_document is not None
                and current_document.get("capture_completeness")
                in {"teilweise_erfasst", "durch_seitenschutz_begrenzt"}
            )
        )
        if baseline_document is None or current_document is None or current_incomplete:
            status = "pruefung_unvollstaendig"
        elif baseline_document["sha256"] == current_document["sha256"]:
            status = "unveraendert_fortbestehend"
        else:
            status = "technische_aenderung_erkannt"
        comparison = {
            "comparison_id": uuid.uuid4().hex,
            "status": status,
            "baseline_evidence_case_id": baseline["evidence_case_id"],
            "current_evidence_case_id": current["evidence_case_id"],
            "baseline_requested_url": baseline["requested_url"],
            "current_requested_url": current["requested_url"],
            "baseline_manifest_sha256": baseline["manifest_sha256"],
            "current_manifest_sha256": current["manifest_sha256"],
            "baseline_text_sha256": baseline_document.get("sha256") if baseline_document else None,
            "current_text_sha256": current_document.get("sha256") if current_document else None,
            "compared_role": (
                str(current_document.get("role")) if current_document else "nicht_verfuegbar"
            ),
            "compared_at": datetime.now(timezone.utc).isoformat(),
            "technical_only": True,
        }
        try:
            updated = monitoring_cases.record_evidence_comparison(case_id, comparison)
        except MonitoringCaseError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "fall_id": updated.fall_id,
            "case_id": updated.case_id,
            "comparison": updated.latest_evidence_comparison,
        }

    @app.post("/api/v1/cases/{case_id}/review")
    async def review_monitoring_case(case_id: str, request: Request):
        if monitoring_cases is None:
            raise HTTPException(404, "Fallbezogene Erfassung ist nicht konfiguriert.")
        payload = await request.json()
        if not isinstance(payload, dict) or set(payload) != {"decision"}:
            raise HTTPException(422, "Genau eine menschliche Fallentscheidung wird erwartet.")
        try:
            return monitoring_cases.review(case_id, payload["decision"]).to_dict()
        except KeyError as exc:
            raise HTTPException(404, "Monitoringfall nicht gefunden.") from exc
        except (MonitoringCaseError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v1/runs")
    @app.post("/api/runs", include_in_schema=False)
    async def start_run(payload: RunRequest):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        if monitoring_cases is None and not anthropic_ready:
            raise HTTPException(503, "ANTHROPIC_API_KEY fehlt am Server.")
        try:
            if payload.verification_mode or payload.god_mode_authorized:
                raise ValueError("Der Überprüfungsmodus ist ausschließlich im BeweisLab verfügbar.")
            run = coordinator.start(payload.url, case_id=payload.case_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse(run.to_dict(), status_code=202)

    @app.get("/api/v1/runs/{run_id}")
    @app.get("/api/runs/{run_id}", include_in_schema=False)
    async def get_run(run_id: str):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        run = coordinator.get(run_id)
        if run is None:
            raise HTTPException(404, "Prüflauf nicht gefunden.")
        return run.to_dict()

    @app.post("/api/v1/evidence-runs")
    async def start_evidence_run(payload: RunRequest):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        if payload.case_id is not None:
            raise HTTPException(422, "Das Beweislabor erwartet ausschließlich eine URL.")
        try:
            run = coordinator.start(
                payload.url,
                direct_url=True,
                verification_mode=payload.verification_mode,
                god_mode_authorized=payload.god_mode_authorized,
            )
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        response = run.to_dict()
        return JSONResponse(response, status_code=202)

    @app.post("/api/v1/evidence-runs/stream")
    async def stream_evidence_run(payload: RunRequest):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        if payload.case_id is not None:
            raise HTTPException(422, "Das Beweislabor erwartet ausschließlich eine URL.")
        try:
            run = coordinator.start(
                payload.url,
                direct_url=True,
                verification_mode=payload.verification_mode,
                god_mode_authorized=payload.god_mode_authorized,
            )
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        async def updates():
            previous: str | None = None
            while True:
                current = coordinator.get(run.run_id)
                if current is None:
                    yield json.dumps(
                        {"type": "error", "detail": "Prüflauf nicht gefunden."},
                        ensure_ascii=False,
                    ) + "\n"
                    return
                current_payload = current.to_dict()
                serialized = json.dumps(current_payload, ensure_ascii=False, sort_keys=True)
                if serialized != previous:
                    yield json.dumps(
                        {"type": "run", "run": current_payload}, ensure_ascii=False
                    ) + "\n"
                    previous = serialized
                if current.status in TERMINAL_RUN_STATUSES:
                    response = current_payload
                    yield json.dumps(
                        {"type": "complete", "run": response}, ensure_ascii=False
                    ) + "\n"
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(
            updates(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/evidence-runs/{run_id}")
    async def get_evidence_run(run_id: str):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        run = coordinator.get(run_id)
        if run is None:
            raise HTTPException(404, "Prüflauf nicht gefunden.")
        return run.to_dict()

    @app.get("/api/v1/cases")
    @app.get("/api/cases", include_in_schema=False)
    async def list_cases():
        result = {"cases": archive.list(), "god_mode_cases": archive.list_god_mode()}
        if monitoring_cases is not None:
            result["monitoring_cases"] = [item.to_dict() for item in monitoring_cases.list()]
        return result

    @app.get("/api/v1/cases/{case_id}")
    @app.get("/api/cases/{case_id}", include_in_schema=False)
    async def get_case(case_id: str):
        if monitoring_cases is not None:
            try:
                return monitoring_cases.get(case_id).to_dict()
            except KeyError:
                pass
        return archive.detail(case_id)

    @app.get("/api/v1/cases/{case_id}/preview/{label}")
    @app.get("/api/cases/{case_id}/preview/{label}", include_in_schema=False)
    async def preview_case_artifact(case_id: str, label: str):
        return {"label": label, "content": archive.preview(case_id, label)}

    @app.get("/api/v1/cases/{case_id}/capture/{role}/preview")
    async def capture_preview(case_id: str, role: str):
        return FileResponse(archive.capture_gallery_path(case_id, role, "preview"))

    @app.get("/api/v1/cases/{case_id}/capture/{role}/tiles/{index}")
    async def capture_tile(case_id: str, role: str, index: int):
        path = archive.capture_gallery_path(case_id, role, "tiles", index)
        return FileResponse(path, filename=path.name)

    @app.get("/api/v1/cases/{case_id}/capture/{role}/originals/{index}")
    async def capture_original(case_id: str, role: str, index: int):
        path = archive.capture_gallery_path(case_id, role, "originals", index)
        return FileResponse(path, filename=path.name)

    @app.get("/api/v1/cases/{case_id}/capture/{role}/documents/{index}")
    async def capture_document(case_id: str, role: str, index: int):
        path = archive.capture_gallery_path(case_id, role, "documents", index)
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/pdf",
            content_disposition_type="inline",
        )

    @app.get("/api/v1/cases/{case_id}/capture/{role}/normalized-text")
    async def capture_normalized_text(case_id: str, role: str):
        path = archive.capture_normalized_text_path(case_id, role)
        content = path.read_bytes()
        truncated = len(content) > MAX_TEXT_PREVIEW_BYTES
        text = content[:MAX_TEXT_PREVIEW_BYTES].decode("utf-8", errors="replace")
        if truncated:
            text += "\n\n[… Vorschau nach 512 KiB gekürzt; vollständige Datei im Beweispaket …]"
        return PlainTextResponse(text)

    @app.get("/api/v1/cases/{case_id}/capture/{role}/raw-html")
    async def capture_raw_html(case_id: str, role: str):
        path = archive.capture_raw_html_path(case_id, role)
        return PlainTextResponse(
            path.read_text(encoding="utf-8", errors="replace"),
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )

    @app.get("/artifact/{case_id}/{label}")
    async def historical_artifact(case_id: str, label: str):
        path = archive.artifact_path(case_id, label)
        kind = ARTIFACT_DEFINITIONS[label][2]
        if kind == "text":
            return PlainTextResponse(
                path.read_text(encoding="utf-8", errors="replace"),
                headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
            )
        return FileResponse(path, filename=path.name if kind == "binary" else None)

    @app.get("/api/v1/cases/{case_id}/download")
    async def download_case_bundle(case_id: str):
        path = archive.build_download(case_id)
        return FileResponse(
            path,
            media_type="application/zip",
            filename=path.name,
        )

    @app.post("/review")
    async def review(request: Request):
        case = load_case()
        assert case is not None
        decision = parse_qs((await request.body()).decode("utf-8")).get("decision", [""])[0]
        try:
            reviews.save(case["evidence"]["manifest_sha256"], decision)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    @app.get("/artifact/{label}")
    async def artifact(label: str):
        case = load_case()
        assert case is not None
        if label not in ARTIFACT_DEFINITIONS:
            raise HTTPException(404, "Artefakt nicht freigegeben.")
        path_value = case.get("artifacts", {}).get(label)
        if not path_value:
            raise HTTPException(404, "Artefakt nicht vorhanden.")
        path = Path(path_value).resolve()
        try:
            path.relative_to(store_root)
        except ValueError as exc:
            raise HTTPException(404, "Artefakt liegt außerhalb der lokalen Ablage.") from exc
        if not path.is_file():
            raise HTTPException(404, "Artefaktdatei fehlt.")
        kind = ARTIFACT_DEFINITIONS[label][2]
        if kind == "text":
            return PlainTextResponse(
                path.read_text(encoding="utf-8", errors="replace"),
                headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
            )
        return FileResponse(path, filename=path.name if kind == "binary" else None)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    if coordinator:
        app.add_event_handler("shutdown", coordinator.close)
    return app
