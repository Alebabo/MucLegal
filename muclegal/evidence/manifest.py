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


def verify_manifest(manifest_path: str | Path) -> VerificationResult:
    manifest_path = Path(manifest_path).resolve()
    bundle_root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    chain = manifest.get("previous_manifest_sha256") or "0" * 64
    for entry in manifest.get("artifacts", []):
        path = (bundle_root / entry["path"]).resolve()
        try:
            path.relative_to(bundle_root)
        except ValueError:
            errors.append(f"Pfad verlässt Paket: {entry['path']}")
            continue
        if not path.is_file():
            errors.append(f"Artefakt fehlt: {entry['path']}")
            continue
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            errors.append(f"Hash weicht ab: {entry['path']}")
        chain = hashlib.sha256(
            f"{chain}\n{entry['label']}\n{entry['path']}\n{entry['sha256']}".encode("utf-8")
        ).hexdigest()
        if chain != entry["chain_sha256"]:
            errors.append(f"Hashkette weicht ab: {entry['path']}")
    if chain != manifest.get("chain_head_sha256"):
        errors.append("Kettenkopf weicht ab.")
    return VerificationResult(not errors, tuple(errors), sha256_file(manifest_path))

