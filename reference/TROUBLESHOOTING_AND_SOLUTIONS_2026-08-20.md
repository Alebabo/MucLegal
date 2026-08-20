# BeweisLab – Probleme, Ursachen und Lösungen

Stand: 20.08.2026

Produktions-URL: `https://muclegal-beweislab.vercel.app/beweis-labor`

Referenz-Commit vor dieser Dokumentation: `ee30a76`

Dieses Dokument hält reale Befunde aus Entwicklung, lokalen Browsertests und
Vercel-Produktionsläufen fest. Es unterscheidet bewusst zwischen gelösten Problemen,
sichtbaren Fallbacks und offenen Grenzen.

## Schnellzuordnung

| Symptom | Ursache | Umgesetzte Lösung | Status |
|---|---|---|---|
| Temu liefert Fehler statt Inhalt | JavaScript-/Bot-Challenge | Schutz erkennen, Art nennen, öffentliche Rechtstexte prüfen; bei vollständiger Blockade Schutzbefund-Paket erzeugen | Beweisbarer Schutzbefund; Hauptinhalt bleibt geschützt |
| Screenshots sind weiß | Aufnahme vor stabiler Darstellung; Lazy Loading; ungeeigneter Vercel-Browserzustand | `DOMContentLoaded`, begrenztes `networkidle`, Layoutprüfung, Scrollimpulse, Bildwartezeit | Gelöst für getestete Standardseiten |
| Screenshot zeigt „kein WLAN“ | Website meldet eigenen Konnektivitätsfehler, obwohl Navigation technisch gelang | Marker erkennen und Screenshot als Fehlerzustand statt Seitennachweis markieren | Gelöst als korrekte Kennzeichnung |
| Screenshots funktionieren lokal, nicht auf Vercel | Chromium und native NSS/NSPR-Libraries fehlten im Function-Bundle | Headless Shell im Build installieren, Libraries kopieren, Browserpfad konfigurieren | Gelöst; Large Function nötig |
| Fallartefakte verschwinden auf Vercel | Serverless-Dateisystem ist nicht dauerhaft | Ergebnisdateien nach dem Lauf nach Vercel Blob hochladen und Blob-URLs ausliefern | Gelöst für ausgelieferte Pakete |
| Prüfverlauf wirkt eingefroren | Polling zeigte grobe Zustände und Vercel konnte Hintergrundzustand verlieren | NDJSON-Streaming pro Lauf, schrittweise Audit-Events, Live-Status in einem Request | Gelöst |
| Nur Haupt-/AGB-Screenshot vorhanden | Rechtstextlinks wurden gefunden, aber nicht separat visuell erfasst | AGB und Datenschutz priorisieren und je einen eigenen Screenshot erzeugen | Gelöst, wenn Links öffentlich auffindbar sind |
| Cookie-Banner verdeckt Beleg | Screenshot war absichtlich ohne Interaktion | Nur datensparsame Consent-Option wählen und Aktion vor Manifestbildung protokollieren | Gelöst mit enger Sicherheitsgrenze |
| Sehr lange Screenshots belasten Function | Full-Page-PNG kann Speicher-/Zeitgrenzen überschreiten | Aufnahme bei 8.000 Pixeln begrenzen und als `page_content_truncated` markieren | Gelöst als transparenter Teilbeleg |
| Wget-WARC-Test scheitert sporadisch | WSL/GNU Wget 1.25.0 erzeugt gelegentlich ungültige Metadaten-/Resource-Digests | Produktiv-WARC aus exakten Snapshotbytes; Wget-Pfad streng validieren und Fehler nicht kaschieren | Produktivpfad stabil; Wget-Flake offen |
| RFC-3161 bleibt `pending` | freeTSA/Netz/Zertifikatsdienst extern nicht verfügbar | Anfrage und Status erhalten, Warnung ausgeben, lokale Primärbeweise nicht verwerfen | Robuster Fallback; Dienstabhängigkeit offen |
| IKEA schließt Chromium auf Vercel | Seitenspezifischer Navigation-/Runtime-Abbruch; Ursache nicht abschließend bewiesen | Direkt geprüften HTML-Stand ohne JavaScript als gekennzeichneten Screenshot rendern | Screenshot-Fallback gelöst; Live-Abbruch offen |

## 1. Seitenschutz bei Temu und ähnlichen Seiten

### Symptom

Der direkte Abruf oder Chromium zeigt eine Challenge statt der eingegebenen Hauptseite.
Frühere Ergebnisse konnten so wirken, als sei die blockierte Seite erfolgreich erfasst
worden, obwohl tatsächlich nur eine AGB-Unterseite zugänglich war.

### Diagnose

- HTTP-Status, sichtbaren Challenge-Text und `_detect_block_page` prüfen.
- `requested_url`, `blocked_url`, `protection_type` und `captured_url` getrennt lesen.
- Den Hauptseiten-Screenshot nicht mit dem Screenshot einer Ersatz-Unterseite ersetzen.

### Lösung

- Schutzarten wie JavaScript-Challenge, CAPTCHA/Bot-Schutz oder Zugriffssperre sichtbar
  klassifizieren.
- Im Überprüfungsmodus einmalig einen frischen Chromium-Kontext ohne Tarnung versuchen.
- Bei fortbestehendem Schutz nur direkt öffentlich erreichbare AGB- und
  Datenschutz-Unterseiten prüfen.
- Schutz-/Fehlerzustand unter der eingegebenen URL separat vom tatsächlich erfassten
  Rechtstext speichern.
- Bleiben Hauptseite und alle direkten Rechtstextpfade blockiert, trotzdem ein Paket
  mit Schutz-Screenshot, Schutzart, geprüften URLs, Einzelfehlern, Manifest,
  Zeitstempelversuch und PDF erzeugen. `captured_url` bleibt dabei `null`.

### Grenze

Es werden keine CAPTCHAs gelöst, Clearance-Cookies übernommen, Proxies eingesetzt oder
Fingerprints manipuliert. Das BeweisLab ist deshalb kein Ersatz für eine menschliche
Browser-Session bei geschützten oder eingeloggten Inhalten.

## 2. Weiße, leere oder unfertige Screenshots

### Symptom

PNG-Dateien waren technisch vorhanden, zeigten aber nur Weißraum, Skeletons oder einen
noch nicht gerenderten Seitenzustand.

### Ursache

`DOMContentLoaded` bedeutet bei JavaScript-Shops nicht, dass Layout, Webfonts, Bilder
und Lazy-Loading-Inhalte bereits sichtbar sind. Reines `networkidle` kann umgekehrt an
dauerhaften Analytics-Verbindungen hängen.

### Lösung

Die Screenshotaufnahme:

1. navigiert bis `DOMContentLoaded`,
2. wartet begrenzt auf `networkidle`,
3. prüft Textlänge und Dokumentabmessungen,
4. scrollt in mehreren Schritten, um Lazy Loading auszulösen,
5. wartet kurz und springt vor der Aufnahme wieder nach oben.

Seiten über 8.000 Pixel werden bewusst gekürzt. Grund und Status stehen am Artefakt.

### Verifikation

MediaMarkt erzeugte in Produktion Haupt-, AGB- und Datenschutzbilder. IKEA war lokal
renderbar. Ein allgemeiner Erfolg bei jeder Website wird nicht behauptet.

## 3. Website zeigt einen eigenen Verbindungsfehler

### Symptom

Der Screenshot enthält Hinweise wie „Keine Verbindung“ oder „Check your internet
connection“, obwohl Playwright eine HTTP-Antwort erhalten hat.

### Ursache

Einige Anwendungen laden ihre Shell erfolgreich, scheitern danach aber bei internen
API- oder Ressourcenabrufen. Ein vorhandenes PNG ist dann kein Beleg des eigentlichen
Seiteninhalts.

### Lösung

Sichtbare Konnektivitätsmarker werden nach dem Rendern erkannt. Der Capture-Status wird
`site_connectivity_error`; UI und Beweispaket bezeichnen das Bild als Schutz-/Fehlerseite.

## 4. Chromium auf Vercel

### Symptom

Lokale Screenshots funktionierten, Vercel-Läufe scheiterten beim Browserstart oder bei
`page.goto`.

### Ursache

Das normale Python-Paket enthält weder automatisch einen passenden Chromium-Build noch
alle nativen Browser-Laufzeitbibliotheken der Vercel-Funktion. Ein echter
Produktionslauf ohne die `ldd`-Kopie belegte dies mit
`libatk-1.0.so.0: cannot open shared object file`.

### Lösung

- `playwright install chromium --only-shell` während des Vercel-Builds.
- NSS/NSPR-RPMs herunterladen, entpacken und benötigte Shared Libraries ins Bundle
  kopieren.
- Zusätzlich alle vom Headless-Shell-Binary über `ldd` aufgelösten Bibliotheken
  bündeln; die Build- und Function-Laufzeiten haben nicht denselben Bestand.
- `PLAYWRIGHT_BROWSERS_PATH` explizit setzen.
- Chromium mit `--disable-dev-shm-usage` starten.
- `.vercelignore` und `excludeFiles` verwenden, damit lokale Stores und Tests das
  Function-Bundle nicht unnötig vergrößern.

### Verbleibende Grenze

Die Funktion überschreitet das Standardlimit und benötigt deshalb Large Functions
(Beta) mit `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`. IKEA verursachte weiterhin einen
seitenspezifischen Chromium-Abbruch. Ohne
reproduzierbaren Root Cause bleibt der Live-Navigationspunkt offen. Für genau den
Fehler `Target page, context or browser has been closed` wird der bereits per HTTP
geprüfte HTML-Stand mit gesetzter Basis-URL und deaktiviertem JavaScript in Chromium
gerendert. Das Ergebnis trägt `capture_state: http_snapshot_rendered` und einen
ausführlichen Grund; es wird nicht als Live-Browsernavigation ausgegeben.

Der Produktionslauf zeigte anschließend, dass Vercel Chromium bei IKEA auch während
`page.set_content` beendet. Der letzte Fallback darf deshalb nicht erneut von demselben
Browserprozess abhängen: Aus dem bereits gespeicherten DOM-Text wird ohne weitere
Netzwerkabrufe ein beschriftetes PNG erzeugt. Es trägt
`capture_state: http_snapshot_visualized`, nennt URL und Herkunft und sagt im Bild
selbst deutlich „KEIN LIVE-BROWSER-SCREENSHOT“. Das ist eine lesbare Beweisansicht des
HTML, keine pixelgetreue Wiedergabe des visuellen Seitenzustands.

Ein Preview-Build nach der Reparatur überschritt zunächst mit 672,94 MB das damalige
Limit, weil Large Functions für Preview nicht aktiviert war. Das Verkleinern auf
320,46 MB durch Entfernen der `ldd`-Bibliotheken ließ den Build passieren, brach aber
den Browserstart in Produktion (`libatk-1.0.so.0` fehlte). Die korrekte Lösung ist
daher nicht, notwendige Laufzeitbibliotheken zu entfernen, sondern Large Functions
auch für Preview zu aktivieren und die `ldd`-Kopie beizubehalten. RPM-, `usr/share`-
und `usr/bin`-Reste werden weiterhin entfernt. Das zusätzlich installierte
FFmpeg-Paket (rund 2,3 MB) wird für reine Screenshots nicht benötigt und ebenfalls
entfernt.

### Visuelle Verifikation des IKEA-Fallbacks

Am 20.08.2026 wurden Hauptseite, AGB und Datenschutzerklärung über diesen statischen
Fallback lokal gerendert. Alle drei Bilder enthielten sichtbaren IKEA-Inhalt, Logo und
Seitentexte. Die 8.000-Pixel-Grenze wurde bei der Hauptseite transparent ausgewiesen.

Die Produktionsverifikation auf Deployment `dpl_41zL97aM3nBSieTCh1TASW7iwLex`
erzeugte für `https://www.ikea.com/de/de/` drei abrufbare Blob-Artefakte:

- Hauptseite: 885.118 Byte
- AGB: 436.097 Byte
- Datenschutzerklärung: 1.199.270 Byte

Alle drei tragen Status `warning` und erklären, dass es sich wegen des Chromium-
Abbruchs um ein browserloses HTML-Beweisbild und nicht um eine pixelgetreue
Live-Aufnahme handelt. Das Beweispaket war ebenfalls abrufbar.

Für `https://www.temu.com/de` endete der Produktionslauf im Überprüfungsmodus mit
`completed_with_warnings`. Er nannte die Schutzart `JavaScript-Challenge`, dokumentierte
13 geprüfte öffentliche Rechtstextpfade und stellte Schutzseiten-PNG (17.238 Byte),
Seitenschutz-Bericht, Manifest, PDF und Beweispaket über Blob bereit. Ein dahinter
liegender Inhalt wurde ausdrücklich nicht als erfasst ausgegeben.

### AGB-Übersicht statt Klauseln

Bei IKEA führte der zuerst gefundene AGB-Link auf eine Rechtstext-Übersicht. Das Bild
zeigte deshalb nur Verweise auf verschiedene AGB-Dokumente. Die Erfassung prüft nun,
ob eine Seite bereits mehrere nummerierte Klauseln und typische Rechtstextmerkmale
enthält. Andernfalls wird ausschließlich innerhalb derselben Website eine konkrete
HTML-Klauselseite ausgewählt; HTML wird gegenüber PDF bevorzugt. Gefundene Übersicht,
tatsächlich abgebildete Klausel-URL und Auswahlmethode stehen getrennt unter
`screenshot_captures` in `legal_pages.json`.

Für IKEA wurde die Übersicht dadurch auf die Seite „AGB Online-Shop“ aufgelöst. Die
visuelle Kontrolle zeigte Klauseln 1 bis 12 im 8.000-Pixel-Bild, darunter Geltung,
Vertragsschluss, Zahlungsmöglichkeiten, Lieferung und Widerrufsrecht. Header,
Navigation und Footer waren entfernt; deutsche Umlaute wurden über die gebündelte
Vera-Schrift korrekt dargestellt.

## 5. Flüchtige Dateien in Serverless Functions

### Symptom

Ein Lauf war abgeschlossen, aber Screenshots oder ZIP-Dateien waren bei einem späteren
Request nicht mehr verfügbar.

### Ursache

Das lokale Dateisystem einer Vercel Function ist nur für die jeweilige Instanz nutzbar.
Ein Folge-Request kann eine andere Instanz treffen.

### Lösung

Nach Fertigstellung werden verfügbare Artefakte und das ZIP-Paket nach Vercel Blob
hochgeladen. Die Falldetailantwort enthält dauerhafte Blob-URLs. Lokale Pfade bleiben
nur interne Erzeugungsdetails.

## 6. Prüfverlauf auf Vercel

### Symptom

Der Nutzer sah einen Ladekreis, aber nur selten aktualisierte oder widersprüchliche
Schritte.

### Ursache

Getrennte Start- und Polling-Requests sind bei flüchtigem In-Memory-Status und
Serverless-Instanzen unzuverlässig. Außerdem fehlten feinere Audit-Ereignisse.

### Lösung

`/api/v1/evidence-runs/stream` hält den Lauf in einem Request und streamt NDJSON-Zeilen.
Die UI rendert Abruf, Normalisierung, Rechtstextsuche, Screenshot, WARC, Manifest und
Zeitstempel fortlaufend in einem ausklappbaren grünen Prüfverlauf.

## 7. AGB- und Datenschutz-Screenshots

### Symptom

Gefundene Rechtstexte erschienen nur als Linkliste oder ein AGB-Screenshot ersetzte den
Beleg der Hauptseite.

### Lösung

- Rechtstextlinks werden aus dem gespeicherten HTML ermittelt.
- Allgemeine Shop-AGB/-Datenschutzseiten werden gegenüber Bonusprogramm- oder
  Sonderbedingungen priorisiert.
- `agb_screenshot` und `privacy_screenshot` sind eigene Artefakte und Pillen.
- Hauptseite, Schutzseite und Rechtstextbilder bleiben semantisch getrennt.

### Grenze

Die Linksuche folgt keinen allgemeinen Klickpfaden. Fehlt ein öffentlicher Link im
gespeicherten HTML, wird das Artefakt als nicht anwendbar ausgewiesen.

## 8. Cookie-Banner vor Screenshots

### Symptom

Consent-Banner verdeckten den relevanten Inhalt in Haupt-, AGB- und
Datenschutzaufnahmen.

### Sicherheitsentscheidung

Erlaubt ist höchstens ein Klick auf eine sichtbare, eindeutig datensparsame Option:

- `Alle ablehnen` / `Reject all`
- `Nur notwendige` / `Essential only`
- `Optionale Cookies ablehnen`
- `Ohne Zustimmung fortfahren`

`Akzeptieren`, `Zustimmen` und `Allow all` sind ausdrücklich ausgeschlossen. Ein bloßes
`Ablehnen` ist nur zulässig, wenn das Element innerhalb eines Cookie-/Consent-/Privacy-
Dialogs liegt. Hauptdokument und eingebettete Consent-Frames werden geprüft.

### Nachweis

Jeder Screenshot erhält eine Interaktionsliste. `screenshot_interactions.json` enthält
Policy, erlaubte Aktionsklassen, Screenshotbezeichnung, Aktion und tatsächlichen
Buttontext. Eine leere Liste bedeutet: kein Klick ausgeführt. Die Datei ist Bestandteil
des SHA-256-Manifests.

### Verifikation

- Unit-Test blockiert `Alle akzeptieren` und generisches `Ablehnen` außerhalb eines
  Consent-Kontexts.
- Ein realer lokaler Chromium-Test schloss `Alle ablehnen` und protokollierte exakt
  diese Aktion.
- Gesamtsuite am 20.08.2026: 78 Tests bestanden.

## 9. WARC und Snapshot-Konsistenz

### Problem

GNU Wget kann zusätzliche Metadaten- und Resource-Records erzeugen; unter WSL mit
Wget 1.25.0 waren deren Digests sporadisch ungültig. `--no-warc-keep-log` beseitigte
das eingebettete Wget-Laufprotokoll, aber ein Gesamttest am 20.08.2026 scheiterte
erneut an `metadata`-/`resource`-Digests und bestand unmittelbar danach. Der Wget-Pfad
ist daher nicht vollständig als behoben anzusehen. Außerdem können getrennte
Browser-/WARC-Aufnahmen unterschiedliche Zustände zeigen.

### Lösung

- Nicht beweisrelevantes Wget-Protokoll nicht einbetten.
- Den produktiven Golden Path mit `capture_snapshot_warc` aus den bereits geprüften,
  exakt gespeicherten Antwortbytes erzeugen.
- Jedes WARC streng mit `warcio` validieren; einen Digestfehler als fehlgeschlagenes
  Beweiselement ausweisen und niemals durch lockere Validierung verdecken.
- Snapshot-Payload-Hash und WARC-Payload-Hash vergleichen.
- Beziehung als `exact_payload`, `separate_recapture_mismatch` oder
  `warc_unavailable` dokumentieren.

### Verifikation und offene Grenze

Der exakte Snapshot-WARC-Test bestand direkt nach dem Flake. Der isolierte Wget-Test
bestand bei unmittelbarer Wiederholung ebenfalls, was die Sporadik bestätigt, aber
keine Lösung darstellt. Bei einem erneuten Befund Wget-Version, WSL-Nutzung und die
betroffenen Record-Typen protokollieren.

## 10. Externe Archiv- und Zeitstempeldienste

### Symptom

freeTSA kann `pending` bleiben; Wayback Save Page Now kann fehlen oder nicht erreichbar
sein.

### Lösung

Diese Dienste sind zusätzliche Vertrauensschichten, nicht Transportweg der
Primärbeweise. Statusdateien und Warnungen bleiben im Paket. Roh-HTML, Header,
Screenshot, WARC und lokales Manifest werden trotzdem fertiggestellt.

### Produktkommunikation

`pending` oder `not_configured` nicht als verifizierten qualifizierten Zeitstempel oder
erfolgreiche externe Archivierung darstellen. Ein qualifizierter eIDAS-Zeitstempel ist
ein Roadmap-Punkt und nicht durch freeTSA gleichzusetzen.

## 11. Effizienter Diagnoseablauf

Bei einem neuen Fehler in dieser Reihenfolge prüfen:

1. Falldetail: angefragte, blockierte und tatsächlich erfasste URL; Schutzart.
2. `capture_transparency.yaml`: Modus, User-Agent, WebDriver, robots.txt, Requestzahlen.
3. `screenshot_interactions.json`: ausgeführte Consent-Aktion oder leere Liste.
4. Screenshotstatus: Inhalt, gekürzt, Schutz-/Konnektivitätsfehler.
5. Roh-HTML und Response-Header.
6. WARC-Status sowie Snapshot-/WARC-Payload-Hash.
7. Manifestprüfung.
8. Erst danach Vercel-Build, Function-Größe, Runtime-Logs und externe Dienste.

Damit wird zuerst der konkrete Beweiszustand untersucht und nicht vorschnell ein
allgemeines Browser- oder Netzwerkproblem angenommen.

## 12. Release-Checkliste

```text
python -m compileall -q muclegal app.py
python -m pytest -q
vercel deploy --prod --yes
vercel inspect muclegal-beweislab.vercel.app
```

Danach:

- `/beweis-labor` im echten Browser öffnen.
- Info-Popover zum Überprüfungsmodus lesen.
- Kleinen Produktionslauf mit `https://example.com` starten.
- Screenshot und `screenshot_interactions.json` öffnen.
- Manifest muss die Interaktionsdatei enthalten.
- ZIP-Download über Blob-URL prüfen.
- Fehlerlogs prüfen; externe Zeitstempelwarnung separat bewerten.
