"""Expliziter, nicht automatisch gewählter Browser-Fallback."""


class PlaywrightUnavailable(RuntimeError):
    pass


def fetch_with_playwright(url: str) -> None:
    """Reserve für vorab klassifizierte JS-Seiten; nicht Teil des Day-1-Pfads."""
    raise PlaywrightUnavailable(
        f"Für {url!r} ist kein Browser-Abruf konfiguriert. "
        "Der HTTP-Modus wird niemals automatisch gewechselt."
    )

