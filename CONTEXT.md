# MucLegal – Repository-Kontext

Stand: 20. August 2026

Diese Datei ist die technische Übergabe für Menschen und Coding-Agents. Verbindliche
Projektgrenzen stehen zusätzlich in `AGENTS.md`.

## Zweck

MucLegal überwacht öffentlich erreichbare Webinhalte nach einer Unterlassungserklärung oder
einem Urteil. Der fachliche Kern ist nicht der wortgleiche Textvergleich, sondern die Prüfung,
ob eine geänderte Darstellung eine kerngleiche Verletzungsform sein kann. Jeder Modelloutput
bleibt ein Prüfentwurf; die abschließende Entscheidung liegt bei einer Juristin.

## Aktuell funktionsfähig

- Konservativer HTTP-Abruf mit identifizierbarem User-Agent, Timeouts, Retry und `robots.txt`.
- Abbruch bei internen Zielen, Login, CAPTCHA oder erkannten Blockseiten.
- Unveränderte lokale Speicherung von HTML und Response-Headern.
- Deterministische NFKC-Normalisierung und konfigurierbare, eng begrenzte CSS-Rauschfilter.
- Seiten- und Klausel-Hashes mit SHA-256 sowie persistierte Klauseln in SQLite.
- Klausel-Split nach rechtlicher Gliederung, Überschrift/Absatz und begrenztem Textblock-Fallback.
- Paarung geänderter Klauseln über Gliederung, Position und `difflib`-Ähnlichkeit.
- Sicherheitsgates: verdächtig kurze Extraktion oder mehr als 50 Prozent Klauselverlust erzeugen
  keinen automatischen Diff beziehungsweise Beseitigt-Befund.
- Optionaler Full-Page-Screenshot mit Playwright, eigenem SHA-256-Hash und Snapshot-Zuordnung.
- Tenor-Entwurf über Anthropic oder deterministischen Offline-Fallback mit striktem Schema.
- Juristische Vorprüfung über Anthropic; Roh-HTML und Screenshot verlassen das System nicht.
- Vier Klassen im neuen Klauselschema: `beseitigt`, `kerngleich`, `neuer_sachverhalt`, `unsicher`.
- Fail-closed-Validierung: unbekanntes Tenor-Element oder nicht wörtlich vorhandenes Zitat wird
  zu `unsicher`.
- WARC/CDX, Hash-Manifest, optionale Wayback-Sicherung, RFC-3161-Versuch und PDF-Bericht.
- Screenshot-Vorschau sowie vollständige Artefaktliste im Proof-Panel.
- Menschliche Freigabe getrennt von Modelloutput; Modell darf sie nie selbst setzen.
- SQLite-Trigger verhindern Änderung/Löschung fachlicher Befunddaten; nur `juristin_*` ist änderbar.
- Versionierte API unter `/api/v1/`; alte `/api/...`-Pfade sind vorläufige Aliase.
- Eval-Suite, Blindprüfbögen und Sicherheits-/Regressionstests.

## Reale Live-Nutzung

Das BeweisLab wird ausschließlich lokal betrieben. Der verbindliche Stabilitäts-, Ressourcen-
und Löschplan für die nächste Umsetzung steht in
`reference/LOCAL_BEWEISLAB_IMPLEMENTATION_PLAN.md`. Es gibt keine produktive Web-URL;
Erfassung und Artefaktbereitstellung laufen ausschließlich auf dem lokalen Rechner.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[demo]"
.venv\Scripts\python -m playwright install chromium
$env:ANTHROPIC_API_KEY = Read-Host -MaskInput "Anthropic API-Key"
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Danach:

- Oberfläche: `http://127.0.0.1:8000`
- API-Dokumentation: `http://127.0.0.1:8000/api/v1/docs`
- Laufdaten: `.muclegal-ui/`

Beweisartefakte dürfen im lokalen Standardbetrieb nicht zu einem Fremdspeicher hochgeladen werden.
Die vollständige lokale Löschung samt Nachweis ist Teil des genannten Umsetzungsplans.

Der erste Abruf einer URL erzeugt die Baseline. Nur ein später veränderter normalisierter Inhalt
startet die LLM-Vorprüfung und das vollständige Dokumentationspaket.

Eine einzelne URL inklusive Screenshot lässt sich auch per CLI prüfen:

```powershell
python -m muclegal check --url https://example.com/ `
  --profile fixtures/public-smoke-profile.json --store .muclegal --screenshot
```

## Daten und Artefakte

SQLite und große Dateien sind bewusst getrennt:

- SQLite: Snapshot-Metadaten, Qualitätsstatus, Klauseln, Screenshot-Metadaten, Tenoren und Befunde.
- Dateiablage: Roh-HTML, Header, normalisierter Text, Diff, PNG, Modellinput/-output, WARC/CDX,
  Manifest, TSA-Dateien und PDF.
- Lokale Laufverzeichnisse sind über `.gitignore` ausgeschlossen.

Das Normalisierungsprofil legt fest:

- optional den einzuschließenden Hauptbereich,
- explizit zu entfernende Selektoren,
- selektorspezifische volatile Werte und ihre typisierten Marker.

Rechtlich relevante Preise, Fristen, Verfügbarkeiten oder Klauseln werden nicht durch globale
Regeln entfernt.

## Wichtige Modulgrenzen

- `muclegal/fetch/`: HTTP-Abruf und Playwright-Screenshot.
- `muclegal/normalize/`: Normalisierung und Klausel-Split.
- `muclegal/clause_diff.py`: deterministische Klausel-Zuordnung.
- `muclegal/storage/`: SQLite und lokale Artefaktreferenzen.
- `muclegal/llm/`: ausschließlich gekapselte Modellaufrufe und Validierung.
- `muclegal/evidence/`: WARC, Manifest, Zeitstempel und PDF.
- `muclegal/live.py`: Orchestrierung des echten Live-Golden-Path.
- `muclegal/ui.py`: FastAPI, versionierte API und Übergangsoberfläche.
- `prompts/`: versionierte Prompt-Dateien.

## Bekannte Lücken

- Die klauselscharfe Vierklassen-Validierung ist in Demo und Live-Golden-Path verdrahtet. Geänderte
  Klauseln werden strukturell gepaart, einzeln klassifiziert, schema-validiert, als append-only
  Findings gespeichert und mit eigenen Modellartefakten im UI ausgewiesen. Das bisherige
  Assessment-Format bleibt als deterministisches Aggregat für PDF und Kompatibilität erhalten.
- Rechtstextsuche bleibt konservativ: Links im gespeicherten HTML sowie bekannte
  öffentliche Standardpfade einschließlich Shopify Policies; keine allgemeinen
  Klickpfade und keine automatische Checkout-Erkundung.
- Keine visuelle Interpretation des Screenshots; er ist nur Dokumentationsartefakt.
- Kein Login, keine Paywall, kein CAPTCHA, keine App- oder Newsletter-Erfassung.
- Kein Queue-System, keine Multi-Tenancy und keine autonome Rechtsentscheidung.
- Wayback und freeTSA können ausfallen; das wird sichtbar dokumentiert und blockiert lokale
  Artefakte nicht.
- Die Dokumentationskette ist keine Behauptung eines gerichtsfesten Beweises.

## Qualitätssicherung

```powershell
python -m pytest -q
```

Aktueller Stand bei Erstellung dieser Datei: 62 Tests bestanden. Zusätzlich wurden der echte
Abruf und ein Playwright-Full-Page-Screenshot von `https://example.com/` erfolgreich geprüft.

## Sicherheits- und Rechtsgrenzen

- Nur öffentlich zugängliche Quellen; `robots.txt` wird respektiert.
- Keine Umgehung technischer oder vertraglicher Zugangshürden.
- Keine echten Mandatsdaten im Repository.
- Rohartefakte werden nicht über fremde Extraktionsdienste geleitet.
- Kein fachlicher Output verlässt den Prüfprozess ohne menschliche Freigabe.
