from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import time
from pathlib import Path
from urllib import parse, request


@dataclass(frozen=True)
class WaybackResult:
    status: str
    message: str
    url: str | None = None


class WaybackClient:
    """Optional Save Page Now client; never a primary evidence dependency."""

    def __init__(
        self,
        *,
        access_key: str | None = None,
        secret_key: str | None = None,
        endpoint: str = "https://web.archive.org/save",
        timeout_seconds: float = 15,
        max_attempts: int = 2,
    ) -> None:
        self.access_key = (access_key or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)

    def save(self, url: str, output_directory: str | Path) -> WaybackResult:
        if not self.access_key or not self.secret_key:
            return _write_result(
                output_directory,
                WaybackResult(
                    "not_configured",
                    "Wayback-Zugang fehlt; lokale Beweise bleiben vollständig.",
                ),
            )
        body = parse.urlencode({"url": url, "capture_all": "1"}).encode("ascii")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"LOW {self.access_key}:{self.secret_key}",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                save_request = request.Request(
                    self.endpoint, data=body, headers=headers, method="POST"
                )
                with request.urlopen(save_request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                job_id = payload.get("job_id")
                timestamp = payload.get("timestamp")
                original_url = payload.get("original_url") or url
                archive_url = None
                if timestamp:
                    archive_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                message = f"Save Page Now angenommen (job_id={job_id})."
                return _write_result(
                    output_directory,
                    WaybackResult("submitted", message, archive_url),
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(attempt)
        return _write_result(
            output_directory,
            WaybackResult("unavailable", f"Wayback-Aufnahme fehlgeschlagen: {last_error}"),
        )


def record_wayback_unavailable(output_directory: str | Path) -> WaybackResult:
    """Dokumentiert den optionalen Offline-Pfad; SPN ist kein Primärbeweis."""
    result = WaybackResult(
        status="not_requested",
        message="Wayback Save Page Now ist optional und wurde im Offline-Demopfad nicht angefragt.",
    )
    return _write_result(output_directory, result)


def _write_result(output_directory: str | Path, result: WaybackResult) -> WaybackResult:
    path = Path(output_directory) / "wayback-status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return result

