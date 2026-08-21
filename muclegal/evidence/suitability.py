from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TechnicalEvidenceOutcome:
    """One user-facing conclusion for every BeweisLab run.

    The classification describes technical capture quality only.  It is deliberately
    separate from any legal assessment or human approval.
    """

    code: str
    label: str
    tone: str
    what_was_found: str
    meaning: str
    next_action: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_NOT_CAPTURABLE_CODES = {
    "invalid_url",
    "non_public_target",
    "credentials_in_url",
    "robots_disallowed",
    "login_required",
    "paywall",
    "captcha",
}


def classify_technical_evidence(
    *,
    capture_completeness: str,
    has_screenshot: bool,
    has_normalized_text: bool,
    has_raw_capture: bool,
    robots_status: str | None,
    failure_code: str | None = None,
    failure_kind: str | None = None,
    god_mode: bool = False,
) -> TechnicalEvidenceOutcome:
    """Return the canonical four-level technical suitability result."""

    if god_mode:
        return TechnicalEvidenceOutcome(
            code="hinweis",
            label="Nicht als Beleg verwendbar – nur Hinweis",
            tone="danger",
            what_was_found="Es wurde eine ausdrücklich autorisierte technische Demonstrationsaufnahme erstellt.",
            meaning=(
                "God-Mode-Dateien sind von regulären Beweispaketen getrennt und nicht für eine "
                "juristische Verwendung bestimmt."
            ),
            next_action=(
                "Für einen regulären Nachweis die Seite ohne God Mode erneut erfassen und das "
                "Ergebnis menschlich prüfen."
            ),
        )

    if failure_code in _NOT_CAPTURABLE_CODES and not has_screenshot:
        reason = _plain_failure_reason(failure_code, failure_kind)
        return TechnicalEvidenceOutcome(
            code="nicht_erfassbar",
            label="URL nicht erfassbar",
            tone="danger",
            what_was_found=reason,
            meaning="Für diese URL wurde kein regulärer öffentlicher Seiteninhalt aufgenommen.",
            next_action=_not_capturable_action(failure_code),
        )

    error_state = (
        capture_completeness in {"durch_seitenschutz_begrenzt", "technisch_fehlgeschlagen"}
        or failure_code is not None
        or failure_kind in {"schutzseite", "leerer_browserzustand", "verbindungsfehler"}
    )
    if error_state:
        if has_screenshot or has_raw_capture:
            return TechnicalEvidenceOutcome(
                code="hinweis",
                label="Nicht als Beleg verwendbar – nur Hinweis",
                tone="danger",
                what_was_found=(
                    "Die Zielseite zeigte dem automatischen Browser keinen zuverlässig "
                    "auswertbaren Inhalt. Der sichtbare Fehler- oder Schutzzustand wurde gespeichert."
                ),
                meaning=(
                    "Die Aufnahme kann auf eine Veränderung oder ein Zugriffsproblem hinweisen, "
                    "belegt aber nicht den dahinterliegenden Seiteninhalt."
                ),
                next_action=(
                    "Für einen rechtssicheren Nachweis muss ein Mensch die Seite zusätzlich "
                    "manuell sichern."
                ),
            )
        return TechnicalEvidenceOutcome(
            code="nicht_erfassbar",
            label="URL nicht erfassbar",
            tone="danger",
            what_was_found=_plain_failure_reason(failure_code, failure_kind),
            meaning="Es konnte kein auswertbarer Seitenzustand gespeichert werden.",
            next_action="URL und Erreichbarkeit prüfen und die Seite anschließend manuell sichern.",
        )

    if (
        capture_completeness != "vollstaendig_erfasst"
        or robots_status == "ungeprueft"
        or not has_normalized_text
        or not has_screenshot
    ):
        return TechnicalEvidenceOutcome(
            code="eingeschraenkt",
            label="Nur eingeschränkt verwendbar",
            tone="warning",
            what_was_found="Die Seite wurde technisch erfasst, einzelne Bestandteile sind jedoch unvollständig oder ungeprüft.",
            meaning="Die vorhandenen Dateien bleiben prüfbar, genügen aber nicht ohne zusätzliche menschliche Einordnung.",
            next_action="Die genannten Grenzen in den technischen Details prüfen und fehlende Ansichten bei Bedarf manuell sichern.",
        )

    return TechnicalEvidenceOutcome(
        code="technisch_verwendbar",
        label="Als technischer Beleg verwendbar",
        tone="success",
        what_was_found="Die öffentliche Seite und die wesentlichen technischen Artefakte wurden regulär erfasst.",
        meaning="Die Aufnahme ist technisch nachvollziehbar; eine rechtliche Verwertbarkeit wird damit nicht garantiert.",
        next_action="Das Beweispaket herunterladen und Inhalt sowie Verwendung durch einen Menschen prüfen lassen.",
    )


def _plain_failure_reason(code: str | None, detail: str | None) -> str:
    reasons = {
        "invalid_url": "Die eingegebene Adresse ist keine gültige öffentliche HTTP(S)-URL.",
        "non_public_target": "Die Adresse verweist auf ein privates oder lokales Ziel und wurde deshalb nicht abgerufen.",
        "credentials_in_url": "Adressen mit eingebetteten Zugangsdaten werden nicht abgerufen.",
        "robots_disallowed": "robots.txt untersagt den automatischen Abruf für den Projekt-User-Agent.",
        "login_required": "Die Webseite zeigte einen Anmeldezustand.",
        "paywall": "Die Webseite zeigte eine Bezahlschranke.",
        "captcha": "Die Webseite verlangte eine CAPTCHA-Prüfung.",
        "normalization_error": "Der sichtbare Seiteninhalt konnte nicht zuverlässig in Text umgewandelt werden.",
    }
    return reasons.get(code) or detail or "Die technische Aufnahme ist vollständig fehlgeschlagen."


def _not_capturable_action(code: str | None) -> str:
    if code in {"invalid_url", "non_public_target", "credentials_in_url"}:
        return "Eine gültige, öffentliche URL ohne Zugangsdaten eingeben und erneut starten."
    if code == "robots_disallowed":
        return "Die Seite nicht automatisiert abrufen; Berechtigung prüfen und den Zustand gegebenenfalls manuell sichern."
    return "Zugangshürde nicht umgehen; den öffentlich sichtbaren Zustand durch einen Menschen sichern."
