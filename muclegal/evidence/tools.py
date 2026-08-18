from __future__ import annotations

import shutil
from pathlib import Path


KNOWN_WINDOWS_TOOLS = {
    "openssl": (
        Path("C:/Program Files/Git/mingw64/bin/openssl.exe"),
        Path("C:/Program Files/Git/usr/bin/openssl.exe"),
    ),
    "wget": (
        Path.home() / "AppData/Local/Microsoft/WinGet/Links/wget.exe",
    ),
    "warcio": (
        Path.home() / "AppData/Local/Programs/Python/Python313/Scripts/warcio.exe",
    ),
}


def find_tool(name: str) -> str:
    discovered = shutil.which(name)
    if discovered:
        return discovered
    for candidate in KNOWN_WINDOWS_TOOLS.get(name, ()):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"Benötigtes Werkzeug {name!r} wurde nicht gefunden.")

