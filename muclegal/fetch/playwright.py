from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

from muclegal.fetch.http import DEFAULT_USER_AGENT, FetchFailure, FetchResult, _detect_block_page


class PlaywrightUnavailable(RuntimeError):
    pass


class ScreenshotCaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScreenshotCapture:
    path: str
    sha256: str
    size_bytes: int
    capture_state: str = "page_content"
    state_reason: str | None = None
    interactions: tuple[dict[str, str], ...] = ()


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


def fetch_rendered_public_page(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_seconds: float = 20.0,
    request_guard: Callable[[str, str], None] | None = None,
) -> FetchResult:
    """Load a public page in Chromium and return its rendered DOM without stealth or interaction."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaywrightUnavailable(
            "Der Überprüfungsmodus benötigt Playwright und einen installierten Chromium-Browser."
        ) from exc

    blocked_requests: list[str] = []
    request_count = 0
    document_request_count = 0
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=user_agent,
                    locale="de-DE",
                )

                def route_request(route) -> None:  # noqa: ANN001
                    nonlocal request_count, document_request_count
                    browser_request = route.request
                    request_count += 1
                    if browser_request.resource_type == "document":
                        document_request_count += 1
                    if browser_request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                        route.abort()
                        return
                    try:
                        if request_guard is not None:
                            request_guard(browser_request.url, browser_request.resource_type)
                    except Exception as exc:  # Guard failures must abort, never escape the callback.
                        blocked_requests.append(str(exc))
                        route.abort()
                        return
                    route.continue_()

                context.route("**/*", route_request)
                page = context.new_page()
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(timeout_seconds * 1000),
                )
                page.wait_for_timeout(1800)
                if response is None:
                    detail = blocked_requests[0] if blocked_requests else "keine HTTP-Antwort"
                    raise FetchFailure(
                        "browser_navigation_failed",
                        f"Browser-Abruf fehlgeschlagen: {detail}.",
                        manual_review=True,
                    )
                if response.status >= 400:
                    raise FetchFailure(
                        "browser_http_error",
                        f"Browser-Abruf endete mit HTTP {response.status}.",
                        status_code=response.status,
                        manual_review=response.status in {401, 403, 407, 429},
                    )
                rendered_html = page.content()
                final_url = page.url
                runtime_user_agent = page.evaluate("navigator.userAgent")
                navigator_webdriver = page.evaluate("navigator.webdriver")
                if request_guard is not None:
                    request_guard(final_url, "document")
                protection = _detect_block_page(rendered_html)
                if protection:
                    raise FetchFailure(
                        "protected_or_login_page",
                        f"Browser-Abruf abgebrochen: {protection}",
                        status_code=response.status,
                        body=rendered_html.encode("utf-8"),
                        manual_review=True,
                    )
                response_headers = [
                    (name, value)
                    for name, value in response.all_headers().items()
                    if name.lower() not in {"content-length", "content-encoding", "content-type"}
                ]
                response_headers.extend(
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("X-MucLegal-Capture-Mode", "browser-rendered-dom"),
                    ]
                )
                redirect_chain: list[str] = []
                redirected_request = response.request
                while redirected_request.redirected_from is not None:
                    redirect_chain.append(redirected_request.url)
                    redirected_request = redirected_request.redirected_from
                redirect_chain.reverse()
            finally:
                browser.close()
    except FetchFailure:
        raise
    except PlaywrightError as exc:
        raise FetchFailure(
            "browser_navigation_failed",
            f"Browser-Abruf fehlgeschlagen: {exc}",
            manual_review=True,
        ) from exc

    body = rendered_html.encode("utf-8")
    return FetchResult(
        requested_url=url,
        final_url=final_url,
        fetched_at=fetched_at,
        status_code=response.status,
        headers=tuple(response_headers),
        redirect_chain=tuple(redirect_chain),
        body=body,
        decoded_html=rendered_html,
        fetch_mode="browser_review",
        browser_metadata={
            "erfassungsmodus": "browsergestuetzt",
            "user_agent": runtime_user_agent,
            "navigator_webdriver": navigator_webdriver,
            "automation_flags": [],
            "proxy": "keiner",
            "context": "frisch_pro_lauf",
            "storage_state": "keiner",
            "profilverzeichnis": "keines",
            "browser_engine": "Chromium",
            "request_count": request_count,
            "document_request_count": document_request_count,
            "blocked_request_count": len(blocked_requests),
        },
    )


def capture_page_screenshot(
    url: str,
    destination: str | Path,
    *,
    timeout_seconds: float = 20.0,
    user_agent: str = DEFAULT_USER_AGENT,
    request_guard: Callable[[str, str], None] | None = None,
) -> ScreenshotCapture:
    """Render a public page and store a full-page PNG with documented consent handling."""
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
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=user_agent,
                    locale="de-DE",
                )
                if request_guard is not None:
                    def route_request(route) -> None:  # noqa: ANN001
                        browser_request = route.request
                        if browser_request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                            route.abort()
                            return
                        try:
                            request_guard(browser_request.url, browser_request.resource_type)
                        except Exception:
                            route.abort()
                            return
                        route.continue_()

                    context.route("**/*", route_request)
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
                interactions = _dismiss_cookie_banner(page)
                _wait_for_visual_capture(page, timeout_seconds=timeout_seconds)
                visible_text = page.locator("body").inner_text(timeout=2_000)
                normalized_visible_text = " ".join(visible_text.lower().split())
                connectivity_markers = (
                    "keine verbindung",
                    "überprüfe deine internetverbindung",
                    "check your internet connection",
                    "you appear to be offline",
                )
                site_reports_connectivity_error = any(
                    marker in normalized_visible_text for marker in connectivity_markers
                )
                page_width = int(page.evaluate("document.documentElement.scrollWidth || 1440"))
                page_height = int(page.evaluate("document.documentElement.scrollHeight || 900"))
                maximum_height = 8_000
                capture_truncated = page_height > maximum_height
                if capture_truncated:
                    page.screenshot(
                        path=str(temporary),
                        full_page=False,
                        clip={
                            "x": 0,
                            "y": 0,
                            "width": min(max(page_width, 1), 1440),
                            "height": maximum_height,
                        },
                        type="png",
                    )
                else:
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
        capture_state=("site_connectivity_error" if site_reports_connectivity_error else (
            "page_content_truncated" if capture_truncated else "page_content"
        )),
        state_reason=(
            "Die Website selbst zeigte statt des Hauptinhalts einen Verbindungsfehler."
            if site_reports_connectivity_error else (
                "Die Seite war höher als 8.000 Pixel; die Aufnahme enthält den oberen Seitenbereich."
                if capture_truncated else None
            )
        ),
        interactions=interactions,
    )


def capture_html_screenshot(
    html: str,
    base_url: str,
    destination: str | Path,
    *,
    timeout_seconds: float = 20.0,
    user_agent: str = DEFAULT_USER_AGENT,
    request_guard: Callable[[str, str], None] | None = None,
    fallback_reason: str | None = None,
) -> ScreenshotCapture:
    """Render already fetched HTML without JavaScript when live navigation crashes."""
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
    base_element = f'<base href="{html_escape(base_url, quote=True)}">'
    if not re.search(r"<base\b", html, re.IGNORECASE):
        if re.search(r"<head\b[^>]*>", html, re.IGNORECASE):
            html = re.sub(
                r"(<head\b[^>]*>)",
                rf"\1{base_element}",
                html,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            html = f"<head>{base_element}</head>{html}"
    protection = _detect_block_page(html)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=user_agent,
                    locale="de-DE",
                    java_script_enabled=False,
                )
                def route_request(route) -> None:  # noqa: ANN001
                    browser_request = route.request
                    if browser_request.url.startswith(("data:", "blob:", "about:")):
                        route.continue_()
                        return
                    # The bytes are already stored. Loading a site's resource graph here
                    # would turn the fallback into an undocumented second web capture and
                    # can crash constrained serverless Chromium processes.
                    route.abort()

                context.route("**/*", route_request)
                page = context.new_page()
                page.set_content(
                    html,
                    wait_until="domcontentloaded",
                    timeout=int(timeout_seconds * 1000),
                )
                _wait_for_visual_capture(page, timeout_seconds=timeout_seconds)
                page_width = int(page.evaluate("document.documentElement.scrollWidth || 1440"))
                page_height = int(page.evaluate("document.documentElement.scrollHeight || 900"))
                maximum_height = 8_000
                capture_truncated = page_height > maximum_height
                if capture_truncated:
                    page.screenshot(
                        path=str(temporary),
                        full_page=False,
                        clip={
                            "x": 0,
                            "y": 0,
                            "width": min(max(page_width, 1), 1440),
                            "height": maximum_height,
                        },
                        type="png",
                    )
                else:
                    page.screenshot(path=str(temporary), full_page=True, type="png")
            finally:
                browser.close()
        temporary.replace(destination)
    except PlaywrightError as exc:
        temporary.unlink(missing_ok=True)
        if _browser_was_closed(exc):
            return _capture_html_evidence_image(
                html,
                base_url,
                destination,
                protection=protection,
                fallback_reason=fallback_reason,
                browser_error=str(exc),
            )
        raise ScreenshotCaptureError(
            f"Fallback-Screenshot aus gespeichertem HTML fehlgeschlagen: {exc}"
        ) from exc
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ScreenshotCaptureError(f"Screenshot konnte nicht gespeichert werden: {exc}") from exc

    payload = destination.read_bytes()
    if protection:
        state = "protected_http_snapshot_rendered"
        reason = f"Gespeicherte Schutzseite ohne JavaScript gerendert: {protection}"
    else:
        state = "http_snapshot_rendered"
        reason = (
            "Live-Browsernavigation wurde von Chromium beendet; der zuvor direkt "
            "abgerufene öffentliche HTML-Stand wurde ohne JavaScript gerendert."
        )
    if capture_truncated:
        reason += " Die Aufnahme wurde bei 8.000 Pixeln transparent gekürzt."
    if fallback_reason:
        reason += f" Technischer Auslöser: {fallback_reason[:500]}"
    return ScreenshotCapture(
        path=str(destination),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        capture_state=state,
        state_reason=reason,
        interactions=(),
    )


def _browser_was_closed(error: Exception) -> bool:
    message = str(error).casefold()
    return any(
        marker in message
        for marker in (
            "target page, context or browser has been closed",
            "browser has been closed",
            "browser closed",
        )
    )


def _capture_html_evidence_image(
    html: str,
    base_url: str,
    destination: Path,
    *,
    protection: str | None,
    fallback_reason: str | None,
    browser_error: str,
) -> ScreenshotCapture:
    """Create a labeled PNG from stored DOM text when Chromium itself terminates.

    This is deliberately not described as a browser screenshot. It preserves a
    human-readable view of the already captured HTML without making further requests.
    """
    try:
        from lxml import html as lxml_html
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise ScreenshotCaptureError(
            "Browserloses HTML-Beweisbild benötigt lxml und Pillow."
        ) from exc

    def font(size: int, *, bold: bool = False):  # noqa: ANN202
        candidates: list[str] = [
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        ]
        try:
            import reportlab

            reportlab_fonts = Path(reportlab.__file__).resolve().parent / "fonts"
            candidates.insert(0, str(reportlab_fonts / ("VeraBd.ttf" if bold else "Vera.ttf")))
        except ImportError:
            pass
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def wrap(draw, value: str, selected_font, maximum_width: int) -> list[str]:  # noqa: ANN001
        words = value.split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=selected_font) <= maximum_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    title = "Gespeicherter öffentlicher HTML-Stand"
    blocks: list[tuple[str, str]] = []
    try:
        document = lxml_html.fromstring(html)
        for unwanted in document.xpath(
            "//script|//style|//noscript|//template|//svg|//iframe|//object|//video|//audio|//header|//footer|//nav"
        ):
            unwanted.drop_tree()
        titles = document.xpath("//title/text()")
        if titles and " ".join(titles[0].split()):
            title = " ".join(titles[0].split())[:300]
        roots = document.xpath("//main | //article")
        content_root = max(
            roots,
            key=lambda node: len(" ".join(node.text_content().split())),
            default=document,
        )
        seen: set[str] = set()
        for node in content_root.xpath(".//h1|.//h2|.//h3|.//p|.//li|.//dt|.//dd|.//blockquote|.//address"):
            value = " ".join(node.text_content().split())
            key = value.casefold()
            if len(value) < 2 or key in seen:
                continue
            seen.add(key)
            blocks.append((str(node.tag).casefold(), value[:2_000]))
            if len(blocks) >= 320:
                break
        if not blocks:
            body = " ".join(content_root.text_content().split())
            blocks = [("p", body[index:index + 1_500]) for index in range(0, len(body), 1_500)]
    except (ValueError, TypeError):
        plain = " ".join(re.sub(r"<[^>]+>", " ", html).split())
        blocks = [("p", plain[index:index + 1_500]) for index in range(0, len(plain), 1_500)]

    width, maximum_height = 1440, 8_000
    canvas = Image.new("RGB", (width, maximum_height), "#f7f7f4")
    draw = ImageDraw.Draw(canvas)
    margin = 72
    content_width = width - (2 * margin)
    font_small = font(22)
    font_body = font(27)
    font_h3 = font(32, bold=True)
    font_h2 = font(38, bold=True)
    font_h1 = font(48, bold=True)
    font_brand = font(25, bold=True)

    draw.rectangle((0, 0, width, 86), fill="#173f38")
    draw.text((margin, 28), "MUCLEGAL  ·  BeweisLab", font=font_brand, fill="#ffffff")
    y = 118
    warning_height = 118
    draw.rounded_rectangle(
        (margin, y, width - margin, y + warning_height), radius=16,
        fill="#e8f1ed", outline="#7ca296", width=2,
    )
    legal_artifact = any(
        marker in destination.stem.casefold() for marker in ("agb", "privacy")
    )
    artifact_kind = (
        "AGB-KLAUSELANSICHT"
        if "agb" in destination.stem.casefold()
        else "DATENSCHUTZTEXT-ANSICHT"
        if "privacy" in destination.stem.casefold()
        else "HTML-BEWEISBILD"
    )
    draw.text(
        (margin + 28, y + 22),
        f"{artifact_kind} · KEIN LIVE-BROWSER-SCREENSHOT",
        font=font_brand,
        fill="#173f38",
    )
    draw.text(
        (margin + 28, y + 65),
        "Browserlos aus dem bereits gespeicherten HTML erzeugt; keine weiteren Webabrufe.",
        font=font_small,
        fill="#355e55",
    )
    y += warning_height + 34
    for line in wrap(draw, base_url, font_small, content_width):
        draw.text((margin, y), line, font=font_small, fill="#5b625e")
        y += 31
    y += 25
    for line in wrap(draw, title, font_h1, content_width):
        draw.text((margin, y), line, font=font_h1, fill="#161b19")
        y += 61
    y += 28

    truncated = False
    for tag, value in blocks:
        selected_font = font_h1 if tag == "h1" else font_h2 if tag == "h2" else font_h3 if tag == "h3" else font_body
        color = "#173f38" if tag.startswith("h") else "#252a28"
        indent = 26 if tag == "li" else 0
        prefix = "• " if tag == "li" else ""
        lines = wrap(draw, prefix + value, selected_font, content_width - indent)
        required = (len(lines) * (selected_font.size + 12)) + (32 if tag.startswith("h") else 20)
        if y + required > maximum_height - 120:
            truncated = True
            break
        for line in lines:
            draw.text((margin + indent, y), line, font=selected_font, fill=color)
            y += selected_font.size + 12
        y += 32 if tag.startswith("h") else 20

    if truncated:
        draw.rectangle((0, maximum_height - 100, width, maximum_height), fill="#e8f1ed")
        draw.text(
            (margin, maximum_height - 68),
            (
                "Ansicht bei 8.000 Pixeln gekürzt · weitere Klauseln unter der angegebenen URL"
                if legal_artifact
                else "Ansicht bei 8.000 Pixeln gekürzt · vollständiges Roh-HTML im Beweispaket"
            ),
            font=font_small,
            fill="#173f38",
        )
        final_height = maximum_height
    else:
        final_height = min(max(y + 70, 900), maximum_height)

    temporary = destination.with_name(f".{destination.stem}.tmp{destination.suffix}")
    try:
        canvas.crop((0, 0, width, final_height)).save(temporary, format="PNG", optimize=True)
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ScreenshotCaptureError(f"HTML-Beweisbild konnte nicht gespeichert werden: {exc}") from exc

    payload = destination.read_bytes()
    if protection:
        state = "protected_http_snapshot_visualized"
        reason = f"Gespeicherte Schutzseite als browserloses HTML-Beweisbild dargestellt: {protection}."
    else:
        state = "http_snapshot_visualized"
        reason = (
            "Chromium wurde von der Hosting-Laufzeit beendet. Deshalb wurde der bereits "
            "direkt abgerufene öffentliche HTML-Stand browserlos als lesbares Beweisbild "
            "dargestellt; es ist keine pixelgetreue Live-Browser-Aufnahme."
        )
    if truncated:
        reason += (
            " Die Ansicht wurde bei 8.000 Pixeln gekürzt; weitere Klauseln können "
            "unter der angegebenen URL folgen."
            if legal_artifact
            else " Die Ansicht wurde bei 8.000 Pixeln gekürzt; das Roh-HTML ist vollständig enthalten."
        )
    technical_reason = fallback_reason or browser_error
    if technical_reason:
        reason += f" Technischer Auslöser: {technical_reason[:500]}"
    return ScreenshotCapture(
        path=str(destination),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        capture_state=state,
        state_reason=reason,
        interactions=(),
    )


_COOKIE_CONTEXT_MARKERS = (
    "cookie",
    "consent",
    "datenschutz",
    "privacy",
    "tracking",
    "einwilligung",
)
_COOKIE_REJECTION_LABELS = (
    ("nur notwendige", "nur_notwendige_cookies"),
    ("nur erforderliche", "nur_notwendige_cookies"),
    ("notwendige cookies", "nur_notwendige_cookies"),
    ("erforderliche cookies", "nur_notwendige_cookies"),
    ("essential only", "nur_notwendige_cookies"),
    ("necessary only", "nur_notwendige_cookies"),
    ("optionale cookies ablehnen", "optionale_cookies_abgelehnt"),
    ("optionale ablehnen", "optionale_cookies_abgelehnt"),
    ("reject optional", "optionale_cookies_abgelehnt"),
    ("alle ablehnen", "alle_optionalen_cookies_abgelehnt"),
    ("alles ablehnen", "alle_optionalen_cookies_abgelehnt"),
    ("reject all", "alle_optionalen_cookies_abgelehnt"),
    ("decline all", "alle_optionalen_cookies_abgelehnt"),
    ("ohne zustimmung fortfahren", "ohne_optionale_zustimmung_fortgefahren"),
    ("continue without accepting", "ohne_optionale_zustimmung_fortgefahren"),
)


def _cookie_rejection_action(label: str, context: str = "") -> str | None:
    """Return a privacy-preserving action only for an unambiguous consent control."""
    normalized_label = " ".join(label.casefold().split())
    normalized_context = " ".join(context.casefold().split())
    if not normalized_label or any(
        marker in normalized_label
        for marker in ("akzept", "accept", "zustimmen", "allow all")
    ):
        return None
    for phrase, action in _COOKIE_REJECTION_LABELS:
        if phrase in normalized_label:
            return action
    if normalized_label in {"ablehnen", "reject", "decline"} and any(
        marker in normalized_context for marker in _COOKIE_CONTEXT_MARKERS
    ):
        return "optionale_cookies_abgelehnt"
    return None


def _dismiss_cookie_banner(page) -> tuple[dict[str, str], ...]:  # noqa: ANN001
    """Click at most one visible reject/necessary-only control and record the action."""
    from playwright.sync_api import Error as PlaywrightError

    candidates: list[tuple[int, object, str, str]] = []
    for frame in page.frames:
        try:
            controls = frame.locator(
                "button, [role='button'], input[type='button'], input[type='submit'], a"
            )
            count = min(controls.count(), 200)
        except PlaywrightError:
            continue
        for index in range(count):
            control = controls.nth(index)
            try:
                if not control.is_visible(timeout=100):
                    continue
                label = " ".join(
                    filter(
                        None,
                        (
                            control.inner_text(timeout=200).strip(),
                            control.get_attribute("value") or "",
                            control.get_attribute("aria-label") or "",
                            control.get_attribute("title") or "",
                        ),
                    )
                ).strip()
                context = control.evaluate(
                    """element => {
                      const root = element.closest(
                        '#onetrust-banner-sdk, [role="dialog"], [aria-modal="true"], '
                        + '[id*="cookie" i], [class*="cookie" i], '
                        + '[id*="consent" i], [class*="consent" i], '
                        + '[id*="privacy" i], [class*="privacy" i]'
                      );
                      return (root?.innerText || '').slice(0, 4000);
                    }"""
                )
                action = _cookie_rejection_action(label, str(context or ""))
                if action is None:
                    continue
                priority = next(
                    (
                        position
                        for position, (phrase, _) in enumerate(_COOKIE_REJECTION_LABELS)
                        if phrase in label.casefold()
                    ),
                    len(_COOKIE_REJECTION_LABELS),
                )
                candidates.append((priority, control, label[:300], action))
            except PlaywrightError:
                continue
    for _, control, label, action in sorted(candidates, key=lambda item: item[0]):
        try:
            control.click(timeout=1_500)
            page.wait_for_timeout(500)
            return (
                {
                    "type": "cookie_banner",
                    "action": action,
                    "button_text": label,
                },
            )
        except PlaywrightError:
            continue
    return ()


def _wait_for_visual_capture(page, *, timeout_seconds: float) -> None:  # noqa: ANN001
    """Wait for dynamic layout and trigger lazy loading after consent handling."""
    from playwright.sync_api import Error as PlaywrightError

    settle_timeout = min(int(timeout_seconds * 1000), 7_000)
    try:
        page.wait_for_load_state("networkidle", timeout=settle_timeout)
    except PlaywrightError:
        # Long-lived analytics connections are common and do not make a screenshot invalid.
        pass

    for _ in range(5):
        try:
            state = page.evaluate(
                """() => ({
                  textLength: (document.body?.innerText || '').trim().length,
                  width: document.documentElement?.scrollWidth || 0,
                  height: document.documentElement?.scrollHeight || 0
                })"""
            )
        except PlaywrightError:
            state = {"textLength": 0, "width": 0, "height": 0}
        if state["textLength"] >= 80 and state["width"] > 0 and state["height"] > 0:
            break
        page.wait_for_timeout(700)

    try:
        page_height = int(page.evaluate("document.documentElement.scrollHeight || 0"))
        viewport_height = int(page.evaluate("window.innerHeight || 900"))
        if page_height > viewport_height:
            steps = min(14, max(2, page_height // max(viewport_height, 1)))
            for index in range(1, steps + 1):
                target = int((page_height - viewport_height) * index / steps)
                page.evaluate("y => window.scrollTo(0, y)", target)
                page.wait_for_timeout(120)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)
    except PlaywrightError:
        # A navigation during settling is reported by the later screenshot operation if fatal.
        pass


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
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
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

