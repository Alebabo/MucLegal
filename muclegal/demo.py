from __future__ import annotations

import json
import shutil
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from muclegal.evidence import (
    OpenSslTsaClient,
    build_pdf_report,
    capture_warc,
    create_manifest,
    verify_manifest,
)
from muclegal.evidence.wayback import record_wayback_unavailable
from muclegal.fetch import FetchPolicy, HttpFetcher
from muclegal.llm import OfflineAnalyzer, analyze_and_store
from muclegal.llm.analyzer import build_model_input
from muclegal.normalize import NormalizationConfig
from muclegal.pipeline import check_url
from muclegal.storage import SnapshotRepository


@dataclass(frozen=True)
class DemoResult:
    case_path: str
    report_path: str
    bundle_path: str
    timestamp_status: str


class _DemoHandler(BaseHTTPRequestHandler):
    page: bytes = b""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\n"
            content_type = "text/plain; charset=utf-8"
        elif self.path == "/page":
            body = type(self).page
            content_type = "text/html; charset=utf-8"
        else:
            body = b"not found"
            content_type = "text/plain; charset=utf-8"
            self.send_response(404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class _DemoServer:
    def __enter__(self):
        self.server = ThreadingHTTPServer(("0.0.0.0", 0), _DemoHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/page"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def run_demo(
    case_name: str,
    store: str | Path,
    *,
    fixtures: str | Path | None = None,
    tsa_client: OpenSslTsaClient | None = None,
    report_output: str | Path | None = None,
) -> DemoResult:
    if case_name not in {"kerngleich", "nicht-umfasst"}:
        raise ValueError("Demo-Fall muss kerngleich oder nicht-umfasst sein.")
    project_root = Path(__file__).resolve().parents[1]
    fixtures = Path(fixtures) if fixtures else project_root / "fixtures"
    store = Path(store).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    bundle = store / "bundles" / f"{stamp}-{case_name}"
    artifacts_dir = bundle / "artifacts"
    analysis_dir = bundle / "analysis"
    capture_dir = bundle / "capture"
    artifacts_dir.mkdir(parents=True, exist_ok=False)
    repository = SnapshotRepository(store / "snapshots")
    config = NormalizationConfig.from_dict(
        json.loads((fixtures / "demo-profile.json").read_text(encoding="utf-8"))
    )
    fetcher = HttpFetcher(FetchPolicy(timeout_seconds=3, max_attempts=1))
    changed_fixture = "demo-kerngleich.html" if case_name == "kerngleich" else "demo-nicht-umfasst.html"

    with _DemoServer() as server:
        _DemoHandler.page = (fixtures / "demo-before.html").read_bytes()
        check_url(server.url, config, repository, fetcher)
        _DemoHandler.page = (fixtures / changed_fixture).read_bytes()
        outcome = check_url(server.url, config, repository, fetcher)
        if not outcome.changed or not outcome.diff_path:
            raise RuntimeError("Demo-Änderung wurde nicht erkannt.")
        warc = capture_warc(server.url, capture_dir)

    snapshot = repository.snapshot_artifacts(outcome.snapshot_id)
    tenor = json.loads((fixtures / "tenor.json").read_text(encoding="utf-8"))
    case_input = json.loads((fixtures / f"llm-input-{case_name}.json").read_text(encoding="utf-8"))
    case_input["belegte_metadaten"].update(
        {
            "url": server.url,
            "erkannt_am": snapshot.fetched_at,
            "snapshot_sha256": snapshot.normalized_sha256,
        }
    )
    model_input = build_model_input(
        tenor,
        case_input["vorher"],
        case_input["nachher"],
        case_input["belegte_metadaten"],
    )
    analysis = analyze_and_store(
        model_input,
        OfflineAnalyzer(fixtures / f"llm-output-{case_name}.json"),
        analysis_dir,
    )
    if not analysis.valid or analysis.assessment is None:
        raise RuntimeError(f"Offline-Demoantwort ist ungültig: {analysis.validation_error}")

    source_artifacts = {
        "raw_html": Path(snapshot.raw_html_path),
        "response_headers": Path(snapshot.response_headers_path),
        "normalized_text": Path(snapshot.normalized_text_path),
        "diff": Path(snapshot.diff_path),
        "model_input": Path(analysis.input_path),
        "model_output": Path(analysis.output_path),
        "warc": Path(warc.warc_path),
        "cdx": Path(warc.cdx_path),
    }
    bundled_artifacts: dict[str, Path] = {}
    for label, source in source_artifacts.items():
        destination = artifacts_dir / f"{label}{source.suffix}"
        shutil.copy2(source, destination)
        bundled_artifacts[label] = destination
    wayback = record_wayback_unavailable(bundle)
    bundled_artifacts["wayback_status"] = bundle / "wayback-status.json"
    manifest = create_manifest(bundled_artifacts, bundle)
    verification = verify_manifest(manifest.manifest_path)
    if not verification.valid:
        raise RuntimeError(f"Manifestprüfung fehlgeschlagen: {verification.errors}")
    tsa_client = tsa_client or OpenSslTsaClient()
    timestamp = tsa_client.timestamp_digest(manifest.manifest_sha256, bundle / "timestamp")

    report_data = {
        "fall_id": tenor["fall_id"],
        "url": model_input["belegte_metadaten"]["url"],
        "erkannt_am": model_input["belegte_metadaten"]["erkannt_am"],
        "vorher": model_input["aenderung"]["vorher"],
        "nachher": model_input["aenderung"]["nachher"],
        "assessment": analysis.assessment.to_dict(),
        "evidence": {
            "warc_status": "valide (warcio check)",
            "manifest_sha256": manifest.manifest_sha256,
            "chain_head_sha256": manifest.chain_head_sha256,
            "timestamp_status": timestamp.status,
            "wayback_status": wayback.status,
        },
    }
    report_destination = Path(report_output) if report_output else bundle / "pruefbericht.pdf"
    report_path = Path(build_pdf_report(report_data, report_destination))
    case_record = {
        **report_data,
        "case_name": case_name,
        "analysis_mode": analysis.mode,
        "freigabe_durch_mensch": None,
        "artifacts": {
            **{label: str(path) for label, path in bundled_artifacts.items()},
            "manifest": manifest.manifest_path,
            "manifest_digest": manifest.digest_path,
            "timestamp_query": timestamp.query_path,
            "timestamp_response": timestamp.response_path,
            "report": str(report_path),
        },
    }
    case_path = bundle / "case.json"
    case_path.write_text(
        json.dumps(case_record, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    latest_path = store / "latest-case.json"
    latest_path.write_text(case_path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return DemoResult(str(latest_path), str(report_path), str(bundle), timestamp.status)
