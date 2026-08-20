from __future__ import annotations

import gzip
import ipaddress
import re
import socket
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from urllib import error, parse, request, robotparser


DEFAULT_USER_AGENT = (
    "MucLegal-Monitor/0.1 "
    "(+https://github.com/Alebabo/MucLegal; public-page compliance monitor)"
)
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class FetchPolicy:
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    retry_backoff_seconds: float = 0.25
    respect_robots: bool = True
    require_public_network: bool = False


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    fetched_at: str
    status_code: int
    headers: tuple[tuple[str, str], ...]
    redirect_chain: tuple[str, ...]
    body: bytes
    decoded_html: str
    fetch_mode: str = "http"
    browser_metadata: dict[str, object] | None = None


class FetchFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        headers: tuple[tuple[str, str], ...] = (),
        body: bytes | None = None,
        manual_review: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.manual_review = manual_review


class _RedirectRecorder(request.HTTPRedirectHandler):
    def __init__(self, before_redirect) -> None:  # noqa: ANN001
        super().__init__()
        self.chain: list[str] = []
        self.before_redirect = before_redirect

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.before_redirect(newurl)
        self.chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpFetcher:
    """Conservative HTTP fetcher for public pages only."""

    def __init__(self, policy: FetchPolicy | None = None) -> None:
        self.policy = policy or FetchPolicy()

    def fetch(self, url: str) -> FetchResult:
        self._validate_url(url)
        if self.policy.respect_robots:
            self._require_robots_permission(url)

        last_failure: FetchFailure | None = None
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return self._fetch_once(url)
            except FetchFailure as exc:
                last_failure = exc
                if exc.status_code not in RETRYABLE_STATUS or attempt == self.policy.max_attempts:
                    raise
                time.sleep(self.policy.retry_backoff_seconds * (2 ** (attempt - 1)))
        assert last_failure is not None
        raise last_failure

    def fetch_in_browser(self, url: str) -> FetchResult:
        """Use a real browser only when explicitly enabled by the caller."""
        self._validate_url(url)
        if self.policy.respect_robots:
            self._require_robots_permission(url)
        from muclegal.fetch.playwright import fetch_rendered_public_page

        validated_origins: set[tuple[str, str]] = set()
        robots_origins: set[tuple[str, str]] = set()

        def guard_request(target_url: str, resource_type: str) -> None:
            parsed = parse.urlsplit(target_url)
            origin = (parsed.scheme, parsed.netloc)
            if origin not in validated_origins:
                self._validate_url(target_url)
                validated_origins.add(origin)
            if (
                self.policy.respect_robots
                and resource_type == "document"
                and origin not in robots_origins
            ):
                self._require_robots_permission(target_url)
                robots_origins.add(origin)

        result = fetch_rendered_public_page(
            url,
            user_agent=self.policy.user_agent,
            timeout_seconds=max(20.0, self.policy.timeout_seconds),
            request_guard=guard_request,
        )
        metadata = dict(result.browser_metadata or {})
        metadata["robots_txt"] = (
            "geprueft_abruf_erlaubt"
            if self.policy.respect_robots
            else "laut_policy_nicht_geprueft"
        )
        return replace(result, browser_metadata=metadata)

    def capture_screenshot(self, url: str, destination: str | Path):
        """Capture one public page with the same URL and robots policy as regular fetching."""
        self._validate_url(url)
        if self.policy.respect_robots:
            self._require_robots_permission(url)
        from muclegal.fetch.playwright import capture_page_screenshot

        initial = parse.urlsplit(url)
        initial_origin = (initial.scheme, initial.netloc)
        validated_origins: set[tuple[str, str]] = {initial_origin}
        robots_origins: set[tuple[str, str]] = {initial_origin}

        def validate_subresource(target_url: str) -> None:
            parsed = parse.urlsplit(target_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise FetchFailure("invalid_url", "Nicht öffentliche Unterressource blockiert.")
            if parsed.username or parsed.password:
                raise FetchFailure("credentials_in_url", "Unterressource mit Zugangsdaten blockiert.")
            hostname = parsed.hostname.lower().rstrip(".")
            if hostname == "localhost" or hostname.endswith(".localhost"):
                raise FetchFailure("non_public_target", "Lokale Unterressource blockiert.")
            try:
                literal_ip = ipaddress.ip_address(hostname)
            except ValueError:
                return
            if not literal_ip.is_global:
                raise FetchFailure("non_public_target", "Private Unterressource blockiert.")

        def guard_request(target_url: str, resource_type: str) -> None:
            parsed = parse.urlsplit(target_url)
            origin = (parsed.scheme, parsed.netloc)
            if resource_type == "document":
                if origin not in validated_origins:
                    self._validate_url(target_url)
                    validated_origins.add(origin)
                if self.policy.respect_robots and origin not in robots_origins:
                    self._require_robots_permission(target_url)
                    robots_origins.add(origin)
            else:
                validate_subresource(target_url)

        return capture_page_screenshot(
            url,
            destination,
            timeout_seconds=max(20.0, self.policy.timeout_seconds),
            user_agent=self.policy.user_agent,
            request_guard=guard_request,
        )

    def _validate_url(self, url: str) -> None:
        parsed = parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise FetchFailure("invalid_url", "Nur öffentliche HTTP(S)-URLs sind zulässig.")
        try:
            port = parsed.port
        except ValueError as exc:
            raise FetchFailure("invalid_url", "Die URL enthält keinen gültigen Port.") from exc
        if parsed.username or parsed.password:
            raise FetchFailure(
                "credentials_in_url",
                "URLs mit Zugangsdaten werden nicht abgerufen.",
                manual_review=True,
            )
        if self.policy.require_public_network:
            try:
                addresses = {
                    item[4][0]
                    for item in socket.getaddrinfo(
                        parsed.hostname,
                        port or (443 if parsed.scheme == "https" else 80),
                    )
                }
            except socket.gaierror as exc:
                raise FetchFailure("dns_error", f"Hostname konnte nicht aufgelöst werden: {exc}") from exc
            if not addresses:
                raise FetchFailure("dns_error", "Hostname lieferte keine Netzwerkadresse.")
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if not ip.is_global:
                    raise FetchFailure(
                        "non_public_target",
                        "Nur öffentlich erreichbare Internetadressen sind zulässig.",
                        manual_review=True,
                    )

    def _require_robots_permission(self, url: str) -> None:
        self._validate_url(url)
        parsed = parse.urlsplit(url)
        robots_url = parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        req = request.Request(robots_url, headers={"User-Agent": self.policy.user_agent})
        redirects = _RedirectRecorder(self._validate_url)
        opener = request.build_opener(redirects)
        try:
            with opener.open(req, timeout=self.policy.timeout_seconds) as response:
                raw = response.read(1_000_000)
                encoding = response.headers.get_content_charset() or "utf-8"
                rules = raw.decode(encoding, errors="replace")
        except error.HTTPError as exc:
            if exc.code == 404:
                return
            raise FetchFailure(
                "robots_unavailable",
                f"robots.txt konnte nicht verlässlich geprüft werden (HTTP {exc.code}).",
                status_code=exc.code,
                manual_review=True,
            ) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise FetchFailure(
                "robots_unavailable",
                f"robots.txt konnte nicht verlässlich geprüft werden: {exc}",
                manual_review=True,
            ) from exc

        parser = robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(rules.splitlines())
        if not parser.can_fetch(self.policy.user_agent, url):
            raise FetchFailure(
                "robots_disallowed",
                "robots.txt untersagt den Abruf für diesen User-Agent.",
                manual_review=True,
            )

    def _fetch_once(self, url: str) -> FetchResult:
        redirects = _RedirectRecorder(
            self._require_robots_permission if self.policy.respect_robots else lambda _url: None
        )
        opener = request.build_opener(redirects)
        req = request.Request(
            url,
            headers={
                "User-Agent": self.policy.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "Accept-Language": "de,en;q=0.5",
                "Accept-Encoding": "identity",
            },
        )
        fetched_at = datetime.now(timezone.utc).isoformat()
        try:
            with opener.open(req, timeout=self.policy.timeout_seconds) as response:
                body = response.read()
                status = response.status
                headers = tuple(response.headers.items())
                final_url = response.geturl()
                decoded = self._decode_body(body, response.headers)
        except error.HTTPError as exc:
            body = exc.read()
            headers = tuple(exc.headers.items()) if exc.headers else ()
            raise FetchFailure(
                "http_error",
                f"HTTP-Abruf fehlgeschlagen (Status {exc.code}).",
                status_code=exc.code,
                headers=headers,
                body=body,
                manual_review=exc.code in {401, 403, 407, 429},
            ) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise FetchFailure("network_error", f"HTTP-Abruf fehlgeschlagen: {exc}") from exc

        block_reason = _detect_block_page(decoded)
        if block_reason:
            raise FetchFailure(
                "protected_or_login_page",
                f"Abruf abgebrochen: {block_reason}",
                status_code=status,
                headers=headers,
                body=body,
                manual_review=True,
            )
        return FetchResult(
            requested_url=url,
            final_url=final_url,
            fetched_at=fetched_at,
            status_code=status,
            headers=headers,
            redirect_chain=tuple(redirects.chain),
            body=body,
            decoded_html=decoded,
        )

    @staticmethod
    def _decode_body(body: bytes, headers: Message) -> str:
        content_encoding = (headers.get("Content-Encoding") or "").lower()
        if content_encoding == "gzip":
            body = gzip.decompress(body)
        charset = headers.get_content_charset() or "utf-8"
        return body.decode(charset, errors="replace")


def _detect_block_page(html: str) -> str | None:
    sample = html[:500_000].lower()
    captcha_markers = ("g-recaptcha", "hcaptcha", "captcha-container", "cf-chl-")
    if any(marker in sample for marker in captcha_markers) or re.search(
        r"\b(?:verify you are human|captcha)\b", sample
    ):
        return "Art des Seitenschutzes: CAPTCHA oder Bot-Challenge. Manuelle Prüfung erforderlich."
    if re.search(r"<input\b[^>]*\btype\s*=\s*['\"]?password\b", sample):
        return "Art des Seitenschutzes: Login-Sperre mit Passwortfeld. Manuelle Prüfung erforderlich."
    if "just a moment" in sample and "cloudflare" in sample:
        return "Art des Seitenschutzes: Cloudflare-Blockseite. Manuelle Prüfung erforderlich."
    if "/chl/js/" in sample and "challenge" in sample:
        return "Art des Seitenschutzes: JavaScript-Challenge. Direkte Rechtstext-Unterseiten werden geprüft."
    return None
