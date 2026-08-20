from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from muclegal.fetch import FetchPolicy, HttpFetcher


REAL_MATRIX = (
    "https://www.temu.com/de",
    "https://mirageperfume.com/",
    "https://www.ikea.com/de/de/",
    "https://www.mcfit.com/",
    "https://www.mediamarkt.de/",
    "https://example.com/",
)


class _DiagnosticHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = (
            "<!doctype html><style>html,body{margin:0}main{height:30000px;background:#eef}"
            "footer{position:absolute;top:29950px}</style><main><h1>Diagnose</h1>"
            "<details><summary>Klausel öffnen</summary><p>Diagnoseklausel</p></details>"
            "<footer>FOOTER-MARKER</footer></main>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def run_capture_diagnostics(output: str | Path, *, include_real: bool = False) -> dict:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DiagnosticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rows.append(_capture_one(f"http://127.0.0.1:{server.server_port}/", output, False))
    finally:
        server.shutdown()
        thread.join(timeout=2)
    if include_real:
        for url in REAL_MATRIX:
            rows.append(_capture_one(url, output, True))
    report = {
        "version": 1,
        "mode": "synthetic_and_real_sequential" if include_real else "synthetic_offline",
        "results": rows,
    }
    metrics = output / "capture-metrics.json"
    metrics.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = output / "capture-diagnostics.md"
    lines = [
        "# Lokale Capture-Diagnose",
        "",
        "| URL | Status | Dauer | Abbruchphase |",
        "|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['url']} | {row['status']} | {row['duration_seconds']:.3f} s | "
            f"{row.get('failure_phase') or '—'} |"
        )
    lines.extend(
        [
            "",
            "Nicht messbare Werte werden in den zugehörigen `resource-metrics.json`-Dateien "
            "als `not_available` mit Begründung ausgewiesen.",
        ]
    )
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"metrics": str(metrics), "report": str(markdown), "results": rows}


def _capture_one(url: str, output: Path, public_network: bool) -> dict:
    started = time.perf_counter()
    fetcher = HttpFetcher(
        FetchPolicy(
            timeout_seconds=20,
            max_attempts=1,
            require_public_network=public_network,
        )
    )
    try:
        if public_network:
            fetcher.fetch(url)
        with fetcher.capture_session(output / "capture-runs") as controller:
            captured = controller.capture_target(url, role="main")
        return {
            "url": url,
            "status": captured.capture_completeness,
            "duration_seconds": time.perf_counter() - started,
            "failure_phase": captured.failure_phase,
            "artifact_directory": captured.artifact_directory,
        }
    except Exception as exc:
        return {
            "url": url,
            "status": "technisch_fehlgeschlagen",
            "duration_seconds": time.perf_counter() - started,
            "failure_phase": "diagnose",
            "error": f"{type(exc).__name__}: {exc}",
        }

