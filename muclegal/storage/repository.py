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
                FROM snapshots
                WHERE url = ? AND normalizer_version = ? AND selector_config_hash = ? AND fetch_mode = ?
                ORDER BY id DESC LIMIT 1
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
                       fetched_at, normalized_sha256
                FROM snapshots WHERE id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Snapshot {snapshot_id} existiert nicht.")
        return SnapshotArtifacts(**dict(row))

    def _new_artifact_directory(self, url: str, kind: str) -> Path:
        url_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.artifacts / url_key / f"{stamp}-{kind}-{uuid.uuid4().hex[:8]}"
        path.mkdir(parents=True, exist_ok=False)
        return path
