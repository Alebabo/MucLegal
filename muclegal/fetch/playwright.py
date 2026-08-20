from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

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


@dataclass(frozen=True)
class DomInspectionCapture:
    path: str
    screenshot_path: str
    sha256: str
    elements: tuple[dict, ...]
    matching_elements: tuple[dict, ...]
    blocked_requests: tuple[dict, ...]
    safe_path_status: str
    manual_review_reasons: tuple[str, ...]
    safe_path: dict | None = None


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


def inspect_expected_element(
    url: str,
    destination: str | Path,
    *,
    label: str,
    function: str,
    timeout_seconds: float = 20.0,
) -> DomInspectionCapture:
    """Inspect a reported element in rendered DOM without creating external state."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaywrightUnavailable(
            "DOM-Prüfung benötigt `pip install -e .[demo]` und `playwright install chromium`."
        ) from exc

    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path = destination.with_suffix(".png")
    blocked_requests: list[dict] = []
    manual_review: list[str] = []
    elements: list[dict] = []
    safe_path_status = "kein_passender_navigationspfad"
    safe_path_evidence: dict | None = None
    origin = urlsplit(url)
    label_tokens = _tokens(label)
    function_tokens = _tokens(function)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=DEFAULT_USER_AGENT,
                    locale="de-DE",
                )

                def route_request(route) -> None:  # noqa: ANN001
                    request = route.request
                    target = urlsplit(request.url)
                    unsafe_method = request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
                    cross_origin_document = (
                        request.resource_type == "document"
                        and (target.scheme, target.netloc) != (origin.scheme, origin.netloc)
                    )
                    if unsafe_method or cross_origin_document:
                        blocked_requests.append(
                            {"method": request.method, "url": request.url, "reason": (
                                "veraendernde_methode" if unsafe_method else "fremder_ursprung"
                            )}
                        )
                        route.abort()
                    else:
                        route.continue_()

                context.route("**/*", route_request)
                page = context.new_page()
                response = page.goto(
                    url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000)
                )
                if response is None or response.status >= 400:
                    status = response.status if response is not None else "ohne Antwort"
                    raise ScreenshotCaptureError(f"DOM-Prüfung endete mit HTTP {status}.")
                candidates = page.locator(
                    "a,button,input[type=button],input[type=submit],[role=button],[role=link]"
                )
                for index in range(min(candidates.count(), 1000)):
                    item = candidates.nth(index)
                    try:
                        detail = item.evaluate(
                            """el => {
                              const style = getComputedStyle(el);
                              const rect = el.getBoundingClientRect();
                              const cx = Math.max(0, Math.min(innerWidth - 1, rect.left + rect.width / 2));
                              const cy = Math.max(0, Math.min(innerHeight - 1, rect.top + rect.height / 2));
                              const top = rect.width > 0 && rect.height > 0 ? document.elementFromPoint(cx, cy) : null;
                              const visible = style.display !== 'none' && style.visibility !== 'hidden'
                                && Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0;
                              return {
                                tag: el.tagName.toLowerCase(), role: el.getAttribute('role'),
                                text: (el.innerText || el.value || '').trim(),
                                accessible_name: (el.getAttribute('aria-label') || el.innerText || el.value
                                  || el.getAttribute('title') || '').trim(),
                                href: el.href || null, disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
                                visible, obscured: visible && top !== el && !el.contains(top),
                                bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                              };
                            }"""
                        )
                    except PlaywrightError:
                        continue
                    haystack = _tokens(
                        f"{detail.get('accessible_name', '')} {detail.get('text', '')} "
                        f"{detail.get('href', '')}"
                    )
                    label_match = bool(label_tokens) and (
                        label_tokens <= haystack
                        or len(label_tokens & haystack) / len(label_tokens) >= 0.6
                    )
                    function_match = bool(function_tokens) and (
                        function_tokens <= haystack
                        or len(function_tokens & haystack) / len(function_tokens) >= 0.6
                    )
                    detail["matches_reported_target"] = label_match or function_match
                    elements.append(detail)

                matching = [item for item in elements if item["matches_reported_target"]]
                if matching:
                    best = next(
                        (item for item in matching if item["visible"] and not item["disabled"]),
                        matching[0],
                    )
                    href = best.get("href")
                    final_markers = ("bestätigen", "zahlungspflichtig", "kostenpflichtig", "absenden")
                    if any(marker in best.get("accessible_name", "").lower() for marker in final_markers):
                        safe_path_status = "vor_finaler_aktion_gestoppt"
                        manual_review.append("Das passende Element ist eine finale Bestätigungsaktion.")
                    elif href:
                        target = urlsplit(urljoin(url, href))
                        if (target.scheme, target.netloc) == (origin.scheme, origin.netloc):
                            target_page = context.new_page()
                            try:
                                target_response = target_page.goto(
                                    target.geturl(),
                                    wait_until="domcontentloaded",
                                    timeout=int(timeout_seconds * 1000),
                                )
                                target_screenshot = destination.with_name(
                                    f"{destination.stem}-target.png"
                                )
                                target_page.screenshot(
                                    path=str(target_screenshot), full_page=True, type="png"
                                )
                                safe_path_evidence = {
                                    "source_url": url,
                                    "target_url": target_page.url,
                                    "status_code": target_response.status if target_response else None,
                                    "title": target_page.title(),
                                    "screenshot_path": str(target_screenshot),
                                    "method": "GET",
                                    "interaction": "Linkziel in isoliertem Tab geöffnet",
                                }
                                safe_path_status = "gleichurspruengliches_ziel_dokumentiert"
                            except PlaywrightError as exc:
                                safe_path_status = "zielnavigation_fehlgeschlagen"
                                manual_review.append(f"Sicheres Linkziel konnte nicht geöffnet werden: {exc}")
                            finally:
                                target_page.close()
                        else:
                            safe_path_status = "fremder_ursprung_blockiert"
                            manual_review.append("Das Zielelement führt auf einen fremden Ursprung.")
                    else:
                        safe_path_status = "interaktion_nicht_ausgefuehrt"
                        manual_review.append(
                            "Element ohne überprüfbaren Link wurde nicht aktiviert; Außenwirkung unklar."
                        )
                page.screenshot(path=str(screenshot_path), full_page=True, type="png")
            finally:
                browser.close()
    except (PlaywrightError, OSError) as exc:
        raise ScreenshotCaptureError(f"DOM-Prüfung fehlgeschlagen: {exc}") from exc

    payload = {
        "url": url,
        "reported_target": {"label": label, "function": function},
        "elements": elements,
        "matching_elements": [item for item in elements if item["matches_reported_target"]],
        "blocked_requests": blocked_requests,
        "safe_path_status": safe_path_status,
        "manual_review_reasons": manual_review,
        "safe_path": safe_path_evidence,
        "screenshot_path": str(screenshot_path),
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return DomInspectionCapture(
        path=str(destination),
        screenshot_path=str(screenshot_path),
        sha256=digest,
        elements=tuple(elements),
        matching_elements=tuple(payload["matching_elements"]),
        blocked_requests=tuple(blocked_requests),
        safe_path_status=safe_path_status,
        manual_review_reasons=tuple(manual_review),
        safe_path=safe_path_evidence,
    )


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß0-9]+", value.casefold()))

