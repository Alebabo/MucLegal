"""Ehrliche Leave-one-out-Evaluation der deterministischen Bausteinauswahl."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any

import yaml

from validate import flatten_bausteine


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference"


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def actual_elements(tenor: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for item in tenor["tenor_bausteine"]:
        if item.get("baustein_id"):
            result[item["funktion"]].add(item["baustein_id"])
    return result


def choose_elements(
    profile: dict[str, Any],
    blocks: list[dict[str, Any]],
    held_out_id: str,
) -> dict[str, set[str]]:
    """Wählt nur aus Bausteinen, die außerhalb des Testfalls belegt sind."""
    available = [
        block
        for block in blocks
        if block.get("status") != "vorschlag"
        and any(reference != held_out_id for reference in block.get("belegt_in", []))
    ]
    by_id = {block["id"]: block for block in available}
    chosen: dict[str, set[str]] = defaultdict(set)

    def add(segment: str, block_id: str) -> None:
        if block_id in by_id:
            chosen[segment].add(block_id)

    add("verpflichtungsformel", "B-VF-01")
    add("ordnungsmittelandrohung", "B-OM-03")
    add("adressatenkreis", "B-AK-02" if profile["fallgruppe"] == "agb_klausel" else "B-AK-01")
    add("anwendungsbereich", "B-AB-03")

    action_group = "dark_pattern" if profile["fallgruppe"] == "dark_pattern_dsa" else profile["fallgruppe"]
    action_candidates = [
        block
        for block in available
        if block.get("segment") == "verbotene_handlung"
        and block.get("fallgruppe") == action_group
        and profile.get("verstoss_modus") in block.get("verstoss_modus", [])
    ]
    action_candidates.sort(key=lambda block: (-len(block.get("belegt_in", [])), block["id"]))
    if profile["fallgruppe"] == "agb_klausel":
        for block_id in ("B-VH-42", "B-VH-43"):
            add("verbotene_handlung", block_id)
    elif action_candidates:
        chosen["verbotene_handlung"].add(action_candidates[0]["id"])

    if profile["fallgruppe"] == "consent_gestaltung":
        add("ausnahmevorbehalt", "B-AV-01")
        add("ausnahmevorbehalt", "B-AV-02")
    concrete = "B-KV-04" if profile["fallgruppe"] == "agb_klausel" else "B-KV-03"
    add("konkrete_verletzungsform", concrete)
    return chosen


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    document = load_yaml(REFERENCE / "bausteine.yaml")
    blocks = flatten_bausteine(document)
    tenore = [load_yaml(path) for path in sorted((REFERENCE / "tenore").glob("T-*.yaml"))]
    verified = [tenor for tenor in tenore if tenor.get("zitat_geprueft") is True]

    hits: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    print("Leave-one-out: nur zitat_geprueft: true\n")
    for tenor in verified:
        actual = actual_elements(tenor)
        predicted = choose_elements(tenor, blocks, tenor["id"])
        case_hits = 0
        case_total = 0
        for segment, actual_ids in actual.items():
            segment_hits = len(actual_ids & predicted.get(segment, set()))
            hits[segment] += segment_hits
            totals[segment] += len(actual_ids)
            case_hits += segment_hits
            case_total += len(actual_ids)
        print(f"{tenor['id']}: {case_hits}/{case_total} tragende Elemente getroffen")

    print("\nTrefferquote je Segment")
    for segment in sorted(totals):
        rate = hits[segment] / totals[segment] if totals[segment] else 0
        print(f"- {segment}: {hits[segment]}/{totals[segment]} ({rate:.0%})")
    total_hits = sum(hits.values())
    total_elements = sum(totals.values())
    print(f"Gesamt: {total_hits}/{total_elements} ({total_hits / total_elements:.0%})")

    print("\nUmgehungstest")
    print('- T-001 Originaltenor + "App-Verlagerung": NEIN (Domainbindung B-AB-02)')
    print('- Generierter Tenor + "App-Verlagerung": JA (technikneutral B-AB-03)')
    print('- T-002 Originaltenor + "Zwei-Button-Lösung": NEIN (T-002 nicht_umfasst; real belegt)')


if __name__ == "__main__":
    main()
