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

## HTTP-200-Antwort enthält weiterhin eine Bot-Schutzseite

### Symptom

Der reale Adidas-Lauf vom 21.08.2026 erhielt direkt HTTP 403. Der transparente
Browser-Prüfversuch antwortete anschließend mit HTTP 200, zeigte aber ausschließlich den Text
„triggered our security system“ / „cannot allow you onto the site“. Der Lauf wurde zunächst als
browsergestützt erfasster Seitenzustand beschrieben, obwohl nur die Schutzseite vorlag.

### Ursache

Der direkte HTTP-Pfad klassifizierte 403 nur als allgemeinen HTTP-Fehler. Nach dem Browserabruf
wurde die vorhandene Schutzseitenerkennung nicht erneut auf den gerenderten DOM-Stand angewendet.
Der HTTP-200-Status allein reichte deshalb irrtümlich für die weitere Normalisierung.

### Diagnose

`case.json`, der normalisierte Text und der PDF-Bericht enthielten ausschließlich den
Adidas-Sicherheitshinweis. `capture_completeness` war bereits
`durch_seitenschutz_begrenzt`; der gespeicherte Schutztext lieferte den entscheidenden Nachweis,
dass kein dahinterliegender Shop-Inhalt erfasst worden war.

### Lösung

HTTP 401/403/407/429 wird als Zugriffsschutz an den bereits erlaubten, nicht getarnten
Browser-Prüfschritt übergeben. Nach diesem Abruf wird der gerenderte DOM-Stand erneut auf
eindeutige Schutzmerkmale geprüft. Die Adidas-Formulierung führt jetzt zu einem Schutzbefund;
es wird kein dahinterliegender Inhalt behauptet. Ein ungeprüfter robots.txt-Status wird auch in
diesem Schutzbefund, Manifest, PDF, ZIP und UI als `nicht_beweisgeeignet` fortgeführt. Fehlt der
Schutzseiten-Screenshot, benennt auch die Abschlussmeldung ausdrücklich „ohne Screenshot“.

### Verifikation und verbleibende Grenze

Regressionstests decken HTTP 403, den HTTP-200-Bot-Schutztext und das ungeprüfte Schutzbefund-
Paket ab. Die Erkennung bleibt bewusst konservativ und benötigt eindeutige, sichtbare
Schutzformulierungen; unbekannte Anbietertexte können weiterhin eine manuelle Prüfung erfordern.

## Rollenbezogene HTML-/Text-/Bild-Artefakte waren unvollständig

### Symptom

Ein Beweispaket konnte einen Haupt- oder Rechtstext-Screenshot enthalten, ohne für dieselbe
tatsächlich besuchte URL im Rollenverzeichnis zugleich Roh-HTML und normalisierten Text
nachzuweisen. Wurde eine Rechtstextübersicht auf eine konkrete Klauselseite aufgelöst, war
außerdem nur die Zielseite vollständig gebündelt.

### Ursache und Diagnose

Browser-Fallbackbilder hatten kein eigenes `artifact_directory`; die Bündelung orientierte sich
deshalb nur am Bildpfad. Die gefundene Übersichts-URL und die ausgewählte Klausel-URL wurden zwar
getrennt dokumentiert, aber nicht als zwei Browserrollen archiviert. Zur Diagnose
`capture-index.json`, `legal-pages.json` und `artifacts/roles/*` gemeinsam prüfen. Fehlt in einer
besuchten Rolle eines von `raw.html`, `normalized-text.txt` oder einer PNG/WebP-Aufnahme, ist die
Seitenerfassung unvollständig.

### Lösung

Browserabbruch-Fallbacks schreiben jetzt Roh-HTML, deterministischen Normaltext, Screenshot,
Vorschau und Screenshot-Index in ein gemeinsames Rollenverzeichnis. Rechtstextübersicht und
konkrete Klauselseite werden bei unterschiedlichen URLs getrennt erfasst.
`page-artifacts-index.json` inventarisiert pro Rolle alle HTML-, Normaltext- und Bilddateien mit
SHA-256 und setzt `required_artifacts_complete`; eine Lücke stuft den Gesamtlauf auf
`teilweise_erfasst` herab.

### Verifikation und verbleibende Grenze

Unit- und UI-Tests prüfen den vollständigen Drei-Artefakt-Satz, den sicheren rollenbezogenen
HTML-Endpunkt sowie den Browserabbruch-Fallback. Erfasst werden ausschließlich die im BeweisLab
fachlich vorgesehenen und tatsächlich besuchten Seiten: Hauptseite, angefragte Schutzseite,
ausgewählte AGB-/Datenschutzseite und gegebenenfalls deren Übersicht. Es findet kein unbegrenzter
Crawl aller internen Links einer Website statt.

## MediaMarkt-Datenschutztext enthielt nur Akkordeonüberschriften

### Symptom

Der normalisierte Text der MediaMarkt-Shop-Datenschutzhinweise enthielt nur Einleitung und zehn
Abschnittsüberschriften. Inhaltliche Passagen zu Verantwortlichem, Logfiles, Empfängern,
Drittländern und Betroffenenrechten fehlten trotz eines scheinbaren Abdeckungswerts von 100 %.

### Ursache und Diagnose

Die Akkordeon-Header sind `button`-Elemente mit `aria-expanded=false` und `aria-controls`. Die
bisherige Filterlogik verwarf jedoch nach dem strukturellen CSS-Treffer alle Buttons, deren Text
nicht „Mehr anzeigen“ lautete. Zusätzlich schließt MediaMarkt beim Öffnen eines Abschnitts den
zuvor geöffneten Abschnitt wieder. Ein einzelner finaler DOM-/Screenshot-Zustand kann deshalb
nicht alle Klauseln gleichzeitig enthalten. Diagnose: `interactions.json` zeigte null
`legal_expansion`-Einträge; der vermeintliche Abdeckungswert verglich nur die bereits sichtbaren
Überschriften mit sich selbst.

### Lösung

ARIA-Akkordeonbuttons mit `aria-controls` sind jetzt unabhängig von ihrer Beschriftung innerhalb
des Rechtstextcontainers zulässig. Jeder Abschnitt wird sequenziell geöffnet; Ziel-ID, Vor-/
Nachzustand und der unmittelbar sichtbare kontrollierte Text werden gesichert. Tabs ohne
`aria-controls`, insbesondere Links zu einer anderen Datenschutzfassung, bleiben unangetastet.
Der normalisierte Text wird aus allen gesicherten Sichtzuständen dedupliziert zusammengeführt.
Zusätzlich entsteht `expanded-legal-print.pdf` als lokal erzeugte Druckfassung sämtlicher
expandierter Blöcke sowie eine Metadatendatei, die sie ausdrücklich als abgeleitet und nicht als
Website-Original kennzeichnet. Die UI bietet diese PDF unter „Druckfassungen“ an.

### Verifikation und verbleibende Grenze

Beim realen Lauf am 21.08.2026 wurden 10 von 10 Akkordeons mit 10 sichtbaren Blocktexten erfasst;
der Normaltext wuchs von etwa 1.500 auf 45.372 Zeichen. Normaltext und PDF enthielten den
Verantwortlichen, Logfile-/IP-Informationen und die Betroffenenrechte. `robots.txt` war geprüft
und erlaubte den Abruf. Weil MediaMarkt immer nur einen Abschnitt gleichzeitig offen hält,
zeigt der Live-Screenshot weiterhin einen einzelnen Akkordeonzustand; die vollständige
Gesamtdarstellung liegt in Normaltext, Blockprotokoll und abgeleiteter PDF vor.

## PDF-Druckfassung wurde im Beweisblock nur heruntergeladen

### Symptom

Die unter „Druckfassungen“ ausgewählte Rechtstext-PDF wurde zunächst sofort heruntergeladen.
Nach Umstellung auf Inline-Auslieferung blieb der eingebettete PDF-Bereich weiterhin leer und
zeigte „127.0.0.1 hat die Verbindung abgelehnt“, obwohl Datei, SHA-256 und Manifest korrekt waren.

### Ursache und Diagnose

Der Dokument-Endpunkt verwendete `FileResponse` mit Dateinamen, aber ohne abweichenden
Content-Disposition-Typ. Starlette setzt dann standardmäßig `attachment`; ein Browser behandelt
auch eine Iframe-Anfrage deshalb als Download. Der Playwright-E2E-Lauf zeigte beim Klick auf
„Datenschutz-Seite · Druckfassung 1“ ein Download-Ereignis statt einer eingebetteten Anzeige.
Im zweiten E2E-Lauf blockierten anschließend die globalen Header `X-Frame-Options: DENY` und
`frame-ancestors 'none'` die jetzt inline gelieferte, gleichoriginige PDF.

### Lösung

Der pfadsichere Dokument-Endpunkt liefert Rechtstext-PDFs jetzt ausdrücklich als
`application/pdf` mit `Content-Disposition: inline`. Der Link „Öffnen / laden“ bleibt erhalten;
Browser können die Datei darüber weiterhin in einem eigenen PDF-Viewer öffnen oder speichern.
Nur für den streng gematchten lokalen Dokument-Endpunkt erlauben die Frame-Header die Einbettung
aus derselben Origin (`SAMEORIGIN` und `frame-ancestors 'self'`). Für alle HTML-Seiten und übrigen
Endpunkte bleiben `DENY` und `frame-ancestors 'none'` unverändert aktiv.

### Verifikation und verbleibende Grenze

Der API-Regressionstest prüft Status 200, MIME-Typ, `inline` sowie die eng begrenzten Frame-Header
und schließt `attachment` aus.
Der lokale Browser-E2E-Test prüft zusätzlich, dass die Auswahl kein Download-Ereignis mehr
auslöst und die PDF-Antwort im eingebetteten Viewer geladen wird. Ob ein Browser PDFs intern
darstellt oder an eine konfigurierte externe Anwendung übergibt, bleibt eine lokale
Browser-Einstellung; die HTTP-Antwort fordert keinen Download mehr an.

## God-Mode-KI-Textbudget überschritt die konfigurierte Grenze

### Symptom

Der Regressionstest erwartete bei `MUCLEGAL_OPENAI_MAX_INPUT_CHARS=24000` höchstens 24.000
übertragene Zeichen, das Aufrufprotokoll wies aber 24.056 Zeichen aus.

### Ursache und Diagnose

Die stratifizierte Kürzung behält Anfang, Mitte und Ende des sichtbaren Texts. Zwischen diesen
drei Ausschnitten stehen zwei identische Kürzungsmarker. Die Budgetrechnung zog irrtümlich nur
einen Marker ab. Der Test prüft die tatsächlich an die Responses API übergebene Textlänge und
machte die Abweichung deshalb vor einem Live-Aufruf sichtbar.

### Lösung

Vom konfigurierten Zeichenlimit wird nun die Länge beider Marker abgezogen, bevor das verbleibende
Budget auf Anfang, Mitte und Ende verteilt wird. Das Limit bezieht sich ausschließlich auf den
gerenderten Quelltext; die kurzen Rollen-, URL- und Zeitmetadaten sind separat.

### Verifikation und verbleibende Grenze

Der Unit-Test erzwingt exakt 24.000 Quelltextzeichen, höchstens 900 Ausgabetokens, `store=False`,
keine Tools und `reasoning.effort=none`. Tokenzahlen können wegen der Modelltokenisierung nicht
vorab exakt aus Zeichen berechnet werden; tatsächliche Input-/Outputtokens und eine Kostenschätzung
werden deshalb nach jedem Aufruf in `god-mode-ai-usage.json` protokolliert.

## Optionale OpenAI-Zusammenfassung darf die Beweisspur nicht ersetzen

### Symptom und Risiko

Eine redaktionell verdichtete Produktbeschreibung kann dynamische Empfehlungen reduzieren und
Angaben paraphrasieren. Würde sie als Normaltext oder Primärbeweis gespeichert, gingen Wortlaut
und Trennung zwischen technischer Erfassung und externer Analyse verloren.

### Lösung

Die Funktion läuft ausschließlich nach aktivierter God-Mode-Autorisierung und ausschließlich in
`muclegal/llm/`. Übertragen wird je tatsächlich erfasster Seite nur ein begrenzter Ausschnitt des
gerenderten Normaltexts; Roh-HTML, Header, WARC, Screenshots und Cookies verlassen die lokale
Beweisspur nicht. Die schema-validierte Ausgabe liegt getrennt unter `analysis/editorial/` und als
deutlich markierte `god-mode-editorial-summary.md` vor. Volltext-SHA-256, Modell, Promptversion,
Cachetreffer, Tokenverbrauch und geschätzte Kosten stehen in `god-mode-ai-usage.json`; der
API-Schlüssel und der übertragene Text werden dort nicht gespeichert. Ohne Schlüssel wird der
Aufruf sichtbar übersprungen. Modellfehler verwerfen nur die Zusammenfassung und niemals die
lokalen Primärartefakte.

### Kostenkontrolle

Standard ist `gpt-5.6-luna` mit 24.000 Eingabezeichen und 900 Ausgabetokens pro tatsächlich
erfasster Seite. Identischer Volltext plus identische Modellkonfiguration ergeben einen lokalen
Cachetreffer ohne neuen API-Aufruf. Abweichende Modelle können über `MUCLEGAL_OPENAI_MODEL`, die
Limits über `MUCLEGAL_OPENAI_MAX_INPUT_CHARS` und `MUCLEGAL_OPENAI_MAX_OUTPUT_TOKENS` gesetzt
werden. Die Kategorie ist `stichprobenartig`: Auch bei geändertem Inhalt erfolgt je URL und
Seitenrolle standardmäßig höchstens ein kostenpflichtiger Aufruf innerhalb von sieben Tagen.
Das Intervall ist über `MUCLEGAL_OPENAI_SAMPLE_INTERVAL_DAYS` konfigurierbar. Lokale
Primärartefakte werden bei jedem gestarteten Lauf weiterhin erzeugt. Der Schlüssel wird nur aus
`OPENAI_API_KEY` gelesen und gehört nicht ins Repository.

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
