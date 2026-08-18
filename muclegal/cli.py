from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from muclegal.fetch import FetchFailure, FetchPolicy, HttpFetcher
from muclegal.normalize import NormalizationConfig, NormalizationError
from muclegal.pipeline import check_url
from muclegal.storage import SnapshotRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="muclegal")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Eine öffentliche URL abrufen und vergleichen")
    check.add_argument("--url", required=True)
    check.add_argument("--profile", required=True, type=Path)
    check.add_argument("--store", type=Path, default=Path(".muclegal"))
    check.add_argument("--timeout", type=float, default=10.0)
    check.add_argument("--attempts", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "check":
        return 2
    try:
        profile_data = json.loads(args.profile.read_text(encoding="utf-8"))
        config = NormalizationConfig.from_dict(profile_data)
        repository = SnapshotRepository(args.store)
        fetcher = HttpFetcher(
            FetchPolicy(timeout_seconds=args.timeout, max_attempts=max(1, args.attempts))
        )
        outcome = check_url(args.url, config, repository, fetcher)
    except (OSError, json.JSONDecodeError, TypeError, NormalizationError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except FetchFailure as exc:
        print(
            json.dumps(
                {
                    "status": "manual_review" if exc.manual_review else "fetch_failed",
                    "error_code": exc.code,
                    "error": str(exc),
                    "http_status": exc.status_code,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3 if exc.manual_review else 2
    print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2))
    return 0

