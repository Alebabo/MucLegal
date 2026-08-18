from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from pathlib import Path

from muclegal.fetch import FetchFailure, HttpFetcher
from muclegal.normalize import NormalizationConfig, normalize_html
from muclegal.storage import SnapshotRepository


@dataclass(frozen=True)
class CheckOutcome:
    status: str
    url: str
    snapshot_id: int
    sha256: str
    previous_sha256: str | None
    changed: bool
    needs_review: bool
    diff_path: str | None
    normalized_text_path: str

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
    diff_text: str | None = None
    if changed and previous:
        old_text = Path(previous.normalized_text_path).read_text(encoding="utf-8")
        diff_text = "".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                normalized.text.splitlines(keepends=True),
                fromfile=f"snapshot-{previous.id}",
                tofile="current",
            )
        )

    record = repository.save_success(fetched, normalized, previous_sha256, diff_text)
    return CheckOutcome(
        status="baseline_created" if previous is None else ("changed" if changed else "unchanged"),
        url=url,
        snapshot_id=record.id,
        sha256=record.normalized_sha256,
        previous_sha256=record.previous_sha256,
        changed=changed,
        needs_review=changed,
        diff_path=record.diff_path,
        normalized_text_path=record.normalized_text_path,
    )

