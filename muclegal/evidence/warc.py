from __future__ import annotations

import os
import hashlib
import json
from io import BytesIO
from http import HTTPStatus
from datetime import datetime
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib import parse

from muclegal.evidence.tools import find_tool
from muclegal.fetch.http import DEFAULT_USER_AGENT


@dataclass(frozen=True)
class WarcResult:
    warc_path: str
    cdx_path: str
    validation_output: str
    response_payload_sha256: str | None = None


def capture_warc(
    url: str,
    output_directory: str | Path,
    *,
    basename: str = "capture",
    wget_path: str | None = None,
    warcio_path: str | None = None,
) -> WarcResult:
    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    effective_url = url
    command_prefix: list[str]
    if wget_path:
        command_prefix = [wget_path]
    elif os.name == "nt" and shutil.which("wsl.exe") and _wsl_has_wget():
        command_prefix = ["wsl.exe", "--cd", str(output_directory), "wget"]
        effective_url = _translate_windows_loopback_for_wsl(url)
    else:
        command_prefix = [find_tool("wget")]
    command = [
        *command_prefix,
        f"--warc-file={basename}",
        "--warc-cdx",
        "--page-requisites",
        "--span-hosts",
        "--timeout=10",
        "--tries=2",
        "--waitretry=1",
        f"--user-agent={DEFAULT_USER_AGENT}",
        "--no-verbose",
        effective_url,
    ]
    completed = subprocess.run(
        command,
        cwd=output_directory,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Wget-WARC-Abruf fehlgeschlagen: {completed.stderr.strip()}")
    warc_path = output_directory / f"{basename}.warc.gz"
    cdx_path = output_directory / f"{basename}.cdx"
    if not warc_path.is_file() or not cdx_path.is_file():
        raise RuntimeError("Wget hat WARC oder CDX nicht erzeugt.")
    validation_output = validate_warc(warc_path, warcio_path=warcio_path)
    payload_sha256 = response_payload_sha256(warc_path, url)
    return WarcResult(str(warc_path), str(cdx_path), validation_output, payload_sha256)


def capture_snapshot_warc(
    url: str,
    output_directory: str | Path,
    *,
    raw_html_path: str | Path,
    response_headers_path: str | Path,
    final_url: str,
    fetched_at: str,
    status_code: int,
    basename: str = "capture",
    warcio_path: str | None = None,
) -> WarcResult:
    """Create the primary WARC from the exact response bytes already vetted and stored."""
    try:
        from warcio.statusandheaders import StatusAndHeaders
        from warcio.warcwriter import WARCWriter
    except ImportError as exc:
        raise RuntimeError("WARC-Erzeugung benötigt `pip install -e .[demo]`.") from exc
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = Path(raw_html_path).read_bytes()
    headers_value = json.loads(Path(response_headers_path).read_text(encoding="utf-8"))
    headers = [(str(name), str(value)) for name, value in headers_value]
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        phrase = "Response"
    http_headers = StatusAndHeaders(
        f"{status_code} {phrase}", headers, protocol="HTTP/1.1"
    )
    warc_path = output / f"{basename}.warc.gz"
    with warc_path.open("wb") as stream:
        writer = WARCWriter(stream, gzip=True)
        record = writer.create_warc_record(
            final_url or url,
            "response",
            payload=BytesIO(body),
            http_headers=http_headers,
            warc_headers_dict={"WARC-Date": fetched_at},
        )
        try:
            writer.write_record(record)
        finally:
            record.raw_stream.close()
    digest = hashlib.sha256(body).hexdigest()
    try:
        timestamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).strftime(
            "%Y%m%d%H%M%S"
        )
    except ValueError:
        timestamp = "-"
    cdx_path = output / f"{basename}.cdx"
    cdx_path.write_text(
        " CDX N b a m s k r M S V g\n"
        f"{final_url or url} {timestamp} {final_url or url} text/html {status_code} "
        f"sha256:{digest} - - - - {warc_path.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    validation_output = validate_warc(warc_path, warcio_path=warcio_path)
    return WarcResult(str(warc_path), str(cdx_path), validation_output, digest)


def response_payload_sha256(warc_path: str | Path, target_url: str) -> str | None:
    """Hash the captured HTTP response body for the requested URL, if present."""
    try:
        from warcio.archiveiterator import ArchiveIterator
    except ImportError as exc:
        raise RuntimeError("WARC-Auswertung benötigt `pip install -e .[demo]`.") from exc
    target = parse.urlsplit(target_url)
    path_match: str | None = None
    with Path(warc_path).open("rb") as stream:
        for record in ArchiveIterator(stream):
            if record.rec_type != "response":
                continue
            uri = record.rec_headers.get_header("WARC-Target-URI")
            digest = hashlib.sha256(record.content_stream().read()).hexdigest()
            if uri == target_url:
                return digest
            parsed = parse.urlsplit(uri or "")
            if (parsed.path, parsed.query) == (target.path, target.query):
                path_match = digest
    return path_match


def _wsl_has_wget() -> bool:
    probe = subprocess.run(
        ["wsl.exe", "-e", "sh", "-lc", "command -v wget"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return probe.returncode == 0


def _translate_windows_loopback_for_wsl(url: str) -> str:
    parsed = parse.urlsplit(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return url
    gateway = subprocess.run(
        ["wsl.exe", "-e", "sh", "-lc", "ip route show default | awk '{print $3}'"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    if not gateway:
        raise RuntimeError("WSL-Gateway für lokalen WARC-Test wurde nicht gefunden.")
    port = f":{parsed.port}" if parsed.port else ""
    return parse.urlunsplit((parsed.scheme, f"{gateway}{port}", parsed.path, parsed.query, parsed.fragment))


def validate_warc(warc_path: str | Path, *, warcio_path: str | None = None) -> str:
    warcio_path = warcio_path or find_tool("warcio")
    completed = subprocess.run(
        [warcio_path, "check", "-v", str(Path(warc_path).resolve())],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if completed.returncode != 0:
        raise RuntimeError(f"WARC-Validierung fehlgeschlagen: {output}")
    return output
