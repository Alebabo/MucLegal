from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


VIOLATION_TYPES = {"klausel", "element"}
ELEMENT_ERRORS = {
    "fehlt",
    "nicht_sichtbar",
    "nicht_leicht_zugaenglich",
    "falsches_ziel",
    "zusaetzliche_huerde",
}
CASE_DECISIONS = {"freigegeben", "abgelehnt", "weitere_pruefung"}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class MonitoringCaseError(ValueError):
    pass


@dataclass(frozen=True)
class MonitoringCase:
    case_id: str
    fall_id: str
    domain: str
    source_url: str
    violation_type: str
    description: str
    tenor_element: str
    monitoring_target: str
    relevant_page_types: tuple[str, ...]
    clause_text: str | None
    element_label: str | None
    element_function: str | None
    element_error: str | None
    allowed_subdomains: tuple[str, ...]
    screenshot_path: str | None
    screenshot_sha256: str | None
    erstverstoss_festgestellt_durch: str
    decision: str
    created_at: str
    decided_at: str | None

    @property
    def approved(self) -> bool:
        return self.decision == "freigegeben"

    def to_dict(self) -> dict:
        return asdict(self)


class MonitoringCaseRepository:
    """Stores manually reported violations separately from system findings."""

    def __init__(self, database_path: str | Path, artifact_root: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.artifact_root = Path(artifact_root).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
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
                CREATE TABLE IF NOT EXISTS monitoring_cases (
                    case_id TEXT PRIMARY KEY,
                    fall_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    violation_type TEXT NOT NULL CHECK (violation_type IN ('klausel', 'element')),
                    description TEXT NOT NULL,
                    tenor_element TEXT NOT NULL,
                    monitoring_target TEXT NOT NULL,
                    relevant_page_types_json TEXT NOT NULL,
                    clause_text TEXT,
                    element_label TEXT,
                    element_function TEXT,
                    element_error TEXT,
                    allowed_subdomains_json TEXT NOT NULL,
                    screenshot_path TEXT,
                    screenshot_sha256 TEXT,
                    erstverstoss_festgestellt_durch TEXT NOT NULL
                        CHECK (erstverstoss_festgestellt_durch = 'verbraucherzentrale'),
                    decision TEXT NOT NULL DEFAULT 'weitere_pruefung'
                        CHECK (decision IN ('freigegeben', 'abgelehnt', 'weitere_pruefung')),
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );
                """
            )

    def create(self, value: dict, screenshot: dict | None = None) -> MonitoringCase:
        cleaned = validate_case_input(value)
        case_id = uuid.uuid4().hex
        screenshot_path: str | None = None
        screenshot_sha256: str | None = None
        if screenshot:
            screenshot_path, screenshot_sha256 = self._save_screenshot(case_id, screenshot)
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO monitoring_cases(
                    case_id, fall_id, domain, source_url, violation_type, description,
                    tenor_element, monitoring_target, relevant_page_types_json, clause_text,
                    element_label, element_function, element_error, allowed_subdomains_json,
                    screenshot_path, screenshot_sha256, erstverstoss_festgestellt_durch,
                    decision, created_at, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                (
                    case_id,
                    cleaned["fall_id"],
                    cleaned["domain"],
                    cleaned["source_url"],
                    cleaned["violation_type"],
                    cleaned["description"],
                    cleaned["tenor_element"],
                    cleaned["monitoring_target"],
                    json.dumps(cleaned["relevant_page_types"], ensure_ascii=False),
                    cleaned.get("clause_text"),
                    cleaned.get("element_label"),
                    cleaned.get("element_function"),
                    cleaned.get("element_error"),
                    json.dumps(cleaned["allowed_subdomains"], ensure_ascii=False),
                    screenshot_path,
                    screenshot_sha256,
                    "verbraucherzentrale",
                    "weitere_pruefung",
                    created_at,
                ),
            )
        return self.get(case_id)

    def get(self, case_id: str) -> MonitoringCase:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM monitoring_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
        if row is None:
            raise KeyError(case_id)
        return _row_to_case(row)

    def list(self) -> list[MonitoringCase]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM monitoring_cases ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_case(row) for row in rows]

    def review(self, case_id: str, decision: str) -> MonitoringCase:
        if decision not in CASE_DECISIONS:
            raise MonitoringCaseError("Ungültige menschliche Fallentscheidung.")
        decided_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE monitoring_cases SET decision = ?, decided_at = ? WHERE case_id = ?",
                (decision, decided_at, case_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(case_id)
        return self.get(case_id)

    def _save_screenshot(self, case_id: str, screenshot: dict) -> tuple[str, str]:
        media_type = str(screenshot.get("media_type", "")).lower()
        if media_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise MonitoringCaseError("Screenshot muss PNG, JPEG oder WebP sein.")
        encoded = screenshot.get("data_base64")
        if not isinstance(encoded, str) or not encoded:
            raise MonitoringCaseError("Screenshot-Daten fehlen.")
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise MonitoringCaseError("Screenshot ist nicht gültig Base64-kodiert.") from exc
        if not payload or len(payload) > 10 * 1024 * 1024:
            raise MonitoringCaseError("Screenshot muss zwischen 1 Byte und 10 MB groß sein.")
        signatures = {
            "image/png": b"\x89PNG\r\n\x1a\n",
            "image/jpeg": b"\xff\xd8\xff",
            "image/webp": b"RIFF",
        }
        if not payload.startswith(signatures[media_type]):
            raise MonitoringCaseError("Dateiinhalt passt nicht zum Screenshot-Medientyp.")
        if media_type == "image/webp" and payload[8:12] != b"WEBP":
            raise MonitoringCaseError("Dateiinhalt ist kein gültiger WebP-Screenshot.")
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[media_type]
        original = SAFE_NAME.sub("-", str(screenshot.get("filename", "erstverstoss"))).strip(".-")
        name = f"{original or 'erstverstoss'}{suffix}"
        directory = (self.artifact_root / case_id).resolve()
        directory.mkdir(parents=True, exist_ok=False)
        path = (directory / name).resolve()
        path.relative_to(self.artifact_root)
        path.write_bytes(payload)
        return str(path), hashlib.sha256(payload).hexdigest()


def validate_case_input(value: dict) -> dict:
    required = (
        "fall_id",
        "domain",
        "source_url",
        "violation_type",
        "description",
        "tenor_element",
        "monitoring_target",
        "relevant_page_types",
    )
    cleaned = dict(value)
    for field in required[:-1]:
        if not isinstance(cleaned.get(field), str) or not cleaned[field].strip():
            raise MonitoringCaseError(f"Pflichtfeld {field!r} fehlt.")
        cleaned[field] = cleaned[field].strip()
    page_types = cleaned.get("relevant_page_types")
    if not isinstance(page_types, list) or not page_types or not all(
        isinstance(item, str) and item.strip() for item in page_types
    ):
        raise MonitoringCaseError("Mindestens ein relevanter Seitentyp ist erforderlich.")
    cleaned["relevant_page_types"] = [item.strip() for item in page_types]
    if cleaned["violation_type"] not in VIOLATION_TYPES:
        raise MonitoringCaseError("Verstoßtyp muss 'klausel' oder 'element' sein.")

    domain_host = _host(cleaned["domain"])
    source_host = _host(cleaned["source_url"])
    allowed = cleaned.get("allowed_subdomains", [])
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise MonitoringCaseError("allowed_subdomains muss eine Liste von Hostnamen sein.")
    allowed_hosts = tuple(sorted({_host(item) for item in allowed if item.strip()}))
    if source_host != domain_host and source_host not in allowed_hosts:
        raise MonitoringCaseError("Fundstellen-URL muss zur Domain oder freigegebenen Subdomain gehören.")
    cleaned["domain"] = domain_host
    cleaned["allowed_subdomains"] = list(allowed_hosts)

    if cleaned["violation_type"] == "klausel":
        clause_text = str(cleaned.get("clause_text") or "").strip()
        if not clause_text:
            raise MonitoringCaseError("Bei Klauselverstößen ist der beanstandete Wortlaut erforderlich.")
        cleaned["clause_text"] = clause_text
        cleaned.update(element_label=None, element_function=None, element_error=None)
    else:
        for field in ("element_label", "element_function", "element_error"):
            if not isinstance(cleaned.get(field), str) or not cleaned[field].strip():
                raise MonitoringCaseError(f"Bei Elementverstößen ist {field!r} erforderlich.")
            cleaned[field] = cleaned[field].strip()
        if cleaned["element_error"] not in ELEMENT_ERRORS:
            raise MonitoringCaseError("Unbekannte Fehlerart für das erwartete Element.")
        cleaned["clause_text"] = None
    return cleaned


def _host(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise MonitoringCaseError("Domain und Fundstelle müssen gültige öffentliche HTTP(S)-Ziele sein.")
    return parsed.hostname.lower().rstrip(".")


def _row_to_case(row: sqlite3.Row) -> MonitoringCase:
    return MonitoringCase(
        case_id=row["case_id"],
        fall_id=row["fall_id"],
        domain=row["domain"],
        source_url=row["source_url"],
        violation_type=row["violation_type"],
        description=row["description"],
        tenor_element=row["tenor_element"],
        monitoring_target=row["monitoring_target"],
        relevant_page_types=tuple(json.loads(row["relevant_page_types_json"])),
        clause_text=row["clause_text"],
        element_label=row["element_label"],
        element_function=row["element_function"],
        element_error=row["element_error"],
        allowed_subdomains=tuple(json.loads(row["allowed_subdomains_json"])),
        screenshot_path=row["screenshot_path"],
        screenshot_sha256=row["screenshot_sha256"],
        erstverstoss_festgestellt_durch=row["erstverstoss_festgestellt_durch"],
        decision=row["decision"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )
