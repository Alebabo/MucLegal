from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates


DECISIONS = {"freigegeben", "abgelehnt", "weitere_pruefung"}


class HumanReviewRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS human_reviews (
                    case_id TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    decided_at TEXT NOT NULL
                )
                """
            )

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
            connection.execute(
                """
                INSERT INTO human_reviews(case_id, decision, decided_at) VALUES (?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET decision=excluded.decision,
                  decided_at=excluded.decided_at
                """,
                (case_id, decision, datetime.now(timezone.utc).isoformat()),
            )

    def get(self, case_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT decision, decided_at FROM human_reviews WHERE case_id = ?", (case_id,)
            ).fetchone()
        return dict(row) if row else None


def create_app(case_path: str | Path, review_database: str | Path) -> FastAPI:
    case_path = Path(case_path).resolve()
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
    reviews = HumanReviewRepository(review_database)
    app = FastAPI(title="MucLegal", docs_url=None, redoc_url=None)

    def load_case() -> dict:
        if not case_path.is_file():
            raise HTTPException(503, "Noch kein Demo-Fall erzeugt.")
        return json.loads(case_path.read_text(encoding="utf-8"))

    @app.get("/")
    async def index(request: Request):
        case = load_case()
        human_review = reviews.get(case["evidence"]["manifest_sha256"])
        return templates.TemplateResponse(
            request,
            "case.html",
            {"case": case, "human_review": human_review},
        )

    @app.post("/review")
    async def review(request: Request):
        case = load_case()
        form = parse_qs((await request.body()).decode("utf-8"))
        decision = form.get("decision", [""])[0]
        try:
            reviews.save(case["evidence"]["manifest_sha256"], decision)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    @app.get("/artifact/{label}")
    async def artifact(label: str):
        case = load_case()
        path_value = case.get("artifacts", {}).get(label)
        if not path_value:
            raise HTTPException(404, "Artefakt nicht vorhanden.")
        path = Path(path_value).resolve()
        if not path.is_file():
            raise HTTPException(404, "Artefaktdatei fehlt.")
        return FileResponse(path)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    return app
