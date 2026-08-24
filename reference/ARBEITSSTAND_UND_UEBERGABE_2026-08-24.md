# Arbeitsstand und Übergabe – 24.08.2026

## Kurzfassung

Der Branch `agent/live-url-ui` enthält den konsolidierten Demo-Stand für den
Fallmonitor, die Tenorschreibhilfe und das technisch getrennte BeweisLab.

Die wichtigsten Ergebnisse:

- Die Tenorschreibhilfe erzeugt über OpenAI zwei fallbezogene, unterscheidbare
  Entwürfe: **Präzise** und **Technikneutral**.
- Beide Entwürfe sind kompakt angeordnet und auf einem üblichen Desktopbildschirm
  ohne Seiten-Scrollen sichtbar. Auf Mobilgeräten zeigt der Button den laufenden
  KI-Vorgang eindeutig an.
- Das vom Nutzer bereitgestellte MucLegal-Logo steht oben links in der Navigation.
- Das BeweisLab verwendet in der Oberfläche den Begriff **Grey Mode**. Interne
  Bezeichner wie `god_mode` bleiben vorläufig aus Kompatibilitätsgründen bestehen.
- Das React-Frontend auf Port `4173` ist die maßgebliche Demooberfläche. Das
  FastAPI-Backend auf Port `8000` stellt APIs und das BeweisLab bereit.
- Eine öffentliche Vorführung ist nur als ausdrücklich gestarteter, zeitlich
  begrenzter ngrok-Tunnel zulässig. Beweisartefakte und API-Schlüssel bleiben lokal.

## 1. Tenorschreibhilfe und OpenAI

### Ablauf

1. Der Nutzer beschreibt den konkreten Fall oder wählt einen vorhandenen Fall.
2. Das Frontend sendet die strukturierten Falldaten an
   `POST /api/v1/tenor-proposals`.
3. Das Backend erstellt nacheinander zwei schema-validierte Entwürfe mit den
   Strategien `precise` und `neutral`.
4. Das Frontend zeigt beide Entwürfe nebeneinander, editierbar und mit Modell- und
   Quellenhinweis an.
5. Eine menschliche Auswahl und Prüfung bleibt zwingend. Die API liefert deshalb
   für jeden Entwurf `human_approval_required: true` und
   `freigabe_durch_mensch: null`.

### Technische Leitplanken

- Modellstandard: `gpt-5.6-luna`, überschreibbar durch
  `MUCLEGAL_OPENAI_TENOR_MODEL`.
- OpenAI Responses API mit strengem JSON-Schema und `store=False`.
- Der bestehende versionierte `TENOR_SYSTEM_PROMPT` wurde nicht verändert.
- Fall-ID und Schuldner dürfen durch den Modelloutput nicht verändert werden.
- Identische Antworten für beide Strategien werden als Fehler verworfen.
- Fehlermeldungen werden vor der Ausgabe von möglichen API-Schlüsseln bereinigt.
- Ein aufgebrauchtes API-Guthaben wird in verständlicher deutscher Sprache gemeldet.

### Fachliche Referenz

Die Vorschläge nutzen jetzt die strukturierte Referenzversion
`Unterlassungsmonitor-Wissensdokument-2026-08-24-v1`. Sie enthält zehn kompakte
Leitlinien, den statusbehafteten Katalog FALL-001 bis FALL-011 und eine
Klauseltypen-Bibliothek. Pro Aufruf werden nur die zum Sachverhalt passenden
Einträge übergeben. Herkunft, Quellhash und fehlende juristische Freigabe bleiben
im Modellinput erhalten. Einzelheiten stehen in
`reference/KI_WISSEN_INTEGRATION_2026-08-24.md`.

### Grenzen

- Ein hochgeladener PDF-Dateiname allein gilt noch nicht als analysierter
  Sachverhalt und aktiviert die Generierung nicht.
- Die Entwürfe ersetzen keine Prüfung von Antrag, Aktivlegitimation, konkreter
  Verletzungsform, Rechtskraft oder Vollstreckungsfähigkeit.
- Der Server benötigt einen gültigen OpenAI-Projektschlüssel mit API-Guthaben.

## 2. Frontend und Bedienung

### Geänderte Oberfläche

- `frontend/public/muclegal-logo.png`: aus der vom Nutzer bereitgestellten
  Logodatei übernommen.
- `AppSidebar.tsx`: großes Logo oben links; im eingeklappten Zustand bleibt die
  kompakte Kennzeichnung `MLM` erhalten.
- `MinimalTenorView.tsx`: kleinere Entwurfsflächen, flexibles Höhenlayout,
  editierbare Vorschläge, sichtbare API-Fehler und eindeutiger Ladezustand. Nach
  Auswahl öffnet sich genau ein Vorschlag in einer breiten Lese- und
  Bearbeitungsansicht; erst ein weiterer Klick übernimmt ihn.
- `MaskTenorView.tsx`: der redundante große Erklärungskopf ist entfernt. Nach der
  Erzeugung verschwindet die Eingabespalte und der Prüfentwurf nutzt die gesamte
  Inhaltsbreite; der Sachverhalt kann über eine eigene Aktion erneut geöffnet werden.
- `routes/index.tsx`: ein im Router-Loader erzeugter Zeitwert verhindert eine
  SSR-/Client-Hydration-Abweichung.

### Maßgebliche Adressen

| Zweck | Lokal |
| --- | --- |
| React-Fallmonitor und Tenorschreibhilfe | `http://127.0.0.1:4173/` |
| Tenorschreibhilfe | `http://127.0.0.1:4173/tenorhilfe` |
| BeweisLab über Frontend-Proxy | `http://127.0.0.1:4173/beweis-labor` |
| FastAPI direkt | `http://127.0.0.1:8000/` |

Für die Demo darf nicht Port `8000` als vermeintliches neues Frontend geteilt
werden. Der Tunnel muss auf Port `4173` zeigen; Vite leitet `/api`,
`/beweis-labor`, `/artifact` und `/static` an FastAPI weiter.

## 3. Grey Mode und BeweisLab

Die sichtbare Bezeichnung wurde von **God Mode** auf **Grey Mode** umgestellt.
Bestehende interne Felder, Verzeichnisse und Kompatibilitätspfade mit `god_mode`
bleiben zunächst erhalten, damit gespeicherte Fälle und APIs nicht brechen.

Wesentliche Änderungen:

- Neutrale graue Kennzeichnung in Bildern und PDFs.
- Dateinamen wie `GREY_MODE.txt`, `grey-mode-editorial-summary.md` und
  `grey-mode-ai-usage.json`.
- Keine automatische technische Herabstufung allein aufgrund des aktivierten
  Modus. Die technische Eignung richtet sich nach dem tatsächlich erfassten
  Zustand.
- Grey-Mode-Artefakte bleiben anhand des Modus von regulären Beweisen
  unterscheidbar.
- Die separate Umschaltung „Automatische Überprüfung“ wurde aus der Oberfläche
  entfernt. Der Grey Mode aktiviert den Browser-/Überprüfungspfad gemeinsam.
- Die ausführliche Ergebnisbox mit interpretierenden Folgefragen wurde zugunsten
  einer kompakteren technischen Ergebnisdarstellung entfernt.

Grey Mode ist kein Freibrief für fremde Zugangsdaten, Logins, Paywalls, CAPTCHAs,
Schwachstellenausnutzung oder Identitätstäuschung. Ziel, Berechtigungsgrundlage,
Funktionen und Zeitpunkt werden weiterhin protokolliert.

## 4. Lokale Konfiguration und Geheimnisse

Die Datei `.env.example` dokumentiert alle benötigten Variablennamen ohne echte
Werte. Für die lokale Nutzung:

```powershell
Copy-Item .env.example .env
# Danach OPENAI_API_KEY in .env eintragen.
```

`app.py` lädt die lokale `.env` mit `override=True`. Das ist beabsichtigt, weil
eine bereits gestartete Desktop-Sitzung andernfalls einen veralteten globalen
`OPENAI_API_KEY` über den projektspezifischen Schlüssel stellen kann.

Sicherheitsregeln:

- `.env` und `.env.*` bleiben ignoriert; nur `.env.example` wird versioniert.
- Schlüssel niemals in Browsercode, URLs, Logs, Screenshots oder Dokumentation
  schreiben.
- Im Chat geteilte OpenAI- und ngrok-Zugangsdaten nach der Demo rotieren.
- Für eine öffentliche Demo einen isolierten Store verwenden, zum Beispiel
  `MUCLEGAL_STORE=.muclegal-demo`, und ausschließlich synthetische oder öffentliche
  Daten zeigen.

## 5. Start, Neustart und temporäre ngrok-Demo

### Backend

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

### Temporärer Tunnel

Nur nach ausdrücklicher Freigabe und ohne Schlüssel in der Befehlszeile oder URL:

```powershell
ngrok http 4173 --host-header=rewrite
```

Der jeweils erzeugte Link ist flüchtig. Soweit verfügbar, ist ngrok-Zugriffsschutz
zu aktivieren. Nach der Vorführung den Tunnelprozess beenden. Ein offener Tunnel
ohne Zugriffsschutz kann die OpenAI-Funktion auf Kosten des hinterlegten Projekts
aufrufen.

## 6. API-Übersicht der neuen Tenorvorschläge

`POST /api/v1/tenor-proposals`

Minimale Anfrage:

```json
{
  "fall_id": "VZ-DEMO-001",
  "schuldner": "Synthetische Beispiel GmbH",
  "fundstelle": "https://example.org/angebot",
  "context": "Konkrete Beschreibung der beanstandeten geschäftlichen Handlung.",
  "fallgruppe": "irrefuehrende_werbung",
  "rechtsgrundlagen": ["§ 5 UWG", "§ 8 Abs. 1 UWG"]
}
```

Die Antwort enthält genau zwei Einträge unter `proposals`, jeweils mit Strategie,
Titel, Text, Quellenkennungen, Warnungen und dem unveränderten menschlichen
Freigabestatus.

## 7. Verifikation am 24.08.2026

| Prüfung | Ergebnis |
| --- | --- |
| `python -m compileall -q muclegal app.py` | bestanden |
| `python -m pytest -q` | **139 bestanden** in 148,91 s |
| `npm run typecheck` | bestanden |
| `npm run test:minimal` | **5 bestanden** |
| `npm run build` | bestanden |
| `npm run lint` | 0 Fehler, 6 vorhandene Fast-Refresh-Warnungen |

Der dokumentierte sporadische GNU-Wget-WARC-Digestfehler trat in diesem Lauf nicht
auf. Er bleibt als bekannte externe Testgrenze in
`TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md` dokumentiert.

Zusätzlich wurden lokal und über den temporären Tunnel geprüft:

- Dashboard und Logo auf Desktop und Mobilgerät.
- Tenorschreibhilfe bei `390 × 844` Pixeln einschließlich Button-Hit-Test und
  sichtbarem Ladehinweis.
- Reale OpenAI-Antwort mit zwei verschiedenen Strategien und zwingender
  menschlicher Prüfung. Der AGB-Livetest verwendete die neue Wissensversion und
  elf passende Quellenanker einschließlich FALL-001 und FALL-009.
- Frontend-Proxy zum FastAPI-Endpunkt.

## 8. Wichtige Dateien

| Datei | Zweck |
| --- | --- |
| `app.py` | `.env`-Ladung und Auswahl der KI-Adapter |
| `muclegal/llm/tenor.py` | OpenAI-Adapter, Schemavalidierung und zwei Strategien |
| `muclegal/ui.py` | FastAPI-Endpunkt und sichere Fehlerabbildung |
| `frontend/src/components/tenor/MinimalTenorView.tsx` | kompakte KI-Tenoroberfläche |
| `frontend/src/lib/tenor-api.ts` | typisierte Client-API |
| `frontend/src/components/AppSidebar.tsx` | Logo in der Navigation |
| `muclegal/templates/evidence_lab.html` | kompakte Grey-Mode-BeweisLab-Oberfläche |
| `muclegal/evidence/suitability.py` | technische Eignung nach Erfassungsqualität |
| `reference/HETZNER_DEMO_UPDATE_RUNBOOK.md` | reproduzierbares Hetzner-Update und Rollback |
| `reference/TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md` | Fehlerbilder, Ursachen und Lösungen |

## 9. Bekannte Grenzen und nächste Schritte

- Die temporäre Hetzner-Demo ist durch Caddy Basic Auth geschützt und wird am
  28.08.2026 um 23:59 Uhr Berliner Zeit automatisch abgeschaltet. Der Server bleibt
  danach kostenpflichtig, bis er in der Hetzner-Konsole gelöscht wird.
- Der OpenAI-Schlüssel liegt root-only außerhalb der Releases. Dennoch kann jeder mit
  gültigen Demo-Zugangsdaten Generierungsaufrufe auslösen.
- Die internen `god_mode`-Bezeichner sollten erst in einer getrennten, vollständig
  migrationsfähigen Änderung umbenannt werden.
- Die sechs ESLint-Warnungen liegen in generischen UI-Komponenten und blockieren den
  Build nicht.
- Vor der finalen Vorführung: Prozesse neu starten, `/tenorhilfe` einmal generieren,
  `/beweis-labor` mit `https://example.com` prüfen, die geschützte HTTPS-Adresse am
  Mobilgerät testen und nach der Demo den Server löschen oder bewusst abschalten.

## 10. Hetzner-Demo und Aktualisierungen

Der am 24.08.2026 geprüfte Stand läuft als getrennte Backend- und Frontend-Dienste
hinter Caddy. Beide Anwendungsports sind nur an Loopback gebunden; öffentlich sind
nur SSH, HTTP und HTTPS geöffnet. Quellcode-Releases liegen unter
`/opt/muclegal/releases`, während `/var/lib/muclegal-demo` und
`/etc/muclegal/muclegal.env` bei Updates unverändert bleiben.

Der verbindliche Update- und Rollback-Ablauf einschließlich lokaler Tests, GitHub-
Push, Releasearchiv, atomarer Aktivierung, Dienstprüfung und Entire-Abschluss steht in
[`HETZNER_DEMO_UPDATE_RUNBOOK.md`](HETZNER_DEMO_UPDATE_RUNBOOK.md).
