# Frontend-Backend-Übergabe

Stand: 21.08.2026
Branch: `agent/live-url-ui`

## Kurzfassung

Das Backend ist grundsätzlich frontendbereit. Die Python-Module wurden erfolgreich
kompiliert und der vollständige Testlauf bestand mit `126 passed`.

Für das Frontend müssen zwei fachlich getrennte Bereiche unterschieden werden:

1. Das **BeweisLab** unter `/beweis-labor` führt eine rein technische Erfassung ohne
   juristische Kerngleichheitsentscheidung durch.
2. Der **Fallmonitor** unter `/` verwaltet gemeldete Erstverstöße, menschliche
   Freigaben und fallbezogene Monitoringläufe.

Der aktuelle fallbezogene Domain-Monitor ist nicht mit dem vollständigen
Einzel-URL-Golden-Path gleichzusetzen. Er verwendet derzeit exakte Treffer und
Textähnlichkeit, aber keine vollständige LLM-Kerngleichheitsprüfung. Das Frontend
darf diesen Pfad daher nicht als abschließende juristische Prüfung darstellen.

## 1. Lokale Anwendung

| Bereich | URL |
|---|---|
| Fallmonitor | `http://127.0.0.1:8000/` |
| BeweisLab | `http://127.0.0.1:8000/beweis-labor` |
| API-Dokumentation | `http://127.0.0.1:8000/api/v1/docs` |
| OpenAPI-Schema | `http://127.0.0.1:8000/api/v1/openapi.json` |

Start:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Alternativ für das BeweisLab:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/doctor-local-beweislab.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-local-beweislab.ps1
```

## 2. Architektur und Persistenz

- Framework: FastAPI mit Jinja2.
- Statische Dateien werden unter `/static` ausgeliefert.
- Standardablage: `.muclegal-ui/`.
- Die Ablage kann über `MUCLEGAL_STORE` geändert werden.
- SQLite speichert Fallaufnahme, Tenor-Entwürfe und menschliche Entscheidungen.
- Snapshots, Screenshots, WARC, Manifest, PDF und ZIP liegen als lokale Dateien vor.
- Aktive Run-Objekte liegen nur im Arbeitsspeicher und gehen bei einem Serverneustart
  verloren.
- Ein `ThreadPoolExecutor(max_workers=1)` erlaubt höchstens einen aktiven Prüflauf.
- Vorhandene lokale Fälle und Beweispakete werden nicht automatisch gelöscht.

Wichtige Dateien:

| Datei | Zuständigkeit |
|---|---|
| `app.py` | Konfiguration und Zusammensetzen der Anwendung |
| `muclegal/ui.py` | FastAPI-Routen, Run-Koordination und Beweisarchiv |
| `muclegal/live.py` | BeweisLab und Einzel-URL-Golden-Path |
| `muclegal/domain_monitor.py` | Fallbezogenes Domain-Monitoring |
| `muclegal/monitoring_cases.py` | Monitoringfall-Datenmodell und Validierung |
| `muclegal/evidence/suitability.py` | Nutzerseitige technische Ergebnisbewertung |

## 3. Fachliche Trennung

### 3.1 BeweisLab

Der kanonische technische Pfad lautet:

```text
URL
→ robots.txt / HTTP-Abruf
→ optionaler Browserabruf
→ Normalisierung
→ Rechtstextsuche
→ Haupt-, AGB- und Datenschutz-Screenshot
→ WARC/CDX
→ SHA-256-Manifest
→ RFC-3161-Versuch
→ PDF/ZIP
```

Das BeweisLab:

- führt keine juristische Kerngleichheitsentscheidung durch;
- benötigt für die normale technische Erfassung kein Anthropic-Modell;
- übermittelt Roh-HTML, Header, DOM, Screenshots und WARC nicht an fremde
  Extraktions- oder Speicherdienste;
- kann bei ungeprüfter `robots.txt` fortfahren, muss den Zustand aber deutlich als
  nicht beweisgeeignet kennzeichnen;
- respektiert eine eindeutige robots.txt-Untersagung im regulären Modus;
- löst keine Logins, Paywalls oder CAPTCHAs;
- darf vor einem Screenshot höchstens eine eindeutig datensparsame Cookie-Option
  wählen und protokolliert diese Aktion.

### 3.2 Fallmonitor

Der Fallmonitor bildet derzeit diesen Ablauf ab:

```text
Erstverstoß manuell erfassen
→ menschliche Fallfreigabe
→ Monitoringlauf starten
→ festgelegte URLs und begrenzten Domainumfang prüfen
→ technischen Befund anzeigen
```

Der aktuelle `case_id`-Pfad:

- verwendet den `CaseDomainMonitor`;
- prüft gemeldete Klauseln per exaktem Treffer und String-Ähnlichkeit;
- prüft gemeldete Elemente über sichtbare DOM-Eigenschaften;
- ruft kein Anthropic-Modell auf;
- erzeugt WARC und Manifest, aber kein vollständiges TSA-/PDF-/Wayback-Paket;
- lässt `freigabe_durch_mensch` auf `null`.

## 4. API-Grundsätze

- Neue Frontend-Implementierungen sollen ausschließlich `/api/v1/...` verwenden.
- Unversionierte `/api/...`-Aliase bestehen nur aus Kompatibilitätsgründen.
- Request-Modelle verbieten unbekannte zusätzliche Felder.
- Normale Anwendungsfehler verwenden `{"detail": "..."}`.
- Pydantic-Validierungsfehler liefern `detail` als Liste.
- Die OpenAPI-Dokumentation enthält die Request-Schemas, dokumentiert viele
  Response-Bodies derzeit aber nur als `{}`. Für Response-Felder sind deshalb die
  folgenden Verträge maßgeblich.

## 5. BeweisLab-Lauf

### 5.1 Empfohlener Stream-Endpunkt

```http
POST /api/v1/evidence-runs/stream
Content-Type: application/json
```

Request:

```json
{
  "url": "https://example.com",
  "verification_mode": true,
  "god_mode_authorized": false
}
```

Die Antwort ist NDJSON:

```http
Content-Type: application/x-ndjson
```

Beispiel:

```json
{"type":"run","run":{"run_id":"...","status":"running"}}
{"type":"run","run":{"run_id":"...","status":"running"}}
{"type":"complete","run":{"run_id":"...","status":"completed"}}
```

Fehler innerhalb des Streams:

```json
{"type":"error","detail":"Prüflauf fehlgeschlagen."}
```

Der Client muss die Antwort zeilenweise lesen. Es handelt sich weder um Server-Sent
Events noch um einen WebSocket.

### 5.2 Start mit anschließendem Polling

```http
POST /api/v1/evidence-runs
```

Erfolgreiche Antwort: HTTP `202` mit einem Run-Objekt.

Status abrufen:

```http
GET /api/v1/evidence-runs/{run_id}
```

### 5.3 Run-Objekt

```json
{
  "run_id": "32-stellige-id",
  "url": "https://example.com",
  "status": "running",
  "current_step": "screenshot",
  "message": "Der sichtbare Seitenzustand wird gespeichert.",
  "result_available": false,
  "monitoring_result": null,
  "steps": {
    "fetch": "success",
    "normalize": "success",
    "screenshot": "active",
    "compare": "waiting",
    "anthropic": "waiting",
    "warc": "waiting",
    "manifest": "waiting",
    "timestamp": "waiting"
  },
  "audit_log": [
    {
      "timestamp": "2026-08-21T10:00:00+00:00",
      "step": "fetch",
      "state": "active",
      "message": "Öffentliche Webseite und robots.txt werden geprüft."
    }
  ],
  "capture_baseline": true,
  "verification_mode": true,
  "god_mode_authorized": false
}
```

Pipeline-Schritte:

```text
fetch
normalize
screenshot
compare
anthropic
warc
manifest
timestamp
```

Schrittzustände:

```text
waiting | active | success | warning | failed | skipped
```

Allgemeine Run-Zustände:

```text
queued
running
baseline_created
unchanged
completed
completed_with_warnings
failed
protected
```

### 5.4 Offene Vertragslücke

Ein abgeschlossener BeweisLab-Run enthält derzeit nicht direkt die `case_id` des
erzeugten Beweispakets. Das bestehende Frontend verwendet daher diesen Workaround:

1. `GET /api/v1/cases`
2. neuesten regulären beziehungsweise God-Mode-Eintrag mit derselben URL suchen
3. `GET /api/v1/cases/{case_id}`

Vor einer größeren Frontend-Implementierung sollte das Backend dem Run ein Feld wie
`evidence_case_id` oder `case_detail_url` hinzufügen. Die URL-basierte Suche ist kein
langfristig stabiler API-Vertrag.

## 6. Beweispakete

### 6.1 Pakete auflisten

```http
GET /api/v1/cases
```

Antwort:

```json
{
  "cases": [],
  "god_mode_cases": [],
  "monitoring_cases": []
}
```

- `cases`: reguläre BeweisLab- und Golden-Path-Pakete
- `god_mode_cases`: getrennte God-Mode-Demonstrationspakete
- `monitoring_cases`: manuell angelegte Fallprofile

`GET /api/v1/cases` ist damit ein zusammengesetzter Listenendpunkt. Für eine reine
Monitoringfall-Liste ist `/api/v1/monitoring-cases` eindeutiger.

### 6.2 Paketdetails

```http
GET /api/v1/cases/{case_id}
```

Beispiel der wichtigsten Felder:

```json
{
  "case_id": "...",
  "url": "https://example.com",
  "erkannt_am": "2026-08-21T10:00:00Z",
  "fall_id": "VZ-2024-0417",
  "status": "completed",
  "result_code": "nicht_bewertet",
  "confidence": 0.0,
  "schema_valid": true,
  "snapshot_sha256": "...",
  "previous_snapshot_sha256": null,
  "manifest_sha256": "...",
  "warc_status": "valide (warcio check)",
  "timestamp_status": "verified",
  "capture_completeness": "vollstaendig_erfasst",
  "technical_result": {
    "code": "technisch_verwendbar",
    "label": "Als technischer Beleg verwendbar",
    "tone": "success",
    "what_was_found": "...",
    "meaning": "...",
    "next_action": "..."
  },
  "warnings": [],
  "evidence_suitability": "regulaer",
  "evidence_suitability_notice": null,
  "robots_txt_status": "geprueft_abruf_erlaubt",
  "god_mode": false,
  "god_mode_notice": null,
  "artifacts": [],
  "capture_galleries": {}
}
```

Für die primäre Ergebnisbox ist `technical_result` maßgeblich. Das Frontend sollte
nicht versuchen, die nutzerseitige Aussage selbst aus `status`, `warnings` oder
einzelnen Artefakten abzuleiten.

## 7. Technische Ergebnisbewertung

### 7.1 `technical_result.code`

| Code | Bedeutung |
|---|---|
| `technisch_verwendbar` | regulär und vollständig technisch erfasst |
| `eingeschraenkt` | erfasst, aber mit unvollständigen oder ungeprüften Teilen |
| `hinweis` | nur Hinweis, insbesondere Schutz-/Fehlerzustand oder God Mode |
| `nicht_erfassbar` | kein regulärer öffentlicher Seiteninhalt aufgenommen |

### 7.2 `technical_result.tone`

```text
success | warning | danger
```

### 7.3 `capture_completeness`

```text
vollstaendig_erfasst
teilweise_erfasst
durch_seitenschutz_begrenzt
technisch_fehlgeschlagen
```

### 7.4 `evidence_suitability`

```text
regulaer
nicht_beweisgeeignet
nicht_juristisch_verwertbar
```

### 7.5 `robots_txt_status`

```text
geprueft_abruf_erlaubt
geprueft_abruf_untersagt
ungeprueft
```

Bei `ungeprueft` muss das Frontend deutlich darauf hinweisen, dass Berechtigung,
Nutzungsbedingungen und rechtliche Zulässigkeit eigenverantwortlich zu prüfen sind.
Der Zustand darf niemals als regulär geprüft dargestellt werden.

## 8. Artefakte

Ein Artefakt in `case.artifacts` hat diese Struktur:

```json
{
  "label": "manifest",
  "title": "Manifest",
  "group": "Beweis",
  "kind": "text",
  "available": true,
  "preview_available": true,
  "size": 4832,
  "status": "available",
  "status_reason": "Im lokalen Beweispaket vorhanden."
}
```

Gruppen:

```text
Hinweis | Abruf | Analyse | Beweis | Bericht
```

Arten:

```text
text | image | pdf | binary
```

Wichtige Labels:

```text
evidence_suitability
god_mode_authorization
god_mode_editorial_summary
god_mode_ai_usage
raw_html
response_headers
normalized_text
legal_pages
capture_transparency
screenshot_interactions
capture_index
page_artifacts_index
capture_metrics
run_result
result_assessment
protection_report
previous_normalized_text
diff
model_input
model_output
clause_model_input
clause_model_output
requested_page_screenshot
screenshot
agb_screenshot
privacy_screenshot
warc
cdx
warc_status
manifest
manifest_digest
timestamp_query
timestamp_response
wayback_status
report
```

Einzelnes Artefakt öffnen oder herunterladen:

```http
GET /artifact/{case_id}/{label}
```

Sichere Textvorschau, maximal 512 KiB:

```http
GET /api/v1/cases/{case_id}/preview/{label}
```

Antwort:

```json
{
  "label": "manifest",
  "content": "..."
}
```

Gesamtes lokales ZIP:

```http
GET /api/v1/cases/{case_id}/download
```

## 9. Capture-Galerien

`capture_galleries` ist nach Seitenrolle organisiert:

```json
{
  "main": {
    "title": "Hauptseite",
    "mode": "full_page",
    "capture_completeness": "vollstaendig_erfasst",
    "tile_count": 0,
    "preview_url": "/api/v1/cases/.../capture/main/preview",
    "tile_urls": [],
    "original_urls": [
      "/api/v1/cases/.../capture/main/originals/0"
    ],
    "document_urls": [],
    "normalized_text_url": "/api/v1/cases/.../capture/main/normalized-text",
    "raw_html_url": "/api/v1/cases/.../capture/main/raw-html"
  }
}
```

Mögliche Rollen:

```text
main
requested
agb
privacy
agb_discovered
privacy_discovered
```

Wichtige Bildmodi:

```text
full_page
tiles
http_snapshot_visualized
```

`http_snapshot_visualized` ist keine pixelgetreue Browseraufnahme und muss sichtbar
als technische Hilfsdarstellung gekennzeichnet werden.

Endpunkte:

```text
GET /api/v1/cases/{case_id}/capture/{role}/preview
GET /api/v1/cases/{case_id}/capture/{role}/tiles/{index}
GET /api/v1/cases/{case_id}/capture/{role}/originals/{index}
GET /api/v1/cases/{case_id}/capture/{role}/documents/{index}
GET /api/v1/cases/{case_id}/capture/{role}/normalized-text
GET /api/v1/cases/{case_id}/capture/{role}/raw-html
```

Die vom Backend gelieferten Galerie-URLs sollen direkt verwendet werden. PDF-
Druckfassungen werden inline ausgeliefert und dürfen in einem same-origin `<iframe>`
angezeigt werden.

## 10. Monitoringfälle

### 10.1 Fall anlegen

```http
POST /api/v1/cases
Content-Type: application/json
```

Beispiel für einen Klauselfall:

```json
{
  "fall_id": "VZ-2024-0417",
  "domain": "example.com",
  "source_url": "https://example.com/agb",
  "violation_type": "klausel",
  "description": "Festgestellter Erstverstoß",
  "tenor_element": "Freigegebener Tenor oder tragendes Tenorelement",
  "monitoring_target": "Was künftig geprüft wird",
  "relevant_page_types": ["AGB"],
  "target_urls": ["https://example.com/agb"],
  "nicht_umfasst": ["Nachweislich zulässiger Gegenfall"],
  "clause_text": "Beanstandeter Klauselwortlaut",
  "allowed_subdomains": []
}
```

Pflichtfelder:

```text
fall_id
domain
source_url
violation_type
description
tenor_element
monitoring_target
relevant_page_types
```

Für `violation_type: "klausel"` ist zusätzlich `clause_text` erforderlich.

Für `violation_type: "element"` sind erforderlich:

```json
{
  "element_label": "Widerrufsbelehrung",
  "element_labels": ["Widerrufsbelehrung", "Widerruf"],
  "element_function": "/widerruf",
  "element_error": "fehlt"
}
```

Zulässige Fehlerarten:

```text
fehlt
nicht_sichtbar
nicht_leicht_zugaenglich
falsches_ziel
zusaetzliche_huerde
```

Optionaler Screenshot:

```json
{
  "screenshot": {
    "filename": "erstverstoss.png",
    "media_type": "image/png",
    "data_base64": "..."
  }
}
```

Grenzen:

- Screenshot maximal 10 MB.
- Gesamter Fall-Request maximal 14 MB.
- Nur PNG, JPEG oder WebP.
- Höchstens 20 Prüf-URLs.
- Höchstens 20 `nicht_umfasst`-Abgrenzungen.
- Höchstens 20 Elementbezeichnungen.
- `source_url` und `target_urls` müssen vollständige HTTP(S)-URLs sein.
- Zugangsdaten in URLs sind nicht zulässig.
- Ziele müssen zur Domain oder zu einer ausdrücklich erlaubten Subdomain gehören.

Erfolgreiche Antwort: HTTP `201` mit dem gespeicherten Monitoringfall.

### 10.2 Fälle lesen

```text
GET /api/v1/monitoring-cases
GET /api/v1/monitoring-cases/{case_id}
```

Ein Monitoringfall enthält insbesondere:

```json
{
  "case_id": "...",
  "fall_id": "VZ-2024-0417",
  "domain": "example.com",
  "source_url": "https://example.com/agb",
  "violation_type": "klausel",
  "target_urls": [],
  "nicht_umfasst": [],
  "erstverstoss_festgestellt_durch": "verbraucherzentrale",
  "decision": "weitere_pruefung",
  "created_at": "...",
  "decided_at": null
}
```

### 10.3 Menschliche Fallfreigabe

```http
POST /api/v1/cases/{case_id}/review
```

```json
{
  "decision": "freigegeben"
}
```

Entscheidungen:

```text
freigegeben | abgelehnt | weitere_pruefung
```

### 10.4 Monitoring starten

```http
POST /api/v1/runs
```

```json
{
  "case_id": "..."
}
```

Eine freie `url` ist in diesem Pfad bei der aktuellen App-Konfiguration nicht
zulässig. Der Fall muss vorher menschlich freigegeben sein.

Run abrufen:

```http
GET /api/v1/runs/{run_id}
```

Aktuell mögliche fallbezogene Endzustände:

```text
referenzzustand_dokumentiert
unveraendert_fortbestehend
beseitigt
kerngleich_wiederaufgetreten
unsicher
pruefung_unvollstaendig
```

`monitoring_result.freigabe_durch_mensch` bleibt `null`.

Das Feld `monitoring_result` enthält insbesondere:

```text
reported_initial_violation
monitoring_findings
document_findings
element_findings
coverage
manual_review_reasons
artifacts
freigabe_durch_mensch
```

## 11. Tenor-Entwürfe

### 11.1 Entwurf erzeugen

```http
POST /api/v1/tenor-drafts
```

```json
{
  "fall_id": "VZ-2024-0417",
  "schuldner": "Beispiel GmbH",
  "fundstelle": "https://example.com/angebote",
  "beschreibung": "Künstliche Dringlichkeit ohne reale Befristung",
  "rechtsgrundlagen": ["§ 5 UWG", "§ 8 Abs. 1 UWG"]
}
```

Antwort:

```json
{
  "draft_id": "...",
  "created_at": "...",
  "mode": "deterministic_demo",
  "model": "kein-modell",
  "input": {},
  "draft": {
    "fall_id": "...",
    "schuldner": "...",
    "entwurf": "...",
    "charakteristischer_kern": "...",
    "kerngleich_umfasst": [],
    "nicht_umfasst": [],
    "rechtsgrundlagen": [],
    "offene_fragen": [],
    "freigabe_durch_mensch": null
  },
  "decision": null,
  "decided_at": null
}
```

### 11.2 Entwurf menschlich entscheiden

```http
POST /api/v1/tenor-drafts/{draft_id}/review
```

```json
{
  "decision": "freigegeben"
}
```

Der freigegebene Entwurf wird derzeit global als `approved-tenor.json` aktiviert.
Er ist noch nicht als unveränderliche vollständige Tenorversion an jeden einzelnen
Monitoringfall gebunden.

## 12. God Mode

God Mode ist ausschließlich im BeweisLab verfügbar:

```json
{
  "url": "https://autorisiertes-ziel.test",
  "verification_mode": true,
  "god_mode_authorized": true
}
```

Das Backend setzt bei aktivem God Mode automatisch auch den Browsermodus.

Frontend-Pflichten:

- Durchgehende sichtbare Kennzeichnung:
  `GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR`.
- Gefahr-/Warnfarbe, nicht nur ein unauffälliger Badge.
- Getrennte Liste `god_mode_cases`.
- Keine Vermischung mit regulären Beweisen.
- Keine Weitergabe an eine juristische Kerngleichheitsprüfung.
- Downloadtext als Demonstrationspaket, nicht als reguläres Beweispaket.

Eine optionale OpenAI-Zusammenfassung ist nur eine getrennte, nicht beweisgeeignete
Arbeitshilfe. Primärartefakte bleiben lokal.

## 13. HTTP-Fehler

| Status | Typischer Fall |
|---|---|
| `201` | Fall oder Tenor-Entwurf angelegt |
| `202` | Run gestartet |
| `403` | Fall nicht freigegeben oder fremde Browser-Origin |
| `404` | Fall, Run oder Artefakt nicht gefunden |
| `409` | Es läuft bereits eine Prüfung |
| `413` | Request zu groß |
| `415` | Artefakt nicht als Textvorschau verfügbar |
| `422` | ungültige Felder oder unzulässiger Ablauf |
| `503` | Workflow nicht konfiguriert |

Anwendungsfehler:

```json
{
  "detail": "Es läuft bereits eine Prüfung."
}
```

Pydantic-Validierungsfehler:

```json
{
  "detail": [
    {
      "loc": ["body", "url"],
      "msg": "...",
      "type": "..."
    }
  ]
}
```

## 14. Browser- und Sicherheitsrahmen für das Frontend

- Mutierende Requests werden nur von derselben Browser-Origin akzeptiert.
- Es gibt keine CORS-Konfiguration für einen separaten Frontend-Devserver.
- Ein Vite-/React-Server auf einem anderen Port kann daher nicht direkt POSTen.
- Für ein getrenntes Frontend ist ein Same-Origin-Proxy oder eine bewusste
  Backend-Erweiterung erforderlich.
- Der `TrustedHostMiddleware` erlaubt standardmäßig nur `127.0.0.1`, `localhost` und
  `testserver`.
- Die Content Security Policy erlaubt Ressourcen im Wesentlichen nur von `'self'`.
- Frontend-Assets und Fonts sollten lokal unter `/static` ausgeliefert werden.
- Inline-CSS und Inline-JavaScript sind in der aktuellen CSP erlaubt.
- Normale Seiten dürfen nicht geframed werden.
- Nur die lokalen PDF-Druckfassungsendpunkte erlauben `SAMEORIGIN`-Einbettung.
- Es gibt keine Authentifizierung, Rollen oder Benutzerverwaltung.
- Es gibt keine Run-Abbruch-, Lösch-, Retry- oder Pagination-API.
- Es gibt noch keine persistente URL-/Tagesquote.

## 15. Bestehende Jinja-Kontexte

Der Fallmonitor unter `/` erhält serverseitig:

```text
case
human_review
workflow_enabled
anthropic_ready
tenor_draft
active_tenor
monitoring_cases
case_intake_enabled
element_errors
```

Das BeweisLab unter `/beweis-labor` erhält aktuell nur:

```text
anthropic_ready
```

Ein neues Frontend kann diese Templates weiterverwenden oder die Ansichten vollständig
über die versionierte API laden. Für den Hackathon ist ein Same-Origin-Frontend innerhalb
der bestehenden FastAPI/Jinja-Struktur der risikoärmste Weg.

## 16. Offene Backendpunkte vor einem finalen Frontendvertrag

1. Dem abgeschlossenen BeweisLab-Run die erzeugte `evidence_case_id` mitgeben.
2. Response-Modelle für Run-, Case-, Artifact- und Monitoring-Responses definieren,
   damit OpenAPI nicht nur `{}` ausweist.
3. `/api/v1/cases/{case_id}` nicht dauerhaft für zwei verschiedene Objekttypen
   verwenden; Monitoringfälle über `/api/v1/monitoring-cases/{case_id}` lesen.
4. Einen JSON-Endpunkt für die menschliche Entscheidung über ein Beweispaket ergänzen.
   Derzeit existiert dafür nur das HTML-Formular `POST /review`, bezogen auf den
   jeweils neuesten Fall.
5. Den freigegebenen vollständigen Tenor versioniert an den konkreten Monitoringfall
   binden.
6. Festlegen, ob der vollständige Einzel-URL-Golden-Path oder der Domain-Monitor der
   verbindliche juristische Produktpfad sein soll.
7. Falls ein separates SPA-Frontend geplant ist: CORS-, Proxy- und CSP-Vertrag bewusst
   definieren.

## 17. Empfohlene Frontend-Reihenfolge

1. BeweisLab-URL-Eingabe und Modusschalter.
2. NDJSON-Fortschrittsanzeige aus `audit_log` und `steps`.
3. Ergebnisbox ausschließlich aus `technical_result`.
4. Pflichtwarnungen aus `evidence_suitability`, `robots_txt_status` und `god_mode`.
5. Screenshot-Galerien direkt aus `capture_galleries`.
6. Artefaktmenü aus `artifacts`, ohne Labels im Frontend als Verfügbarkeit zu erraten.
7. ZIP-Download.
8. Monitoringfall-Aufnahme und menschliche Freigabe.
9. Juristische Monitoring-Ergebnisansicht erst nach Festlegung des kanonischen
   Backendpfads.

## 18. Verifikation des beschriebenen Stands

Ausgeführt am 21.08.2026:

```powershell
python -m compileall -q muclegal app.py
python -m pytest -q
```

Ergebnis:

```text
126 passed in 113.12s
```

Bei dieser Dokumentation wurden keine Backenddateien verändert.
