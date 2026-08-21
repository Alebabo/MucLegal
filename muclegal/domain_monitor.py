from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from lxml import etree, html

from muclegal.fetch import DomInspectionCapture, FetchFailure, HttpFetcher
from muclegal.evidence import capture_snapshot_warc, create_manifest, verify_manifest
from muclegal.monitoring_cases import MonitoringCase
from muclegal.normalize import NormalizationConfig, normalize_html, normalize_plain_text, split_clauses


DISCOVERY_TERMS = (
    "agb", "allgemeine geschäftsbedingungen", "bedingungen", "terms", "vertrag",
    "kündig", "kuendig", "konto", "checkout", "warenkorb", "widerruf",
)
TRACKING_PARAMETERS = {"fbclid", "gclid", "msclkid", "ref", "source"}
COMMON_PROFILE_PATHS = {
    "agb": ("/agb", "/terms", "/policies/terms-of-service"),
    "datenschutz": ("/datenschutz", "/privacy-policy.html", "/policies/privacy-policy"),
}


@dataclass(frozen=True)
class ScanPolicy:
    max_urls: int = 50
    max_depth: int = 3
    max_seconds: float = 600.0
    max_dom_pages: int = 10


@dataclass(frozen=True)
class DomainMonitoringResult:
    run_id: str
    case_id: str
    status: str
    created_at: str
    reported_initial_violation: dict
    monitoring_findings: tuple[dict, ...]
    document_findings: tuple[dict, ...]
    element_findings: tuple[dict, ...]
    coverage: dict
    manual_review_reasons: tuple[str, ...]
    artifacts: dict
    freigabe_durch_mensch: None = None

    def to_dict(self) -> dict:
        return asdict(self)


class CaseDomainMonitor:
    """Monitor a manually reported violation; never discovers initial violations."""

    def __init__(
        self,
        store: str | Path,
        *,
        fetcher: HttpFetcher,
        dom_inspector: Callable[..., DomInspectionCapture] | None = None,
        policy: ScanPolicy | None = None,
    ) -> None:
        self.store = Path(store).resolve()
        self.store.mkdir(parents=True, exist_ok=True)
        self.fetcher = fetcher
        self.dom_inspector = dom_inspector
        self.policy = policy or ScanPolicy()

    def run(self, case: MonitoringCase, progress: Callable[[str, str], None] | None = None) -> DomainMonitoringResult:
        if not case.approved:
            raise PermissionError("Monitoring startet erst nach menschlicher Freigabe des Falls.")
        progress = progress or (lambda _step, _message: None)
        progress("fetch", "Die freigegebene Domain wird fallbezogen und begrenzt durchsucht.")
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
        run_root = self.store / case.case_id / run_id
        pages_root = run_root / "pages"
        dom_root = run_root / "dom"
        pages_root.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        allowed_hosts = {case.domain, *case.allowed_subdomains}
        required_targets = tuple(dict.fromkeys(canonical_url(url) for url in case.target_urls))
        queue: deque[tuple[str, int, str, bool]] = deque(
            (url, 0, "fallprofil", True) for url in required_targets
        )
        for candidate in _profile_path_candidates(case):
            queue.append((candidate, 0, "bekannter_rechtstextpfad", False))
        for sitemap_url in self._sitemap_urls(case.source_url):
            for candidate in self._read_sitemap(sitemap_url):
                if _allowed(candidate, allowed_hosts):
                    queue.append((canonical_url(candidate), 1, "sitemap", True))

        visited: list[str] = []
        skipped: list[dict] = []
        blocked: list[dict] = []
        pages: list[dict] = []
        seen: set[str] = set()
        budget_exhausted = False
        while queue:
            if len(visited) >= self.policy.max_urls or time.monotonic() - started >= self.policy.max_seconds:
                budget_exhausted = True
                break
            url, depth, source, required = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            if depth > self.policy.max_depth:
                skipped.append({"url": url, "reason": "linktiefe", "depth": depth})
                continue
            if not _allowed(url, allowed_hosts):
                skipped.append({"url": url, "reason": "nicht_freigegebener_host", "depth": depth})
                continue
            try:
                fetched = self.fetcher.fetch(url)
            except FetchFailure as exc:
                failure = {
                    "url": url,
                    "reason": exc.code,
                    "message": str(exc),
                    "manual_review": exc.manual_review,
                    "source": source,
                    "required_by_case_profile": required,
                }
                if required:
                    blocked.append(failure)
                else:
                    skipped.append(failure)
                continue
            visited.append(url)
            extension = ".pdf" if _is_pdf(fetched.headers, fetched.body, url) else ".html"
            page_path = pages_root / f"{len(visited):03d}-{hashlib.sha256(url.encode()).hexdigest()[:10]}{extension}"
            page_path.write_bytes(fetched.body)
            headers_path = page_path.with_suffix(page_path.suffix + ".headers.json")
            _write_json(headers_path, list(fetched.headers))
            text = _extract_document_text(fetched, extension)
            page = {
                "url": url,
                "final_url": fetched.final_url,
                "depth": depth,
                "source": source,
                "required_by_case_profile": url in required_targets,
                "content_type": "pdf" if extension == ".pdf" else "html",
                "artifact_path": str(page_path),
                "headers_path": str(headers_path),
                "sha256": hashlib.sha256(fetched.body).hexdigest(),
                "text": text,
                "fetched_at": fetched.fetched_at,
                "status_code": fetched.status_code,
            }
            pages.append(page)
            if extension == ".html" and depth < self.policy.max_depth:
                discovered = _links(fetched.decoded_html, fetched.final_url)
                discovered.sort(key=lambda item: (_priority(item[0], item[1]), item[0]), reverse=True)
                for link, label in discovered:
                    if link not in seen and _allowed(link, allowed_hosts):
                        queue.append((link, depth + 1, f"link:{label[:100]}", True))

        progress("normalize", "AGB- und Seitentexte wurden ausschließlich gegen den gemeldeten Verstoß geprüft.")
        document_findings = self._document_findings(case, pages)
        element_findings: list[dict] = []
        manual_reasons = [item["message"] for item in blocked if item.get("manual_review")]
        if case.violation_type == "element":
            progress("screenshot", "Gemeldete Elemente werden im gerenderten DOM geprüft.")
            element_findings, dom_reasons = self._inspect_elements(case, pages, dom_root)
            manual_reasons.extend(dom_reasons)

        dom_incomplete = case.violation_type == "element" and not element_findings
        captured_required_targets = [url for url in required_targets if url in visited]
        missing_required_targets = [url for url in required_targets if url not in visited]
        complete = (
            not budget_exhausted
            and not blocked
            and not dom_incomplete
            and not missing_required_targets
        )
        monitoring_status = _monitoring_status(case, document_findings, element_findings, complete, self._has_history(case.case_id))
        coverage = {
            "strategy": "menschliches_fallprofil+bekannte_rechtstextpfade+sitemap+priorisierte_interne_links",
            "allowed_hosts": sorted(allowed_hosts),
            "required_target_urls": list(required_targets),
            "captured_required_target_urls": captured_required_targets,
            "missing_required_target_urls": missing_required_targets,
            "limits": asdict(self.policy),
            "visited_urls": visited,
            "skipped_urls": skipped,
            "blocked_urls": blocked,
            "dom_inspection_incomplete": dom_incomplete,
            "budget_exhausted": budget_exhausted,
            "complete_within_scope": complete,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        if not complete:
            manual_reasons.append("Der dokumentierte Prüfumfang konnte nicht vollständig abgeschlossen werden.")
        monitoring_findings = ({
            "status": monitoring_status,
            "tenor_element": case.tenor_element,
            "source": "system_monitoring_nach_menschlicher_fallfreigabe",
            "freigabe_durch_mensch": None,
        },)
        reported = {
            "fall_id": case.fall_id,
            "source_url": case.source_url,
            "violation_type": case.violation_type,
            "description": case.description,
            "tenor_element": case.tenor_element,
            "monitoring_target": case.monitoring_target,
            "target_urls": list(case.target_urls),
            "element_labels": list(case.element_labels),
            "nicht_umfasst": list(case.nicht_umfasst),
            "erstverstoss_festgestellt_durch": "verbraucherzentrale",
            "system_detected": False,
            "screenshot_path": case.screenshot_path,
            "screenshot_sha256": case.screenshot_sha256,
        }
        progress("compare", f"Fallbezogener Befund: {monitoring_status}.")
        coverage_path = run_root / "coverage.json"
        findings_path = run_root / "monitoring-findings.json"
        _write_json(coverage_path, coverage)
        _write_json(
            findings_path,
            {
                "reported_initial_violation": reported,
                "monitoring_findings": monitoring_findings,
                "document_findings": document_findings,
                "element_findings": element_findings,
                "manual_review_reasons": manual_reasons,
            },
        )
        evidence_files: dict[str, str | Path] = {
            "coverage": coverage_path,
            "monitoring_findings": findings_path,
        }
        for index, page in enumerate(pages, start=1):
            evidence_files[f"page_{index:03d}"] = page["artifact_path"]
            evidence_files[f"page_{index:03d}_headers"] = page["headers_path"]
        for path in sorted(dom_root.glob("*")) if dom_root.exists() else ():
            if path.is_file():
                evidence_files[f"dom_{path.stem}_{path.suffix.lstrip('.')}"] = path
        reported_screenshot = None
        if case.screenshot_path and Path(case.screenshot_path).is_file():
            reported_screenshot = run_root / f"reported-initial-violation{Path(case.screenshot_path).suffix}"
            shutil.copy2(case.screenshot_path, reported_screenshot)
            evidence_files["reported_initial_violation_screenshot"] = reported_screenshot

        warc_root = run_root / "warc"
        warc_errors: list[str] = []
        for index, page in enumerate(pages, start=1):
            try:
                captured = capture_snapshot_warc(
                    page["url"],
                    warc_root,
                    raw_html_path=page["artifact_path"],
                    response_headers_path=page["headers_path"],
                    final_url=page["final_url"],
                    fetched_at=page["fetched_at"],
                    status_code=page["status_code"],
                    basename=f"page-{index:03d}",
                )
                evidence_files[f"warc_{index:03d}"] = captured.warc_path
                evidence_files[f"cdx_{index:03d}"] = captured.cdx_path
            except Exception as exc:
                warc_errors.append(f"WARC für {page['url']} konnte nicht erzeugt werden: {exc}")
        manual_reasons.extend(warc_errors)
        manifest = create_manifest(evidence_files, run_root)
        if not verify_manifest(manifest.manifest_path).valid:
            raise RuntimeError("Hash-Manifest des Domainlaufs konnte nicht verifiziert werden.")
        result = DomainMonitoringResult(
            run_id=run_id,
            case_id=case.case_id,
            status=monitoring_status,
            created_at=datetime.now(timezone.utc).isoformat(),
            reported_initial_violation=reported,
            monitoring_findings=monitoring_findings,
            document_findings=tuple(document_findings),
            element_findings=tuple(element_findings),
            coverage=coverage,
            manual_review_reasons=tuple(dict.fromkeys(manual_reasons)),
            artifacts={
                "coverage": str(coverage_path),
                "monitoring_findings": str(findings_path),
                "pages_directory": str(pages_root),
                "dom_directory": str(dom_root) if dom_root.exists() else None,
                "reported_screenshot": str(reported_screenshot) if reported_screenshot else None,
                "manifest": manifest.manifest_path,
                "manifest_digest": manifest.digest_path,
                "manifest_sha256": manifest.manifest_sha256,
                "chain_head_sha256": manifest.chain_head_sha256,
                "warc_status": "captured" if not warc_errors else "completed_with_warnings",
                "timestamp_status": "pending_human_confirmation",
            },
        )
        _write_json(run_root / "result.json", result.to_dict())
        _write_json(self.store / case.case_id / "latest.json", result.to_dict())
        return result

    def _sitemap_urls(self, source_url: str) -> tuple[str, ...]:
        parsed = urlsplit(source_url)
        return (urlunsplit((parsed.scheme, parsed.netloc, "/sitemap.xml", "", "")),)

    def _read_sitemap(self, sitemap_url: str) -> list[str]:
        try:
            fetched = self.fetcher.fetch(sitemap_url)
            root = etree.fromstring(fetched.body)
        except (FetchFailure, etree.XMLSyntaxError, ValueError):
            return []
        return [str(value).strip() for value in root.xpath("//*[local-name()='loc']/text()") if str(value).strip()]

    def _document_findings(self, case: MonitoringCase, pages: list[dict]) -> list[dict]:
        target = normalize_plain_text(case.clause_text or case.monitoring_target).strip()
        profile_targets = {canonical_url(url) for url in case.target_urls}
        findings: list[dict] = []
        for page in pages:
            lower_identity = f"{page['url']} {page['source']}".casefold()
            is_document = any(term in lower_identity for term in DISCOVERY_TERMS) or page["url"] in profile_targets
            if not is_document:
                continue
            text = normalize_plain_text(page["text"]).strip() if page["text"] else ""
            exact = bool(target and target.casefold() in text.casefold())
            similarity = 0.0
            best_quote: str | None = None
            if target and text and not exact:
                for clause in split_clauses(text):
                    score = SequenceMatcher(None, target.casefold(), clause.text.casefold()).ratio()
                    if score > similarity:
                        similarity, best_quote = score, clause.text
            findings.append(
                {
                    "url": page["url"],
                    "kind": page["content_type"],
                    "reported_clause_exact": exact,
                    "similarity": round(1.0 if exact else similarity, 3),
                    "candidate_quote": target if exact else best_quote,
                    "artifact_path": page["artifact_path"],
                    "sha256": page["sha256"],
                }
            )
        return findings

    def _inspect_elements(
        self, case: MonitoringCase, pages: list[dict], destination: Path
    ) -> tuple[list[dict], list[str]]:
        if self.dom_inspector is None:
            return [], ["Playwright-DOM-Prüfung ist nicht konfiguriert."]
        destination.mkdir(parents=True, exist_ok=True)
        profile_targets = {canonical_url(url) for url in case.target_urls}
        relevant = [
            page for page in pages
            if page["content_type"] == "html" and (
                page["url"] in profile_targets
                or any(term in f"{page['url']} {page['source']}".casefold() for term in DISCOVERY_TERMS)
            )
        ][: self.policy.max_dom_pages]
        findings: list[dict] = []
        reasons: list[str] = []
        for index, page in enumerate(relevant, start=1):
            try:
                capture = self.dom_inspector(
                    page["url"],
                    destination / f"{index:03d}-dom.json",
                    label=case.element_label or case.monitoring_target,
                    labels=case.element_labels,
                    function=case.element_function or case.monitoring_target,
                )
            except Exception as exc:
                reasons.append(f"DOM-Prüfung für {page['url']} fehlgeschlagen: {exc}")
                continue
            matches = list(capture.matching_elements)
            state = _element_state(case, matches, capture.safe_path_status)
            if state == "manuelle_pruefung_erforderlich":
                reasons.append(
                    f"Die Funktion des Elements auf {page['url']} lässt sich ohne Außenwirkung nicht abschließend prüfen."
                )
            findings.append(
                {
                    "url": page["url"],
                    "state": state,
                    "matches": matches,
                    "safe_path_status": capture.safe_path_status,
                    "safe_path": capture.safe_path,
                    "blocked_requests": list(capture.blocked_requests),
                    "dom_artifact_path": capture.path,
                    "screenshot_path": capture.screenshot_path,
                    "sha256": capture.sha256,
                }
            )
            reasons.extend(capture.manual_review_reasons)
        return findings, reasons

    def _has_history(self, case_id: str) -> bool:
        directory = self.store / case_id
        return directory.is_dir() and any(directory.glob("*/result.json"))


def _monitoring_status(
    case: MonitoringCase,
    documents: list[dict],
    elements: list[dict],
    complete: bool,
    has_history: bool,
) -> str:
    if not complete:
        return "pruefung_unvollstaendig"
    if case.violation_type == "klausel":
        exact = [item for item in documents if item["reported_clause_exact"]]
        similar = [item for item in documents if not item["reported_clause_exact"] and item["similarity"] >= 0.72]
        if exact:
            if not has_history:
                return "referenzzustand_dokumentiert"
            if any(item["url"] != canonical_url(case.source_url) for item in exact):
                return "kerngleich_wiederaufgetreten"
            return "unveraendert_fortbestehend"
        if similar:
            return "unsicher"
        return "beseitigt"
    if not elements:
        return "pruefung_unvollstaendig"
    if any(item["state"] == "manuelle_pruefung_erforderlich" for item in elements):
        return "unsicher"
    violation_persists = not any(item["state"] == "gefunden" for item in elements)
    if violation_persists:
        return "referenzzustand_dokumentiert" if not has_history else "unveraendert_fortbestehend"
    return "beseitigt"


def _element_state(
    case: MonitoringCase, matches: list[dict], safe_path_status: str
) -> str:
    if not matches:
        return "nicht_gefunden_im_pruefumfang"
    accessible = [
        item for item in matches
        if item.get("visible") and not item.get("disabled") and not item.get("obscured")
        and str(item.get("accessible_name") or "").strip()
    ]
    if not accessible:
        return "vorhanden_aber_fehlerhaft"
    if case.element_error == "falsches_ziel":
        expected = (case.element_function or "").strip().casefold()
        target_values = [str(item.get("href") or "").casefold() for item in accessible]
        if expected.startswith(("http://", "https://")) or expected.startswith("/"):
            return "gefunden" if any(expected in target for target in target_values) else "vorhanden_aber_fehlerhaft"
        return "manuelle_pruefung_erforderlich"
    if case.element_error == "zusaetzliche_huerde":
        return (
            "gefunden"
            if safe_path_status == "gleichurspruengliches_ziel_dokumentiert"
            else "manuelle_pruefung_erforderlich"
        )
    return "gefunden"


def _profile_path_candidates(case: MonitoringCase) -> list[str]:
    """Add a small same-origin path set; explicit human targets remain authoritative."""
    parsed = urlsplit(case.source_url)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    page_types = " ".join(case.relevant_page_types).casefold()
    paths: list[str] = []
    if any(term in page_types for term in ("agb", "beding", "terms")):
        paths.extend(COMMON_PROFILE_PATHS["agb"])
    if any(term in page_types for term in ("datenschutz", "privacy")):
        paths.extend(COMMON_PROFILE_PATHS["datenschutz"])
    explicit = {canonical_url(url) for url in case.target_urls}
    return [
        candidate
        for candidate in dict.fromkeys(canonical_url(urljoin(origin, path)) for path in paths)
        if candidate not in explicit
    ]


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    query = urlencode(
        sorted((key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if key.casefold() not in TRACKING_PARAMETERS)
    )
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))


def _allowed(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in allowed_hosts and not parsed.username


def _priority(url: str, label: str) -> int:
    haystack = f"{url} {label}".casefold()
    return sum(10 for term in DISCOVERY_TERMS if term in haystack)


def _links(raw_html: str, base_url: str) -> list[tuple[str, str]]:
    try:
        document = html.document_fromstring(raw_html)
    except (etree.ParserError, ValueError):
        return []
    result: list[tuple[str, str]] = []
    for anchor in document.xpath("//a[@href]"):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = canonical_url(urljoin(base_url, href))
        label = " ".join(anchor.itertext()).strip()
        result.append((absolute, label))
    return result


def _is_pdf(headers: tuple[tuple[str, str], ...], body: bytes, url: str) -> bool:
    content_type = next((value for key, value in headers if key.lower() == "content-type"), "")
    return "application/pdf" in content_type.lower() or body.startswith(b"%PDF-") or urlsplit(url).path.lower().endswith(".pdf")


def _extract_document_text(fetched, extension: str) -> str:  # noqa: ANN001
    if extension == ".pdf":
        try:
            from io import BytesIO
            from pypdf import PdfReader

            return normalize_plain_text("\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(fetched.body)).pages))
        except Exception:
            return ""
    try:
        return normalize_html(fetched.decoded_html, NormalizationConfig()).text
    except Exception:
        try:
            document = html.document_fromstring(fetched.decoded_html)
            return normalize_plain_text(" ".join(document.itertext()))
        except Exception:
            return ""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
