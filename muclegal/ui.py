from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from muclegal.live import PIPELINE_STEPS, LiveMonitorWorkflow


DECISIONS = {"freigegeben", "abgelehnt", "weitere_pruefung"}
TERMINAL_RUN_STATUSES = {
    "baseline_created", "unchanged", "completed", "completed_with_warnings", "failed",
}
MAX_TEXT_PREVIEW_BYTES = 512 * 1024
CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ARTIFACT_DEFINITIONS = {
    "raw_html": ("Abruf", "Roh-HTML", "text"),
    "response_headers": ("Abruf", "Header", "text"),
    "normalized_text": ("Abruf", "Normalisierter Text", "text"),
    "previous_normalized_text": ("Abruf", "Vorheriger Text", "text"),
    "diff": ("Abruf", "Diff", "text"),
    "model_input": ("Analyse", "Modellinput", "text"),
    "model_output": ("Analyse", "Validierter Modelloutput", "text"),
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
    url: str


@dataclass
class RunState:
    run_id: str
    url: str
    status: str = "queued"
    current_step: str = "queued"
    message: str = "Prüfung wurde eingeplant."
    result_available: bool = False
    steps: dict[str, str] = field(default_factory=lambda: {step: "waiting" for step in PIPELINE_STEPS})

    def to_dict(self) -> dict:
        return asdict(self)


class RunCoordinator:
    def __init__(self, workflow: LiveMonitorWorkflow) -> None:
        self.workflow = workflow
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="muclegal-run")
        self._lock = threading.Lock()
        self._runs: dict[str, RunState] = {}
        self._active_run_id: str | None = None

    def start(self, url: str) -> RunState:
        with self._lock:
            if self._active_run_id:
                active = self._runs[self._active_run_id]
                if active.status not in TERMINAL_RUN_STATUSES:
                    raise RuntimeError("Es läuft bereits eine Prüfung.")
            run = RunState(run_id=uuid.uuid4().hex, url=url.strip())
            self._runs[run.run_id] = run
            self._active_run_id = run.run_id
            self._executor.submit(self._execute, run.run_id)
            return RunState(**run.to_dict())

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

        with self._lock:
            url = self._runs[run_id].url
        try:
            result = self.workflow.run(url, progress)
            with self._lock:
                run = self._runs[run_id]
                run.status = result.status
                run.message = result.message
                run.result_available = result.case_path is not None
                if result.step_states:
                    run.steps = dict(result.step_states)
                reached = [step for step in PIPELINE_STEPS if run.steps[step] != "skipped"]
                run.current_step = reached[-1] if reached else "compare"
        except Exception as exc:
            with self._lock:
                run = self._runs[run_id]
                run.status = "failed"
                if run.current_step in PIPELINE_STEPS:
                    run.steps[run.current_step] = "failed"
                run.message = str(exc)
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

    def detail(self, case_id: str) -> dict:
        record = self._read(self._case_path(case_id))
        summary = self._summary(case_id, record)
        artifacts: list[dict] = []
        stored = record.get("artifacts", {})
        for label, (group, title, kind) in ARTIFACT_DEFINITIONS.items():
            artifact = {"label": label, "title": title, "group": group, "kind": kind,
                        "available": False, "preview_available": False, "size": None}
            if stored.get(label):
                try:
                    path = self._safe_artifact_path(label, record)
                    artifact["available"] = True
                    artifact["size"] = path.stat().st_size
                    artifact["preview_available"] = (
                        kind == "text" and path.stat().st_size <= MAX_TEXT_PREVIEW_BYTES
                    ) or kind == "pdf"
                except HTTPException:
                    pass
            artifacts.append(artifact)
        return {**summary, "artifacts": artifacts}

    def artifact_path(self, case_id: str, label: str) -> Path:
        return self._safe_artifact_path(label, self._read(self._case_path(case_id)))

    def preview(self, case_id: str, label: str) -> str:
        definition = ARTIFACT_DEFINITIONS.get(label)
        if not definition or definition[2] != "text":
            raise HTTPException(415, "Für dieses Artefakt ist keine Textvorschau erlaubt.")
        path = self.artifact_path(case_id, label)
        if path.stat().st_size > MAX_TEXT_PREVIEW_BYTES:
            raise HTTPException(413, "Artefakt ist für die Inline-Vorschau zu groß.")
        return path.read_text(encoding="utf-8", errors="replace")

    def _case_path(self, case_id: str) -> Path:
        if not CASE_ID_PATTERN.fullmatch(case_id):
            raise HTTPException(404, "Beweislauf nicht gefunden.")
        path = (self.bundle_root / case_id / "case.json").resolve()
        try:
            path.relative_to(self.bundle_root)
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

    def _safe_artifact_path(self, label: str, record: dict) -> Path:
        if label not in ARTIFACT_DEFINITIONS:
            raise HTTPException(404, "Artefakt nicht freigegeben.")
        path_value = record.get("artifacts", {}).get(label)
        if not path_value:
            raise HTTPException(404, "Artefakt nicht vorhanden.")
        path = Path(path_value).resolve()
        try:
            path.relative_to(self.store_root)
        except ValueError as exc:
            raise HTTPException(404, "Artefakt liegt außerhalb der lokalen Ablage.") from exc
        if not path.is_file():
            raise HTTPException(404, "Artefaktdatei fehlt.")
        return path

    @staticmethod
    def _summary(case_id: str, record: dict) -> dict:
        evidence = record.get("evidence", {})
        assessment = record.get("assessment", {})
        warnings = record.get("warnings", [])
        return {
            "case_id": case_id, "url": record.get("url", ""),
            "erkannt_am": record.get("erkannt_am", ""), "fall_id": record.get("fall_id", ""),
            "status": "completed_with_warnings" if warnings else "completed",
            "result_code": assessment.get("ergebnis"), "confidence": assessment.get("confidence"),
            "schema_valid": record.get("schema_valid", True),
            "snapshot_sha256": record.get("snapshot_sha256"),
            "previous_snapshot_sha256": record.get("previous_snapshot_sha256"),
            "manifest_sha256": evidence.get("manifest_sha256"),
            "warc_status": evidence.get("warc_status"),
            "timestamp_status": evidence.get("timestamp_status"),
            "warnings": warnings if isinstance(warnings, list) else [],
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


def create_app(case_path: str | Path, review_database: str | Path, *,
               workflow: LiveMonitorWorkflow | None = None, anthropic_ready: bool = True,
               asset_directory: str | Path | None = None) -> FastAPI:
    case_path = Path(case_path).resolve()
    store_root = case_path.parent
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
    reviews = HumanReviewRepository(review_database)
    coordinator = RunCoordinator(workflow) if workflow else None
    archive = CaseArchive(store_root)
    app = FastAPI(title="MucLegal Pipeline Test Harness", docs_url=None, redoc_url=None)
    app.state.run_coordinator = coordinator
    if asset_directory:
        app.mount("/static", StaticFiles(directory=Path(asset_directory).resolve()), name="static")

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
        })

    @app.post("/api/runs")
    async def start_run(payload: RunRequest):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        if not anthropic_ready:
            raise HTTPException(503, "ANTHROPIC_API_KEY fehlt am Server.")
        if not payload.url.strip():
            raise HTTPException(422, "Eine Webadresse ist erforderlich.")
        try:
            run = coordinator.start(payload.url)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return JSONResponse(run.to_dict(), status_code=202)

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str):
        if coordinator is None:
            raise HTTPException(404, "Live-Prüfung ist nicht konfiguriert.")
        run = coordinator.get(run_id)
        if run is None:
            raise HTTPException(404, "Prüflauf nicht gefunden.")
        return run.to_dict()

    @app.get("/api/cases")
    async def list_cases():
        return {"cases": archive.list()}

    @app.get("/api/cases/{case_id}")
    async def get_case(case_id: str):
        return archive.detail(case_id)

    @app.get("/api/cases/{case_id}/preview/{label}")
    async def preview_case_artifact(case_id: str, label: str):
        return {"label": label, "content": archive.preview(case_id, label)}

    @app.get("/artifact/{case_id}/{label}")
    async def historical_artifact(case_id: str, label: str):
        path = archive.artifact_path(case_id, label)
        if ARTIFACT_DEFINITIONS[label][2] == "binary":
            return FileResponse(path, filename=path.name)
        return FileResponse(path)

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
        return FileResponse(path)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    if coordinator:
        app.add_event_handler("shutdown", coordinator.close)
    return app
