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

## Aktueller Arbeitsstand (20.08.2026)

- Aktiver Entwicklungsbranch: `agent/live-url-ui`
- Produktion: `https://muclegal-beweislab.vercel.app/beweis-labor`
- Kanonischer BeweisLab-Pfad: URL → robots.txt/HTTP-Abruf → Normalisierung →
  Rechtstextsuche → Haupt-, AGB- und Datenschutz-Screenshot → WARC/CDX →
  SHA-256-Manifest → RFC-3161-Versuch → PDF/ZIP.
- Das BeweisLab ist eine **technische Erfassung ohne juristische Modellentscheidung**.
  Anthropic gehört nur in die spätere Kerngleichheitsprüfung eines freigegebenen Falls.
- Browser-Erfassung erfolgt mit Projekt-User-Agent, `navigator.webdriver=true`, ohne
  Stealth, Proxy, persistentes Profil oder wiederverwendeten Storage-State.
- Neue Beweispakete enthalten `capture_transparency.yaml` und
  `screenshot_interactions.json`; beide liegen vor der Manifestbildung vor.
- Referenzen für neue Agents:
  - `reference/TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md`
  - `reference/BROWSER_MODE_AUDIT.md`
  - `reference/BACKEND_ALIGNMENT_2026-08-20.md`

## Nicht-Ziele (nicht bauen, auch nicht "schnell nebenbei")

- Login, Benutzerverwaltung, Multi-Tenancy, Rollen
- Dashboard mit mehreren Ansichten
- Datenbank-Migrationen, ORM-Layer, Docker-Compose-Stack
- Vollautomatische Entscheidung ohne menschliche Freigabe
- Vision-/Screenshot-Analyse (Roadmap, nicht Scope)
- Allgemeine Klickpfad-Automatisierung. Einzige derzeit erlaubte Ausnahme ist die
  dokumentierte Wahl einer eindeutig datensparsamen Cookie-Option unmittelbar vor
  einem Screenshot.

## Harte Grenzen

- **Niemals** Logins überwinden, Paywalls umgehen, CAPTCHAs lösen oder
  technische Schutzmaßnahmen aushebeln. robots.txt respektieren.
- Vor Screenshots darf höchstens eine sichtbare Cookie-Option wie `Alle ablehnen`,
  `Nur notwendige` oder eine gleichbedeutende datensparsame Auswahl betätigt werden.
  Niemals Zustimmung erteilen. Buttontext und Aktion müssen in
  `screenshot_interactions.json` stehen. Generisches `Ablehnen` ist nur innerhalb
  eines eindeutig erkannten Consent-Kontexts zulässig.
- **Beweisspur niemals durch fremde APIs leiten.** Rohes HTML, Header, WARC,
  Screenshot werden selbst erhoben. Nur die Analysespur darf externe
  Extraktions-APIs nutzen.
- Keine echten Mandats- oder Verbandsdaten im Repo. Nur öffentliche Quellen
  und synthetische Beispiele.
- Kein juristischer Analyse- oder Befundoutput verlässt das System ohne
  `freigabe_durch_mensch`. Ein vom Nutzer ausdrücklich gestartetes BeweisLab darf
  seine rein technischen Beweisartefakte ohne juristische Bewertung zum Download
  bereitstellen.

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
- Monitoring-Demos verwenden eingefrorene lokale Snapshots. Das separat ausgewiesene
  BeweisLab darf nach ausdrücklichem Start durch den Nutzer eine öffentliche URL live
  erfassen; seine Artefakte werden lokal erzeugt und auf Vercel anschließend in Blob
  persistiert.
- Prompt-Änderungen nach dem Freeze (Do 20.08. abends) sind verboten:
  die Eval-Zahl hängt daran.

## Prioritätenreihenfolge

1. Stufe 1 (Crawl + Normalisierung + Hash)
2. Stufe 3 (Tenor-Extraktion + Kerngleichheitsprüfung)
3. Stufe 4 (Beweispaket) – der Wow-Moment im Pitch
4. Ein-Screen-UI, ohne Erklärung bedienbar
5. Eval-Auswertung

Bei Zeitmangel: nach unten streichen, nie nach oben.

## Arbeitsprotokoll für Agents

### Vor Änderungen

1. `git status --short`, aktuellen Branch und Remote prüfen. Fremde Änderungen nicht
   überschreiben.
2. Zuerst `rg`/`rg --files` verwenden. Vor einer neuen Lösung die drei oben verlinkten
   Referenzdateien auf bekannte Ursachen durchsuchen.
3. BeweisLab (`/beweis-labor`) und Fallmonitor (`/`) fachlich getrennt halten.
4. Keine neue externe Beweis-API und keine Schutzumgehung einführen.

### Verifikation

1. Syntax: `python -m compileall -q muclegal app.py`
2. Gesamttests: `python -m pytest -q`
3. Lokal: `python -m uvicorn app:app --host 127.0.0.1 --port 8010`
4. Browser-Smoke-Test: `/beweis-labor` öffnen; URL-Feld, Überprüfungsmodus,
   Prüfverlauf, Pillen, Bildvorschau, Info-Popover und Download prüfen.
5. Für Screenshotänderungen zusätzlich einen synthetischen Consent-Dialog mit
   `Alle ablehnen` testen und sicherstellen, dass `Alle akzeptieren` nie gewählt wird.
6. Nach Vercel-Deploy: Alias öffnen, `vercel inspect` ausführen und einen kleinen
   Live-Lauf mit `https://example.com` prüfen. Ein ausstehender externer Zeitstempel
   ist eine sichtbare Warnung, kein Grund, lokale Primärbeweise zu verwerfen.

### Bekannte Testziele und Grenzen

- `example.com`: stabiler vollständiger Smoke-Test ohne Rechtstextlinks.
- MediaMarkt: Hauptseite sowie AGB-/Datenschutz-Screenshots waren erfolgreich; sehr
  hohe Seiten werden bei 8.000 Pixeln transparent als gekürzt markiert.
- Temu: Hauptseite kann eine JavaScript-Challenge liefern. Schutzart, blockierte URL
  und tatsächlich erfasste öffentliche Unterseite müssen getrennt bleiben.
- IKEA: lokal grundsätzlich renderbar; auf Vercel trat ein seitenspezifisches Schließen
  von Chromium bei der Navigation auf. Nicht als allgemein behoben ausgeben.
- freeTSA und Wayback sind externe Zusatzdienste. Ausfälle werden dokumentiert; WARC,
  Roh-HTML, Screenshot und lokales Manifest bleiben die Primärbeweise.
- Der separate GNU-Wget-WARC-Test ist unter WSL/Wget 1.25.0 sporadisch: Metadaten-
  oder Resource-Records können bei `warcio check` Digestfehler melden. Der produktive
  Golden Path verwendet `capture_snapshot_warc` aus den exakt gespeicherten Bytes und
  muss unabhängig davon bestehen. Einen Wget-Flake niemals als grünen Test ausgeben.

### Vercel

- Chromium wird über `[tool.vercel.scripts]` in `pyproject.toml` installiert; benötigte
  NSS/NSPR-Bibliotheken werden in das Function-Bundle kopiert.
- `.vercelignore` klein halten. Tests, Referenzen, lokale `.muclegal*`-Stores und
  Entwicklungsartefakte dürfen nicht ins Deployment gelangen.
- Das Function-Bundle ist groß und nutzt derzeit Vercels Large-Functions-Beta. Keine
  zusätzlichen Browser oder umfangreichen Binärabhängigkeiten hinzufügen.
- Das Serverless-Dateisystem ist flüchtig. Benutzerrelevante Fallartefakte werden über
  Vercel Blob bereitgestellt; nicht auf Persistenz zwischen Function-Instanzen vertrauen.

### Dokumentationspflicht

Wenn ein neuer produktionsrelevanter Fehler gefunden wird, denselben Turn nutzen, um
`reference/TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md` zu ergänzen: Symptom,
Ursache, Diagnose, Lösung, Verifikation und verbleibende Grenze. Keine Vermutung als
gelöste Ursache dokumentieren.
