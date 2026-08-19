from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from muclegal.fetch.http import DEFAULT_USER_AGENT


class PlaywrightUnavailable(RuntimeError):
    pass


class ScreenshotCaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScreenshotCapture:
    path: str
    sha256: str
    size_bytes: int


def capture_page_screenshot(
    url: str,
    destination: str | Path,
    *,
    timeout_seconds: float = 20.0,
) -> ScreenshotCapture:
    """Render a public page and store an unmodified full-page PNG locally."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaywrightUnavailable(
            "Screenshots benötigen `pip install -e .[demo]` und `playwright install chromium`."
        ) from exc

    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.tmp{destination.suffix}")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=DEFAULT_USER_AGENT,
                    locale="de-DE",
                )
                page = context.new_page()
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(timeout_seconds * 1000),
                )
                if response is None:
                    raise ScreenshotCaptureError("Browsernavigation lieferte keine HTTP-Antwort.")
                if response.status >= 400:
                    raise ScreenshotCaptureError(
                        f"Browsernavigation endete mit HTTP {response.status}."
                    )
                page.screenshot(path=str(temporary), full_page=True, type="png")
            finally:
                browser.close()
        temporary.replace(destination)
    except ScreenshotCaptureError:
        temporary.unlink(missing_ok=True)
        raise
    except PlaywrightError as exc:
        temporary.unlink(missing_ok=True)
        raise ScreenshotCaptureError(f"Playwright-Screenshot fehlgeschlagen: {exc}") from exc
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ScreenshotCaptureError(f"Screenshot konnte nicht gespeichert werden: {exc}") from exc

    payload = destination.read_bytes()
    return ScreenshotCapture(
        path=str(destination),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def fetch_with_playwright(url: str) -> None:
    """Compatibility placeholder; browser fetching is never selected automatically."""
    raise PlaywrightUnavailable(
        f"Für {url!r} ist kein Browser-Abruf konfiguriert. "
        "Der HTTP-Modus wird niemals automatisch gewechselt."
    )

