from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class WaybackResult:
    status: str
    message: str
    url: str | None = None


def record_wayback_unavailable(output_directory: str | Path) -> WaybackResult:
    """Dokumentiert den optionalen Offline-Pfad; SPN ist kein Primärbeweis."""
    result = WaybackResult(
        status="not_requested",
        message="Wayback Save Page Now ist optional und wurde im Offline-Demopfad nicht angefragt.",
    )
    path = Path(output_directory) / "wayback-status.json"
    path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return result

