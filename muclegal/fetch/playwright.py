from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import statistics
import tempfile
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

from muclegal.fetch.http import DEFAULT_USER_AGENT, FetchFailure, FetchResult, _detect_block_page
from muclegal.fetch.consent import handle_consent


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
    preview_path: str | None = None
    index_path: str | None = None
    tile_paths: tuple[str, ...] = ()
    artifact_directory: str | None = None
    capture_completeness: str = "vollstaendig_erfasst"
    metrics_path: str | None = None


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


@dataclass(frozen=True)
class BrowserTargetCapture:
    fetch_result: FetchResult
    screenshot: ScreenshotCapture | None
    artifact_directory: str
    capture_completeness: str
    failure_phase: str | None = None


class CaptureRunController:
    """One Chromium process per run and one fresh, non-persistent context per target."""

    launch_args = ("--disable-dev-shm-usage",)

    def __init__(
        self,
        output_root: str | Path,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 20.0,
        request_guard: Callable[[str, str], None] | None = None,
        after_initial_hook: Callable[[object, Path], None] | None = None,
    ) -> None:
        self.output_root = Path(output_root).resolve()
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.request_guard = request_guard
        self.after_initial_hook = after_initial_hook
        self.run_id = uuid.uuid4().hex
        self.run_root = self.output_root / self.run_id
        self.run_root.mkdir(parents=True, exist_ok=False)
        self._playwright_manager = None
        self._playwright = None
        self._browser = None
        self._cache: dict[str, BrowserTargetCapture] = {}
        self.browser_starts = 0
        self.contexts = 0
        self.pages = 0
        self.started_at = time.perf_counter()

    def __enter__(self) -> "CaptureRunController":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlaywrightUnavailable(
                "Der lokale Erfassungslauf benötigt Playwright und Chromium."
            ) from exc
        self._playwright_manager = sync_playwright()
        self._playwright = self._playwright_manager.__enter__()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=list(self.launch_args),
        )
        self.browser_starts = 1
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._playwright_manager is not None:
                self._playwright_manager.__exit__(exc_type, exc, traceback)

    def capture_target(self, url: str, *, role: str = "main") -> BrowserTargetCapture:
        if url in self._cache:
            return self._cache[url]
        if self._browser is None:
            raise RuntimeError("CaptureRunController muss als Kontextmanager verwendet werden.")
        role_slug = re.sub(r"[^a-z0-9_-]+", "-", role.casefold()).strip("-") or "page"
        target_root = self.run_root / f"{len(self._cache) + 1:02d}-{role_slug}"
        target_root.mkdir(parents=True, exist_ok=False)
        result = self._capture_new_context(url, role, target_root)
        self._cache[url] = result
        return result

    def _capture_new_context(
        self, url: str, role: str, target_root: Path
    ) -> BrowserTargetCapture:
        from playwright.sync_api import Error as PlaywrightError

        process_samples = [_process_sample()]
        phase_started = time.perf_counter()
        phase_durations: dict[str, float] = {}
        request_counts: dict[str, int] = {}
        transferred_bytes = 0
        transferred_unknown = 0
        blocked_requests: list[dict[str, str]] = []
        interactions: list[dict] = []
        initial: dict | None = None
        failure_phase: str | None = None
        failure_message: str | None = None
        screenshot: ScreenshotCapture | None = None
        context = None
        page = None
        try:
            context = self._browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=self.user_agent,
                locale="de-DE",
            )
            self.contexts += 1

            def route_request(route) -> None:  # noqa: ANN001
                browser_request = route.request
                resource_type = browser_request.resource_type
                request_counts[resource_type] = request_counts.get(resource_type, 0) + 1
                if browser_request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                    blocked_requests.append({"url": browser_request.url, "reason": "method"})
                    route.abort()
                    return
                try:
                    if self.request_guard is not None:
                        self.request_guard(browser_request.url, resource_type)
                except Exception as exc:
                    blocked_requests.append({"url": browser_request.url, "reason": str(exc)})
                    route.abort()
                    return
                route.continue_()

            def record_response(response) -> None:  # noqa: ANN001
                nonlocal transferred_bytes, transferred_unknown
                try:
                    value = response.headers.get("content-length")
                    if value and value.isdigit():
                        transferred_bytes += int(value)
                    else:
                        transferred_unknown += 1
                except PlaywrightError:
                    transferred_unknown += 1

            context.route("**/*", route_request)
            page = context.new_page()
            self.pages += 1
            page.on("response", record_response)
            failure_phase = "navigation_domcontentloaded"
            navigation_started = time.perf_counter()
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(self.timeout_seconds * 1000),
            )
            phase_durations["navigation_domcontentloaded"] = time.perf_counter() - navigation_started
            if response is None:
                raise ScreenshotCaptureError("Browsernavigation lieferte keine HTTP-Antwort.")
            failure_phase = "initialzustand_sichern"
            initial = _capture_initial_state(page, response, url)
            _write_initial_artifacts(target_root, initial)
            process_samples.append(_process_sample())
            if self.after_initial_hook is not None:
                self.after_initial_hook(page, target_root)
            phase_durations["initialzustand_sichern"] = (
                time.perf_counter() - navigation_started
                - phase_durations["navigation_domcontentloaded"]
            )
            if int(initial["status_code"]) >= 400:
                raise ScreenshotCaptureError(
                    f"Browsernavigation endete mit HTTP {initial['status_code']}."
                )

            failure_phase = "consent"
            consent = handle_consent(
                page, str(target_root / "screenshot-before-consent.png")
            )
            interactions.append(consent)
            _write_text(target_root / "dom-after-consent.html", page.content())
            _write_text(
                target_root / "visible-text-after-consent.txt", _visible_text(page)
            )
            phase_durations["consent"] = time.perf_counter() - navigation_started - sum(
                phase_durations.values()
            )
            process_samples.append(_process_sample())

            failure_phase = "expansion"
            legal_expansion_summary: dict[str, object] | None = None
            if role in {"agb", "privacy", "datenschutz"}:
                expansion_records = _expand_legal_controls(page)
                interactions.extend(expansion_records)
                legal_expansion_summary = _legal_expansion_summary(
                    page, expansion_records
                )
            _write_text(target_root / "dom-after-expansion.html", page.content())
            final_text = _visible_text(page)
            _write_text(target_root / "visible-text-final.txt", final_text)
            final_evidence_text = (
                _legal_container_text(page)
                if role in {"agb", "privacy", "datenschutz"}
                else final_text
            )
            expanded_blocks = [
                {
                    "target_text": str(record.get("target_text", "")),
                    "aria_controls": record.get("aria_controls"),
                    "text": str(record.get("expanded_text", "")),
                    "changed": bool(record.get("changed")),
                }
                for record in interactions
                if record.get("type") == "legal_expansion"
                and str(record.get("expanded_text", "")).strip()
            ]
            if role in {"agb", "privacy", "datenschutz"}:
                _write_json(
                    target_root / "expanded-legal-blocks.json",
                    {"blocks": expanded_blocks},
                )
            evidence_text = _merge_evidence_text(
                final_evidence_text,
                *(block["text"] for block in expanded_blocks),
            )
            normalized_text = "\n".join(
                line.strip() for line in evidence_text.splitlines() if line.strip()
            )
            visible_blocks = [line for line in evidence_text.splitlines() if line.strip()]
            included_blocks = [line for line in normalized_text.splitlines() if line.strip()]
            coverage_ratio = (
                len(included_blocks) / len(visible_blocks) if visible_blocks else 0.0
            )
            _write_text(target_root / "normalized-text.txt", normalized_text)
            _write_json(
                target_root / "clauses.json",
                {
                    "clauses": _simple_clauses(normalized_text),
                    "source": "visible-text-final_and_sequential_expansions",
                },
            )
            _write_json(
                target_root / "content-coverage.json",
                {
                    "method": "semantic_main_container_visible_text",
                    "normalized_visible_blocks": len(visible_blocks),
                    "included_blocks": len(included_blocks),
                    "coverage_ratio": coverage_ratio,
                    "omitted_blocks": [],
                    "legal_expansion": legal_expansion_summary,
                },
            )
            phase_durations["expansion"] = time.perf_counter() - navigation_started - sum(
                phase_durations.values()
            )
            process_samples.append(_process_sample())

            failure_phase = "screenshot"
            _wait_for_visual_capture(page, timeout_seconds=self.timeout_seconds)
            screenshot = _capture_validated_screenshots(page, target_root, interactions)
            if role in {"agb", "privacy", "datenschutz"}:
                _capture_expanded_legal_print_pdf(
                    page,
                    target_root,
                    legal_expansion_summary or {},
                    expanded_blocks,
                    normalized_text,
                )
            expansion_incomplete = bool(
                legal_expansion_summary
                and not legal_expansion_summary.get("complete", False)
            )
            if role in {"agb", "privacy", "datenschutz"} and (
                coverage_ratio < 0.98 or expansion_incomplete
            ):
                reason = (
                    f"Rechtstextabdeckung {coverage_ratio:.1%} liegt unter 98 %."
                    if coverage_ratio < 0.98
                    else "Nicht alle erkannten Rechtstext-Akkordeons konnten geöffnet werden."
                )
                screenshot = replace(
                    screenshot,
                    capture_state="page_content_truncated",
                    state_reason=reason,
                    capture_completeness="teilweise_erfasst",
                )
            phase_durations["screenshot"] = time.perf_counter() - navigation_started - sum(
                phase_durations.values()
            )
            process_samples.append(_process_sample())
            failure_phase = None
        except PlaywrightError as exc:
            failure_message = f"{type(exc).__name__}: {exc}"
            if not (initial and _browser_was_closed(exc)):
                raise ScreenshotCaptureError(
                    f"Browser-Abruf fehlgeschlagen in Phase {failure_phase}: {exc}"
                ) from exc
        except ScreenshotCaptureError as exc:
            failure_message = f"{type(exc).__name__}: {exc}"
            if initial is None:
                raise
        finally:
            try:
                if page is not None:
                    page.close()
            except PlaywrightError:
                pass
            finally:
                try:
                    if context is not None:
                        context.close()
                except PlaywrightError:
                    pass

        if initial is None:
            raise ScreenshotCaptureError("Kein Initialzustand konnte gesichert werden.")
        normalized_path = target_root / "normalized-text.txt"
        if not normalized_path.is_file():
            _write_text(normalized_path, _normalized_html_text(initial["dom"]))
        protection = _detect_block_page(initial["dom"])
        if protection:
            completeness = "durch_seitenschutz_begrenzt"
        elif failure_message or screenshot is None or not initial["raw_response"]:
            completeness = "teilweise_erfasst"
        else:
            completeness = screenshot.capture_completeness
        process_samples.append(_process_sample())
        rss_values = [
            int(sample["rss_bytes"])
            for sample in process_samples
            if isinstance(sample.get("rss_bytes"), int)
        ]
        handles = [
            int(sample["handles"])
            for sample in process_samples
            if isinstance(sample.get("handles"), int)
        ]
        stored_files = [path for path in target_root.rglob("*") if path.is_file()]
        metrics = {
            "duration_seconds": round(time.perf_counter() - phase_started, 6),
            "phase_durations_seconds": {
                key: round(max(0.0, value), 6) for key, value in phase_durations.items()
            },
            "python_rss_bytes": (
                {
                    "average": round(statistics.fmean(rss_values)),
                    "maximum": max(rss_values),
                    "samples": rss_values,
                }
                if rss_values
                else {"value": "not_available", "reason": "psutil lieferte keine RSS-Probe."}
            ),
            "python_cpu_time_seconds": {
                "start": {
                    "user": process_samples[0].get("cpu_user_seconds"),
                    "system": process_samples[0].get("cpu_system_seconds"),
                },
                "end": {
                    "user": process_samples[-1].get("cpu_user_seconds"),
                    "system": process_samples[-1].get("cpu_system_seconds"),
                },
            },
            "python_peak_handles_or_fds": max(handles) if handles else {
                "value": "not_available",
                "reason": "psutil lieferte keine Handle-/FD-Probe.",
            },
            "chromium_peak_rss_bytes": {
                "value": "not_available",
                "reason": "Playwright stellt unter Windows keine stabile Chromium-PID bereit.",
            },
            "requests_by_resource_type": request_counts,
            "transferred_bytes_from_content_length": transferred_bytes,
            "responses_without_content_length": transferred_unknown,
            "temporary_storage_bytes": sum(path.stat().st_size for path in stored_files),
            "raw_response_bytes": (target_root / "raw-response.bin").stat().st_size,
            "dom_initial_bytes": (target_root / "dom-initial.html").stat().st_size,
            "dom_final_bytes": (
                (target_root / "dom-after-expansion.html").stat().st_size
                if (target_root / "dom-after-expansion.html").is_file()
                else {"value": "not_available", "reason": "Browser endete vor dem Finalzustand."}
            ),
            "browser_starts": self.browser_starts,
            "contexts": self.contexts,
            "pages": self.pages,
            "failure_phase": failure_phase,
            "failure_message": failure_message,
        }
        metrics_path = target_root / "resource-metrics.json"
        _write_json(metrics_path, metrics)
        _write_json(target_root / "interactions.json", {"interactions": interactions})
        browser_metadata = {
            "erfassungsmodus": "browsergestuetzt",
            "user_agent": initial["user_agent"],
            "navigator_webdriver": initial["navigator_webdriver"],
            "automation_flags": [],
            "proxy": "keiner",
            "context": "frisch_pro_ziel_url",
            "storage_state": "keiner",
            "profilverzeichnis": "keines",
            "browser_engine": "Chromium",
            "browser_version": self._browser.version,
            "launch_args": list(self.launch_args),
            "request_count": sum(request_counts.values()),
            "document_request_count": request_counts.get("document", 0),
            "blocked_request_count": len(blocked_requests),
            "capture_artifact_directory": str(target_root),
            "capture_completeness": completeness,
            "failure_phase": failure_phase,
            "failure_message": failure_message,
        }
        _write_json(target_root / "browser-metadata.json", browser_metadata)
        headers = tuple(initial["headers"].items()) + (
            ("X-MucLegal-Capture-Mode", "browser-rendered-dom"),
        )
        fetch_result = FetchResult(
            requested_url=url,
            final_url=initial["final_url"],
            fetched_at=initial["captured_at"],
            status_code=int(initial["status_code"]),
            headers=headers,
            redirect_chain=tuple(initial["redirect_chain"]),
            body=initial["dom"].encode("utf-8"),
            decoded_html=initial["dom"],
            fetch_mode="browser_review",
            browser_metadata=browser_metadata,
        )
        return BrowserTargetCapture(
            fetch_result=fetch_result,
            screenshot=screenshot,
            artifact_directory=str(target_root),
            capture_completeness=completeness,
            failure_phase=failure_phase,
        )


def _capture_initial_state(page, response, requested_url: str) -> dict:  # noqa: ANN001
    redirect_chain: list[str] = []
    redirected_request = response.request
    while redirected_request.redirected_from is not None:
        redirect_chain.append(redirected_request.url)
        redirected_request = redirected_request.redirected_from
    redirect_chain.reverse()
    try:
        raw_response = response.body()
        raw_response_source = "playwright_document_response_body"
    except Exception as exc:
        raw_response = b""
        raw_response_source = f"not_available:{type(exc).__name__}:{exc}"
    snapshot = page.evaluate(
        """() => ({
          title: document.title,
          dom: document.documentElement?.outerHTML || '',
          visibleText: document.body?.innerText || '',
          userAgent: navigator.userAgent,
          navigatorWebdriver: navigator.webdriver,
          viewport: {width: window.innerWidth, height: window.innerHeight},
          scrollWidth: document.documentElement?.scrollWidth || 0,
          scrollHeight: document.documentElement?.scrollHeight || 0
        })"""
    )
    return {
        "requested_url": requested_url,
        "final_url": page.url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status_code": response.status,
        "headers": response.all_headers(),
        "redirect_chain": redirect_chain,
        "title": snapshot["title"],
        "dom": snapshot["dom"],
        "visible_text": snapshot["visibleText"],
        "dimensions": {
            "viewport": snapshot["viewport"],
            "scrollWidth": snapshot["scrollWidth"],
            "scrollHeight": snapshot["scrollHeight"],
        },
        "user_agent": snapshot["userAgent"],
        "navigator_webdriver": snapshot["navigatorWebdriver"],
        "raw_response": raw_response,
        "raw_response_source": raw_response_source,
    }


def _write_initial_artifacts(root: Path, state: dict) -> None:
    _write_json(
        root / "request.json",
        {
            "requested_url": state["requested_url"],
            "final_url": state["final_url"],
            "captured_at": state["captured_at"],
            "status_code": state["status_code"],
            "redirect_chain": state["redirect_chain"],
            "title": state["title"],
            "viewport": state["dimensions"]["viewport"],
            "scrollWidth": state["dimensions"]["scrollWidth"],
            "scrollHeight": state["dimensions"]["scrollHeight"],
            "user_agent": state["user_agent"],
            "navigator_webdriver": state["navigator_webdriver"],
            "raw_response_source": state["raw_response_source"],
        },
    )
    _write_json(root / "response-headers.json", state["headers"])
    _write_bytes(root / "raw-response.bin", state["raw_response"])
    _write_text(root / "raw.html", state["dom"])
    _write_text(root / "dom-initial.html", state["dom"])
    _write_text(root / "visible-text-initial.txt", state["visible_text"])


def _visible_text(page) -> str:  # noqa: ANN001
    return page.locator("body").inner_text(timeout=2_000)


def _simple_clauses(text: str) -> list[dict[str, object]]:
    blocks = [block.strip() for block in re.split(r"\n{2,}|(?<=\.)\s+(?=[A-ZÄÖÜ0-9])", text)]
    return [
        {"ordinal": index, "text": block}
        for index, block in enumerate(blocks, 1)
        if block
    ]


def _merge_evidence_text(*values: str) -> str:
    """Merge sequential visible states without duplicating identical text lines."""
    lines: list[str] = []
    seen: set[str] = set()
    for value in values:
        for raw_line in value.splitlines():
            line = " ".join(raw_line.split())
            key = line.casefold()
            if not line or key in seen:
                continue
            seen.add(key)
            lines.append(line)
    return "\n".join(lines)


def _legal_container_text(page) -> str:  # noqa: ANN001
    return str(
        page.evaluate(
            """() => {
              const candidates = [...document.querySelectorAll('main, article, [role="main"]')]
                .filter(element => {
                  const style = getComputedStyle(element);
                  return style.visibility !== 'hidden' && style.display !== 'none';
                });
              const selected = candidates.sort(
                (left, right) => (right.innerText || '').length - (left.innerText || '').length
              )[0] || document.body;
              return selected?.innerText || '';
            }"""
        )
    )


def _expand_legal_controls(page) -> list[dict]:  # noqa: ANN001
    from playwright.sync_api import Error as PlaywrightError

    records: list[dict] = []
    container = page.locator("main, article, [role='main']").first
    try:
        if container.count() == 0:
            container = page.locator("body")
        controls = container.locator(
            "details:not([open]) > summary, [aria-expanded='false'][aria-controls], "
            "[role='tab'][aria-selected='false'], button"
        )
        count = min(controls.count(), 100)
        eligible_total = int(
            container.evaluate(
                """root => [...root.querySelectorAll(
                  "details:not([open]) > summary, [aria-expanded='false'][aria-controls], " +
                  "[role='tab'][aria-selected='false'], button"
                )].filter(el => {
                  const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
                  return (el.tagName === 'SUMMARY' && !!el.closest('details:not([open])')) ||
                    (el.getAttribute('aria-expanded') === 'false' && !!el.getAttribute('aria-controls')) ||
                    (el.getAttribute('role') === 'tab' && el.getAttribute('aria-selected') === 'false' &&
                      !!el.getAttribute('aria-controls')) ||
                    (el.tagName === 'BUTTON' && /\\bmehr\\s+anzeigen\\b/i.test(text));
                }).slice(0, 100).length"""
            )
        )
    except PlaywrightError:
        return records
    for index in range(count):
        control = controls.nth(index)
        try:
            if not control.is_visible(timeout=100):
                continue
            handle = control.element_handle()
            if handle is None:
                continue
            before = handle.evaluate(
                """el => ({
                  text: (el.innerText || el.getAttribute('aria-label') || '').trim(),
                  aria_expanded: el.getAttribute('aria-expanded'),
                  aria_controls: el.getAttribute('aria-controls'),
                  details_open: el.closest('details')?.open ?? null,
                  url: document.URL,
                  text_length: (document.body?.innerText || '').length
                })"""
            )
            structure = handle.evaluate(
                """el => ({
                  tag_name: el.tagName.toLowerCase(),
                  details_summary: el.tagName === 'SUMMARY' && !!el.closest('details:not([open])'),
                  aria_accordion: el.getAttribute('aria-expanded') === 'false' && !!el.getAttribute('aria-controls'),
                  inactive_tab: el.getAttribute('role') === 'tab' &&
                    el.getAttribute('aria-selected') === 'false' && !!el.getAttribute('aria-controls')
                })"""
            )
            more_button = bool(
                structure["tag_name"] == "button"
                and re.search(r"\bmehr\s+anzeigen\b", before["text"], re.IGNORECASE)
            )
            if not any(
                (
                    structure["details_summary"],
                    structure["aria_accordion"],
                    structure["inactive_tab"],
                    more_button,
                )
            ):
                continue
            handle.click(timeout=1_500)
            page.wait_for_timeout(250)
            after = handle.evaluate(
                """el => ({
                  aria_expanded: el.getAttribute('aria-expanded'),
                  details_open: el.closest('details')?.open ?? null,
                  url: document.URL,
                  text_length: (document.body?.innerText || '').length,
                  expanded_text: (() => {
                    const controlled = el.getAttribute('aria-controls');
                    const target = controlled ? document.getElementById(controlled) : null;
                    return (target?.innerText || el.closest('details')?.innerText || '').trim();
                  })()
                })"""
            )
            records.append(
                {
                    "type": "legal_expansion",
                    "clicked_at": datetime.now(timezone.utc).isoformat(),
                    "selector_strategy": "rechtstextcontainer:zulässige_struktur",
                    "structure": structure,
                    "target_text": before["text"][:500],
                    "aria_controls": before["aria_controls"],
                    "eligible_total": eligible_total,
                    "expanded_text": after["expanded_text"][:200_000],
                    "before": before,
                    "after": after,
                    "changed": before["aria_expanded"] != after["aria_expanded"]
                    or before["details_open"] != after["details_open"]
                    or before["text_length"] != after["text_length"]
                    or before["url"] != after["url"],
                }
            )
        except PlaywrightError:
            continue
    return records


def _legal_expansion_summary(page, records: list[dict]) -> dict[str, object]:  # noqa: ANN001
    from playwright.sync_api import Error as PlaywrightError

    try:
        container = page.locator("main, article, [role='main']").first
        if container.count() == 0:
            container = page.locator("body")
        remaining = container.locator(
            "details:not([open]) > summary, [aria-expanded='false'][aria-controls]"
        ).count()
    except PlaywrightError:
        remaining = -1
    attempted = len(records)
    changed = sum(bool(record.get("changed")) for record in records)
    eligible = max(
        (int(record.get("eligible_total", 0)) for record in records),
        default=0,
    )
    captured = sum(bool(str(record.get("expanded_text", "")).strip()) for record in records)
    return {
        "eligible_controls": eligible,
        "attempted": attempted,
        "changed": changed,
        "captured_expanded_texts": captured,
        "unchanged": attempted - changed,
        "remaining_collapsed_controls": remaining,
        "limit": 100,
        "complete": attempted == eligible and changed == attempted and captured == attempted,
    }


def _capture_expanded_legal_print_pdf(
    page,
    root: Path,
    expansion_summary: dict[str, object],
    expanded_blocks: list[dict[str, object]],
    normalized_text: str,
) -> None:  # noqa: ANN001
    """Store a derived PDF containing every sequentially expanded legal block."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    pdf_path = root / "expanded-legal-print.pdf"
    metadata_path = root / "expanded-legal-print.json"
    source_url = page.url
    try:
        font_name = "Helvetica"
        for candidate in (
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                pdfmetrics.registerFont(TTFont("MucLegalUnicode", candidate))
                font_name = "MucLegalUnicode"
                break
            except (OSError, ValueError):
                continue
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "MucLegalTitle",
            parent=styles["Title"],
            fontName=font_name,
            alignment=TA_CENTER,
            fontSize=15,
            leading=19,
        )
        heading_style = ParagraphStyle(
            "MucLegalHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            spaceBefore=8,
        )
        body_style = ParagraphStyle(
            "MucLegalBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            spaceAfter=5,
        )
        story = [
            Paragraph("MucLegal – Druckfassung sequenziell expandierter Rechtstextblöcke", title_style),
            Spacer(1, 4 * mm),
            Paragraph(f"Quelle: {html_escape(source_url)}", body_style),
            Paragraph(
                "Technischer Hinweis: Diese PDF wurde lokal aus den nach jedem kontrollierten "
                "Akkordeon-Klick sichtbaren Textständen erzeugt. Sie ist keine unveränderte "
                "Original-PDF der Website.",
                body_style,
            ),
            Spacer(1, 4 * mm),
        ]
        blocks = expanded_blocks or [
            {"target_text": "Vollständiger sichtbarer Rechtstext", "text": normalized_text}
        ]
        for block in blocks:
            story.append(
                Paragraph(html_escape(str(block.get("target_text") or "Rechtstextblock")), heading_style)
            )
            text = str(block.get("text") or "")
            for paragraph in re.split(r"\n{2,}|\n", text):
                value = " ".join(paragraph.split())
                if value:
                    story.append(Paragraph(html_escape(value), body_style))
        document = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title="MucLegal – expandierte Rechtstext-Druckfassung",
            author="MucLegal BeweisLab",
        )
        document.build(story)
        _write_json(
            metadata_path,
            {
                "kind": "locally_generated_sequential_expansion_print",
                "source_url": source_url,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sha256": _sha256_path(pdf_path),
                "size_bytes": pdf_path.stat().st_size,
                "website_original": False,
                "expanded_block_count": len(expanded_blocks),
                "expansion_summary": expansion_summary,
            },
        )
    except (OSError, ValueError) as exc:
        _write_json(
            metadata_path,
            {
                "kind": "locally_generated_sequential_expansion_print",
                "source_url": source_url,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "website_original": False,
                "expansion_summary": expansion_summary,
            },
        )


def _capture_validated_screenshots(page, root: Path, interactions: list[dict]) -> ScreenshotCapture:  # noqa: ANN001
    from PIL import Image
    from playwright.sync_api import Error as PlaywrightError

    heights = []
    for _ in range(3):
        height = int(page.evaluate("document.documentElement.scrollHeight || 0"))
        heights.append(height)
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(250)
    page.evaluate("window.scrollTo(0, 0)")
    document_height = max(heights or [900])
    width = min(max(int(page.evaluate("document.documentElement.scrollWidth || 1440")), 1), 1440)
    full_path = root / "screenshot-full-page.png"
    full_error: str | None = None
    full_metrics: dict | None = None
    try:
        page.screenshot(path=str(full_path), full_page=True, type="png")
        full_metrics = _image_metrics(full_path)
        if full_metrics["invalid_nearly_white"]:
            full_error = "Vollbild ist nach der 99,5%-/Standardabweichungsregel nahezu weiß."
        elif full_metrics["width"] < 1 or full_metrics["height"] < document_height:
            full_error = "Vollbild deckt die dokumentierte Seitenhöhe nicht ab."
    except (PlaywrightError, OSError) as exc:
        full_error = f"{type(exc).__name__}: {exc}"

    tile_paths: list[Path] = []
    tiles: list[dict] = []
    tile_errors: list[str] = []
    invalid_tiles = 0
    reached_height = document_height
    completeness = "vollstaendig_erfasst"
    if full_error is not None:
        tiles_root = root / "screenshot-tiles"
        tiles_root.mkdir(exist_ok=True)
        tile_height = 2_000
        overlap = 100
        step = tile_height - overlap
        y = 0
        while y < document_height and len(tiles) < 100:
            current_height = max(
                int(page.evaluate("document.documentElement.scrollHeight || 0")), 1
            )
            current_width = min(
                max(int(page.evaluate("document.documentElement.scrollWidth || 1440")), 1),
                1440,
            )
            if y >= current_height:
                completeness = "teilweise_erfasst"
                tile_errors.append(
                    "Die Seite schrumpfte während der Aufnahme; weitere Kacheln lagen "
                    "außerhalb des aktuellen Dokuments."
                )
                break
            y_end = min(y + tile_height, document_height, current_height)
            tile_path = tiles_root / f"tile-{len(tiles):04d}.png"
            try:
                page.screenshot(
                    path=str(tile_path),
                    full_page=False,
                    clip={
                        "x": 0,
                        "y": y,
                        "width": min(width, current_width),
                        "height": y_end - y,
                    },
                    type="png",
                )
            except (PlaywrightError, OSError) as exc:
                completeness = "teilweise_erfasst"
                tile_errors.append(f"Kachel ab CSS-Pixel {y} nicht aufgenommen: {exc}")
                break
            metrics = _image_metrics(tile_path)
            if metrics["invalid_nearly_white"]:
                invalid_tiles += 1
            tile_paths.append(tile_path)
            tiles.append(
                {
                    "index": len(tiles),
                    "path": str(tile_path.relative_to(root)).replace("\\", "/"),
                    "y_start": y,
                    "y_end": y_end,
                    "device_scale_factor": 1,
                    "pixel_width": metrics["width"],
                    "pixel_height": metrics["height"],
                    "sha256": _sha256_path(tile_path),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "image_metrics": metrics,
                }
            )
            reached_height = y_end
            if y_end >= document_height:
                break
            y += step
        if reached_height < document_height:
            completeness = "teilweise_erfasst"
        if invalid_tiles:
            completeness = "teilweise_erfasst"
    index = {
        "mode": "full_page" if full_error is None else "tiles",
        "full_page_attempt": {
            "path": full_path.name if full_path.exists() else None,
            "valid": full_error is None,
            "error": full_error,
            "metrics": full_metrics,
        },
        "document_height_css_px": document_height,
        "height_measurements_css_px": heights,
        "tile_height_css_px": 2_000,
        "overlap_css_px": 100,
        "tile_limit": 100,
        "tiles": tiles,
        "tile_errors": tile_errors,
        "reached_height_css_px": reached_height,
        "continuous_coverage": _continuous_coverage(tiles, document_height),
        "invalid_nearly_white_tiles": invalid_tiles,
        "capture_completeness": completeness,
    }
    index_path = root / "screenshot-index.json"
    _write_json(index_path, index)
    if full_error is not None and not tile_paths:
        raise ScreenshotCaptureError(
            "Weder validiertes Vollbild noch eine gültige Screenshot-Kachel vorhanden: "
            f"{full_error}; {'; '.join(tile_errors) or 'Kachelaufnahme ohne Bild'}"
        )
    source = full_path if full_error is None else tile_paths[0]
    preview_path = root / "screenshot-preview.webp"
    with Image.open(source) as image:
        preview = image.convert("RGB")
        preview.thumbnail((1200, 1600))
        preview.save(preview_path, "WEBP", quality=82, method=6)
    primary = full_path if full_error is None else preview_path
    payload = primary.read_bytes()
    action_records = tuple(
        interaction["action"]
        for interaction in interactions
        if interaction.get("action")
    )
    return ScreenshotCapture(
        path=str(primary),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        capture_state="page_content" if completeness == "vollstaendig_erfasst" else "page_content_truncated",
        state_reason=None if completeness == "vollstaendig_erfasst" else (
            f"Bildserie erreichte {reached_height} von {document_height} CSS-Pixeln."
        ),
        interactions=action_records,
        preview_path=str(preview_path),
        index_path=str(index_path),
        tile_paths=tuple(str(path) for path in tile_paths),
        artifact_directory=str(root),
        capture_completeness=completeness,
    )


def _image_metrics(path: Path) -> dict[str, object]:
    from PIL import Image, ImageStat

    with Image.open(path) as source:
        image = source.convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        background.alpha_composite(image)
        rgb = background.convert("RGB")
        grayscale = rgb.convert("L")
        stat = ImageStat.Stat(grayscale)
        histogram = grayscale.histogram()
        total = max(1, rgb.width * rgb.height)
        near_white = sum(histogram[248:]) / total
        deviation = float(stat.stddev[0])
        return {
            "width": rgb.width,
            "height": rgb.height,
            "compressed_size_bytes": path.stat().st_size,
            "uncompressed_size_bytes": rgb.width * rgb.height * 3,
            "luminance_mean": round(float(stat.mean[0]), 6),
            "luminance_stddev": round(deviation, 6),
            "nearly_white_pixel_ratio": round(near_white, 8),
            "invalid_nearly_white": near_white >= 0.995 and deviation < 3.0,
        }


def _continuous_coverage(tiles: list[dict], expected_height: int) -> bool:
    if not tiles:
        return False
    reached = 0
    for tile in tiles:
        if int(tile["y_start"]) > reached:
            return False
        reached = max(reached, int(tile["y_end"]))
    return reached >= expected_height


def _process_sample() -> dict[str, object]:
    try:
        import psutil

        process = psutil.Process()
        memory = process.memory_info()
        cpu = process.cpu_times()
        return {
            "rss_bytes": memory.rss,
            "cpu_user_seconds": cpu.user,
            "cpu_system_seconds": cpu.system,
            "handles": process.num_handles() if os.name == "nt" else process.num_fds(),
        }
    except Exception as exc:
        return {"value": "not_available", "reason": f"{type(exc).__name__}: {exc}"}


def _write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _write_text(path: Path, value: str) -> None:
    _write_bytes(path, value.encode("utf-8"))


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    artifact_directory: str | Path | None = None,
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
    preview_path: Path | None = None
    index_path: Path | None = None
    artifact_root = Path(artifact_directory).resolve() if artifact_directory else None
    if artifact_root is not None:
        artifact_root.mkdir(parents=True, exist_ok=True)
        raw_html_path = artifact_root / "raw.html"
        if not raw_html_path.is_file():
            _write_text(raw_html_path, html)
        normalized_path = artifact_root / "normalized-text.txt"
        if not normalized_path.is_file():
            _write_text(normalized_path, _normalized_html_text(html))
        preview_path = artifact_root / "screenshot-preview.webp"
        with Image.open(destination) as source:
            preview = source.convert("RGB")
            preview.thumbnail((1200, 1600))
            preview.save(preview_path, "WEBP", quality=82, method=6)
        index_path = artifact_root / "screenshot-index.json"
        with Image.open(destination) as source:
            width, height = source.size
        _write_json(
            index_path,
            {
                "mode": "http_snapshot_visualized",
                "full_page_attempt": {
                    "path": destination.name,
                    "valid": True,
                    "error": None,
                },
                "document_height_css_px": height,
                "height_measurements_css_px": [height],
                "tiles": [],
                "continuous_coverage": True,
                "capture_completeness": "durch_seitenschutz_begrenzt" if protection else "teilweise_erfasst",
                "pixel_width": width,
                "pixel_height": height,
            },
        )
    return ScreenshotCapture(
        path=str(destination),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        capture_state=state,
        state_reason=reason,
        interactions=(),
        preview_path=str(preview_path) if preview_path else None,
        index_path=str(index_path) if index_path else None,
        artifact_directory=str(artifact_root) if artifact_root else None,
        capture_completeness=(
            "durch_seitenschutz_begrenzt" if protection else "teilweise_erfasst"
        ),
    )


def _normalized_html_text(html: str) -> str:
    """Create a deterministic text fallback for a stored DOM without another request."""
    try:
        from lxml import html as lxml_html

        document = lxml_html.fromstring(html)
        for unwanted in document.xpath("//script|//style|//noscript|//template|//svg"):
            unwanted.drop_tree()
        value = document.text_content()
    except (ValueError, TypeError):
        value = re.sub(r"<[^>]+>", " ", html)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


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
    labels: tuple[str, ...] | list[str] | None = None,
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
    reported_labels = tuple(
        dict.fromkeys(
            item.strip() for item in (labels or (label,)) if isinstance(item, str) and item.strip()
        )
    ) or (label,)
    label_token_sets = tuple(_tokens(item) for item in reported_labels if _tokens(item))
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
                    label_match = any(
                        tokens <= haystack
                        or len(tokens & haystack) / len(tokens) >= 0.6
                        for tokens in label_token_sets
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
        "reported_target": {
            "label": label,
            "label_variants": list(reported_labels),
            "function": function,
        },
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

