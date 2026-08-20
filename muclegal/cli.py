from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from muclegal.fetch import FetchFailure, FetchPolicy, HttpFetcher, capture_page_screenshot
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
    check.add_argument(
        "--screenshot", action="store_true", help="Zusätzlich einen Full-Page-Screenshot speichern"
    )
    demo = subparsers.add_parser("demo", help="Golden Path mit lokalen Fixtures ausführen")
    demo.add_argument("--case", choices=["kerngleich", "nicht-umfasst"], default="kerngleich")
    demo.add_argument("--store", type=Path, default=Path(".muclegal-demo"))
    demo.add_argument("--report", type=Path)
    evaluation = subparsers.add_parser("eval", help="Juristische Eval-Suite ausführen")
    evaluation.add_argument("--suite", type=Path, default=Path("fixtures/eval-suite.json"))
    evaluation.add_argument("--output", type=Path, default=Path("output/eval"))
    evaluation.add_argument("--live", action="store_true", help="Anthropic statt Offline-Fixtures")
    blind = subparsers.add_parser("blind-review", help="Blinde Prüfbögen für Juristinnen erzeugen")
    blind.add_argument("--suite", type=Path, default=Path("fixtures/eval-suite.json"))
    blind.add_argument("--output", type=Path, default=Path("output/legal-review"))
    diagnose = subparsers.add_parser(
        "diagnose-capture", help="Lokale Browser- und Ressourcen-Diagnose ausführen"
    )
    diagnose.add_argument("--output", required=True, type=Path)
    diagnose.add_argument(
        "--real", action="store_true", help="Zusätzlich die reale Matrix streng sequenziell prüfen"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "demo":
        from muclegal.demo import run_demo

        try:
            result = run_demo(args.case, args.store, report_output=args.report)
        except Exception as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0
    if args.command == "eval":
        from muclegal.evaluation import run_evaluation

        try:
            report = run_evaluation(args.suite, args.output, live=args.live)
        except Exception as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.passed else 4
    if args.command == "blind-review":
        from muclegal.legal_review import prepare_blind_review

        try:
            paths = prepare_blind_review(args.suite, args.output)
        except Exception as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps({"status": "pending_human_review", "files": paths}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "diagnose-capture":
        from muclegal.diagnostics import run_capture_diagnostics

        result = run_capture_diagnostics(args.output, include_real=args.real)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if all(
            item["status"] != "technisch_fehlgeschlagen" for item in result["results"]
        ) else 5
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
        output = outcome.to_dict()
        if args.screenshot:
            snapshot = repository.snapshot_artifacts(outcome.snapshot_id)
            destination = Path(snapshot.raw_html_path).parent / "screenshot.png"
            try:
                captured = capture_page_screenshot(args.url, destination)
                repository.save_snapshot_screenshot(
                    outcome.snapshot_id,
                    path=captured.path,
                    sha256=captured.sha256,
                    size_bytes=captured.size_bytes,
                )
                output["screenshot"] = {
                    "status": "captured",
                    "path": captured.path,
                    "sha256": captured.sha256,
                    "size_bytes": captured.size_bytes,
                }
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                repository.save_snapshot_screenshot(
                    outcome.snapshot_id, error_message=message
                )
                output["screenshot"] = {"status": "failed", "error": message}
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
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0

