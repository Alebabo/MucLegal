from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from muclegal.fetch import FetchFailure, FetchResult
from muclegal.normalize import NormalizedDocument
from muclegal.normalize.clauses import Clause
from muclegal.llm.classification import ClauseClassification


@dataclass(frozen=True)
class SnapshotRecord:
    id: int
    normalized_sha256: str
    normalized_text_path: str
    previous_sha256: str | None
    diff_path: str | None


@dataclass(frozen=True)
class SnapshotArtifacts:
    raw_html_path: str
    response_headers_path: str
    normalized_text_path: str
    diff_path: str | None
    fetched_at: str
    normalized_sha256: str
    final_url: str
    status_code: int
    redirect_chain_json: str


@dataclass(frozen=True)
class ClauseRecord:
    id: str
    snapshot_id: int
    ordinal: int
    heading_path: str | None
    text: str
    clause_hash: str
    is_tenor_relevant: bool


@dataclass(frozen=True)
class FindingRecord:
    id: str
    classification: str
    tenor_element_id: str | None
    confidence: str
    evidence_quote: str | None
    reasoning: str
    model: str
    prompt_version: str
    juristin_entscheidung: str | None
    juristin_kommentar: str | None
    entschieden_von: str | None
    entschieden_at: str | None


@dataclass(frozen=True)
class SnapshotScreenshot:
    snapshot_id: int
    status: str
    path: str | None
    sha256: str | None
    size_bytes: int | None
    error_message: str | None


class SnapshotRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.artifacts = self.root / "artifacts"
        self.database_path = self.root / "muclegal.sqlite3"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS fetch_attempts (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    attempted_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    status_code INTEGER,
                    error_code TEXT,
                    error_message TEXT,
                    manual_review INTEGER NOT NULL DEFAULT 0,
                    response_headers_path TEXT,
                    response_body_path TEXT
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY,
                    fetch_attempt_id INTEGER NOT NULL REFERENCES fetch_attempts(id),
                    url TEXT NOT NULL,
                    final_url TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    response_headers_path TEXT NOT NULL,
                    raw_html_path TEXT NOT NULL,
                    normalized_text_path TEXT NOT NULL,
                    normalized_sha256 TEXT NOT NULL,
                    previous_sha256 TEXT,
                    diff_path TEXT,
                    normalizer_version TEXT NOT NULL,
                    selector_config_hash TEXT NOT NULL,
                    fetch_mode TEXT NOT NULL,
                    redirect_chain_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS snapshots_profile_idx
                ON snapshots(url, normalizer_version, selector_config_hash, fetch_mode, id DESC);

                CREATE TABLE IF NOT EXISTS snapshot_quality (
                    snapshot_id INTEGER PRIMARY KEY REFERENCES snapshots(id),
                    extraction_ok INTEGER NOT NULL DEFAULT 1,
                    clause_count INTEGER NOT NULL,
                    warning TEXT
                );
                CREATE TABLE IF NOT EXISTS snapshot_screenshots (
                    snapshot_id INTEGER PRIMARY KEY REFERENCES snapshots(id),
                    status TEXT NOT NULL CHECK (status IN ('captured', 'failed')),
                    path TEXT,
                    sha256 TEXT,
                    size_bytes INTEGER,
                    error_message TEXT,
                    CHECK (
                        (status = 'captured' AND path IS NOT NULL AND sha256 IS NOT NULL
                          AND size_bytes IS NOT NULL AND error_message IS NULL)
                        OR
                        (status = 'failed' AND path IS NULL AND sha256 IS NULL
                          AND size_bytes IS NULL AND error_message IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    company_id TEXT REFERENCES companies(id),
                    title TEXT NOT NULL,
                    basis TEXT NOT NULL CHECK (basis IN ('ue', 'urteil')),
                    basis_date TEXT,
                    vertragsstrafe NUMERIC,
                    status TEXT NOT NULL CHECK (status IN ('aktiv', 'wiedervorlage', 'geschlossen')),
                    next_review_at TEXT
                );
                CREATE TABLE IF NOT EXISTS tenors (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    case_id TEXT NOT NULL REFERENCES cases(id),
                    version INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    elements_json TEXT NOT NULL,
                    verstoss_typ TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    approved_by TEXT,
                    approved_at TEXT,
                    UNIQUE(case_id, version)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_tenor_per_case
                ON tenors(case_id) WHERE is_active = 1;
                CREATE TABLE IF NOT EXISTS tenor_drafts (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    case_id TEXT REFERENCES cases(id),
                    verstoss_input TEXT NOT NULL,
                    verstoss_typ TEXT,
                    draft_text TEXT NOT NULL,
                    draft_elements_json TEXT,
                    final_text TEXT,
                    status TEXT NOT NULL,
                    korrektur_kategorie TEXT,
                    anmerkung TEXT,
                    model TEXT,
                    prompt_version TEXT
                );
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    case_id TEXT NOT NULL REFERENCES cases(id),
                    url TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('html', 'pdf')),
                    label TEXT,
                    crawl_config_json TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_crawled_at TEXT
                );
                CREATE TABLE IF NOT EXISTS clauses (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    ordinal INTEGER NOT NULL,
                    heading_path TEXT,
                    text TEXT NOT NULL,
                    clause_hash TEXT NOT NULL,
                    is_tenor_relevant INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(snapshot_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS clauses_snapshot_hash_idx
                ON clauses(snapshot_id, clause_hash);
                CREATE INDEX IF NOT EXISTS clauses_hash_idx ON clauses(clause_hash);
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    case_id TEXT REFERENCES cases(id),
                    tenor_id TEXT REFERENCES tenors(id),
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    clause_id TEXT REFERENCES clauses(id),
                    prev_clause_id TEXT REFERENCES clauses(id),
                    classification TEXT NOT NULL CHECK (
                        classification IN ('beseitigt', 'kerngleich', 'neuer_sachverhalt', 'unsicher')
                    ),
                    tenor_element_id TEXT,
                    confidence TEXT CHECK (confidence IN ('hoch', 'mittel', 'niedrig')),
                    evidence_quote TEXT,
                    reasoning TEXT,
                    model TEXT,
                    prompt_version TEXT,
                    juristin_entscheidung TEXT CHECK (
                        juristin_entscheidung IN ('vertragsstrafe', 'neue_abmahnung', 'verworfen')
                        OR juristin_entscheidung IS NULL
                    ),
                    juristin_kommentar TEXT,
                    entschieden_von TEXT,
                    entschieden_at TEXT
                );
                CREATE TABLE IF NOT EXISTS evidence_packages (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    finding_id TEXT NOT NULL REFERENCES findings(id),
                    screenshot_path TEXT,
                    warc_path TEXT,
                    warc_sha256 TEXT,
                    screenshot_sha256 TEXT,
                    text_sha256 TEXT,
                    chain_hash TEXT NOT NULL,
                    prev_chain_hash TEXT,
                    tsr_path TEXT,
                    tsa_url TEXT,
                    wayback_url TEXT,
                    pdf_report_path TEXT
                );
                CREATE VIEW IF NOT EXISTS korrektur_signale AS
                SELECT korrektur_kategorie, COUNT(*) AS n
                FROM tenor_drafts
                WHERE korrektur_kategorie IS NOT NULL
                GROUP BY korrektur_kategorie HAVING COUNT(*) >= 3;

                CREATE TRIGGER IF NOT EXISTS findings_no_delete
                BEFORE DELETE ON findings BEGIN
                    SELECT RAISE(ABORT, 'findings sind append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS findings_protected_update
                BEFORE UPDATE ON findings WHEN
                    OLD.id IS NOT NEW.id OR OLD.created_at IS NOT NEW.created_at OR
                    OLD.case_id IS NOT NEW.case_id OR OLD.tenor_id IS NOT NEW.tenor_id OR
                    OLD.snapshot_id IS NOT NEW.snapshot_id OR OLD.clause_id IS NOT NEW.clause_id OR
                    OLD.prev_clause_id IS NOT NEW.prev_clause_id OR
                    OLD.classification IS NOT NEW.classification OR
                    OLD.tenor_element_id IS NOT NEW.tenor_element_id OR
                    OLD.confidence IS NOT NEW.confidence OR
                    OLD.evidence_quote IS NOT NEW.evidence_quote OR
                    OLD.reasoning IS NOT NEW.reasoning OR OLD.model IS NOT NEW.model OR
                    OLD.prompt_version IS NOT NEW.prompt_version
                BEGIN
                    SELECT RAISE(ABORT, 'nur juristin_* darf aktualisiert werden');
                END;
                CREATE TRIGGER IF NOT EXISTS evidence_packages_no_update
                BEFORE UPDATE ON evidence_packages BEGIN
                    SELECT RAISE(ABORT, 'evidence_packages sind append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS evidence_packages_no_delete
                BEFORE DELETE ON evidence_packages BEGIN
                    SELECT RAISE(ABORT, 'evidence_packages sind append-only');
                END;
                """
            )

    def latest_compatible(
        self,
        url: str,
        normalizer_version: str,
        selector_config_hash: str,
        fetch_mode: str,
    ) -> SnapshotRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, normalized_sha256, normalized_text_path, previous_sha256, diff_path
                FROM snapshots AS s
                LEFT JOIN snapshot_quality AS q ON q.snapshot_id = s.id
                WHERE url = ? AND normalizer_version = ? AND selector_config_hash = ? AND fetch_mode = ?
                  AND COALESCE(q.extraction_ok, 1) = 1
                ORDER BY s.id DESC LIMIT 1
                """,
                (url, normalizer_version, selector_config_hash, fetch_mode),
            ).fetchone()
        return SnapshotRecord(**dict(row)) if row else None

    def save_success(
        self,
        result: FetchResult,
        normalized: NormalizedDocument,
        previous_sha256: str | None,
        diff_text: str | None,
    ) -> SnapshotRecord:
        directory = self._new_artifact_directory(result.requested_url, "snapshot")
        raw_path = directory / "raw.html"
        headers_path = directory / "headers.json"
        normalized_path = directory / "normalized.txt"
        diff_path = directory / "change.diff" if diff_text else None
        raw_path.write_bytes(result.body)
        headers_path.write_text(
            json.dumps(list(result.headers), ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        normalized_path.write_text(normalized.text, encoding="utf-8", newline="\n")
        if diff_path:
            diff_path.write_text(diff_text, encoding="utf-8", newline="\n")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO fetch_attempts(url, attempted_at, outcome, status_code,
                  response_headers_path, response_body_path)
                VALUES (?, ?, 'success', ?, ?, ?)
                """,
                (
                    result.requested_url,
                    result.fetched_at,
                    result.status_code,
                    str(headers_path),
                    str(raw_path),
                ),
            )
            attempt_id = cursor.lastrowid
            cursor = connection.execute(
                """
                INSERT INTO snapshots(fetch_attempt_id, url, final_url, fetched_at, status_code,
                  response_headers_path, raw_html_path, normalized_text_path, normalized_sha256,
                  previous_sha256, diff_path, normalizer_version, selector_config_hash,
                  fetch_mode, redirect_chain_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    result.requested_url,
                    result.final_url,
                    result.fetched_at,
                    result.status_code,
                    str(headers_path),
                    str(raw_path),
                    str(normalized_path),
                    normalized.sha256,
                    previous_sha256,
                    str(diff_path) if diff_path else None,
                    normalized.normalizer_version,
                    normalized.selector_config_hash,
                    result.fetch_mode,
                    json.dumps(result.redirect_chain, ensure_ascii=False),
                ),
            )
            snapshot_id = int(cursor.lastrowid)
        return SnapshotRecord(
            snapshot_id,
            normalized.sha256,
            str(normalized_path),
            previous_sha256,
            str(diff_path) if diff_path else None,
        )

    def save_failure(self, url: str, failure: FetchFailure) -> None:
        directory = self._new_artifact_directory(url, "failed-fetch")
        headers_path: Path | None = None
        body_path: Path | None = None
        if failure.headers:
            headers_path = directory / "headers.json"
            headers_path.write_text(
                json.dumps(list(failure.headers), ensure_ascii=False, indent=2),
                encoding="utf-8",
                newline="\n",
            )

        if failure.body is not None:
            body_path = directory / "response.bin"
            body_path.write_bytes(failure.body)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fetch_attempts(url, attempted_at, outcome, status_code, error_code,
                  error_message, manual_review, response_headers_path, response_body_path)
                VALUES (?, ?, 'failure', ?, ?, ?, ?, ?, ?)
                """,
                (
                    url,
                    datetime.now(timezone.utc).isoformat(),
                    failure.status_code,
                    failure.code,
                    str(failure),
                    int(failure.manual_review),
                    str(headers_path) if headers_path else None,
                    str(body_path) if body_path else None,
                ),
            )

    def snapshot_artifacts(self, snapshot_id: int) -> SnapshotArtifacts:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT raw_html_path, response_headers_path, normalized_text_path, diff_path,
                       fetched_at, normalized_sha256, final_url, status_code, redirect_chain_json
                FROM snapshots WHERE id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Snapshot {snapshot_id} existiert nicht.")
        return SnapshotArtifacts(**dict(row))

    def save_clauses(self, snapshot_id: int, clauses: tuple[Clause, ...]) -> tuple[ClauseRecord, ...]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            for clause in clauses:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO clauses(
                      id, created_at, snapshot_id, ordinal, heading_path, text,
                      clause_hash, is_tenor_relevant
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), created_at, snapshot_id, clause.ordinal,
                        clause.heading_path, clause.text, clause.clause_hash,
                        int(clause.is_tenor_relevant),
                    ),
                )
            rows = connection.execute(
                """
                SELECT id, snapshot_id, ordinal, heading_path, text, clause_hash,
                       is_tenor_relevant
                FROM clauses WHERE snapshot_id = ? ORDER BY ordinal
                """,
                (snapshot_id,),
            ).fetchall()
        return tuple(
            ClauseRecord(
                id=row["id"], snapshot_id=row["snapshot_id"], ordinal=row["ordinal"],
                heading_path=row["heading_path"], text=row["text"],
                clause_hash=row["clause_hash"],
                is_tenor_relevant=bool(row["is_tenor_relevant"]),
            )
            for row in rows
        )

    def save_snapshot_quality(
        self, snapshot_id: int, clause_count: int, extraction_ok: bool, warning: str | None = None
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO snapshot_quality(snapshot_id, extraction_ok, clause_count, warning)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO NOTHING
                """,
                (snapshot_id, int(extraction_ok), clause_count, warning),
            )

    def save_snapshot_screenshot(
        self,
        snapshot_id: int,
        *,
        path: str | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
        error_message: str | None = None,
    ) -> SnapshotScreenshot:
        status = "failed" if error_message else "captured"
        if status == "captured" and (not path or not sha256 or size_bytes is None):
            raise ValueError("Ein erfolgreicher Screenshot benötigt Pfad, Hash und Dateigröße.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO snapshot_screenshots(
                  snapshot_id, status, path, sha256, size_bytes, error_message
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO NOTHING
                """,
                (snapshot_id, status, path, sha256, size_bytes, error_message),
            )
        return self.snapshot_screenshot(snapshot_id)

    def snapshot_screenshot(self, snapshot_id: int) -> SnapshotScreenshot:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id, status, path, sha256, size_bytes, error_message
                FROM snapshot_screenshots WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Für Snapshot {snapshot_id} ist kein Screenshot-Status gespeichert.")
        return SnapshotScreenshot(**dict(row))

    def clauses_for_snapshot(self, snapshot_id: int) -> tuple[ClauseRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, snapshot_id, ordinal, heading_path, text, clause_hash,
                       is_tenor_relevant
                FROM clauses WHERE snapshot_id = ? ORDER BY ordinal
                """,
                (snapshot_id,),
            ).fetchall()
        return tuple(
            ClauseRecord(
                id=row["id"], snapshot_id=row["snapshot_id"], ordinal=row["ordinal"],
                heading_path=row["heading_path"], text=row["text"],
                clause_hash=row["clause_hash"],
                is_tenor_relevant=bool(row["is_tenor_relevant"]),
            )
            for row in rows
        )

    def save_finding(
        self,
        *,
        snapshot_id: int,
        classification: ClauseClassification,
        model: str,
        prompt_version: str,
        case_id: str | None = None,
        tenor_id: str | None = None,
        clause_id: str | None = None,
        prev_clause_id: str | None = None,
    ) -> FindingRecord:
        finding_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO findings(
                  id, created_at, case_id, tenor_id, snapshot_id, clause_id,
                  prev_clause_id, classification, tenor_element_id, confidence,
                  evidence_quote, reasoning, model, prompt_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id, datetime.now(timezone.utc).isoformat(), case_id, tenor_id,
                    snapshot_id, clause_id, prev_clause_id, classification.classification,
                    classification.tenor_element_id, classification.confidence,
                    classification.evidence_quote, classification.reasoning, model,
                    prompt_version,
                ),
            )
        return self.finding(finding_id)

    def finding(self, finding_id: str) -> FindingRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, classification, tenor_element_id, confidence, evidence_quote,
                       reasoning, model, prompt_version, juristin_entscheidung,
                       juristin_kommentar, entschieden_von, entschieden_at
                FROM findings WHERE id = ?
                """,
                (finding_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Befund {finding_id} existiert nicht.")
        return FindingRecord(**dict(row))

    def decide_finding(
        self,
        finding_id: str,
        *,
        decision: str,
        reviewer: str,
        comment: str | None = None,
    ) -> FindingRecord:
        allowed = {"vertragsstrafe", "neue_abmahnung", "verworfen"}
        if decision not in allowed:
            raise ValueError(f"Unzulässige Juristinnen-Entscheidung: {decision!r}")
        if not reviewer.strip():
            raise ValueError("Die prüfende Person muss angegeben werden.")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE findings SET juristin_entscheidung = ?, juristin_kommentar = ?,
                  entschieden_von = ?, entschieden_at = ? WHERE id = ?
                """,
                (
                    decision, comment, reviewer.strip(),
                    datetime.now(timezone.utc).isoformat(), finding_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Befund {finding_id} existiert nicht.")
        return self.finding(finding_id)

    def _new_artifact_directory(self, url: str, kind: str) -> Path:
        url_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.artifacts / url_key / f"{stamp}-{kind}-{uuid.uuid4().hex[:8]}"
        path.mkdir(parents=True, exist_ok=False)
        return path
