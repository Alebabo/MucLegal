"""Entpackt TENORREGISTER_BUNDLE.md deterministisch nach reference/."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


MARKER = re.compile(r"^===== DATEI: (?P<path>[^=]+?) =====\s*$", re.MULTILINE)


def unbundle(bundle_path: Path, output_dir: Path) -> list[Path]:
    text = bundle_path.read_text(encoding="utf-8")
    markers = list(MARKER.finditer(text))
    if not markers:
        raise ValueError("Keine DATEI-Marker im Bundle gefunden.")

    written: list[Path] = []
    root = output_dir.resolve()
    for index, marker in enumerate(markers):
        relative = Path(marker.group("path").strip())
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsicherer Pfad im Bundle: {relative}")
        target = (root / relative).resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"Pfad verlaesst reference/: {relative}")

        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        content = text[start:end].lstrip("\r\n").rstrip() + "\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        written.append(target)

    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", nargs="?", default="TENORREGISTER_BUNDLE.md")
    parser.add_argument("--output", default="reference")
    args = parser.parse_args()

    written = unbundle(Path(args.bundle), Path(args.output))
    print(f"Tenorregister entpackt: {len(written)} Dateien nach {Path(args.output)}")


if __name__ == "__main__":
    main()
