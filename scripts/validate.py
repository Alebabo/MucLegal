"""Validiert das Tenorregister und erzeugt die geprüfte Frontend-Datenquelle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TENOR_FIELDS = {
    "id",
    "quelle",
    "gericht_az",
    "fallgruppe",
    "rechtsgrundlage",
    "sachverhalt",
    "tenor_text",
    "tenor_bausteine",
    "kerngleich_umfasst",
    "nicht_umfasst",
}

SEGMENT_KEYS = (
    "verpflichtungsformel",
    "ordnungsmittelandrohung",
    "adressatenkreis",
    "anwendungsbereich",
    "verbotene_handlung",
    "ausnahmevorbehalt",
    "konkrete_verletzungsform",
)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def flatten_bausteine(document: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for segment in SEGMENT_KEYS:
        group = document.get(segment, [])
        if segment == "verbotene_handlung":
            if not isinstance(group, dict):
                raise ValueError("verbotene_handlung muss nach Fallgruppen gegliedert sein.")
            for fallgruppe, items in group.items():
                for item in items:
                    flattened.append({**item, "segment": segment, "fallgruppe": fallgruppe})
        else:
            if not isinstance(group, list):
                raise ValueError(f"{segment} muss eine Liste sein.")
            for item in group:
                flattened.append({**item, "segment": segment})
    return flattened


def validate(reference_dir: Path) -> dict[str, Any]:
    bausteine_path = reference_dir / "bausteine.yaml"
    schema_path = reference_dir / "verstossprofil.schema.yaml"
    tenor_paths = sorted((reference_dir / "tenore").glob("T-*.yaml"))
    if not bausteine_path.exists() or not schema_path.exists() or not tenor_paths:
        raise ValueError("Tenorregister unvollstaendig; zuerst scripts/unbundle.py ausfuehren.")

    baustein_document = load_yaml(bausteine_path)
    schema = load_yaml(schema_path)
    tenore = [load_yaml(path) for path in tenor_paths]
    if not isinstance(baustein_document, dict) or not isinstance(schema, dict):
        raise ValueError("Baustein- oder Schemadatei ist kein YAML-Objekt.")

    bausteine = flatten_bausteine(baustein_document)
    baustein_ids = {item.get("id") for item in bausteine if isinstance(item, dict)}
    tenor_ids = {item.get("id") for item in tenore if isinstance(item, dict)}

    errors: list[str] = []
    for tenor in tenore:
        if not isinstance(tenor, dict):
            errors.append("Tenordatei enthaelt kein Objekt")
            continue
        tenor_id = tenor.get("id", "<ohne ID>")
        missing = sorted(REQUIRED_TENOR_FIELDS - tenor.keys())
        if missing:
            errors.append(f"{tenor_id}: Pflichtfelder fehlen: {', '.join(missing)}")
        for item in tenor.get("tenor_bausteine", []):
            baustein_id = item if isinstance(item, str) else item.get("baustein_id")
            if baustein_id is None:
                continue
            if baustein_id not in baustein_ids:
                errors.append(f"{tenor_id}: unbekannte baustein_id {baustein_id!r}")

    for baustein in bausteine:
        if not isinstance(baustein, dict):
            errors.append("bausteine.yaml enthaelt einen ungueltigen Eintrag")
            continue
        baustein_id = baustein.get("id", "<ohne ID>")
        belegt_in = baustein.get("belegt_in", [])
        for tenor_id in belegt_in:
            if tenor_id not in tenor_ids:
                errors.append(f"{baustein_id}: belegt_in verweist auf unbekannten Tenor {tenor_id}")
        if baustein.get("status") == "vorschlag" and belegt_in:
            errors.append(f"{baustein_id}: status vorschlag erfordert leeres belegt_in")

    if errors:
        raise ValueError("Tenorregister-Validierung fehlgeschlagen:\n- " + "\n- ".join(errors))

    verified = sum(item.get("zitat_geprueft") is True for item in tenore)
    print(
        "Tenorregister geladen: "
        f"{len(tenore)} Tenore, {len(bausteine)} Bausteine, "
        f"{verified} Faelle mit zitat_geprueft: true"
    )
    return {
        "meta": baustein_document.get("meta", {}),
        "bausteine": bausteine,
        "pruefregeln": baustein_document.get("pruefregeln", []),
        "schema": schema,
        "tenore": tenore,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="reference")
    parser.add_argument("--frontend-output")
    args = parser.parse_args()

    data = validate(Path(args.reference))
    if args.frontend_output:
        output = Path(args.frontend_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Gepruefte Frontend-Daten geschrieben: {output}")


if __name__ == "__main__":
    main()
