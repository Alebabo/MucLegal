from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CONSENT_CONTEXT_MARKERS = (
    "cookie",
    "consent",
    "datenschutz",
    "privacy",
    "tracking",
    "einwilligung",
)
ACCEPTANCE_MARKERS = ("akzept", "accept", "zustimmen", "allow all")
ALLOWED_LABELS = (
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


def classify_privacy_action(
    label: str,
    context: str = "",
    *,
    visible_alternatives: tuple[str, ...] = (),
    dialog_role: str | None = None,
) -> str | None:
    """Return an action only when a visible control is unambiguously privacy preserving."""
    normalized_label = " ".join(label.casefold().split())
    normalized_context = " ".join(context.casefold().split())
    if not normalized_label or any(marker in normalized_label for marker in ACCEPTANCE_MARKERS):
        return None
    for phrase, action in ALLOWED_LABELS:
        if phrase in normalized_label:
            return action
    if normalized_label not in {"ablehnen", "reject", "decline"}:
        return None
    alternatives = " ".join(visible_alternatives).casefold()
    has_consent_context = any(marker in normalized_context for marker in CONSENT_CONTEXT_MARKERS)
    has_accept_alternative = any(marker in alternatives for marker in ACCEPTANCE_MARKERS)
    if dialog_role in {"dialog", "alertdialog"} and has_consent_context and has_accept_alternative:
        return "optionale_cookies_abgelehnt"
    return None


def handle_consent(page: Any, before_screenshot: str | None = None) -> dict[str, Any]:
    """Inspect all visible consent controls and perform at most one conservative click."""
    from playwright.sync_api import Error as PlaywrightError

    if before_screenshot:
        page.screenshot(path=before_screenshot, full_page=False, type="png")
    record: dict[str, Any] = {
        "policy": "nur_eindeutige_datensparsame_cookie_auswahl",
        "inspected_at": datetime.now(timezone.utc).isoformat(),
        "page_url": page.url,
        "visible_controls": [],
        "action": None,
        "result": "kein_eindeutiger_consent_kandidat",
    }
    candidates: list[tuple[int, Any, dict[str, Any]]] = []
    for frame_index, frame in enumerate(page.frames):
        try:
            controls = frame.locator(
                "button, [role='button'], input[type='button'], input[type='submit'], a"
            )
            count = min(controls.count(), 300)
        except PlaywrightError:
            continue
        visible_labels: list[str] = []
        frame_controls: list[tuple[Any, dict[str, Any]]] = []
        for index in range(count):
            control = controls.nth(index)
            try:
                if not control.is_visible(timeout=100):
                    continue
                detail = control.evaluate(
                    """element => {
                      const dialog = element.closest(
                        '#onetrust-banner-sdk, [role="dialog"], [role="alertdialog"], '
                        + '[aria-modal="true"], [id*="cookie" i], [class*="cookie" i], '
                        + '[id*="consent" i], [class*="consent" i], '
                        + '[id*="privacy" i], [class*="privacy" i]'
                      );
                      const root = element.getRootNode();
                      const host = root && root.host ? root.host : null;
                      return {
                        label: [element.innerText, element.value,
                          element.getAttribute('aria-label'), element.title]
                          .filter(Boolean).join(' ').trim(),
                        dialog_text: (dialog?.innerText || '').slice(0, 6000),
                        dialog_role: dialog?.getAttribute('role') ||
                          (dialog?.getAttribute('aria-modal') === 'true' ? 'dialog' : null),
                        dialog_name: dialog?.getAttribute('aria-label') ||
                          dialog?.getAttribute('aria-labelledby') || null,
                        selector_strategy: element.id ? `id:${element.id}` :
                          `role:${element.getAttribute('role') || element.tagName.toLowerCase()}`,
                        shadow_context: host ? (host.id || host.tagName.toLowerCase()) : null
                      };
                    }"""
                )
            except PlaywrightError:
                continue
            label = " ".join(str(detail.get("label") or "").split())[:500]
            if not label:
                continue
            visible_labels.append(label)
            item = {
                "button_text": label,
                "frame_index": frame_index,
                "frame_url": frame.url,
                "dialog_role": detail.get("dialog_role"),
                "dialog_name": detail.get("dialog_name"),
                "selector_strategy": detail.get("selector_strategy"),
                "shadow_context": detail.get("shadow_context"),
                "consent_context": bool(detail.get("dialog_text")),
            }
            frame_controls.append((control, {**item, "_context": detail.get("dialog_text") or ""}))
            record["visible_controls"].append(item)
        alternatives = tuple(visible_labels)
        for control, item in frame_controls:
            action = classify_privacy_action(
                item["button_text"],
                item.pop("_context"),
                visible_alternatives=alternatives,
                dialog_role=item.get("dialog_role"),
            )
            if action:
                priority = next(
                    (position for position, (phrase, _) in enumerate(ALLOWED_LABELS)
                     if phrase in item["button_text"].casefold()),
                    len(ALLOWED_LABELS),
                )
                candidates.append((priority, control, {**item, "action": action}))
    for _, control, action_record in sorted(candidates, key=lambda item: item[0]):
        try:
            control.click(timeout=1_500)
            page.wait_for_timeout(500)
            still_visible = control.is_visible(timeout=200)
            record["action"] = {
                **action_record,
                "clicked_at": datetime.now(timezone.utc).isoformat(),
                "result": "dialog_fortbestehend" if still_visible else "dialog_verschwunden",
            }
            record["result"] = record["action"]["result"]
            return record
        except PlaywrightError:
            continue
    if any(item.get("consent_context") for item in record["visible_controls"]):
        record["result"] = "consent_ungeklaert"
    return record
