from __future__ import annotations

from typing import Any


MONITOR_KNOWLEDGE_VERSION = "Unterlassungsmonitor-Wissensdokument-2026-08-24-v1"
MONITOR_KNOWLEDGE_SOURCE_SHA256 = (
    "f537bc5747d3bd2412b7792530088575f2e7a11fe23ba1abd0a60b12ef7cb222"
)
MONITOR_KNOWLEDGE_STATUS = "nutzerbereitgestellt_nicht_juristisch_freigegeben"


MONITOR_GUIDANCE: tuple[dict[str, Any], ...] = (
    {
        "id": "KW-001",
        "groups": ("all",),
        "regel": (
            "Die Vorprüfung ist dreistufig: KERNGLEICH entspricht kerngleich/"
            "kerngleich_umfasst, UNSICHER entspricht unsicher/unklar und NICHT_ERFASST "
            "entspricht neuer_sachverhalt/nicht_umfasst. Bei Zweifel nicht hochstufen."
        ),
    },
    {
        "id": "KW-002",
        "groups": ("all",),
        "regel": (
            "Inter-partes zuerst prüfen: Ein Titel bindet nur den titulierten Schuldner. "
            "Adressatenwechsel und Klauselmigration zu einer anderen juristischen Person "
            "sind für die Vollstreckung aus diesem Titel nicht erfasst."
        ),
    },
    {
        "id": "KW-003",
        "groups": ("all",),
        "regel": (
            "Die Kerntheorie streng anwenden: Nur im Erkenntnisverfahren geprüfte "
            "charakteristische Elemente tragen eine Erweiterung. Eine bewusste Beschränkung "
            "auf die konkrete Verletzungsform nicht überdehnen."
        ),
    },
    {
        "id": "KW-004",
        "groups": ("agb_klausel",),
        "regel": (
            "Bei AGB-Tenoren fünf Bausteine erhalten, soweit belegt: Verbotsadressat, "
            "Verbraucherbezug, Inhaltsgleichheitsformel, Vertragstypbegrenzung und "
            "Doppelausspruch aus Verwenden und Sich-Berufen."
        ),
    },
    {
        "id": "KW-005",
        "groups": ("agb_klausel",),
        "regel": (
            "Bezugnahmeklauseln nur zusammen mit ihrer ausdrücklich genannten "
            "Kontextklausel erfassen. Fehlt der Bezugskontext, darf derselbe Klauselsatz "
            "nicht automatisch als erfasst behandelt werden."
        ),
    },
    {
        "id": "KW-006",
        "groups": ("agb_klausel",),
        "regel": (
            "Klagerücknahmen liefern keinen gerichtlich bestätigten Tenor. Bei fehlendem "
            "Antrag, unklarer Teilabweisung oder bloßem Suchindex-Auszug die Datenlücke "
            "sichtbar lassen und keine zusätzliche Reichweite ableiten."
        ),
    },
    {
        "id": "KW-007",
        "groups": ("agb_klausel",),
        "regel": (
            "Separierte und integrierte Ordnungsmittelandrohungen sind mögliche "
            "Tenorbauformen. Die Bauform ist von der materiellen Reichweite zu trennen; "
            "Beträge und Vollstreckungsadressat sind bei Abweichungen zu prüfen."
        ),
    },
    {
        "id": "KW-008",
        "groups": ("kuendigungsbutton",),
        "regel": (
            "Bei Kündigungswegen den Umgehungsmechanismus vergleichen, nicht nur Wörter: "
            "Login-Hürde, versteckter Zugang, konkurrierende Schaltflächen, Pflichtangaben "
            "und mehrschrittige Sichtbarkeit können unterschiedliche Kerne bilden."
        ),
    },
    {
        "id": "KW-009",
        "groups": ("all",),
        "regel": (
            "Prüfreihenfolge: identischer Schuldner, Vertragstyp und Adressatenkreis; danach "
            "Reichweitenformel, charakteristisches Element und erforderlicher Bezugskontext."
        ),
    },
    {
        "id": "KW-010",
        "groups": ("all",),
        "regel": (
            "Keine Rechtsberatung, keinen Verfahrensausgang und keinen Ordnungsmittelantrag "
            "formulieren. Nur im Input belegte Normen und Quellen verwenden; menschliche "
            "Freigabe bleibt erforderlich."
        ),
    },
)


MONITOR_CASE_REFERENCES: tuple[dict[str, Any], ...] = (
    {
        "id": "FALL-001",
        "groups": ("agb_klausel",),
        "terms": ("fernabsatz", "verbrauchsgüterkauf", "rücksend", "schriftform"),
        "default": True,
        "status_im_wissensdokument": "V",
        "verwendung": (
            "Strukturbeispiel für einen separierten AGB-Tenor mit fünf Pflichtbausteinen "
            "und Bezugnahmeklauseln; keine juristische Freigabe."
        ),
    },
    {
        "id": "FALL-002",
        "groups": ("agb_klausel",),
        "terms": ("finanzsanierung", "beschaffungsgebühr", "fin express"),
        "status_im_wissensdokument": "V_mit_datenluecken",
        "verwendung": (
            "Teilabweisung ohne vollständigen Antrag und abweichender Klauselverwender; "
            "Reichweite und Diff bleiben ausdrücklich ungeklärt."
        ),
    },
    {
        "id": "FALL-003",
        "groups": ("agb_klausel",),
        "terms": ("mietfahrzeug", "kaution", "schlüsselverlust", "geschwindigkeit"),
        "status_im_wissensdokument": "V_ohne_tenor",
        "verwendung": (
            "Negativkorpus nach Klagerücknahme: Klauseln typisieren, aber nicht als "
            "gerichtlich bestätigte Tenorvorbilder verwenden."
        ),
    },
    {
        "id": "FALL-004",
        "groups": ("agb_klausel",),
        "terms": ("tierkranken", "wartezeit", "versicherung"),
        "status_im_wissensdokument": "V_ohne_tenor",
        "verwendung": (
            "Negativkorpus nach Klagerücknahme mit verschachtelten Ausnahmen und fehlendem "
            "Vollstreckungsadressaten im Antrag."
        ),
    },
    {
        "id": "FALL-005",
        "groups": ("agb_klausel",),
        "terms": ("versicherungsvermittlung", "mahngebühr", "formumwandlung"),
        "status_im_wissensdokument": "T",
        "verwendung": (
            "Hinweis auf dokumentierte Formumwandlung und eine Drittgesellschaft im "
            "Klauseltext; Rechtsnachfolge nicht ohne Beleg verallgemeinern."
        ),
    },
    {
        "id": "FALL-006",
        "groups": ("agb_klausel",),
        "terms": ("topmaxx", "finanzsanierung", "klauselmigration"),
        "status_im_wissensdokument": "T",
        "verwendung": (
            "Klauselmigration zwischen verschiedenen Unternehmen: strukturell ähnlich, "
            "aber nicht aus dem fremden Titel vollstreckbar."
        ),
    },
    {
        "id": "FALL-007",
        "groups": ("agb_klausel",),
        "terms": ("photovoltaik", "solar", "demag", "dema"),
        "status_im_wissensdokument": "T",
        "verwendung": (
            "Tippfehlerkorrekturen im Tenor als redaktionelle Abweichung erkennen und "
            "nicht automatisch als materiellen Diff behandeln."
        ),
    },
    {
        "id": "FALL-008",
        "groups": ("agb_klausel",),
        "terms": ("teilliefer", "decathlon", "freistell"),
        "status_im_wissensdokument": "T",
        "verwendung": (
            "Bezugnahmeklausel und Inter-partes-Grenze bei anderem Schuldner; nur den "
            "konkret titulierten Kontext zugrunde legen."
        ),
    },
    {
        "id": "FALL-009",
        "groups": ("agb_klausel",),
        "terms": ("fasten", "gesundheit", "fastic", "rückbelast"),
        "default": True,
        "status_im_wissensdokument": "T",
        "verwendung": (
            "Beispiel einer integrierten Tenorbauform; nur als teilverifizierten "
            "Strukturhinweis verwenden."
        ),
    },
    {
        "id": "FALL-010",
        "groups": ("agb_klausel",),
        "terms": ("fitness", "videoüberwach", "öffnungszeiten"),
        "status_im_wissensdokument": "P",
        "verwendung": (
            "PDF-Auszug zu Fitnessstudio-AGB; wegen P-Status nur als Themen- und "
            "Vertragstyp-Hinweis verwenden."
        ),
    },
    {
        "id": "FALL-011",
        "groups": ("kuendigungsbutton",),
        "terms": ("kündig", "button", "sky", "login", "abo beenden"),
        "default": True,
        "status_im_wissensdokument": "V_mit_datumskonflikt",
        "verwendung": (
            "Sky-Umgehungskette als Unsicherheitsbeispiel bei einem Wechsel des "
            "Gestaltungsmechanismus; das Wissensdokument weist für B-3 einen "
            "Datumswiderspruch aus."
        ),
    },
)


CLAUSE_TYPES: tuple[dict[str, Any], ...] = (
    {"id": "beweislast", "terms": ("beweislast", "gefahrübergang"), "norm": "§ 477 BGB"},
    {"id": "kostenpauschale", "terms": ("pauschal", "mahngebühr", "rückfracht", "rücklastschrift"), "norm": "§ 309 Nr. 5 BGB"},
    {"id": "leistungsaenderung", "terms": ("öffnungszeiten", "leistungsänder", "fahrzeugtausch"), "norm": "§ 308 Nr. 4 BGB"},
    {"id": "kuendigungshindernis", "terms": ("kündig", "login", "abo beenden"), "norm": "§ 312k BGB"},
    {"id": "vertragsstrafe", "terms": ("vertragsstrafe", "schlüsselverlust"), "norm": "§ 309 Nr. 6 BGB"},
    {"id": "haftungsausschluss", "terms": ("haftung", "eigene gefahr", "fahrlässigkeit"), "norm": "§ 309 Nr. 7 BGB"},
    {"id": "einbeziehung", "terms": ("agb gelesen", "agb erhalten", "vertragsgegenstand"), "norm": "§ 305 BGB"},
    {"id": "salvatorisch", "terms": ("unwirksame bestimmung", "wirtschaftlichen zweck"), "norm": "§ 306 BGB"},
    {"id": "schriftform", "terms": ("schriftform",), "norm": "§ 309 Nr. 13 BGB"},
    {"id": "aufrechnungsverbot", "terms": ("aufrechnung",), "norm": "§ 309 Nr. 3 BGB"},
    {"id": "wartezeitklausel", "terms": ("wartezeit",), "norm": "§ 307 BGB"},
    {"id": "abo_umwandlung", "terms": ("wandelt sich", "automatisch in", "abo"), "norm": "§ 308 Nr. 5 BGB / § 312k BGB"},
    {"id": "bezugnahmeklausel", "terms": ("soweit auf", "verwiesen wird"), "norm": "kontextabhängig"},
    {"id": "dark_pattern", "terms": ("dark pattern", "schaltfläche", "nagging"), "norm": "Art. 25 DSA / UWG-Kontext prüfen"},
    {"id": "preisanpassung", "terms": ("preiserhöhung", "preisanpass"), "norm": "§ 307 BGB"},
    {"id": "verlaengerungsklausel", "terms": ("verlängert sich", "vertragsverlänger"), "norm": "§ 309 Nr. 9 BGB"},
)


def build_monitor_knowledge(
    *, fallgruppe: str | None = None, text: str = ""
) -> dict[str, Any]:
    """Return a small, provenance-bearing subset of the user-supplied knowledge."""

    group = fallgruppe or _infer_group(text)
    rules = [
        _public_rule(rule)
        for rule in MONITOR_GUIDANCE
        if "all" in rule["groups"] or group in rule["groups"]
    ]
    lowered = text.casefold()
    case_references = [
        _public_case(item)
        for item in MONITOR_CASE_REFERENCES
        if group in item["groups"]
        and (
            item.get("default", False)
            or any(term in lowered for term in item.get("terms", ()))
        )
    ][:4]
    clause_types = _matching_clause_types(text)
    source_ids = [item["id"] for item in rules]
    source_ids.extend(item["id"] for item in case_references)
    return {
        "version": MONITOR_KNOWLEDGE_VERSION,
        "source_sha256": MONITOR_KNOWLEDGE_SOURCE_SHA256,
        "source_status": MONITOR_KNOWLEDGE_STATUS,
        "fallgruppe": group,
        "leitlinien": rules,
        "fallreferenzen": case_references,
        "erkannte_klauseltypen": clause_types,
        "source_ids": source_ids,
        "hinweis": (
            "Die Wissensbasis ist nutzerbereitgestellt und nicht juristisch freigegeben. "
            "Fallsätze mit T/P-Status oder Datenlücken nur als Hinweis verwenden."
        ),
    }


def _matching_clause_types(text: str) -> list[dict[str, str]]:
    lowered = text.casefold()
    return [
        {"id": item["id"], "typische_norm": item["norm"]}
        for item in CLAUSE_TYPES
        if any(term in lowered for term in item["terms"])
    ][:4]


def _infer_group(text: str) -> str:
    lowered = text.casefold()
    if any(term in lowered for term in ("klausel", "agb", "schriftform")):
        return "agb_klausel"
    if any(term in lowered for term in ("kündig", "kuendig", "abo beenden")):
        return "kuendigungsbutton"
    if any(term in lowered for term in ("cookie", "consent", "tracking")):
        return "consent_gestaltung"
    if any(term in lowered for term in ("dark pattern", "schaltfläche", "nagging")):
        return "dark_pattern_dsa"
    return "allgemein"


def _public_rule(rule: dict[str, Any]) -> dict[str, str]:
    return {"id": rule["id"], "regel": rule["regel"]}


def _public_case(item: dict[str, Any]) -> dict[str, str]:
    return {
        "id": item["id"],
        "status_im_wissensdokument": item["status_im_wissensdokument"],
        "verwendung": item["verwendung"],
    }
