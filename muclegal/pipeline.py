from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from pathlib import Path

from muclegal.fetch import FetchFailure, HttpFetcher
from muclegal.normalize import NormalizationConfig, normalize_html, split_clauses
from muclegal.storage import SnapshotRepository


@dataclass(frozen=True)
class CheckOutcome:
    status: str
    url: str
    snapshot_id: int
    previous_snapshot_id: int | None
    sha256: str
    previous_sha256: str | None
    changed: bool
    needs_review: bool
    diff_path: str | None
    normalized_text_path: str
    previous_normalized_text_path: str | None
    clause_count: int
    extraction_ok: bool
    warning: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def check_url(
    url: str,
    config: NormalizationConfig,
    repository: SnapshotRepository,
    fetcher: HttpFetcher | None = None,
) -> CheckOutcome:
    fetcher = fetcher or HttpFetcher()
    try:
        fetched = fetcher.fetch(url)
    except FetchFailure as failure:
        repository.save_failure(url, failure)
        raise

    normalized = normalize_html(fetched.decoded_html, config)
    previous = repository.latest_compatible(
        url,
        normalized.normalizer_version,
        normalized.selector_config_hash,
        fetched.fetch_mode,
    )
    previous_sha256 = previous.normalized_sha256 if previous else None
    changed = previous is not None and previous_sha256 != normalized.sha256
    clauses = split_clauses(normalized.text)
    extraction_ok = True
    warning: str | None = None
    diff_text: str | None = None
    old_text: str | None = None
    if previous:
        old_text = Path(previous.normalized_text_path).read_text(encoding="utf-8")
        previous_clauses = split_clauses(old_text)
        if len(old_text.strip()) >= 200 and len(normalized.text.strip()) < 200:
            extraction_ok = False
            warning = "Extraktion ist verdächtig kurz (< 200 Zeichen nach zuvor längerem Dokument)."
        elif previous_clauses and len(clauses) < len(previous_clauses) / 2:
            extraction_ok = False
            warning = "Klauselzahl ist gegenüber dem letzten erfolgreichen Lauf um mehr als 50 % gefallen."
    if changed and previous and extraction_ok and old_text is not None:
        diff_text = "".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                normalized.text.splitlines(keepends=True),
                fromfile=f"snapshot-{previous.id}",
                tofile="current",
            )
        )

    record = repository.save_success(fetched, normalized, previous_sha256, diff_text)
    repository.save_clauses(record.id, clauses)
    repository.save_snapshot_quality(record.id, len(clauses), extraction_ok, warning)
    return CheckOutcome(
        status=(
            "extraction_failed"
            if not extraction_ok
            else ("baseline_created" if previous is None else ("changed" if changed else "unchanged"))
        ),
        url=url,
        snapshot_id=record.id,
        previous_snapshot_id=previous.id if previous else None,
        sha256=record.normalized_sha256,
        previous_sha256=record.previous_sha256,
        changed=changed,
        needs_review=changed or not extraction_ok,
        diff_path=record.diff_path,
        normalized_text_path=record.normalized_text_path,
        previous_normalized_text_path=previous.normalized_text_path if previous else None,
        clause_count=len(clauses),
        extraction_ok=extraction_ok,
        warning=warning,
    )

