# AGENTS.md – Unterlassungs- und Umsetzungsmonitor

## Kontext

Hackathon-Prototyp (Legal Loves Tech 2026, München). Finale: 27.08.2026.
Feature-Freeze: 25.08. abends. Ein Entwickler, zwei Juristinnen im Team.
Bewertet wird zu 83 % nicht-technisch – Code muss laufen und lesbar sein,
nicht schön oder vollständig sein.

**Problem:** Nach einem Verbraucherrechtsverstoß gibt ein Unternehmen eine
Unterlassungserklärung ab. Danach prüft niemand nach, ob die Praxis wirklich
eingestellt wurde. Kommt sie abgewandelt zurück, merkt es keiner.

**Kernthese:** Der Verstoß wiederholt sich meist nicht wortgleich, er *wandert*
– andere URL, andere Ebene, anderer Kanal. Text-Diff versagt. Gefragt ist die
juristische Frage der **kerngleichen Verletzungsform**: Ist der aktuelle Zustand
vom Unterlassungstenor erfasst?

**Zielnutzer:** Verbraucherzentralen, Wettbewerbsverbände, IHK, Kanzleien.

## Nicht-Ziele (nicht bauen, auch nicht "schnell nebenbei")

- Login, Benutzerverwaltung, Multi-Tenancy, Rollen
- Dashboard mit mehreren Ansichten
- Datenbank-Migrationen, ORM-Layer, Docker-Compose-Stack
- Vollautomatische Entscheidung ohne menschliche Freigabe
- Vision-/Screenshot-Analyse (Roadmap, nicht Scope)
- Klickpfad-Automatisierung, solange Stufe 4 nicht steht

## Harte Grenzen

- **Niemals** Logins überwinden, Paywalls umgehen, CAPTCHAs lösen oder
  technische Schutzmaßnahmen aushebeln. robots.txt respektieren.
- **Beweisspur niemals durch fremde APIs leiten.** Rohes HTML, Header, WARC,
  Screenshot werden selbst erhoben. Nur die Analysespur darf externe
  Extraktions-APIs nutzen.
- Keine echten Mandats- oder Verbandsdaten im Repo. Nur öffentliche Quellen
  und synthetische Beispiele.
- Kein Output verlässt das System ohne `freigabe_durch_mensch`.

## Architektur – vier Stufen

1. **Täglich, kostenlos:** abrufen → normalisieren (Zeitstempel, Session-IDs,
   Cookie-Banner, Werbeblöcke entfernen) → Hash. Unverändert = Ende.
   *Die Normalisierung ist der Kern. Ohne sie ändert sich jeder Hash täglich.*
2. **Bei Hash-Änderung:** Embedding-Vorfilter lokalisiert die geänderte Passage.
3. **Bei Kandidat:** LLM prüft Kerngleichheit gegen den Tenor. Output immer mit
   Begründung und Confidence, nie nur ja/nein.
4. **Bei bestätigtem Treffer:** WARC + SHA-256-Hashkette + RFC-3161-Zeitstempel
   (freeTSA) + Wayback Save Page Now → PDF-Beweispaket.

Kostenlogik: Stufe 1 läuft täglich und darf nichts kosten. Stufe 3 läuft
10–20×/Jahr pro Fall. Stufe 4 idealerweise nie.

## Stack

- Python 3.11+
- Playwright (Rendering, Beweisspur)
- trafilatura (Boilerplate-Entfernung); optional Firecrawl/Jina Reader nur
  in der Analysespur
- Anthropic SDK: `claude-sonnet-5` für Kerngleichheitsprüfung,
  `claude-haiku-4-5` für Vorfilter/Klassifikation
- WARC via `wget --warc` oder pywb
- rfc3161-Client gegen freeTSA
- Persistenz: SQLite + Dateiablage. Kein Postgres, kein ORM.
- UI: ein einziger Screen (FastAPI + Jinja oder Streamlit). Kein SPA-Framework.

## Datenmodell

Tenor-Objekt:

```json
{
  "fall_id": "VZ-2024-0417",
  "schuldner": "Beispiel Moebel GmbH",
  "ue_datum": "2024-11-08",
  "vertragsstrafe": {"modus": "neuer_hamburger_brauch", "richtwert_eur": 5100},
  "tenor": "Es wird untersagt, mit zeitlich befristeten Rabattaktionen zu
             werben, wenn die angegebene Frist tatsaechlich nicht besteht.",
  "verbotene_praxis": "kuenstliche Dringlichkeit ohne realen Hintergrund",
  "kerngleich_umfasst": ["Countdown", "Restmengenanzeige", "nur heute"],
  "nicht_umfasst": ["echte befristete Aktion mit belegbarem Enddatum"],
  "kanaele": ["Startseite", "PDP", "Checkout", "Newsletter"],
  "rechtsgrundlage": ["§ 5 UWG", "§ 8 Abs. 1 UWG"]
}
```

Befund-Objekt:

```json
{
  "fall_id": "VZ-2024-0417",
  "erkannt_am": "2025-06-14T03:12:00Z",
  "url": "https://.../angebote",
  "fundstelle": "Nur noch 3 Stueck auf Lager - Aktion endet in Kuerze",
  "kerngleich": true,
  "confidence": 0.86,
  "begruendung": "Andere Formulierung, identische Wirkung.",
  "beweis": {"warc_sha256": "...", "tsa_token": "...", "wayback_url": "..."},
  "freigabe_durch_mensch": null
}
```

`nicht_umfasst` ist das wichtigste Feld gegen Fehlalarme. `freigabe_durch_mensch`
bleibt `null`, bis ein Mensch im UI bestätigt – das ist die RDG-Antwort.

## Konventionen

- Deutsche Fachbegriffe im Datenmodell (Tenor, kerngleich, Fundstelle),
  englische Bezeichner im Code.
- LLM-Aufrufe ausschließlich in `llm/` gekapselt, mit deterministischem
  Fallback-Pfad für Demo ohne Netz.
- Jeder LLM-Output wird gegen ein Schema validiert. Nie ungeprüft weiterreichen.
- Alle Snapshots lokal ablegen – die Live-Demo darf nicht crawlen müssen.
- Prompt-Änderungen nach dem Freeze (Do 20.08. abends) sind verboten:
  die Eval-Zahl hängt daran.

## Prioritätenreihenfolge

1. Stufe 1 (Crawl + Normalisierung + Hash)
2. Stufe 3 (Tenor-Extraktion + Kerngleichheitsprüfung)
3. Stufe 4 (Beweispaket) – der Wow-Moment im Pitch
4. Ein-Screen-UI, ohne Erklärung bedienbar
5. Eval-Auswertung

Bei Zeitmangel: nach unten streichen, nie nach oben.
