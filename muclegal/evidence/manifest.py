from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ManifestResult:
    manifest_path: str
    digest_path: str
    manifest_sha256: str
    chain_head_sha256: str


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    errors: tuple[str, ...]
    manifest_sha256: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_manifest(
    artifacts: dict[str, str | Path],
    bundle_root: str | Path,
    *,
    previous_manifest_sha256: str | None = None,
    notice: str | None = None,
) -> ManifestResult:
    bundle_root = Path(bundle_root).resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    if previous_manifest_sha256 is not None and not _is_sha256(previous_manifest_sha256):
        raise ValueError("previous_manifest_sha256 muss ein SHA-256-Digest sein.")
    entries: list[dict] = []
    chain = previous_manifest_sha256 or "0" * 64
    for label in sorted(artifacts):
        path = Path(artifacts[label]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            relative = path.relative_to(bundle_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Artefakt liegt außerhalb des Beweispakets: {path}") from exc
        digest = sha256_file(path)
        chain = hashlib.sha256(f"{chain}\n{label}\n{relative}\n{digest}".encode("utf-8")).hexdigest()
        entries.append(
            {
                "label": label,
                "path": relative,
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "chain_sha256": chain,
            }
        )
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hash_algorithm": "sha256",
        "previous_manifest_sha256": previous_manifest_sha256,
        "artifacts": entries,
        "chain_head_sha256": chain,
        "notice": notice,
    }
    manifest_path = bundle_root / "manifest.json"
    digest_path = bundle_root / "manifest.sha256"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    manifest_digest = sha256_file(manifest_path)
    digest_path.write_text(f"{manifest_digest}  manifest.json\n", encoding="ascii", newline="\n")
    return ManifestResult(str(manifest_path), str(digest_path), manifest_digest, chain)


def verify_manifest(
    manifest_path: str | Path,
    *,
    expected_manifest_sha256: str | None = None,
    require_digest_file: bool = False,
) -> VerificationResult:
    manifest_path = Path(manifest_path).resolve()
    bundle_root = manifest_path.parent
    errors: list[str] = []
    if not manifest_path.is_file():
        return VerificationResult(False, ("Manifestdatei fehlt.",), "")

    manifest_sha256 = sha256_file(manifest_path)
    if expected_manifest_sha256 is not None:
        if not _is_sha256(expected_manifest_sha256):
            errors.append("Erwarteter Manifest-Hash ist kein gültiger SHA-256-Digest.")
        elif manifest_sha256 != expected_manifest_sha256.lower():
            errors.append("Erwarteter Manifest-Hash weicht ab.")

    digest_path = manifest_path.with_name("manifest.sha256")
    if digest_path.is_file():
        try:
            digest_parts = digest_path.read_text(encoding="ascii").strip().split()
        except (OSError, UnicodeError) as exc:
            errors.append(f"Manifest-Digest ist nicht lesbar: {type(exc).__name__}.")
        else:
            if (
                len(digest_parts) != 2
                or not _is_sha256(digest_parts[0])
                or digest_parts[1] != manifest_path.name
            ):
                errors.append("Manifest-Digestdatei hat ein ungültiges Format.")
            elif digest_parts[0].lower() != manifest_sha256:
                errors.append("Manifest-Digest weicht ab.")
    elif require_digest_file:
        errors.append("Manifest-Digestdatei fehlt.")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Manifest ist nicht als JSON lesbar: {type(exc).__name__}.")
        return VerificationResult(False, tuple(errors), manifest_sha256)
    if not isinstance(manifest, dict):
        errors.append("Manifestwurzel muss ein JSON-Objekt sein.")
        return VerificationResult(False, tuple(errors), manifest_sha256)
    if manifest.get("version") != 1:
        errors.append("Manifestversion wird nicht unterstützt.")
    if manifest.get("hash_algorithm") != "sha256":
        errors.append("Manifest verwendet nicht den erwarteten Hashalgorithmus sha256.")

    previous = manifest.get("previous_manifest_sha256")
    if previous is not None and not _is_sha256(previous):
        errors.append("Vorheriger Manifest-Hash ist ungültig.")
        chain = "0" * 64
    else:
        chain = previous.lower() if isinstance(previous, str) else "0" * 64

    entries = manifest.get("artifacts")
    if not isinstance(entries, list):
        errors.append("Artefaktliste muss ein JSON-Array sein.")
        return VerificationResult(False, tuple(errors), manifest_sha256)

    seen_labels: set[str] = set()
    seen_paths: set[str] = set()
    chain_computable = True
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"Artefakteintrag {index} muss ein JSON-Objekt sein.")
            chain_computable = False
            continue
        label = entry.get("label")
        relative = entry.get("path")
        expected_sha256 = entry.get("sha256")
        expected_size = entry.get("size_bytes")
        entry_chain = entry.get("chain_sha256")
        if not isinstance(label, str) or not label:
            errors.append(f"Artefakteintrag {index} hat kein gültiges Label.")
            chain_computable = False
            continue
        if label in seen_labels:
            errors.append(f"Artefaktlabel ist doppelt: {label}")
        seen_labels.add(label)
        if not isinstance(relative, str) or not relative:
            errors.append(f"Artefaktpfad fehlt für Label {label}.")
            chain_computable = False
            continue
        if relative in seen_paths:
            errors.append(f"Artefaktpfad ist doppelt: {relative}")
        seen_paths.add(relative)
        if not _is_sha256(expected_sha256):
            errors.append(f"Artefakt-Hash ist ungültig: {relative}")
            chain_computable = False
            continue
        if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
            errors.append(f"Artefaktgröße ist ungültig: {relative}")
        if not _is_sha256(entry_chain):
            errors.append(f"Kettenwert ist ungültig: {relative}")

        path = (bundle_root / relative).resolve()
        try:
            path.relative_to(bundle_root)
        except ValueError:
            errors.append(f"Pfad verlässt Paket: {relative}")
            continue
        if not path.is_file():
            errors.append(f"Artefakt fehlt: {relative}")
            continue
        actual = sha256_file(path)
        if actual != expected_sha256.lower():
            errors.append(f"Hash weicht ab: {relative}")
        if isinstance(expected_size, int) and not isinstance(expected_size, bool):
            if path.stat().st_size != expected_size:
                errors.append(f"Größe weicht ab: {relative}")
        chain = hashlib.sha256(
            f"{chain}\n{label}\n{relative}\n{expected_sha256}".encode("utf-8")
        ).hexdigest()
        if _is_sha256(entry_chain) and chain != entry_chain.lower():
            errors.append(f"Hashkette weicht ab: {relative}")
    chain_head = manifest.get("chain_head_sha256")
    if not _is_sha256(chain_head):
        errors.append("Kettenkopf ist ungültig.")
    elif chain_computable and chain != chain_head.lower():
        errors.append("Kettenkopf weicht ab.")
    return VerificationResult(not errors, tuple(errors), manifest_sha256)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )

