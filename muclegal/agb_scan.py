"""Bridge to the slim AGB scanner in ``scanner/`` for the local BeweisLab.

The scanner stays the single source of truth for scan logic and UI, so the
Vercel deployment and the local app cannot drift apart. The local app only adds
the Evidence view, which uses the existing BeweisLab capture pipeline.
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

SCANNER_DIR = Path(__file__).resolve().parents[1] / "scanner"

# Files the browser may load from the scanner folder. Everything else (Python
# sources, fixtures, tests) stays private.
STATIC_FILES = {
    "style.css": "text/css",
    "design.css": "text/css",
    "app.js": "application/javascript",
    "evidence.js": "application/javascript",
    "muclegal-logo.png": "image/png",
}
ASSET_PREFIX = "/beweis-labor/"
FONT_SUFFIXES = {".css": "text/css", ".woff2": "font/woff2", ".txt": "text/plain"}


@lru_cache(maxsize=1)
def _api_module():
    if str(SCANNER_DIR) not in sys.path:
        sys.path.append(str(SCANNER_DIR))
    spec = importlib.util.spec_from_file_location(
        "muclegal_scanner_api", SCANNER_DIR / "api" / "index.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("AGB-Scanner nicht gefunden.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_payload(body: bytes):
    return _api_module().parse_payload(body)


def stream_events(payload: dict, step_delay: float | None = None):
    module = _api_module()
    delay = module.STEP_DELAY_SECONDS if step_delay is None else step_delay
    return module.stream_events(payload, step_delay=delay)


def index_html() -> str:
    """Scanner page under /beweis-labor/ with the local Evidence view enabled.

    The app's CSP forbids <base>, so relative asset paths are prefixed here.
    """
    html = (SCANNER_DIR / "index.html").read_text(encoding="utf-8")
    for name in STATIC_FILES:
        html = html.replace(f'="{name}"', f'="{ASSET_PREFIX}{name}"')
    html = html.replace("__APP_ORIGIN__", "")
    return html.replace("<body>", '<body data-evidence="on">', 1)


def static_file(name: str) -> tuple[Path, str] | None:
    if name in STATIC_FILES:
        return SCANNER_DIR / name, STATIC_FILES[name]
    parts = name.split("/")
    if len(parts) == 2 and parts[0] == "fonts" and "\\" not in parts[1]:
        path = SCANNER_DIR / "fonts" / parts[1]
        media_type = FONT_SUFFIXES.get(path.suffix)
        if media_type and path.is_file() and path.parent == SCANNER_DIR / "fonts":
            return path, media_type
    return None
