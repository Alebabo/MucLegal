# BeweisLab: Fehlerbilder und Lösungen

Stand: 20.08.2026
Betriebsart: ausschließlich lokal unter `http://127.0.0.1:8000/beweis-labor`

## Diagnose-Reihenfolge

1. `run-result.json`: Endstatus, angefragte und tatsächlich erfasste URL, Abbruchphase.
2. `capture-transparency.yaml`: User-Agent, `navigator.webdriver`, robots.txt, Context und Requests.
3. `protection-report.json`: sichtbarer Schutzbefund und geprüfte Rechtstextpfade.
4. Rollenverzeichnis: `dom-initial.html`, sichtbare Texte, Consent- und Expansionszustände.
5. `screenshot-index.json`: erwartete und erreichte Höhe, Vollbildversuch, Kachelabdeckung.
6. `resource-metrics.json` und `capture-metrics.json`: Phasen, Speicher und Größen.
7. WARC/CDX und Manifestprüfung; externe Zusatzdienste zuletzt bewerten.

## Browser schließt nach `domcontentloaded`

### Symptom

Playwright meldet `Target page, context or browser has been closed`, obwohl die Navigation zuvor
erfolgreich war. Früher ging der gesamte Zielzustand dadurch verloren.

### Ursache

Die optionale Settle-, Consent- oder Screenshotphase lief vor der dauerhaften Sicherung des
bereits verfügbaren DOM-Zustands. Der exakte externe Auslöser eines Prozessabbruchs kann
seitenspezifisch bleiben.

### Lösung

Der Run-Controller sichert unmittelbar nach `domcontentloaded` in einem zusammenhängenden
Initialzustand URL, Status, Redirectkette, Titel, DOM, sichtbaren Text, Dimensionen, User-Agent
und `navigator.webdriver`. Erst danach folgen Consent, Expansion und Bilder. Ein späterer
Browserabbruch liefert `teilweise_erfasst`, die exakte Abbruchphase und die erhaltenen Dateien;
es wird kein zweiter Browser gestartet.

### Verifikation und Grenze

`tests/test_playwright_capture.py` schließt die Page unmittelbar nach der Initialsicherung.
`dom-initial.html` bleibt vorhanden und der Lauf wird nicht als vollständig ausgegeben. Ein
Abbruch vor der Initialsicherung bleibt `technisch_fehlgeschlagen`.

## Hohe Seite endet bei 8.000 Pixeln

### Symptom

Sehr hohe Haupt- oder Rechtstextseiten enthielten früher nur den oberen Bereich.

### Ursache

Die frühere Screenshotfunktion setzte eine feste 8.000-Pixel-Grenze.

### Lösung

Zuerst wird ein echtes Playwright-Vollbild versucht und mit Pillow validiert. Bei Fehler oder
ungültigem Bild folgt eine Serie aus exakt 2.000 CSS-Pixel hohen Kacheln mit 100 Pixeln
Überlappung. `screenshot-index.json` dokumentiert jede Kachel, Hash, Maße und die lückenlose
Abdeckung. Nach höchstens 100 Kacheln wird transparent `teilweise_erfasst` gemeldet.

### Verifikation und Grenze

Synthetische Tests decken 1.000, 7.999, 8.001 und 30.000 Pixel ab. Der Kachelfallback erreicht
den Footer der 30.000-Pixel-Seite. Unendlich nachladende Seiten bleiben auf drei Höhenmessungen
und 100 Kacheln begrenzt.

## Weißes oder fast leeres Bild

### Symptom

Eine technisch erzeugte PNG-Datei zeigte keinen verwertbaren Seitenzustand.

### Ursache

Eine vorhandene Datei allein war bisher das Erfolgskriterium.

### Lösung

Pillow misst Maße, Dateigröße, unkomprimierte Größe, Luminanzstreuung und nahezu weiße Pixel.
Mindestens 99,5 Prozent nahezu weiße Pixel bei einer Standardabweichung unter 3 machen das Bild
ungültig und lösen den Kachelfallback aus. Ungültige Kacheln verhindern einen vollständigen Status.

### Verifikation und Grenze

Der deterministische Fallbacktest erzeugt zunächst ein weißes Vollbild und anschließend gültige
Kacheln. Die Messung ist ein technisches Signal und keine inhaltliche Bildanalyse.

## Cookie-Auswahl ist mehrdeutig

### Symptom

Ein Cookie-Banner bleibt sichtbar oder ein generisches „Ablehnen“ könnte zu einem fremden
Produkt- oder Formularbutton gehören.

### Ursache

Reine Textsuche ohne Dialog-, Alternativ- und Framekontext ist nicht eindeutig.

### Lösung

`muclegal/fetch/consent.py` untersucht sichtbare Controls im Hauptdokument, in Frames und offenen
Shadow Roots. Die enge Positivliste erlaubt nur datensparsame Optionen. Generisches „Ablehnen“
setzt eine Dialogrolle, sichtbaren Consent-Kontext und eine gleichzeitig sichtbare
Zustimmungsalternative voraus. Pro Dokument ist höchstens ein Klick möglich; Vorherbild,
Buttontext, Frame, Selektorstrategie, Zeitpunkt und Ergebnis werden gespeichert.

### Verifikation und Grenze

Regressionstests belegen, dass „Alle akzeptieren“ nie gewählt wird. Geschlossene Shadow Roots,
unklare Banner und unzulässige Frames bleiben `consent_ungeklaert`.

## Inaktiver CAPTCHA-Code erzeugt Fehlalarm

### Symptom

Eine normale Shopify-Seite wurde allein wegen eines ausgelieferten CAPTCHA-Bootstrap-Skripts
als geschützt eingestuft.

### Ursache

Die alte Erkennung suchte im vollständigen HTML einschließlich Script-, Template- und
Datenschutztexten nach einzelnen CAPTCHA-Wörtern.

### Lösung

Script-, Style-, Template- und Noscript-Inhalte werden vor der Schutzklassifikation entfernt.
Ein CAPTCHA-Befund setzt eine sichtbare Komponente oder eine eindeutige Aufforderung zur
Menschenprüfung voraus. Schutzmaßnahmen werden lediglich dokumentiert, niemals bedient.

## Rechtstextbild zeigt nur eine Übersicht

### Symptom

Das AGB-Bild enthält Links zu Dokumenten, aber keinen eigentlichen Klauseltext.

### Ursache

Discovery-URL und inhaltsreichste Klauselseite waren nicht getrennt.

### Lösung

Die Pipeline speichert `discovered_url` und `captured_url` separat, bewertet sichtbare Zeichen,
Überschriften, Klauseln und Auswahlscore und prüft ausschließlich klar rechtstextbezogene
Same-Origin-Unterseiten. PDF-Rechtstexte werden unverändert gespeichert und mit `pypdf`
seitenweise abgeleitet. Initial-, Consent- und Expansionszustände bleiben erhalten.

### Verifikation und Grenze

Allgemeine Site-Navigation wird nicht gecrawlt. Eine Rechtstextübersicht ohne eindeutige
öffentliche Klauselseite bleibt eine dokumentierte Teilgrenze.

## Paketierung mit älteren Screenshot-Doubles fehlgeschlagen

### Symptom

Nach Einführung von Rollenverzeichnissen scheiterten sieben vorhandene Tests mit fehlenden
Attributen oder nicht initialisierten Statusvariablen.

### Ursache

Die neue Paketlogik setzte Metadaten voraus, die minimale Test-Doubles der kompatiblen
`ScreenshotCapture`-API absichtlich nicht liefern.

### Lösung

Optionale neue Metadaten werden über konservative Standardwerte gelesen; Schutz- und
Anfragefelder werden vor allen Pfaden initialisiert. Alte Screenshotobjekte bleiben paketierbar.

### Verifikation und Grenze

Die gezielte UI-/Workflow-Suite besteht wieder. Neue Rollenmetadaten sind nur bei Captures des
lokalen Run-Controllers vollständig verfügbar.

## Große HTTP-Antwort, aber zu dünner gerenderter Rechtstext

### Symptom

Die Nachher-Abnahme von MediaMarkt am 20.08.2026 klassifizierte den Lauf zunächst als vollständig.
Der direkte Datenschutzabruf enthielt zwar eine sehr große HTML-Antwort, der tatsächlich
gerenderte semantische Hauptcontainer enthielt aber nur 957 Zeichen und drei Klauseln. Die
AGB-Auswahl blieb außerdem eine Übersicht ohne auflösbare konkrete Klauselseite.

### Ursache

Der Auswahlscore bewertete den gesamten direkten HTML-Text einschließlich umfangreicher
technischer Inhalte. Die Vollständigkeitsentscheidung berücksichtigte danach zwar die
Blockabdeckung des gewählten Containers, aber noch keine Mindestplausibilität des tatsächlich
gerenderten Rechtstexts und keinen ungelösten Übersichtsstatus.

### Lösung

Eine `übersicht_ohne_auflösbare_klauselseite` erzwingt jetzt `teilweise_erfasst`. Dasselbe gilt,
wenn ein gerenderter Datenschutztext weniger als 1.500 Zeichen oder fünf Klauseln und ein
gerenderter AGB-Text weniger als 1.000 Zeichen oder fünf Klauseln enthält. Diese Schwellen sind
technische Plausibilitätsgates, keine juristische Inhaltsbewertung.

### Verifikation und verbleibende Grenze

Ein synthetischer Regressionstest prüft Übersicht, kurze Datenschutzseite und die korrekte
Rollenzuordnung öffentlicher Ersatzquellen. Der reale MediaMarkt-Lauf wurde wegen des festgelegten
Requestbudgets nicht wiederholt; eine spätere manuelle Abnahme muss den neuen Teilstatus bestätigen
oder eine inhaltsreichere Same-Origin-Klauselseite belegen.

## Externe Zusatzdienste

freeTSA und Wayback sind optionale Zusatzdienste. Ein Ausfall wird mit Status und Grund
dokumentiert. Gespeicherte Antwortbytes, DOM, Bilder, WARC und lokales Manifest bleiben die
Primärbeweise. Ein separater GNU-Wget-WARC-Test kann versionsabhängige Digestfehler in Metadaten-
oder Resource-Records zeigen; der produktive Snapshot-WARC-Pfad muss davon unabhängig bestehen.

## Lokale Verifikation

```powershell
python -m compileall -q muclegal app.py
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/doctor-local-beweislab.ps1
python -m muclegal diagnose-capture --output output/capture-diagnose
powershell -ExecutionPolicy Bypass -File scripts/start-local-beweislab.ps1
```

Danach `/beweis-labor` öffnen und URL-Feld, Automatikschalter, Prüfverlauf,
Vollständigkeitsstatus, Kachelgalerie, Originaldownload, Info-Popover und ZIP prüfen.
