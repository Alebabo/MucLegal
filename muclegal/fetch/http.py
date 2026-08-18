from __future__ import annotations

import gzip
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
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

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise FetchFailure("invalid_url", "Nur öffentliche HTTP(S)-URLs sind zulässig.")
        if parsed.username or parsed.password:
            raise FetchFailure(
                "credentials_in_url",
                "URLs mit Zugangsdaten werden nicht abgerufen.",
                manual_review=True,
            )

    def _require_robots_permission(self, url: str) -> None:
        parsed = parse.urlsplit(url)
        robots_url = parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        req = request.Request(robots_url, headers={"User-Agent": self.policy.user_agent})
        try:
            with request.urlopen(req, timeout=self.policy.timeout_seconds) as response:
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
        return "CAPTCHA oder Bot-Challenge erkannt; manuelle Prüfung erforderlich."
    if re.search(r"<input\b[^>]*\btype\s*=\s*['\"]?password\b", sample):
        return "Login-Seite erkannt; manuelle Prüfung erforderlich."
    if "just a moment" in sample and "cloudflare" in sample:
        return "technische Blockseite erkannt; manuelle Prüfung erforderlich."
    return None
