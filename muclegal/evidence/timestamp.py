from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib import request

from muclegal.evidence.tools import find_tool


TSA_URL = "https://freetsa.org/tsr"
TSA_CERT_URL = "https://freetsa.org/files/tsa.crt"
CA_CERT_URL = "https://freetsa.org/files/cacert.pem"
EXPECTED_TSA_CERT_SHA256 = "8bfb0305bb64e2571ca507552ef3245cb1c2fee8728e0ff8689225081ea13467"
EXPECTED_CA_CERT_SHA256 = "2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438"


@dataclass(frozen=True)
class TimestampResult:
    status: str
    message: str
    query_path: str
    response_path: str | None
    tsa_certificate_path: str | None
    ca_certificate_path: str | None
    tsa_certificate_sha256: str | None
    ca_certificate_sha256: str | None
    fingerprint_source: str


class OpenSslTsaClient:
    def __init__(
        self,
        *,
        openssl_path: str | None = None,
        tsa_url: str = TSA_URL,
        tsa_cert_url: str = TSA_CERT_URL,
        ca_cert_url: str = CA_CERT_URL,
        timeout_seconds: float = 12,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 1,
    ) -> None:
        self.openssl_path = openssl_path or find_tool("openssl")
        self.tsa_url = tsa_url
        self.tsa_cert_url = tsa_cert_url
        self.ca_cert_url = ca_cert_url
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff_seconds = retry_backoff_seconds

    def timestamp_digest(self, digest_hex: str, output_directory: str | Path) -> TimestampResult:
        if len(digest_hex) != 64 or any(char not in "0123456789abcdef" for char in digest_hex.lower()):
            raise ValueError("Ein SHA-256-Digest mit 64 Hex-Zeichen wird erwartet.")
        output_directory = Path(output_directory).resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        query_path = output_directory / "manifest.tsq"
        response_path = output_directory / "manifest.tsr"
        tsa_cert_path = output_directory / "tsa.crt"
        ca_cert_path = output_directory / "cacert.pem"
        status_path = output_directory / "tsa-status.json"
        tsa_cert_sha256: str | None = None
        ca_cert_sha256: str | None = None
        query = subprocess.run(
            [
                self.openssl_path,
                "ts",
                "-query",
                "-digest",
                digest_hex,
                "-sha256",
                "-cert",
                "-out",
                str(query_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if query.returncode != 0:
            raise RuntimeError(f"OpenSSL konnte die Zeitstempelanfrage nicht erzeugen: {query.stderr}")

        last_error: Exception | None = None
        result: TimestampResult | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response_request = request.Request(
                    self.tsa_url,
                    data=query_path.read_bytes(),
                    headers={"Content-Type": "application/timestamp-query"},
                    method="POST",
                )
                with request.urlopen(response_request, timeout=self.timeout_seconds) as response:
                    response_path.write_bytes(response.read())
                self._download(self.tsa_cert_url, tsa_cert_path)
                self._download(self.ca_cert_url, ca_cert_path)
                tsa_cert_sha256 = self._verify_certificate_hash(
                    tsa_cert_path, EXPECTED_TSA_CERT_SHA256, "TSA"
                )
                ca_cert_sha256 = self._verify_certificate_hash(
                    ca_cert_path, EXPECTED_CA_CERT_SHA256, "CA"
                )
                verification = subprocess.run(
                    [
                        self.openssl_path,
                        "ts",
                        "-verify",
                        "-in",
                        response_path.name,
                        "-queryfile",
                        query_path.name,
                        "-CAfile",
                        ca_cert_path.name,
                        "-untrusted",
                        tsa_cert_path.name,
                    ],
                    cwd=output_directory,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                if verification.returncode != 0 or "Verification: OK" not in verification.stdout:
                    raise RuntimeError((verification.stdout + verification.stderr).strip())
                result = TimestampResult(
                    "verified",
                    "RFC-3161-Zeitstempel lokal mit der geprüften freeTSA-Kette verifiziert.",
                    str(query_path),
                    str(response_path),
                    str(tsa_cert_path),
                    str(ca_cert_path),
                    tsa_cert_sha256,
                    ca_cert_sha256,
                    "https://freetsa.org/index_en.php",
                )
                break
            except Exception as exc:  # Externer Dienst darf den lokalen Beweis nicht zerstören.
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.retry_backoff_seconds * attempt)
        if result is None:
            result = TimestampResult(
                "pending",
                f"Zeitstempel offen; lokaler Manifest-Hash bleibt vollständig: {last_error}",
                str(query_path),
                str(response_path) if response_path.is_file() else None,
                str(tsa_cert_path) if tsa_cert_path.is_file() else None,
                str(ca_cert_path) if ca_cert_path.is_file() else None,
                tsa_cert_sha256,
                ca_cert_sha256,
                "https://freetsa.org/index_en.php",
            )
        status_path.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
        return result

    def _download(self, url: str, destination: Path) -> None:
        with request.urlopen(url, timeout=self.timeout_seconds) as response:
            destination.write_bytes(response.read())

    @staticmethod
    def _verify_certificate_hash(path: Path, expected: str, label: str) -> str:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"{label}-Zertifikatfingerprint weicht von freeTSA-Angabe ab.")
        return actual
