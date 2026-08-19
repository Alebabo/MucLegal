from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


def prepare_blind_review(
    suite_path: str | Path,
    output_directory: str | Path,
    reviewers: tuple[str, ...] = ("juristin-a", "juristin-b"),
) -> list[str]:
    suite_path = Path(suite_path).resolve()
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    root = suite_path.parent
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for reviewer in reviewers:
        cases: list[dict] = []
        for case in suite["cases"]:
            case_input = case.get("input")
            if not isinstance(case_input, dict):
                input_path = (root / case["input_path"]).resolve()
                input_path.relative_to(root)
                case_input = json.loads(input_path.read_text(encoding="utf-8"))
            cases.append(
                {
                    "id": case["id"],
                    "vorher": case_input["vorher"],
                    "nachher": case_input["nachher"],
                    "belegte_metadaten": case_input["belegte_metadaten"],
                    "bewertung": None,
                    "charakteristischer_kern": "",
                    "staerkstes_gegenargument": "",
                    "erforderliche_zusatzbelege": "",
                }
            )
        seed = int.from_bytes(
            hashlib.sha256(f"{suite['name']}:{reviewer}".encode("utf-8")).digest()[:8],
            "big",
        )
        random.Random(seed).shuffle(cases)
        sheet = {
            "reviewer": reviewer,
            "suite": suite["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "instructions": (
                "Ohne Modelloutput bewerten. Zulässige Bewertungen: "
                "kerngleich_umfasst, nicht_umfasst, unklar. Alle Textfelder ausfüllen."
            ),
            "cases": cases,
        }
        path = output / f"{reviewer}.json"
        path.write_text(
            json.dumps(sheet, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        paths.append(str(path))
    status = {
        "status": "pending_human_review",
        "required_reviewers": list(reviewers),
        "case_count": len(suite["cases"]),
        "completed_reviewers": [],
    }
    (output / "blind-review-status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return paths
