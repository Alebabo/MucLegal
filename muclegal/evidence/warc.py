from __future__ import annotations

import os
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
    return WarcResult(str(warc_path), str(cdx_path), validation_output)


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
