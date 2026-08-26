# BeweisLab: Fehlerbilder und Lösungen

Stand: 21.08.2026
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

## Grey Mode enthielt entgegen dem BeweisLab-Scope eine KI-Analyse

### Symptom

Im Grey Mode erschien eine optionale redaktionelle KI-Analyse. Bei fehlendem
`OPENAI_API_KEY` wurde sogar eine sichtbare Warnung ausgegeben, obwohl technische
Grey-Mode-Beweise vollständig ohne Modell erzeugt werden müssen.

### Ursache und Diagnose

Die später ergänzte Funktion `god_mode_summary` war direkt in den technischen
`LiveMonitorWorkflow` eingebunden. Dadurch konnte jeder erfolgreiche Grey-Mode-Lauf
normalisierten Seitentext an OpenAI senden und zusätzliche Analyseartefakte in Manifest,
UI und ZIP aufnehmen. Das widersprach dem verbindlichen BeweisLab-Grundsatz
„technische Erfassung ohne juristische Modellentscheidung“.

### Lösung

Der Grey-Mode-KI-Aufruf, sein Adapter, die Grey-Mode-spezifischen Modellvariablen sowie
alle UI- und Artefaktfreigaben wurden entfernt. `god_mode_authorization.json` nennt keine
KI-Funktion mehr. Neue Grey-Mode-Fälle speichern ausschließlich `analysis_mode=capture_only`
und markieren den allgemeinen Pipeline-Schritt `anthropic` als `skipped`.

### Verifikation und verbleibende Grenze

Der Regressionstest prüft, dass Grey Mode keine KI-Funktion autorisiert, keine KI-Artefakte
oder KI-Analysefelder speichert und den Modellschritt überspringt. Bereits lokal
vorhandene historische Beweispakete werden gemäß Aufbewahrungsregel nicht automatisch gelöscht;
ihre alten Analyseartefakte werden in der aktuellen UI jedoch nicht mehr angeboten.

## Adidas-Lauf zeigt nach Codeänderung keinen Browser-Screenshot

### Symptom

Bei `https://www.adidas.com/` erschien nach dem direkten HTTP-Schutz weder der neue
Browser-Fallback im Prüfverlauf noch eine Screenshot-Vorschau, obwohl die automatische
Überprüfung im BeweisLab aktiviert war.

### Ursache und Diagnose

Der lokale Uvicorn-Prozess lief ohne `--reload` und war vor den Änderungen am Robots- und
Browser-Fallback gestartet worden. Damit lieferte die HTML-Oberfläche zwar den aktuellen
Dateistand aus, der bereits importierte Python-Workflow im Serverprozess blieb jedoch alt.
Gezielte Regressionstests für `robots.txt`-Status `ungeprueft` und den standardmäßig aktivierten
Browsermodus waren grün; erst der Neustart brachte den Live-Endpunkt auf denselben Stand.

### Lösung

Den bestehenden Uvicorn-Prozess sauber beenden und mit
`python -m uvicorn app:app --host 127.0.0.1 --port 8000` neu starten. Danach setzt ein Adidas-Lauf
nach dem direkten HTTP-403 den transparenten Playwright-Abruf ein. Liefert Adidas weiterhin nur
eine Bot-Schutzseite, wird deren sichtbarer Zustand als „Angefragte Seite“ gespeichert und klar
als nicht beweisgeeigneter Schutzbefund ausgewiesen.

### Verifikation und verbleibende Grenze

Der reale Lauf wechselte in den Schritt „echter Browser mit JavaScript“, erzeugte ein 114.528
Byte großes Schutzseitenbild und stellte es im UI unter „Screenshot · Angefragte Seite“ ohne
Konsolenfehler dar. `robots.txt` blieb wegen HTTP 403 `ungeprueft`; der Lauf endete deshalb mit
`nicht_beweisgeeignet`. Playwright wird verwendet, überwindet aber keinen Bot-Schutz, kein CAPTCHA,
keinen Login und keine Paywall. Der dahinterliegende Adidas-Shopinhalt muss bei fortbestehendem
Schutz manuell gesichert werden.

## Leerer Browserzustand führte nach zweiter Normalisierung zu keinem Fallpaket

### Symptom

Ein transparenter Browserlauf konnte bereits Screenshot, DOM, Browsermetadaten und
Request-Metriken gespeichert haben, während sichtbarer und normalisierter Text leer blieben.
Bei Temu zeigte Chromium beispielsweise „No connection“. Die zweite Normalisierung warf erneut
`NormalizationError`; der Lauf endete früher mit der technischen Meldung und ohne sichtbaren
Ergebnisdatensatz.

### Ursache und Diagnose

`muclegal/live.py` fing nur den ersten Normalisierungsfehler des direkten HTTP-Abrufs ab. Der
zweite Aufruf von `check_url(..., fetched=rendered)` lag außerhalb eines terminalen
Fehlerpaketpfads. Dadurch blieben die bereits in der Browserrolle vorhandenen Dateien zwar
teilweise auf der Platte, wurden aber weder inventarisiert noch manifestiert oder im UI angeboten.

### Lösung

Jeder direkte BeweisLab-Lauf wird jetzt über eine zentrale vierstufige technische
Ergebnisbewertung abgeschlossen. Scheitert die Normalisierung auch nach dem Browser-Fallback,
entsteht ein lokales Fehler-/Schutzbefund-Paket. Es übernimmt vorhandenen Screenshot, Roh-HTML,
initiales DOM, Browsermetadaten, Interaktionsprotokoll und Request-Metriken in eine Rollenstruktur,
ergänzt `run-result.json`, `protection_report.json`, Erfassungstransparenz, Ergebnisbewertung und
Manifest und kennzeichnet den Lauf sichtbar als
„Nicht als Beleg verwendbar – nur Hinweis“. Die Originalexception steht ausschließlich in den
technischen Paketdateien. Ungültige und private URLs erhalten entsprechend den terminalen Status
„URL nicht erfassbar“ mit Zeitpunkt, Grund und Handlungsempfehlung.

### Verifikation und verbleibende Grenze

Der Regressionstest erzwingt zwei aufeinanderfolgende `NormalizationError`-Ausnahmen bei einem
gespeicherten `site_connectivity_error`-Screenshot. Er prüft terminalen Laufstatus,
`technisch_fehlgeschlagen`, Screenshot-Galerie, Fehlercode im Paket und dass
`NormalizationError` nicht in der Hauptmeldung erscheint. Ein weiterer Test belegt den
Ergebnisdatensatz für eine private URL. Der Fehlerzustand weist nur das Zugriffsproblem nach; ein
Mensch muss den dahinterliegenden Seiteninhalt weiterhin zusätzlich manuell sichern.

## Nicht verlinkte Shopify-AGB fehlten trotz erreichbarer Rechtstextseite

### Symptom

Bei einem erfolgreichen Lauf auf einer Shopify-Startseite wurde keine AGB-Seite
angezeigt, obwohl der öffentliche Standardpfad
`/policies/terms-of-service` erreichbar beziehungsweise als Fallziel bekannt
war.

### Ursache und Diagnose

Die normale Rechtstextsuche wertete ausschließlich Links im gespeicherten HTML
aus. Die Liste bekannter AGB- und Datenschutzpfade wurde nur im
Schutzseiten-Fallback verwendet. Eine erfolgreich geladene Startseite ohne
ausgelieferten Footer-Link verhinderte deshalb den Fallback. `legal_pages.json`
enthielt keine AGB-Kandidaten, obwohl das HTML Shopify-Merkmale enthielt.

### Lösung

Bei erkannter Shopify-Seite ergänzt die reguläre Rechtstextsuche jetzt genau
die beiden öffentlichen Standardpfade `/policies/terms-of-service` und
`/policies/privacy-policy`, wenn die jeweilige Kategorie keinen HTML-Link
lieferte. Zusätzlich kann ein menschlich freigegebenes Fallprofil bis zu 20
verbindliche Prüf-URLs vorgeben. Diese Ziele werden vor Sitemap- und
Linkkandidaten geprüft; fehlende Pflichtziele erscheinen ausdrücklich in
`missing_required_target_urls`.

### Verifikation und verbleibende Grenze

Ein synthetischer Shopify-Shop ohne Footer-Link liefert beide Standardpfade in
`legal-pages.json`. Ein Fallprofil mit einer nicht verlinkten
`/policies/terms-of-service`-URL erfasst die Seite und findet die gemeldete
Klausel. Mehrere dokumentierte Button-Bezeichnungen werden an die transparente
DOM-Prüfung weitergegeben. Alte SQLite-Fälle bleiben ohne Migration lesbar.

Der reale Ankerkraut-Lauf vom 21.08.2026 fand den zuvor fehlenden AGB-Kandidaten
als `known_shopify_public_path`. Der anschließende Abruf wurde jedoch korrekt
abgelehnt, weil `robots.txt` den Pfad für den Projekt-User-Agent untersagte. Die
Seite fehlt damit nicht mehr unbemerkt: Kandidat, URL, Auswahlmethode und
Robots-Ablehnung stehen in `legal_pages.json` und in den Warnungen; ein
AGB-Screenshot wird nicht vorgetäuscht.

Es werden keine beliebigen Pfade erraten. Nicht verlinkte Seiten anderer
Plattformen benötigen eine Fallprofil-URL, eine öffentliche Sitemap oder einen
eigenen eng begrenzten und belegten Plattformpfad. Login, Paywall, CAPTCHA und
verändernde Formularaktionen bleiben ausgeschlossen.

## Mirage-Rechtstextbilder brachen an einer nicht verfügbaren Windows-Schrift ab

### Symptom

Ein Grey-Mode-Lauf vom 24.08.2026 für `https://mirageperfume.com/` fand die
öffentlichen Shopify-Rechtstextpfade, gab AGB und Datenschutz aber nicht als
Bild aus. Die Oberfläche meldete unter anderem
`AGB-Screenshot nicht erzeugt: TTFError: Can't open file
"C:/Windows/Fonts/arial.ttf"`.

### Ursache und Diagnose

Der Fehler lag nicht in der Rechtstextsuche oder an einem fehlenden API-Schlüssel.
Während einer Rechtstextaufnahme wird zusätzlich eine lokale PDF-Druckfassung
sequenziell expandierter Klauselblöcke erzeugt. Deren ReportLab-Fontauswahl
versuchte feste Windows- und Linux-Pfade. ReportLabs `TTFError` erbt weder von
`OSError` noch von `ValueError`; deshalb erfassten die vorhandenen Fehlerpfade
die nicht lesbare Arial-Datei nicht. Die optionale Druckfassung brach daraufhin
den übergeordneten AGB-/Datenschutz-Erfassungspfad ab.

### Lösung

Die Fontauswahl bevorzugt nun die mit ReportLab ausgelieferte `Vera.ttf`, prüft
Kandidaten vor dem Öffnen und behandelt `TTFError` sowohl je Kandidat als auch
im äußeren PDF-Fehlerpfad. Ist keine TrueType-Schrift verwendbar, wird die
integrierte Helvetica-Schrift genutzt. Ein Fehlschlag der abgeleiteten
Druckfassung kann dadurch keinen Rechtstext-Screenshot mehr verhindern;
unvollständige PDF-Dateien werden entfernt und der PDF-Status bleibt getrennt
dokumentiert.

### Verifikation und verbleibende Grenze

Ein Regressionstest erzwingt exakt einen ReportLab-`TTFError` mit dem gemeldeten
Arial-Pfad. Die Funktion fällt ohne Ausnahme auf Helvetica zurück und erzeugt
weiterhin eine als lokal abgeleitet gekennzeichnete PDF. Die bestehenden Tests
für Shopify-Pfaderkennung und browserlose Rechtstextbilder bleiben grün.
Anschließend sind beide Mirage-Rollen in einem neuen Grey-Mode-Lauf zu prüfen;
ein externer Seitenschutz oder ein Chromium-Abbruch kann weiterhin einen
transparent gekennzeichneten HTML-Fallback statt eines pixelgetreuen
Live-Screenshots erforderlich machen.

## Dynamisch schrumpfende Rechtstextseite ließ Kachelaufnahme abbrechen

### Symptom

Beim realen Ankerkraut-Datenschutzlauf scheiterte die Screenshotphase mit
`Page.screenshot: Clipped area is either empty or outside the resulting image`.
Der zuvor gemessene sehr hohe DOM war während der Kachelserie geschrumpft.

### Ursache und Diagnose

Die Kachelschleife verwendete während der gesamten Aufnahme ausschließlich die
anfänglich gemessene Dokumenthöhe. War die Seite nach Lazy-Loading oder
Layoutänderungen kürzer, lag eine spätere `clip`-Position außerhalb des nun
aktuellen Dokuments. Die Playwright-Ausnahme wurde innerhalb der Kachelschleife
nicht abgefangen und verwarf deshalb auch bereits gültige Kacheln.

### Lösung

Vor jeder Kachel werden aktuelle Höhe und Breite neu gemessen. Liegt die nächste
Kachel außerhalb des geschrumpften Dokuments oder lehnt Playwright einen Clip
ab, endet die Serie kontrolliert als `teilweise_erfasst`. Bereits valide
Kacheln, Index und Vorschau bleiben erhalten; `tile_errors` dokumentiert die
Grenze. Nur wenn weder Vollbild noch eine einzige Kachel vorhanden ist, gilt die
Screenshotaufnahme als fehlgeschlagen.

### Verifikation und verbleibende Grenze

Ein Regressionstest simuliert eine Seite, die von 5.000 auf 1.000 CSS-Pixel
schrumpft. Er bestätigt eine erhaltene Kachel, `teilweise_erfasst`, eine
protokollierte Kachelgrenze und keinen unbehandelten Clip-Fehler. Eine dynamisch
schrumpfende Seite bleibt möglicherweise unvollständig; sie wird nicht als
lückenloser Vollbildbeweis bezeichnet.

## Grey Mode konnte intern die juristische Analysespur erreichen

### Symptom

Ein direkter Python-Aufruf von `LiveMonitorWorkflow.run(god_mode=True)` ohne
`capture_baseline=True` konnte nach einer bereits vorhandenen Grey-Mode-Baseline
in die Kerngleichheits- und Modellanalyse verzweigen. Der UI-Pfad setzte zwar
stets `capture_baseline=True`, die Workflow-Grenze selbst erzwang diese Trennung
aber nicht. In diesem seltenen Pfad wurde außerdem der reguläre statt des
separaten Grey-Mode-Latest-Pfads zurückgegeben.

### Ursache und Diagnose

`RunCoordinator` koppelte Grey Mode korrekt an die technische BeweisLab-Erfassung.
`LiveMonitorWorkflow.run` akzeptierte die Parameter jedoch unabhängig voneinander.
Dadurch beruhte die fachlich zwingende Trennung nur auf dem Verhalten eines
einzigen Aufrufers; Tests deckten ausschließlich den regulären UI-Aufruf ab.

### Lösung

Die Workflow-Grenze lehnt `god_mode=True` jetzt ab, wenn nicht zugleich
`capture_baseline=True` gesetzt ist. Damit kann kein interner Aufrufer
Grey-Mode-Artefakte einer juristischen Kerngleichheitsprüfung zuführen. Der
nachgelagerte Rückgabepfad verwendet zusätzlich den bereits berechneten,
modusabhängigen Latest-Pfad.

### Verifikation und verbleibende Grenze

Ein Regressionstest bestätigt, dass der unzulässige Parameterverbund vor jedem
Abruf mit `ValueError` endet und weder ein reguläres noch ein Grey-Mode-Paket
erzeugt. Die bestehenden Grey-Mode-Tests bestätigen weiterhin die getrennte
Speicherung, sichtbare Kennzeichnung und übersprungene Anthropic-Stufe. Neue
interne Einstiegspunkte müssen weiterhin `LiveMonitorWorkflow.run` verwenden
und dürfen keine privaten Workflow-Methoden direkt aufrufen.

## Artefaktpfad konnte auf ein anderes lokales Beweispaket zeigen

### Symptom

Ein beschädigtes oder nachträglich manipuliertes `case.json` konnte für ein
Artefakt auf eine Datei in einem anderen Bundle unterhalb derselben lokalen
Ablage verweisen. Der Vorschau-Endpunkt und die ZIP-Erzeugung akzeptierten den
Pfad, solange er nur innerhalb des gesamten Store-Verzeichnisses lag. Dadurch
hätte insbesondere ein Grey-Mode-Artefakt in ein reguläres Downloadpaket kopiert
werden können.

### Ursache und Diagnose

Die Pfadprüfung in `CaseArchive` verwendete `store_root` als Vertrauensgrenze.
Diese Grenze verhindert zwar einen Zugriff außerhalb von `.muclegal-ui`, trennt
aber reguläre Bundles und `god-mode-bundles` nicht voneinander. Die übrigen
Galeriepfade wurden bereits strenger gegen das jeweilige Paket geprüft.

### Lösung

Jeder freigegebene Artefaktpfad muss jetzt innerhalb des Verzeichnisses des
konkreten `case.json` liegen. Vorschau, Detailansicht und ZIP-Erzeugung verwenden
dieselbe Bundle-Grenze. Symlink- und `..`-Auflösungen werden weiterhin über den
aufgelösten absoluten Pfad geprüft.

### Verifikation und verbleibende Grenze

Ein Regressionstest lässt ein reguläres `case.json` auf eine Grey-Mode-HTML-Datei
zeigen. Der Artefakt-Endpunkt antwortet mit 404; das reguläre ZIP enthält weder
den Alias unter `artefakte/` noch den fremden Dateiinhalt. Die lokale Ablage muss
weiterhin gegen direkte Betriebssystem-Manipulation geschützt werden; absichtlich
veränderte Paketdateien werden nicht automatisch repariert.

## Gültiges Vollbild meldete widersprüchlich keine lückenlose Abdeckung

### Symptom

Die synthetische 30.000-Pixel-Diagnose erzeugte ein validiertes Full-Page-PNG
mit 30.021 Pixeln Höhe und Status `vollstaendig_erfasst`. Gleichzeitig enthielt
`screenshot-index.json` den Wert `continuous_coverage: false`.

### Ursache und Diagnose

Das Feld `continuous_coverage` wurde ausschließlich aus der Liste der
Fallback-Kacheln berechnet. Bei einem erfolgreichen Vollbild ist diese Liste
absichtlich leer; die Kachelprüfung lieferte deshalb `false`, obwohl das
validierte Vollbild die dokumentierte Seitenhöhe vollständig abdeckte.

### Lösung

Ein erfolgreich validiertes Vollbild setzt `continuous_coverage` jetzt direkt
auf `true`. Nur im Kachelmodus wird die überlappungsfreie Abdeckung weiterhin
aus `y_start`, `y_end` und Dokumenthöhe berechnet.

### Verifikation und verbleibende Grenze

Die Playwright-Regressionstests prüfen das Feld für 1.000, 7.999, 8.001 und
30.000 CSS-Pixel; alle elf Capture-Tests bestehen. Eine erneute synthetische
Diagnose erfasste 30.021 von 30.021 Pixeln und meldete konsistent
`continuous_coverage: true`. Die Aussage bezieht sich auf die dokumentierte
Seitenhöhe zum Aufnahmezeitpunkt; spätere dynamische Inhaltsänderungen bleiben
durch Höhenmessungen und Aufnahmezeitpunkt begrenzt.

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

## Temu- und Adidas-Rechtstextpfade fehlten bei Start auf der Domainwurzel

### Symptom

Ein BeweisLab-Lauf mit `https://www.temu.com/` prüfte neun allgemeine
Rechtstextpfade, aber nicht die bekannte deutsche AGB-URL
`https://www.temu.com/de/terms-of-use.html`. Entsprechend konnte auch
`https://www.temu.com/de/privacy-policy.html` fehlen. Für Adidas konnte
`https://www.adidas.de/terms_and_conditions` übersehen werden, wenn der Link
nicht im gespeicherten HTML stand.

### Ursache und Diagnose

`_legal_subpage_candidates` leitete eine Sprachkennung nur aus dem ersten
Segment der eingegebenen URL ab. Bei der Domainwurzel `/` gab es kein Segment
`de`; deshalb entstanden nur nicht lokalisierte Standardpfade. Der gespeicherte
Temu-`protection_report.json` bestätigte, dass die beiden `/de/`-Ziele im
betroffenen Lauf nicht geprüft wurden. Die bereitgestellte Temu-`robots.txt`
enthält für den Projekt-User-Agent kein Verbot dieser Rechtstextpfade; sie war
nicht die Ursache.

### Lösung

Eine kleine zentrale Zuordnung priorisiert jetzt für passende Hosts immer die
belegten öffentlichen Ziele:

- `temu.com`: `/de/terms-of-use.html` und `/de/privacy-policy.html`,
- `adidas.de`: `/terms_and_conditions`.

Die Zuordnung gilt sowohl für die normale Rechtstextsuche als auch für den
Schutzseiten-Fallback. Bekannte Website-Pfade stehen jeweils vor allgemeinen
Pfadkandidaten und werden in `legal_pages.json` mit
`source: known_site_public_path` ausgewiesen.

### Verifikation und verbleibende Grenze

Regressionstests prüfen Domainwurzel, lokalisierte Temu-URL, Kandidatenreihenfolge
und die Ausgabe in `legal_pages.json`. Die Änderung stellt nur sicher, dass die
richtige URL versucht und dokumentiert wird. Liefert Temu oder Adidas dort eine
JavaScript-Challenge, einen leeren Browserzustand, Login oder sonstigen
Seitenschutz, bleibt der Lauf weiterhin ehrlich begrenzt; es wird keine
Schutzmaßnahme umgangen.

## Rechtstext-Fallback fehlte bei allgemeinen Erfassungsfehlern und im Grey Mode

### Symptom

Die öffentlichen AGB- und Datenschutzpfade wurden nur dann als Ausweichziele
geprüft, wenn der Hauptseitenfehler zuvor ausdrücklich als Seitenschutz erkannt
worden war. Endete die Browser-Erfassung dagegen mit leerem Text, einem
Verbindungsfehler oder einer sonstigen technischen Ausnahme, erzeugte der
Workflow unmittelbar ein Fehlerpaket. Das galt auch für einen fehlgeschlagenen
Grey-Mode-Lauf.

### Ursache und Diagnose

Der Rechtstext-Fallback war in `_run_impl` ausschließlich an den Fehlercode
`protected_or_login_page` gekoppelt. Der allgemeine Abschluss in `run` kannte
nur das terminale Fehlerpaket. Der Temu-Lauf mit leerem Browserzustand bestätigte
diesen Pfad: Das Paket enthielt den Hauptseitenfehler, aber keine Liste der
anschließend geprüften AGB- und Datenschutzziele.

### Lösung

Vor dem allgemeinen Fehlerabschluss startet für jede gültige HTTP(S)-Zielseite
jetzt derselbe begrenzte Rechtstext-Fallback. Er prüft die bekannten und
allgemeinen öffentlichen AGB- und Datenschutzpfade; Kindläufe dürfen den
Fallback nicht erneut starten. Ein bereits vorhandener Browser-Screenshot des
Fehlerzustands bleibt erhalten. Schutz-, Normalisierungs- und sonstige
Technikfehler werden im Paket getrennt bezeichnet. Auch Grey Mode nutzt diesen
Weg und bleibt über den Modus von regulären Beweisen unterscheidbar. Ein spezieller
Disclaimer oder Hinweis ist optional und wird vom Nutzer bestimmt.

Der Fallback startet bewusst nicht bei ungültigen URLs, eingebetteten
Zugangsdaten, privaten Zielen oder einer ausdrücklichen Ablehnung durch
`robots.txt`. Dadurch werden die bestehenden Zugriffsgrenzen nicht ausgeweitet.

### Verifikation und verbleibende Grenze

Regressionstests bestätigen den Fallback nach leerem Direkt- und Browserinhalt,
die erhaltene Fehleraufnahme, die Temu-Reihenfolge mit
`/de/terms-of-use.html` und `/de/privacy-policy.html` sowie die Weitergabe des
Grey-Mode-Status. Sind auch diese Unterseiten blockiert oder technisch leer,
enthält das Hinweispaket die vollständig geprüfte Pfadliste und die einzelnen
Fehler. Das ist ein Nachweis des Erfassungsversuchs, kein Beweis für den Inhalt
oder das Fehlen einer Klausel.

## Temu-Rechtstext erscheint erst nach der gespeicherten Texterfassung

### Symptom

Der reguläre Live-Lauf vom 21.08.2026 auf `https://www.temu.com/` erkannte auf
der Hauptseite eine JavaScript-Challenge und prüfte anschließend wie vorgesehen
zuerst:

- `https://www.temu.com/de/terms-of-use.html`,
- `https://www.temu.com/de/privacy-policy.html`.

Für beide deutschen Rechtstexte entstanden vollständige, lesbare
Full-Page-Screenshots mit 15.864 beziehungsweise 19.690 CSS-Pixeln Höhe.
`visible-text-final.txt`, `normalized-text.txt` und `clauses.json` blieben jedoch
leer. Das Paket meldete deshalb für AGB und Datenschutz jeweils `0 Zeichen` und
`0 Klauseln`. Erst der spätere allgemeine Pfad
`https://www.temu.com/privacy-policy.html` lieferte 30.450 normalisierte Zeichen.

### Ursache und Diagnose

Die Ursache ist durch die gespeicherten Phasenartefakte und die Reihenfolge in
`BrowserCaptureRun._capture_new_context` belegt: Direkt nach
`domcontentloaded` wurden ein rund 3 KB großer Challenge-DOM sowie der zu diesem
Zeitpunkt leere sichtbare Text gespeichert und normalisiert. Erst danach rief
der Workflow `_wait_for_visual_capture` auf. Während dieses Wartens erschien
der eigentliche Rechtstext; die anschließende Screenshotaufnahme erfasste ihn
vollständig. DOM und Text wurden nach dem visuellen Warten aber nicht erneut
gesichert oder normalisiert. Daher widersprechen sich in diesem Fall nicht die
Webseite und das Bild, sondern die Erfassungszeitpunkte von Text und Screenshot.

Der Lauf zeigte zusätzlich eine zweite, anhand der SHA-256-Werte belegte
Zuordnungsgrenze: Nachdem der allgemeine englische Datenschutzpfad als primäres
Fallback-Ziel erfolgreich war, klassifizierte `_page_role_captures` diese
Hauptaufnahme ebenfalls als Rolle `privacy`. Dadurch zeigt die Galerie im UI
unter „Datenschutz-Screenshot“ die englische allgemeine Datenschutzseite. Der
deutsche Datenschutz-Screenshot bleibt zwar unverändert als
`artifacts/privacy_screenshot.png` im Paket, wird aber in der Rollengalerie vom
Fallback-Hauptbild verdrängt.

### Lösung

Die produktive Korrektur ist noch offen. Nach `_wait_for_visual_capture` muss
für Rechtstextrollen ein zweiter, ausdrücklich als stabilisierter Zustand
gesichert werden. Enthält dieser Zustand erstmals relevanten sichtbaren Text,
müssen DOM, sichtbarer Text, Normalisierung, Klauseln und Abdeckungsmetrik daraus
neu erzeugt werden. Der anfängliche Challenge-DOM bleibt als separates
Phasenartefakt erhalten; er darf nicht überschrieben oder nachträglich als
regulärer Rechtstext bezeichnet werden. Schutzbefund, Übergang und verwendeter
Textstand müssen in Transparenzdatei und Manifest nachvollziehbar bleiben.

Zusätzlich darf eine erfolgreiche Fallback-Hauptseite keine bereits belegte
Rechtstextrolle überschreiben. Die Fallback-Aufnahme benötigt eine eigene Rolle,
beispielsweise `captured_fallback`; `agb` und `privacy` müssen weiterhin auf die
gezielt ausgewählten deutschen Rechtstextziele zeigen. Auch diese Korrektur ist
noch nicht umgesetzt.

### Verifikation und verbleibende Grenze

Der Live-Lauf bestätigte die richtige Kandidatenreihenfolge, getrennte AGB- und
Datenschutzbilder, gültiges Manifest, verifizierten RFC-3161-Zeitstempel und ein
11.314.651 Byte großes ZIP-Paket. Er bestätigt ausdrücklich noch keine
erfolgreiche deutsche Text- oder Klauselerfassung. Vor Freigabe einer Korrektur
ist ein Regressionstest mit verzögert erscheinendem Rechtstext erforderlich:
Initialzustand leer oder Challenge, stabilisierter Zustand inhaltsreich,
Screenshot und normalisierter Text aus demselben späten Zustand. Bis dahin sind
die Temu-Bilder als visueller Hinweis vorhanden; Hashvergleich und
Klauselmonitoring dürfen für die beiden deutschen Rechtstexte nicht als
erfolgreich dargestellt werden. Ein weiterer Regressionstest muss sicherstellen,
dass ein als Datenschutzseite klassifiziertes Fallback-Ziel die bereits
gesicherte deutsche Datenschutzrolle weder in `capture_galleries` noch im UI
überschreibt.

## Temu-Fallback-Paket wird im UI durch einen älteren Root-Fall ersetzt

### Symptom

Ein am 21.08.2026 gestarteter Lauf für `https://www.temu.com/` erzeugte das neue
Paket `20260821T155017397646Z-4bae2d59`. Darin ist die angeforderte URL als
`requested_url` erhalten und die tatsächlich erfasste öffentliche AGB-Seite als
`captured_url: https://www.temu.com/de/terms-of-use.html` ausgewiesen. Nach dem
Abschluss zeigte die Oberfläche trotzdem den älteren Fall
`20260821T090820744158Z-182f5021` für die Temu-Startseite. Dadurch wirkten die
AGB- und Datenschutz-Schaltflächen fälschlich deaktiviert, obwohl im neuen Paket
Rechtstextbilder vorhanden waren.

### Ursache und Diagnose

Die Ursache ist im UI-Ladeweg belegt. `loadNewest(expectedUrl)` sucht in der
Fallliste zuerst nach `entry.url === expectedUrl`. Die Fallzusammenfassung aus
`CaseArchive._summary` enthält jedoch kein `requested_url`. Bei einem
erfolgreichen Rechtstext-Fallback ist `url` die tatsächlich erfasste Unterseite
und damit nicht mehr die angeforderte Startseite. Liegt ein älterer Fall vor,
dessen `url` noch exakt der Startseite entspricht, wird deshalb dieser ältere
Fall ausgewählt. Die Dateizeitstempel, Fallkennungen sowie `requested_url` und
`captured_url` des neuen Pakets schließen eine fehlende neue Erfassung als
Ursache aus.

### Lösung

Die Fallzusammenfassung gibt nun `requested_url` und `captured_url` getrennt
aus. `loadNewest` sucht zuerst nach `requested_url`, danach aus
Abwärtskompatibilitätsgründen nach `url` und erst zuletzt nach dem neuesten Fall
insgesamt. Da die Fallliste absteigend nach Erfassungszeit sortiert ist, wird so
der neueste Lauf zur ursprünglich eingegebenen URL geöffnet. Das Eingabefeld
zeigt ebenfalls weiterhin `requested_url`; `url` und `captured_url` bleiben für
die Transparenz der tatsächlich gesicherten Seite erhalten.

Für eine eindeutige lokale Vorführung kann zusätzlich ein bestimmter
gespeicherter Fall über `/beweis-labor?case_id=<Fallkennung>` geöffnet werden.
Die Kennung wird weiterhin durch den bestehenden pfadsicheren API-Endpunkt
validiert; die Ansicht verändert oder kopiert keine Beweisdaten.

### Verifikation und verbleibende Grenze

Ein Regressionstest legt einen älteren Fall mit der Root-URL und einen neuen
Fallback-Fall mit derselben `requested_url`, aber abweichender `captured_url`
an. Er bestätigt die Sortierung, beide URL-Felder in der API und die Priorität
von `requested_url` im UI-Ladeweg. Der Browser-Smoke-Test mit dem vorhandenen
Temu-Paket öffnete danach den Fall `20260821T155017397646Z-4bae2d59`, zeigte die
Temu-Nutzungsbedingungen und ließ die AGB- sowie Datenschutz-Schaltflächen
aktiv. Adidas war bei der Vorführung nicht von diesem Anzeigefehler betroffen,
weil dessen blockierte Root-Seite zugleich die `captured_url` blieb.

Ein unmittelbar danach gestarteter neuer Temu-Lauf
`20260821T160217037848Z-2948c897` wurde dagegen von Temu auf der Hauptseite und
allen elf geprüften Rechtstextpfaden mit derselben JavaScript-Challenge
begrenzt. Die Oberfläche zeigte dafür nach der Korrektur richtigerweise den
neuen Schutzbefund mit deaktivierten Rechtstext-Schaltflächen. Der frühere,
erfolgreich bebilderte Lauf bleibt über seine Fallkennung getrennt aufrufbar.
Damit werden ein archivierter erfolgreicher Stand und ein aktueller
Schutzbefund nicht miteinander vermischt.

## Adidas-Rechtstexte liefern im lokalen Lauf dieselbe HTTP-403-Schutzseite

### Symptom

Der Lauf vom 21.08.2026 für `https://www.adidas.de/` versuchte nach dem
geschützten Hauptabruf ausdrücklich die bekannte deutsche AGB-Adresse
`https://www.adidas.de/terms_and_conditions`. Hauptseite und AGB-Ziel antworteten
mit HTTP 403. Das erzeugte Bild zeigt deshalb nur die Adidas-Hinweisseite zur
automatischen Bot-Kontrolle und ist korrekt als browserlose HTML-Visualisierung,
nicht als Live-Browser-Screenshot oder Klauselbeweis, beschriftet.

Die automatische Datenschutzsuche versuchte dabei noch
`https://www.adidas.de/privacy-policy.html`. Die öffentlich belegte deutsche
Adresse lautet dagegen `https://www.adidas.de/privacy_policy`.

### Ursache und Diagnose

Für die AGB liegt kein fehlender Zielpfad vor: `legal_pages.json` weist den
bekannten Pfad `/terms_and_conditions` und den fehlgeschlagenen Abruf mit HTTP
403 aus. Auch der transparente Browsermodus mit Projekt-User-Agent,
`navigator.webdriver=true`, ohne Stealth, Proxy oder gespeichertes Profil erhielt
die Adidas-Schutzseite. Die AGB-Erfassung scheiterte daher an der externen
Zugriffskontrolle.

Beim Datenschutz besteht zusätzlich eine lokale Pfadlücke: In der zentralen
Website-Zuordnung ist bisher nur der Adidas-AGB-Pfad hinterlegt. Deshalb fiel die
Suche auf den allgemeinen, für Adidas falschen Kandidaten
`/privacy-policy.html` zurück.

### Lösung

Die produktive Pfadkorrektur ist noch offen: Für `adidas.de` muss
`/privacy_policy` als bekannter öffentlicher Datenschutzpfad ergänzt und vor
allgemeinen Kandidaten geprüft werden. Dies verbessert Pfadwahl und
Dokumentation, hebt aber die beobachtete HTTP-403-Sperre nicht auf.

Die Zugriffskontrolle wird nicht umgangen. Bleibt auch der korrekte öffentliche
Pfad im transparenten Abruf gesperrt, endet der Lauf weiterhin mit einem klar
bezeichneten Schutzbefund. Für einen Inhaltsbeweis ist dann eine zulässige
manuelle Erfassung oder eine ausdrückliche Bereitstellung beziehungsweise
Freigabe durch Adidas erforderlich.

### Verifikation und verbleibende Grenze

Der Lauf `20260821T155127210246Z-4c51d898` belegt den HTTP-403-Status für
Hauptseite und bekannten AGB-Pfad sowie die korrekte Kennzeichnung des
Ersatzbildes. Nach Ergänzung des Datenschutzpfads sind Kandidatenreihenfolge,
`legal_pages.json` und ein Schutzbefund mit exakt `/privacy_policy` per
Regressionstest zu prüfen. Ein erfolgreicher Suchmaschinenabruf des öffentlichen
Textes belegt die Adresse, ist aber kein Ersatz für eine eigene Beweiserfassung
durch das BeweisLab.

## Aura-Frontend: BeweisLab-Start wird als fremde Browser-Origin abgewiesen

### Symptom

Das über den lokalen Aura-Frontendserver unter `http://127.0.0.1:4173/beweis-labor`
geöffnete BeweisLab lud vollständig. Beim Start einer Erfassung antwortete der
Stream-Endpunkt jedoch mit HTTP 403 und der sichtbaren Meldung
`Fremde Browser-Origin ist nicht zulässig.`

### Ursache und Diagnose

Der Vite-Proxy leitete `/api` korrekt an `http://127.0.0.1:8000` weiter und setzte
mit `changeOrigin` den Ziel-Host. Der vom Browser gesendete `Origin`-Header blieb
aber `http://127.0.0.1:4173`. Die unveränderte Same-Origin-Prüfung in
`muclegal/ui.py` verglich diesen Header mit dem bereits auf Port 8000 umgeschriebenen
Host und wies die Anfrage deshalb korrekt ab. Ein leerer Test-POST an
`/api/v1/tenor-drafts` reproduzierte vor der Korrektur HTTP 403.

### Lösung

Nur der lokale `/api`-Proxy setzt den weitergeleiteten Origin-Header nun explizit
auf `http://127.0.0.1:8000`. Die Backend-Sicherheitsprüfung wird nicht gelockert;
direkte Anfragen mit einer fremden Origin bleiben unzulässig. BeweisLab, Artefakte
und statische Dateien werden weiterhin ausschließlich an den lokalen
FastAPI-Prozess weitergeleitet.

### Verifikation und verbleibende Grenze

Der identische leere Test-POST liefert über Port 4173 nach der Korrektur HTTP 422
für die erwarteten fehlenden Pflichtfelder statt HTTP 403. Damit erreicht die
Anfrage den regulären Request-Validator, ohne einen Erfassungslauf zu starten.
Der Browser-Smoke-Test prüft zusätzlich den sichtbaren Startpfad und das Fehlen
einer 403-Origin-Meldung. Die Proxy-Korrektur gilt nur für die lokale
Entwicklungsadresse auf Port 4173; wird der Frontend-Port geändert, muss das lokale
Proxy-Ziel konsistent angepasst oder Frontend und Backend unter derselben Origin
ausgeliefert werden.
# Windows-Anwendungsrichtlinie blockiert `warcio.exe` trotz installiertem Paket

### Symptom

Der vollständige lokale Testlauf vom 24.08.2026 scheiterte in mehreren Golden-Path-
und WARC-Tests mit `OSError: [WinError 4551] Eine Anwendungssteuerungsrichtlinie hat
diese Datei blockiert`. Fallbezogene Läufe stuften den WARC-Schritt dadurch als
`warning` und den Gesamtstatus als `completed_with_warnings` ein.

### Ursache und Diagnose

`find_tool("warcio")` fand den von Python installierten Windows-Console-Script-Shim
`Python313/Scripts/warcio.exe`. Die lokale Anwendungssteuerung blockierte erst den
Prozessstart dieses EXE-Shims. Deshalb griff der bereits vorhandene In-Process-
Fallback nicht: Er war bisher ausschließlich für den Fall vorgesehen, dass kein
CLI-Pfad gefunden wird. `warcio` selbst war als Python-Paket installiert und
importierbar; lediglich der separate EXE-Start war untersagt.

### Lösung

`validate_warc` fängt jetzt auch einen Betriebssystemfehler beim Start des gefundenen
CLI-Shims ab und wechselt zu `_validate_warc_in_process`. Dieser Pfad liest weiterhin
alle Records mit `ArchiveIterator(check_digests=True)`, konsumiert die Record-Inhalte
vollständig und verwirft leere Archive. Die WARC-Validierung wird damit nicht
übersprungen oder abgeschwächt.

### Verifikation und verbleibende Grenze

Der zuvor blockierte produktive Snapshot-WARC-Test, beide Offline-Golden-Path-Tests,
der fallbezogene Status-Test und der Live-Workflow-Status-Test bestanden nach der
Korrektur. Der vollständige Lauf ohne den separat bekannten Wget-Flake bestand mit
`129 passed, 1 deselected`. Der GNU-Wget-Test selbst scheiterte in diesem Lauf an
einem abweichenden Response-Payload-Hash und wird deshalb ausdrücklich nicht als grün
ausgegeben. Echte Digest- oder Payloadfehler in von Wget erzeugten Records müssen
weiterhin strikt fehlschlagen und dürfen nicht durch den Fallback kaschiert werden.

# Minimal-Tenorschreibhilfe ordnet „wirbt“ der falschen Fallgruppe zu

### Symptom

Die am 24.08.2026 wieder aktivierte Minimalansicht erzeugte für einen beschriebenen
Werbeverstoß mit der Formulierung „das Unternehmen wirbt …“ einen Entwurf zur
Kündigungsschaltfläche. Eine Autovervollständigung konnte außerdem einen ungefüllten
Registerplatzhalter wie `{{vollstreckungsperson}}` anzeigen.

### Ursache und Diagnose

Die deterministische Fallgruppenerkennung kannte `Werbung` und den Wortstamm `werb`,
nicht aber die häufige Verbform `wirbt`. Dadurch fiel sie auf die Default-Fallgruppe
`kuendigungsbutton` zurück. Die Autovervollständigung gab den Rohbaustein statt des
bereits mit dem Profil gerenderten Bausteins zurück.

### Lösung

Die Erkennung liegt nun als getestete reine Funktion in
`frontend/src/lib/minimal-tenor-logic.ts` und umfasst `werb`, `wirb` sowie
`irreführ`. `nextAutofillBlock` rendert Slots vor der Anzeige mit demselben lokalen
Profil wie die beiden Entwurfsvorschläge.

### Verifikation und verbleibende Grenze

Der neue Unit-Test unterscheidet die Formen `wirbt` und `Werbung`; TypeScript-Prüfung
und Produktionsbuild bestehen. Die Erkennung bleibt eine transparente,
deterministische Prototyp-Heuristik. Nicht erkannte Fallgruppen dürfen weiterhin nur
lokale Vorschläge erzeugen; eine menschliche Freigabe erfolgt ausschließlich über die
backendgebundene Maske.

# Hetzner-Domainmonitor meldet Windows-`warcio.exe` trotz gültigem Linux-WARC

### Symptom

Der manuell freigegebene Viagogo-Erstlauf vom 24.08.2026
(`20260824T210107215540Z-57fc3a84`) beendete die fachliche Prüfung wegen eines
HTTP-403-Schutzes der erforderlichen Ticketseite nachvollziehbar als
`pruefung_unvollstaendig`. Zusätzlich enthielt `result.json` jedoch den davon
unabhängigen Warnhinweis, die WARC-Datei der erreichbaren Startseite habe wegen
`[Errno 13] Permission denied:
'/home/muclegal/AppData/Local/Programs/Python/Python313/Scripts/warcio.exe'` nicht
erzeugt werden können. Tatsächlich lagen `page-001.warc.gz` und `page-001.cdx` im
Laufverzeichnis.

### Ursache und Diagnose

Die unmittelbare Fehlerursache ist die Auswahl eines nicht zur Linux-Laufzeit
passenden Windows-Console-Script-Pfads für die WARC-Validierung. Die systemd-Unit
läuft als `muclegal` aus `/opt/muclegal/releases/20260824-191613-add4929`; ihr
`PATH` enthält `/opt/muclegal/venv/bin` nicht. Dort ist aber ein ausführbares
Linux-`warcio` installiert. Der gespeicherte WARC-Datensatz bestand anschließend
mit genau diesem CLI die Digestprüfung. Auch ein separater Aufruf von
`validate_warc` unter demselben Benutzer, demselben Release, demselben `HOME` und
dem eingeschränkten Service-`PATH` fiel korrekt auf die In-Process-Validierung
zurück und las einen Record erfolgreich. Warum der abgeschlossene Workerlauf trotz
des vorhandenen `OSError`-Fallbacks den Windows-Pfad als Warnung speicherte, ließ
sich nachträglich nicht reproduzieren; eine weitergehende Ursache wird daher nicht
als geklärt ausgegeben.

### Lösung

`find_tool` berücksichtigt die fest hinterlegten Windows-Werkzeugpfade jetzt nur
noch bei `os.name == "nt"`. Unter Linux kann dadurch auch ein versehentlich
vorhandener Pfad unter `AppData/.../warcio.exe` niemals als Validator ausgewählt
werden. Weil die systemd-Unit den Venv-Binärpfad nicht in `PATH` führt, verwendet
das Hetzner-Backend weiterhin den bereits vorhandenen gleichwertigen
In-Process-Validator mit `ArchiveIterator(check_digests=True)`. Der gültige
WARC-Datensatz des ursprünglichen Laufs wird nicht wegen des fehlerhaften
Warnhinweises verworfen.

### Verifikation und verbleibende Grenze

`/opt/muclegal/venv/bin/warcio check -v` meldete für die erzeugte
`page-001.warc.gz` `digest pass`; `validate_warc` meldete im separaten
Service-Umgebungs-Probeaufruf `warcio (Python): 1 Record(s) erfolgreich gelesen.`
Der neue Plattformtest erzwingt unabhängig vom Entwicklungsbetriebssystem eine
POSIX-Laufzeit und bestätigt, dass ein vorhandener synthetischer Windows-Pfad dort
nicht verwendet wird. Der vollständige lokale Lauf bestand mit `160 passed`.
Ein erneuter produktiver Domainlauf muss zusätzlich ohne Windows-Pfad-Warnung
enden.

# Fallmonitor versuchte nach HTTP 403 keinen transparenten Browserabruf

### Symptom

Im Viagogo-Erstlauf `20260824T210107215540Z-57fc3a84` wurde die ausdrücklich im
Fallprofil verlangte Ticketseite nach der direkten HTTP-403-Antwort sofort unter
`blocked_urls` abgelegt. Obwohl der Fehlertext selbst einen transparenten
Browser-Prüfversuch als zulässige nächste Stufe bezeichnete, wurde nur die direkt
erreichbare Startseite mit Playwright auf das gemeldete Element geprüft. Der Lauf
endete nach 4,224 Sekunden als `pruefung_unvollstaendig`.

### Ursache und Diagnose

Die Warteschleife in `CaseDomainMonitor.run` behandelte jeden `FetchFailure`
terminal. Der bereits vorhandene, robots-konforme `HttpFetcher.fetch_in_browser`
und sein laufbezogener `CaptureRunController` wurden im Domainmonitor nicht
aufgerufen. Zusätzlich galt die DOM-Abdeckung schon dann als vollständig, wenn
irgendeine relevante Seite erfolgreich geprüft worden war. Das Scheitern eines
zweiten erforderlichen Prüfziels blieb deshalb außerhalb der allgemeinen URL-
Abdeckung ohne eigenes DOM-Abdeckungsgate.

### Lösung

Nur für ein vom Menschen freigegebenes, ausdrücklich erforderliches Fallprofilziel
mit `protected_or_login_page` startet der Domainmonitor jetzt genau einen
transparenten Browser-Fallback. Robots-Regeln, öffentlicher Netzwerkcheck,
Projekt-User-Agent, `navigator.webdriver=true`, frischer Kontext, fehlender Proxy
und das Verbot verändernder Requests bleiben unverändert. Direkter Schutzstatus,
Browserausgang und Erfassungsumfang werden in `coverage.browser_fallbacks`
getrennt dokumentiert. Sämtliche dabei erzeugten HTML-, Text-, Metadaten- und
Bildartefakte liegen innerhalb des Laufverzeichnisses und werden in das SHA-256-
Manifest aufgenommen.

Für Elementfälle vergleicht das Abschlussgate außerdem alle erforderlichen URLs
mit `inspected_dom_target_urls`. Jede nicht erfolgreich geprüfte Pflichtseite
erscheint in `missing_dom_target_urls` und erzwingt weiterhin
`pruefung_unvollstaendig`; ein erfolgreicher Scan nur der Startseite kann damit
nicht mehr als vollständige Prüfung der Ticketseite gelten.

### Verifikation und verbleibende Grenze

Ein synthetischer Regressionstest reproduziert direkten HTTP-403-Schutz, liefert
die Pflichtseite anschließend im Browsermodus aus und bestätigt vollständige
Abdeckung sowie das manifestierte Browserbild. Ein zweiter Test lässt nur eines
von zwei erforderlichen DOM-Zielen scheitern und bestätigt den unvollständigen
Status. Zusammen mit allen übrigen Tests bestand der lokale Lauf mit
`160 passed`; der isolierte Browser-Smoke-Test mit `https://example.com` erzeugte
ein herunterladbares technisches Beweispaket. Der Browser-Fallback überwindet
keinen fortbestehenden Seitenschutz: Liefert auch Chromium eine Challenge, ein
Login oder HTTP 403, bleibt der Fall mit den gespeicherten Schutzartefakten zur
manuellen Prüfung offen.

# DataDome-Interstitial wurde als teilweise erfasste Ticketseite behandelt

### Symptom

Der erste Viagogo-Wiederholungslauf nach Aktivierung des transparenten
Browser-Fallbacks (`20260824T212640008341Z-b8158375`) erfasste nach dem direkten
HTTP 403 im Browser ein HTML-Dokument mit `geo.captcha-delivery.com`, einem
`/interstitial/`-Iframe und dem Titel `DataDome Device Check`. Dieser Stand wurde
als `browser_status: captured` und `capture_completeness: teilweise_erfasst` in
die Seitenliste aufgenommen, obwohl er ausschließlich eine CAPTCHA-Zwischenseite
enthielt.

### Ursache und Diagnose

`_detect_block_page` erkannte sichtbare reCAPTCHA-, hCaptcha- und Cloudflare-
Komponenten, aber noch keine DataDome-Interstitials. Die gespeicherte Browser-DOM-
Datei belegt, dass der Marker außerhalb von Script-, Style-, Template- und
Noscript-Blöcken als tatsächliches `iframe src` vorhanden war. Es handelt sich
daher nicht um den bei Shopify bekannten inaktiven CAPTCHA-Bootstrapcode.

### Lösung

Die konservative Komponentenerkennung umfasst jetzt in sichtbarem Markup auch
`captcha-delivery.com` und `datadome`. Ein bloßer Treffer in einem Script bleibt
durch die bestehende Entfernung inaktiver Scriptblöcke ausdrücklich unbeachtlich.
Der transparente Browser-Fallback gibt einen solchen Stand damit als
`protected_or_login_page` zurück; das CAPTCHA wird weder bedient noch umgangen.
Endet Chromium bei einem Schutzstand vor der regulären Screenshotphase, verwendet
der Domainmonitor zusätzlich denselben beschrifteten HTML-Bildfallback wie das
BeweisLab. Der Pfad beziehungsweise ein verbleibender Bildfehler wird im
Browser-Fallback-Eintrag dokumentiert und das erzeugte PNG in das Manifest
aufgenommen.

### Verifikation und verbleibende Grenze

Ein Regressionstest verwendet denselben DataDome-Aufbau aus Script und sichtbarem
Interstitial-Iframe und erwartet den Schutztyp `CAPTCHA oder Bot-Challenge`. Der
bestehende Test für inaktiven Shopify-CAPTCHA-Code bleibt grün. Ein weiterer
Regressionstest beendet den Browser-Fallback geschützt vor der Screenshotphase
und bestätigt das manifestierte Schutzbild. Ein erneuter Hetzner-Lauf muss das
DataDome-Ziel unter `blocked_urls` mit Browser-Fallback-Schutzbefund führen, darf
dessen HTML nicht mehr als Ticketseiteninhalt in `document_findings` aufnehmen
und muss das Ersatzbild manifestieren. Der Schutz wird weiterhin nicht überwunden;
ohne eine frei zugängliche Seite bleibt die inhaltliche Prüfung unvollständig.

# OpenAI-Tenorvorschläge scheitern trotz gültigem API-Schlüssel mit HTTP 429

### Symptom

Der reale Zwei-Entwurfs-Lauf der Tenorschreibhilfe vom 24.08.2026 erreichte die
OpenAI Responses API, brach aber vor der ersten schema-validierten Antwort mit
`429 credit_balance_exhausted` und dem Hinweis auf fehlendes Guthaben ab. Der zuvor
ausgeführte reine Authentifizierungstest auf `/v1/models` hatte HTTP 200 geliefert.

### Ursache und Diagnose

Der Projekt-API-Schlüssel ist syntaktisch gültig und authentifiziert. Das zugehörige
OpenAI-Projekt verfügt jedoch über kein verbleibendes API-Guthaben beziehungsweise
kein ausreichendes Abrechnungslimit. Ein erfolgreicher Aufruf der Modellliste belegt
nur die Authentifizierung; er belegt nicht, dass kostenpflichtige Generierungen
freigeschaltet sind.

### Lösung

Es wurde ein Schlüssel eines freigeschalteten OpenAI-Projekts in der von Git
ausgeschlossenen lokalen `.env` hinterlegt. `app.py` lädt diese Datei vor der
Bereitschaftsprüfung serverseitig; der Schlüssel gelangt nicht in den Browser. Das
Backend übersetzt den Fehler eines nicht finanzierten Projekts weiterhin in eine
kurze deutsche Handlungsanweisung; es gibt keinen stillen oder als KI bezeichneten
deterministischen Ersatzentwurf aus.

### Verifikation und verbleibende Grenze

Ein realer Responses-API-Lauf mit `gpt-5.6-luna` war anschließend erfolgreich und
lieferte die Strategien `precise` und `neutral` als zwei unterschiedliche,
schema-validierte Entwürfe. Beide behielten `human_approval_required: true` und
`freigabe_durch_mensch: null`. Der fokussierte Testsatz besteht mit neun Tests; ein
Prozess ohne vorab gesetzte Umgebungsvariable bestätigt zusätzlich, dass die lokale
`.env` geladen wird. Der im Chat offengelegte Schlüssel ist unabhängig davon nach
dem Test zu widerrufen und durch einen neuen, nicht im Chat geteilten Server-Schlüssel
zu ersetzen.

# Temporärer ngrok-Tunnel scheitert an alter Agent-Version oder Host-Header-Schutz

### Symptom

Der am 24.08.2026 ausdrücklich gestartete Demo-Tunnel brach mit
`ERR_NGROK_121` ab, obwohl der Authtoken gültig war. Nach der Agent-Aktualisierung
lieferte der authentifizierte Tunnel zunächst `Invalid host header`, während der
anonyme Zugriff bereits korrekt mit HTTP 401 abgewiesen wurde.

### Ursache und Diagnose

Das über die normale Winget-Quelle angebotene Paket enthielt ngrok 3.3.1; das
verwendete Konto verlangte mindestens 3.20.0. Der eingebaute Updater installierte
zwar eine aktuelle Version, deren direkt ersetzte Binärdatei wurde auf diesem
Windows-System jedoch durch die Anwendungssteuerung wegen fehlender Reputation
blockiert. Die anschließend erreichbare ngrok-Domain wurde außerdem von der bewusst
engen `TrustedHostMiddleware` des lokalen Servers abgewiesen.

### Lösung

Das alte Winget-Paket wurde ausschließlich durch die offizielle
Microsoft-Store-Ausgabe ersetzt. Der temporäre Tunnel leitet weiter auf
`127.0.0.1:8000` und schreibt den eingehenden Host-Header auf den lokalen Zielhost um.
Zunächst aktivierte Basisauthentifizierung wurde auf ausdrückliche Nutzeranweisung
wieder entfernt, weil der eingebettete Browser des Test-Handys den Anmeldedialog nicht
öffnete. Der Backendprozess verwendet einen isolierten Store unter
`.muclegal-demo/`; bestehende Beweisartefakte in `.muclegal-ui/` bleiben unberührt.
Authtoken und frühere Demo-Zugangsdaten werden nicht im Repository gespeichert.

### Verifikation und verbleibende Grenze

Nach der ausdrücklich angeordneten Öffnung erhält ein nicht authentifizierter Abruf
von `/beweis-labor` HTTP 200 und den erwarteten App-Inhalt. Der Browser-Smoke-Test
bestätigt sichtbaren Inhalt, interaktive Elemente und keine Framework-Fehleranzeige.
Der Tunnel ist damit für jeden erreichbar, der die temporäre URL kennt, und muss nach
der Demo beendet werden. Er ist nur verfügbar, solange der lokale Uvicorn- und
ngrok-Prozess laufen. Der verwendete ngrok-Schalter für die Host-Umschreibung ist
inzwischen veraltet; bei einer dauerhaften Wiederholung ist er durch eine äquivalente
ngrok Traffic Policy zu ersetzen.

# ngrok zeigt das alte FastAPI-Frontend statt des React-Fallmonitors

### Symptom

Der öffentliche Demo-Link war erreichbar, zeigte auf `/` aber die ältere
FastAPI-/Jinja-Fallmaske statt des Aura-Dashboards und der kompakten React-
Tenorschreibhilfe.

### Ursache und Diagnose

Der ngrok-Tunnel leitete direkt auf `127.0.0.1:8000`. Dieser Port gehört zum
FastAPI-Backend und liefert auf der Root-Route weiterhin das Backend-Template aus.
Das kanonische React-Frontend läuft separat über Vite auf Port 4173 und besitzt dort
den erforderlichen Proxy für `/api`, `/static`, `/artifact` und `/beweis-labor`.

### Lösung

Das Vite-Frontend wurde mit dem dokumentierten lokalen Port 4173 gestartet. Der
temporäre ngrok-Tunnel leitet nun auf `127.0.0.1:4173`; Vite reicht Backend- und
BeweisLab-Anfragen intern an `127.0.0.1:8000` weiter. Dadurch bleibt genau eine
öffentliche Origin für Navigation und API-Aufrufe erhalten.

### Verifikation und verbleibende Grenze

Der öffentliche Browser-Smoke-Test zeigt auf `/` den Titel
`Fallmonitor – Muc Legal Monitoring`, das Dashboard und die Aura-Navigation. Unter
`/tenorhilfe` erscheinen die Tabs `MINIMAL` und `MASKE` sowie das Eingabefeld der
kompakten Tenorschreibhilfe; ein Fehleroverlay ist auf beiden Routen nicht vorhanden.
`/api/v1/monitoring-cases` liefert über denselben öffentlichen Ursprung HTTP 200 mit
`application/json`. Für die Demo müssen Backend, Vite-Frontend und ngrok-Tunnel
gleichzeitig weiterlaufen.

# Tenorhilfe meldet fehlendes Guthaben trotz funktionierendem `.env`-Schlüssel

### Symptom

Der öffentliche Aufruf von `POST /api/v1/tenor-proposals` endete am 24.08.2026 mit
HTTP 502 und der UI-Meldung, das OpenAI-Projekt habe kein Guthaben. Der Nutzer sah
gleichzeitig weiterhin verfügbare Credits im vorgesehenen API-Projekt.

### Ursache und Diagnose

Ein echter Minimalaufruf mit dem ausschließlich aus `.env` geladenen Schlüssel war
erfolgreich. Der anonymisierte SHA-256-Fingerprint dieses Schlüssels unterschied sich
jedoch vom Fingerprint des im laufenden Uvicorn-Prozess vorhandenen Schlüssels. Die
Desktop-Sitzung hatte einen älteren `OPENAI_API_KEY` vererbt; `load_dotenv(...,
override=False)` ließ diesen Umgebungswert vor der ausdrücklich eingerichteten lokalen
`.env` gewinnen. Der ältere Schlüssel gehörte zu dem bereits erschöpften Projekt.

### Lösung

Der Backendprozess wurde mit dem Schlüssel aus der lokalen `.env` neu gestartet.
Für diesen ausschließlich lokalen Hackathon-Prototyp lädt `app.py` die von Git
ausgeschlossene `.env` nun bewusst mit `override=True`, damit ein veralteter geerbter
Desktop-Wert den ausgewählten Projektschlüssel bei späteren Neustarts nicht erneut
überlagert. Der Schlüssel selbst wird weder ausgegeben noch in Git aufgenommen.

### Verifikation und verbleibende Grenze

Nach dem Neustart stimmen die anonymisierten Fingerprints von `.env` und
Backendprozess überein. Ein echter öffentlicher Tenorlauf mit `gpt-5.6-luna` lieferte
zwei unterschiedliche, schema-validierte Strategien (`precise`, `neutral`), jeweils
mit `human_approval_required: true`. Die OpenAI-Projektabrechnung bleibt extern; wenn
der nun tatsächlich verwendete Projektschlüssel später sein eigenes Limit erreicht,
ist eine erneute 429-Antwort weiterhin korrekt und wird sichtbar ausgegeben.

# Tenor-Generierungsbutton wirkt auf dem Handy ohne Funktion

### Symptom

Der Nutzer meldete am 24.08.2026, dass der Generierungsbutton der minimalen
Tenorschreibhilfe nicht funktioniere. Parallel protokollierte Vite einen React-
Hydrationfehler auf dem Dashboard, weil Server und Browser zwei unterschiedliche
Minutenwerte renderten.

### Ursache und Diagnose

Ein reproduzierter öffentlicher Klick erreichte `POST /api/v1/tenor-proposals`, erhielt
HTTP 200 und zeigte nach rund 15 Sekunden beide Entwürfe. Die mobile Trefferfläche war
sichtbar, nicht deaktiviert, vollständig im Viewport und tatsächlich anklickbar.
Während der Wartezeit änderte sich jedoch nur das kleine Spinner-Symbol; der Text
`Generieren` blieb unverändert und vermittelte auf dem Handy keinen ausreichenden
Fortschritt. Unabhängig davon erzeugte `new Date()` direkt beim Rendern der Startseite
unterschiedliche SSR- und Clientwerte an einer Minutengrenze.

### Lösung

Der Button trägt während der Anfrage nun `aria-busy=true` und den sichtbaren,
barrierearmen Statustext `KI erstellt zwei Entwürfe …`. Die Dashboard-Route liefert
den Referenzzeitpunkt einmalig über ihren Loader; Server- und Client-Render verwenden
dadurch denselben Zeitwert.

### Verifikation und verbleibende Grenze

Der öffentliche Browserlauf wechselt nach dem Klick erfolgreich zu `Wähle einen
Entwurf` und zeigt die bearbeitbaren Varianten `Präzise` und `Technikneutral` ohne
Alert. Bei 390 × 844 Pixeln liegt der Button vollständig im Viewport und besteht den
Hit-Test. Die Antwortzeit hängt weiterhin von der OpenAI Responses API ab; während
dieser Zeit bleibt die neue Fortschrittsmeldung sichtbar und ein Doppelklick gesperrt.

# Formulierung „zu werben“ aktiviert den Generierungsbutton nicht

### Symptom

Im Browser-Smoke-Test blieb die Tenorschreibhilfe bei einem inhaltlich vollständigen
Satz mit der Formulierung `mit einer falschen Frist zu werben` im Rückfragezustand.
Statt des Generierungsbuttons erschien die Frage nach der konkreten Handlung.

### Ursache und Diagnose

Die Fallgruppenerkennung akzeptierte bereits den Wortstamm `werb`, die getrennte
semantische Vollständigkeitsprüfung erkannte dagegen nur das Substantiv `Werbung`.
Der Infinitiv `werben` erfüllte deshalb die Dimension `handlung` nicht. Der Fehler
wurde mit genau dem im Browser verwendeten vollständigen Satz reproduziert.

### Lösung

Die deterministische Handlungserkennung verwendet nun ebenfalls den Wortstamm
`werb` und deckt damit `werben`, `wirbt` und `Werbung` ab. Der Frontend-Logiktest
enthält einen vollständigen Satz mit `zu werben` als Regressionstest.

### Verifikation und verbleibende Grenze

Der ergänzte Test besteht; anschließend erschienen im echten Browser sowohl der
Generierungsbutton als auch die beiden OpenAI-Entwürfe. Nach Auswahl nutzt der
Entwurf die breite Einzeldarstellung. Die Vollständigkeitsprüfung bleibt eine
begrenzte, sichtbare Schlüsselwortlogik und kann weitere bislang unbekannte Synonyme
übersehen; sie trifft keine juristische Bewertung.

# Ausgewählter Tenor ist mobil zu schmal und Diktat wiederholt Sätze nach Pausen

### Symptom

In der Einzeldarstellung blieb der ausgewählte Tenor zu klein zum konzentrierten
Lesen. Bei 390 × 844 Pixeln war das Textfeld nur 94 Pixel breit. Außerdem hängte die
Browser-Spracherkennung nach einer Sprechpause den bereits erkannten ersten Satz
erneut an, bevor sie den nächsten Satz ergänzte.

### Ursache und Diagnose

Die ausgewählte Fassung erbte die für den Zwei-Spalten-Vergleich gedachte kompakte
Höhe und Innenbreite. Zusätzlich blieb die 248 Pixel breite Desktop-Seitenleiste auch
unterhalb des `md`-Breakpoints sichtbar. Beim Diktat wurde bei jedem `onresult` die
gesamte kumulierte `results`-Liste an den jeweils aktuellen Text angehängt. Die Web
Speech API liefert nach einer Pause frühere Ergebnisse weiterhin in dieser Liste und
kennzeichnet nur über `resultIndex`, ab welcher Position sich Resultate geändert
haben.

### Lösung

Die ausgewählte Fassung verwendet nun eine eigene hohe Lese- und Bearbeitungsansicht
mit größerer Schrift, 32 Pixel Zeilenhöhe und nahezu der gesamten verfügbaren
Inhaltsbreite. Die Desktop-Seitenleiste wird auf kleinen Viewports ausgeblendet. Das
Diktat hält den Text vor Beginn der Aufnahme unverändert fest und verwaltet jedes
Sprachresultat unter seinem Ergebnisindex. Finale und vorläufige Updates ersetzen
damit das jeweilige Segment; der sichtbare Text wird aus Basis und geordneten
Segmenten rekonstruiert und nicht mehr kumulativ an sich selbst angehängt. Beginnt der
Nutzer während eines laufenden Diktats manuell zu schreiben, wird die Aufnahme
beendet, damit ein spätes Sprachergebnis die Eingabe nicht überschreibt.

### Verifikation und verbleibende Grenze

Der Logiktest simuliert `erster Satz → Finalisierung → Pause → zweiter Satz` und
bestätigt jeden Satz genau einmal. Ein Browserlauf mit kontrollierter
SpeechRecognition-Implementierung ergab exakt
`Der erste Satz. Nach der Pause folgt Satz zwei.` und keine Konsolenfehler. Die
ausgewählte Textfläche maß bei 1280 × 720 Pixeln 984 × 440 Pixel und bei 390 × 844
Pixeln 342 × 473 Pixel; der mobile Dokumentkörper hatte keinen horizontalen
Überlauf. Erkennungsqualität, Zeichensetzung und Mikrofonfreigabe bleiben Funktionen
der im jeweiligen Browser verfügbaren Web Speech API.

# Vite liefert nach überlappenden HMR-Änderungen einen veralteten Modulstand

### Symptom

Während der laufenden Bearbeitung zeigte die Tenorhilfe nach einem vollständigen
Reload die Fehlerseite. Die Browserkonsole meldete `needsMoreContext is not defined`,
obwohl dieser Bezeichner im aktuellen Quelltext bereits nicht mehr vorkam.

### Ursache und Diagnose

Mehrere zeitlich überlappende Änderungen an `MinimalTenorView.tsx` wurden vom lange
laufenden Vite-Prozess nacheinander per Hot Module Replacement verarbeitet. Der über
Port 4173 ausgelieferte transformierte Modultext enthielt noch die alte JSX-Referenz,
aber nicht mehr deren Deklaration. Der aktuelle Quelltext und der frische
Produktions-Build enthielten diese inkonsistente Kombination nicht.

### Lösung

Der Vite-Entwicklungsprozess wurde vollständig beendet und auf demselben Host und
Port neu gestartet. Der bestehende ngrok-Tunnel konnte dadurch unverändert auf das
frisch geladene Frontend weiterleiten.

### Verifikation und verbleibende Grenze

Nach dem Neustart lud `/tenorhilfe` lokal wieder vollständig. Die mobile
Einzeldarstellung und der Diktat-Pausenlauf liefen anschließend ohne Konsolenfehler.
HMR ist nur eine Entwicklungsfunktion; bei erneut überlappenden Dateiänderungen muss
der Dev-Prozess vor einer Demo sauber neu gestartet werden. Ein erfolgreicher
Produktions-Build allein repariert den Speicherzustand eines bereits laufenden
Dev-Prozesses nicht.

# Tenor-Rückfragen wiederholen sich oder verlassen die Fallgruppe

### Symptom

Die Tenorschreibhilfe konnte dieselbe Tatsache mehrfach und paraphrasiert abfragen.
Entweder-oder-Fragen erschienen als Ja/Nein-Fragen. Bei eigenständig zu beurteilenden
AGB-Klauseln waren außerdem Fragen nach URL, Fundort, Nutzungskanal oder konkreter
Verwendung möglich, obwohl diese Angaben für den Klauseltenor nicht tragend sind.

### Ursache und Diagnose

Die frühere Rückfragelogik stützte sich im Wesentlichen auf freie
Modellformulierungen. Den Fragen fehlte eine serverseitig kontrollierte Themen-ID;
es gab weder fallgruppenabhängige Themenkataloge noch eine Ähnlichkeitsprüfung gegen
bereits gestellte Fragen. Die drei bisherigen Antworttypen konnten echte
Auswahlfragen nicht korrekt abbilden.

### Lösung

Jede Rückfrage trägt nun eine validierte `topic_id`. Bereits im Sachverhalt enthaltene,
gestellte oder beantwortete Themen werden aus dem fallgruppenabhängigen Katalog
entfernt; eine normalisierte Textähnlichkeit fängt zusätzlich falsch etikettierte
Paraphrasen ab. Ungültige Modellvorschläge werden höchstens zweimal neu angefordert,
danach erscheint ein Fehler statt einer stillen Vollständigkeitsannahme.
`single_choice` liefert zwei bis fünf konkrete Optionen, während die Oberfläche immer
`Andere Angabe …` mit Freitext ergänzt. Ja/Nein bleibt binären Tatsachenfragen und
Slider bleiben quantifizierbaren Angaben vorbehalten. Für AGB-Klauseln sperrt der
Server insbesondere Fragen nach URL, Fundort, Kanal, Verwendungsdauer und
Verwendungsnachweis; die üblichen Formeln zum Verwenden, Berufen und inhaltsgleichen
Klauseln werden als Tenorstandard behandelt. Der eingefrorene Prompt der eigentlichen
Tenorerzeugung blieb unverändert.

### Verifikation und verbleibende Grenze

Backendtests prüfen doppelte Themen, paraphrasierte Wiederholungen, irrelevante
AGB-Fragen, falsch typisierte Alternativen, ungeeignete Slider und drei gescheiterte
Korrekturversuche. Frontendtests prüfen Themenübertragung sowie gewählte und freie
Auswahlantworten. Im Browser führte eine vollständige synthetische AGB-Klausel ohne
Rückfrage direkt zur Generierung. Ein synthetischer Kündigungsbutton-Fall zeigte
Auswahlbuttons und `Andere Angabe …`; die Freitextantwort blieb unter der Frage stehen
und führte zu einer anderen Anschlussfrage. Themenkatalog und Erkennung bereits
enthaltener Tatsachen bleiben bewusst deterministische Prototyp-Logik; die
Tenorerzeugung unterliegt weiterhin der menschlichen Freigabe.

# Vertrags-PDF wird trotz geringer Dateigröße als zu groß abgelehnt

### Symptom

Der erste echte Browser-Smoke-Test des neuen Vertragsuploads lehnte das vorhandene,
nur 132 KB große Challenge-PDF mit HTTP 413 und `Anfrage ist zu groß.` ab. Die UI
zeigte deshalb `nicht ausgelesen`, obwohl der PDF-Endpunkt selbst 10 MB erlaubte.

### Ursache und Diagnose

Die allgemeine HTTP-Sicherheitsmiddleware begrenzte alle schreibenden Endpunkte außer
dem Fallupload pauschal auf 64 KB. Diese Prüfung lief vor dem neuen
`/api/v1/tenor-pdf-text`-Handler und verhinderte deshalb dessen eigene, strengere
PDF-Prüfung. Ein direkter `curl`-Abruf reproduzierte denselben 413-Fehler; die
abweichende Fehlermeldung ordnete ihn eindeutig der Middleware zu.

### Lösung

Die Middleware verwendet für den Tenor-PDF-Endpunkt nun dasselbe Limit von 10 MB wie
die nachgelagerte PDF-Extraktion. Größen-, PDF-Signatur-, Seiten-, Verschlüsselungs-
und Textprüfungen im Handler bleiben unverändert bestehen. Ein API-Regressionstest
lädt bewusst eine gültige synthetische PDF mit mehr als 64 KB und weniger als 10 MB.

### Verifikation und verbleibende Grenze

Der Regressionstest besteht. Nach einem vollständigen Backend-Neustart beantwortete
der reale Upload des 132-KB-PDFs den Endpoint mit HTTP 200. Die Minimalansicht zeigte
`2 Seiten · im Tenor berücksichtigt` und bot ohne zusätzliche Texteingabe
`KI-Rückfragen starten` an; Browserkonsole und Fehlerliste blieben leer. Bildbasierte
Scan-PDFs werden weiterhin nicht per OCR verarbeitet, sondern mit einem sichtbaren
OCR-Hinweis abgelehnt.

# Hetzner-Frontend installiert unter Debian nur Node 20 statt der benötigten Node-22-Laufzeit

### Symptom

Beim ersten Hetzner-Deployment installierte Debian 13 über `apt` Node 20.19.2. Das
anschließende `npm install` lief zwar durch, meldete aber für mehrere
`@tanstack/react-start`-Pakete `EBADENGINE` und die Anforderung `node >=22.12.0`.
Ein Dienststart auf dieser nicht unterstützten Laufzeit wäre trotz erfolgreicher
Paketinstallation nicht belastbar gewesen.

### Ursache und Diagnose

Die Debian-Paketquelle und die im Frontend aufgelösten TanStack-Pakete haben
unterschiedliche Laufzeitzyklen. Entscheidend war nicht die erfolgreiche npm-
Installation, sondern die in den Paketmetadaten ausgewiesene Engine-Anforderung.
`node --version`, `npm --version` und die `EBADENGINE`-Zeilen ordneten den Fehler
eindeutig der Serverlaufzeit und nicht dem Anwendungscode zu.

### Lösung

Node 22.23.2 wurde als offizielles Linux-x64-Archiv geladen, vor dem Entpacken gegen
die offizielle `SHASUMS256.txt` geprüft und unter `/opt/node` versioniert eingebunden.
Der Frontenddienst verwendet ausdrücklich `/opt/node/bin/npm`; damit hängt er nicht
von der älteren Debian-Version unter `/usr/bin` ab. Nach dem Laufzeitwechsel wurden
die npm-Abhängigkeiten erneut abgeglichen und der Frontend-Build neu erzeugt.

### Verifikation und verbleibende Grenze

Der Server meldete Node 22.23.2 und npm 10.9.8. `npm run build` erzeugte Client-, SSR-
und Nitro-Ausgaben ohne Engine-Warnung; der systemd-Dienst startete anschließend auf
`127.0.0.1:4173` und antwortete mit HTTP 200. Playwright Chromium startete separat
erfolgreich. Die Node-Laufzeit wird nicht automatisch durch `apt upgrade`
aktualisiert. Vor einem späteren Versionswechsel müssen Archiv, SHA-256-Prüfung,
Frontend-Build und Browser-Smoke-Test erneut durchgeführt werden; nicht ungeprüft auf
die jeweils neueste Hauptversion springen.

# Wayback-Ausgangsbeweis lässt sich keinem Fall der archivierten Originaldomain zuordnen

### Symptom

Der regulär erzeugte Beweis für die archivierte Decathlon-AGB unter
`web.archive.org/web/.../https://www.decathlon.de/...` war vollständig und
manifestvalid. Das BeweisLab bot dennoch keinen passenden Decathlon-Fall zur
Zuordnung an; ein direkter API-Versuch wurde mit einer abweichenden Domain
zurückgewiesen.

### Ursache und Diagnose

Frontend und Backend verglichen ausschließlich den äußeren Host
`web.archive.org` mit `www.decathlon.de`. Bei einem Wayback-Replay bezeichnet der
eingebettete HTTP(S)-URL-Teil jedoch die tatsächlich archivierte Website. Manifest,
Eignungsstatus und Grey-Mode-Trennung des Pakets waren korrekt; nur die
Hostzuordnung war falsch.

### Lösung

Nur für den exakten Host `web.archive.org` wird nun das bekannte
`/web/<Zeitstempel>/<HTTP(S)-Original-URL>`-Format ausgewertet. Client und Server
verwenden den Host der eingebetteten Original-URL; das Backend bleibt maßgeblich.
Andere Archivhosts, unvollständige Replaypfade und eingebettete Nicht-HTTP(S)-Werte
bleiben beim äußeren Host und bestehen die Gleichheitsprüfung nicht. Dasselbe gilt
für eingebettete URLs mit Benutzername oder Passwort. Alle bisherigen
Manifest-, Eignungs- und Grey-Mode-Prüfungen bleiben unverändert.

### Verifikation und verbleibende Grenze

Der echte Beweis `20260824T200541463233Z-4a1d3218` ließ sich anschließend im
Browser beiden Decathlon-Fällen zuordnen. Der API-Regressionstest prüft zusätzlich
einen synthetischen Wayback-Beweis; die gemeinsame Backend-/UI-Testsuite bestand.
Unterstützt wird bewusst nur das exakte Wayback-Replayformat, nicht jeder beliebige
Archiv- oder Redirectdienst. Berechtigung und rechtliche Zulässigkeit des Abrufs
bleiben vom Nutzer zu prüfen.

# Rechtstext-Akkordeons hinter vielen Seitenschaltern und unklare Fallzuordnung

### Symptom

Bei einem Decathlon-Demolauf blieb der Zuordnungsbutton zunächst deaktiviert, obwohl
genau ein passender Monitoringfall angeboten wurde. Auf Rechtstextseiten konnten
geschlossene Datenschutzhinweise außerdem unberücksichtigt bleiben, wenn vor dem
eigentlichen Akkordeon mehr als 100 gewöhnliche Buttons im DOM standen oder mehrere
semantische Hauptbereiche vorhanden waren.

### Ursache und Diagnose

Die Fallauswahl verlangte auch bei genau einem Domain-Treffer einen zusätzlichen
manuellen Auswahlklick. Die Rechtstextlogik begrenzte dagegen zuerst die gemischte
Menge aus Akkordeons und sämtlichen Buttons auf 100 und prüfte erst danach die
fachliche Zulässigkeit. Außerdem verwendete der Klickpfad stets den ersten
`main`-/`article`-Knoten, während die Texterfassung bereits den inhaltsreichsten
Hauptbereich nutzte. Ein realer Decathlon-Lauf zeigte zusätzlich eine davon getrennte
Grenze: Der aktuelle Root-Abruf war eine Cloudflare-Blockseite; der ältere
Wayback-Datenschutz-Unterabruf scheiterte an `ERR_CONNECTION_REFUSED`. Beides ist
kein Aufklappfehler und darf nicht als vollständig erfasster Rechtstext erscheinen.

### Lösung

Bei exakt einem zulässigen Domain-Treffer wird der Monitoringfall jetzt automatisch
ausgewählt. Ein unvollständiger Scan kann damit bewusst zugeordnet werden und wird als
`pruefung_unvollstaendig` dokumentiert. Die Akkordeonlogik wählt deterministisch den
sichtbaren semantischen Hauptbereich mit dem meisten Text, schließt Navigation,
Header, Footer und Formulare aus und begrenzt erst anschließend bis zu 100 tatsächlich
zulässige Controls. Unterstützt werden native `details`, ARIA-Akkordeons und Tabs,
gängige Accordion-/Disclosure-Klassen, `data-state="closed"` sowie eindeutig
beschriftete Mehr-anzeigen-Schalter. Decathlon erhält zusätzlich feste öffentliche
Kandidaten für die aktuellen und bisherigen AGB-/Datenschutzpfade.

### Verifikation und verbleibende Grenze

Regressionstests decken 130 vorangestellte irrelevante Buttons, mehrere `main`-Knoten,
ARIA-Controls und `data-state`-Disclosures ab. Im Browser wurde geprüft, dass ein
einziger Decathlon-Fall ohne Zusatzklick ausgewählt und der Zuordnungs-/Vergleichsbutton
aktiv ist. Eine Website kann technisch erzwingen, dass immer nur ein Abschnitt zugleich
offen ist; dann werden die Abschnitte sequenziell erfasst und zusammen im normalisierten
Text sowie in der abgeleiteten Druckfassung gesichert. Cloudflare, nicht erreichbare
Wayback-Unterseiten, Logins, Paywalls und CAPTCHAs werden dadurch nicht umgangen und
bleiben sichtbar unvollständige Erfassungen.

# Kommas zerlegen juristische „Nicht umfasst“-Abgrenzungen in Satzfragmente

### Symptom

Der im Formular als eine Zeile eingegebene Satz
`Freistellung nur für Ansprüche, die ... beruhen, einschließlich ...` erschien in
der Fallansicht als drei mit Semikolon verbundene Fragmente. Gleiches geschah bei der
Teillieferungsabgrenzung. Dadurch verlor das wichtigste Feld gegen Fehlalarme seinen
syntaktischen Zusammenhang.

### Ursache und Diagnose

Eine gemeinsame Hilfsfunktion trennte sämtliche Mehrfachfelder sowohl an
Zeilenumbrüchen als auch an Kommas. Die Beschriftung der Textfelder verlangte dagegen
ausdrücklich eine Angabe pro Zeile. Nur das einzeilige Feld für alternative
Buttonbezeichnungen war tatsächlich als kommagetrennte Kurzliste gestaltet.

### Lösung

Relevante Seitentypen, Prüf-URLs, `nicht_umfasst` und erlaubte Subdomains werden nur
noch an Zeilenumbrüchen getrennt. Eine eigene Funktion erhält die bisherige
Komma-Unterstützung ausschließlich für alternative kurze Elementbezeichnungen. Die
beiden bereits angelegten isolierten Decathlon-Demoprofile wurden nach einer lokalen
Datenbanksicherung auf die ungeteilten Sätze korrigiert.

### Verifikation und verbleibende Grenze

Ein Frontend-Regressionstest prüft einen juristischen Satz mit zwei Kommas und eine
mehrzeilige Abgrenzung. Typprüfung und Produktions-Build bestanden; der Browser zeigte
beide Decathlon-Abgrenzungen danach wieder als vollständige Sätze. Mehrere wirklich
eigenständige Abgrenzungen müssen weiterhin jeweils in eine neue Zeile geschrieben
werden.

# Langer Domainlauf bleibt nach 120 Sekunden mit einer Fortschrittsmeldung stehen

### Symptom

Der erste echte Decathlon-Domainlauf arbeitete im Backend 294,071 Sekunden und wurde
mit `result.json` sowie verifiziertem Manifest abgeschlossen. Die Hinweise-Seite
zeigte nach zwei Minuten weiterhin nur
`Die freigegebene Domain wird fallbezogen und begrenzt durchsucht.` und übernahm den
späteren Endstatus nicht mehr.

### Ursache und Diagnose

Das Frontend beendete sein Polling nach 240 Abfragen zu je 500 Millisekunden, also
nach 120 Sekunden. Die serverseitige `ScanPolicy` erlaubt einem Domainlauf dagegen
bis zu 600 Sekunden; anschließend kann noch die lokale WARC- und Manifestbildung
folgen. Der Browser hatte damit vor dem zulässigen Backendbudget aufgegeben.

### Lösung

Das Polling bleibt nun elf Minuten mit dem gestarteten Lauf verbunden: zehn Minuten
Backendbudget plus eine Minute für die lokale Artefaktbildung. Bei einem trotzdem
nicht terminalen Lauf nennt die UI ausdrücklich, dass der Server weiterarbeitet und
die Hinweise später neu geladen werden sollen. Nach einem terminalen Ergebnis wird
der Fall-Query invalidiert.

### Verifikation und verbleibende Grenze

Der reale 294-Sekunden-Lauf belegt die zuvor zu kurze Grenze; die neue Konstante deckt
ihn mit deutlichem Abstand ab. Frontend-Test, Typprüfung und Produktions-Build
bestanden. Ein Browserfenster, das geschlossen oder neu geladen wird, kann den
laufenden In-Memory-Poll nicht fortsetzen; der Backendlauf und seine lokalen
Artefakte laufen davon unabhängig weiter.

# Optional entdeckte Shoplinks machen einen vollständig erfassten Pflichtumfang unvollständig

### Symptom

Im ersten Decathlon-Vergleich war die einzige verbindliche Prüf-URL erfolgreich als
Seite 001 erfasst. Der Lauf endete dennoch mit `pruefung_unvollstaendig`, weil unter
anderem automatisch entdeckte Produkt-, Warenkorb- und Hilfe-Links Cloudflare-,
CAPTCHA- oder robots-Hinweise lieferten.

### Ursache und Diagnose

Die Warteschlange kennzeichnete jeden Sitemap- und Navigationsfund als
`required_by_case_profile=True`. Damit wurden automatisch gefundene Pfade so streng
behandelt wie die vom Menschen ausdrücklich gespeicherten Prüf-URLs. Die Coverage des
realen Laufs zeigte 45 erfasste Seiten, die vollständig erfasste Pflicht-URL und
zahlreiche blockierte, aber nicht vom Fallprofil gewählte Shopseiten.

### Lösung

Nur `source_url` und die ausdrücklich gespeicherten `target_urls` bleiben
Pflichtziele. Sitemap- und Linkfunde sind weiterhin Bestandteil der begrenzten
Wanderungssuche und werden mit URL, Quelle und Fehlergrund in `skipped_urls`
dokumentiert; ihr einzelner Ausfall entwertet den ausdrücklich definierten
Prüfumfang aber nicht mehr. Ein unerreichbares Pflichtziel bleibt unverändert ein
unvollständiger Lauf.

### Verifikation und verbleibende Grenze

Backendtests prüfen nun beide Seiten: Ein blockierter optionaler Shoplink lässt ein
vollständig erfasstes Profil erfolgreich, ein blockierter ausdrücklich eingetragener
AGB-Pfad bleibt `pruefung_unvollstaendig`. Alle zwölf Domainmonitor-Tests bestanden.
Beim unmittelbaren Live-Wiederholungslauf blockierte Cloudflare inzwischen gerade die
verbindliche Decathlon-Fundstelle; dieser Lauf wurde deshalb korrekt in 2,186 Sekunden
als unvollständig dokumentiert und nicht umgangen. Eine spätere Wiederholung nach
Abkühlung oder eine manuelle Prüfung bleibt für diesen externen Schutz erforderlich.

# Aktueller BeweisLab-Scan überschreibt den Webarchiv-Ausgangsbeweis

### Symptom

Wurde nach einem archivierten Ausgangsbeweis eine aktuelle URL im BeweisLab erfasst
und demselben Fall zugeordnet, ersetzte der neue Lauf still den vorhandenen
Ausgangsbeweis. Ein Vergleich zwischen altem und aktuellem Stand fand nicht statt.

### Ursache und Diagnose

Die BeweisLab-Schaltfläche rief unabhängig vom Zustand des Falls immer den
`baseline-evidence`-Endpunkt auf. Repository und API erlaubten das erneute Schreiben
von `baseline_evidence`, obwohl die UI den Fall bereits als „Ausgangsbeweis
vorhanden“ kennzeichnete.

### Lösung

Ein vorhandener Ausgangsbeweis ist nun unveränderlich; ein erneuter Attach-Versuch
endet mit HTTP 409. Für aktuelle BeweisLab-Pakete gibt es einen getrennten,
manifestgeprüften und gleich-domainigen Vergleichsendpunkt. Er vergleicht den
normalisierten Haupttext, speichert nur Beweis-IDs und Hashes als aktuelle
Beweiskettenstufe und liefert bei Abweichung `technische_aenderung_erkannt`. Die UI
wechselt dann auf „Mit Ausgangsbeweis vergleichen“ und übergibt eine einmalige,
versionierte Benachrichtigung an die Hinweise-Seite.

### Verifikation und verbleibende Grenze

Repository-, API- und Frontendtests prüfen Überschreibschutz, Abweichung,
Unverändertheit, Selbstvergleich und die sichere Übergabe der klickbaren Meldung.
Der Vergleich ist ausdrücklich rein technisch und keine Aussage zur juristischen
Kerngleichheit. Er vergleicht den bevorzugten Haupt-/AGB-Text der beiden vollständigen
Beweispakete; Screenshots, WARC und weitere Unterseiten bleiben separat gehasht im
jeweiligen Paket erhalten.

# Schutz- oder 404-Aufnahme löst fälschlich eine Änderungsbenachrichtigung aus

### Symptom

Beim realen Decathlon-Demolauf war die angefragte AGB-Seite durch Cloudflare
begrenzt. Der Rechtstext-Fallback speicherte zusätzlich eine erreichbare
Datenschutzseite und eine nur teilweise erfasste 404-Seite als AGB-Rolle. Der
anschließende technische Vergleich meldete dennoch
`technische_aenderung_erkannt` und zeigte das klickbare Änderungsbanner.

### Ursache und Diagnose

Der Vergleich prüfte bisher nur, ob beide bevorzugten Dokumentrollen Text und
unterschiedliche Hashes enthielten. Die bereits im Beweispaket dokumentierte
`capture_completeness` des aktuellen Gesamtstands und der gewählten Rolle wurde
nicht in die Statusentscheidung übernommen. Dadurch wurde der Text einer
Schutz-/404-Aufnahme wie ein vollständiger aktueller AGB-Stand behandelt.

### Lösung

Die manifestgeprüfte Vergleichsquelle übernimmt nun die Vollständigkeit des
Gesamtpakets und jeder Dokumentrolle. Ist der aktuelle Lauf
`durch_seitenschutz_begrenzt` oder die bevorzugte Haupt-/AGB-Rolle nur
`teilweise_erfasst`, wird der Vergleich deterministisch als
`pruefung_unvollstaendig` gespeichert. Dieser Status löst keine
Änderungsbenachrichtigung aus.

### Verifikation und verbleibende Grenze

Ein API-Test deckt vollständig geänderte, unveränderte und schutzbedingt
unvollständige Vergleichspakete ab. Der reale Decathlon-Lauf wurde nach dem Fix mit
demselben Paket erneut verglichen und korrekt als `pruefung_unvollstaendig`
klassifiziert. Solange Decathlon die verbindliche AGB-URL für den transparenten
Projektbrowser blockiert, ist diese Live-Demo extern begrenzt; die Anwendung umgeht
den Schutz nicht und stellt den Lauf nicht als belastbaren Änderungsbeleg dar.

# Hetzner-Release enthält das neue UE-Beispielregister nicht

### Symptom

Ein nach dem bisherigen Hetzner-Runbook erzeugtes Release enthält zwar
`muclegal/llm/tenor_examples.py`, aber nicht die zur Laufzeit geladene Datei
`reference/ue_examples.json`. Die Tenorhilfe würde deshalb beim Laden oder Auswählen
der verifizierten UE-Beispiele mit einem nicht lesbaren Beispielregister scheitern.

### Ursache und Diagnose

Der explizite `git archive`-Dateisatz im Runbook wurde vor Einführung des
versionierten UE-Referenzkorpus festgelegt und umfasste das Verzeichnis `reference`
nicht. Der lokale Archivinhalt ließ sich mit `tar -tf` prüfen; dort fehlte die von
`UE_EXAMPLE_SOURCE_PATH` erwartete Datei.

### Lösung

Das Runbook nimmt `reference/ue_examples.json` nun ausdrücklich in jedes Release-
Archiv auf. Das übrige `reference`-Verzeichnis wird weiterhin nicht pauschal
ausgerollt. Dadurch bleibt das Release klein und enthält genau die zusätzlich
benötigte Laufzeitdatei, aber keine sonstigen Arbeitsdokumente.

### Verifikation und verbleibende Grenze

Vor dem Upload werden Archivinhalt und Ausschlussmuster geprüft. Die serverseitige
Releasevorbereitung muss zusätzlich die Tenortests ausführen oder mindestens das
Register mit `load_ue_examples()` laden. Künftige neue Laufzeitdateien außerhalb der
bisher archivierten Pfade müssen weiterhin bewusst in den Release-Dateisatz
aufgenommen werden.

# Verschachtelte oder verzögert geladene Rechtstextabschnitte fehlen im Beweis

### Symptom

Nach der automatischen Rechtstexterweiterung konnten innere `details`-Abschnitte,
inaktive Tabs oder erst verzögert nachgeladene Klauseln im normalisierten Text und
im Druckbeweis fehlen. Bei mehr als 100 zulässigen Bedienelementen konnte die
Abdeckung außerdem fälschlich als vollständig erscheinen. Bereits vollständig
geöffnete Decathlon-Akkordeons wurden im Wayback-Lauf sogar erneut angeklickt und
dadurch für den Hauptscreenshot geschlossen.

### Ursache und Diagnose

Die vorab ermittelten Playwright-Locators waren an die laufende Position in einer
dynamischen Selektorliste gebunden. Sobald ein äußerer Abschnitt geöffnet wurde,
verschob sich diese Liste; ein späterer Locator zeigte dadurch auf ein anderes
Element. Zusätzlich war die Wartezeit nach jedem Klick fest auf 250 Millisekunden
begrenzt und die auf 100 Treffer gekappte Suche erkannte keinen 101. Treffer. Eine
bloße CSS-Klasse mit `accordion` galt außerdem auch bei `aria-expanded="true"` als
Öffnungskandidat.
`interactions.json` machte den Locator-Fehler sichtbar: Die gespeicherte Struktur
war eine verschachtelte Summary, der tatsächlich gelesene Zieltext aber ein Tab.

### Lösung

Zulässige Rechtstext-Steuerelemente werden vor dem ersten Klick als stabile
DOM-Handles festgehalten. Nach jedem Klick wird bis zu zwei Sekunden auf einen
stabilen sichtbaren Inhalt gewartet. Die Suche prüft gezielt auf einen weiteren
Treffer jenseits des Limits und kennzeichnet die Erweiterung dann als partiell,
statt Vollständigkeit zu behaupten. Eine Akkordeon-/Disclosure-Klasse genügt nur
noch, wenn das zugeordnete Inhaltsziel tatsächlich verborgen ist; bereits offene
Abschnitte bleiben unangetastet.

### Verifikation und verbleibende Grenze

Die Chromium-Regressionsmatrix deckt verschachtelte `details`, ARIA-Akkordeons,
inaktive Tabs, 700 Millisekunden verzögerten Inhalt, irreführende externe
Navigation, bereits offene Akkordeons und das Erweiterungslimit ab. Es werden
weiterhin nur deterministisch als Rechtstext-Steuerung klassifizierte Elemente im
Rechtstextcontainer geöffnet, höchstens 100 pro Seite. Externe Navigation wird
nicht ausgelöst, und Inhalte, die erst nach mehr als zwei Sekunden erscheinen,
werden als unvollständige Erweiterung erkennbar statt unbegrenzt abgewartet.

# Nummerierte AGB-Klausel wird in der Tenormaske nicht als Wortlaut erkannt

### Symptom

Eine vollständig eingefügte Klausel wie `Abs. 14.5 Jegliche Ansprüche ...` wurde
in der Fallgruppe „AGB-Klausel“ mit „vollständiger wörtlicher Klauseltext fehlt“
zurückgewiesen, wenn sie weder in Anführungszeichen stand noch ausdrücklich mit
`Klausel:` eingeleitet wurde. Unabhängig davon konnte ein strukturell gültiger
Modelloutput mit `nicht_umfasst: []` als HTTP-502-Fehler enden.

### Ursache und Diagnose

Erkennung und Extraktion akzeptierten ausschließlich Anführungszeichen oder den
Marker `Klausel:`. Die sichtbare Absatznummer aus dem Vertragsdokument war noch
kein deterministisches Erkennungsmerkmal. Beim zweiten Fehler erlaubte das
Modell-JSON-Schema eine leere Abgrenzungsliste, während der nachgelagerte Validator
sie im Widerspruch dazu verbot.

### Lösung

Ast C erkennt nun nummerierte Klauselanfänge wie `Abs. 14.5`, `Ziffer 14.5`,
`Nr. 14.5`, `§ 14` und `14.5.`. Der Wortlaut reicht bis zu einem folgenden,
eindeutig bezeichneten Metadatenblock wie `Adressatenkreis:` oder
`Rechtsgrundlagen:`. Die vorangestellte Gliederungsnummer wird dabei als Fundstellen-
bezeichnung vom eigentlichen Klauselwortlaut getrennt. Die Wortlautprüfung bleibt
erhalten und normalisiert nur Leerraum, nicht den Inhalt. `nicht_umfasst` darf leer sein; die Oberfläche weist
dann sichtbar darauf hin, dass keine Abgrenzung belegt ist, statt eine zu erfinden.

### Verifikation und verbleibende Grenze

Unit- und API-Regressionstests verwenden die Eingabe aus der gemeldeten Maske und
prüfen, dass der vollständige Klauselwortlaut übernommen, der anschließende
Adressatenhinweis aber nicht zum Klauselwortlaut gemacht wird. Eine bloße
Paraphrase bleibt unzulässig. Nicht nummerierte Klauseltexte müssen weiterhin in
Anführungszeichen stehen oder mit `Klausel:` gekennzeichnet werden; dadurch wird
nicht beliebiger Beschreibungstext als wörtliche Vertragsklausel behandelt.

# Hetzner-Release fehlt lokaler Kerngleichheits-Kalibrierungskontext

### Symptom

Der lokal und in Tests funktionierende Kerngleichheitscheck würde nach einem
Hetzner-Update beim Aufbau der `wissensbasis` mit `FileNotFoundError` abbrechen.
Das Release-Archiv enthielt die neue Laufzeitdatei
`reference/kerngleichheit_anonyme_stimmen_2026-08-25.json` nicht.

### Ursache und Diagnose

Das Deployment erzeugt absichtlich ein eng begrenztes Archiv aus explizit genannten
Git-Pfaden. Nach Einführung des lokalen Kalibrierungsdatensatzes blieb die Pfadliste
im Hetzner-Runbook unverändert. Ein Vergleich der von
`muclegal/llm/monitor_knowledge.py` gelesenen Dateien mit `tar -tf` zeigte die
Lücke vor der Serveraktivierung.

### Lösung

Die versionierte JSON-Datei wird im `git archive`-Aufruf ausdrücklich aufgenommen.
Der Loader prüft den SHA-256 nach einer expliziten LF-Kanonisierung, weil
`git archive` auf dem Windows-Deploymenthost Textdateien mit CRLF exportieren kann.
Der Release bleibt vollständig aus dem gepushten Commit reproduzierbar; Drive wird
zur Laufzeit nicht kontaktiert.

### Verifikation und verbleibende Grenze

Vor Aktivierung wird mit `tar -tf` und einem Python-Import aus dem entpackten
Release geprüft, dass der Snapshot vorhanden ist und sein kanonisierter SHA-256 dem
im Code fixierten Wert entspricht. Künftige neue Laufzeitdateien unter `reference/` müssen
weiterhin bewusst in die Allowlist aufgenommen werden; der enge Archivumfang bleibt
als Schutz gegen versehentliche Geheimnis- oder Artefaktuploads bestehen.

# Gesamtvertrag wird fälschlich als ausgewählte AGB-Klausel behandelt

### Symptom

Nach dem Upload eines längeren Vertrags und der Auswahl von Ast C meldete die
Tenorhilfe, es gebe keine weitere tenorbezogene Sachverhaltsfrage. Die anschließende
Erzeugung scheiterte dennoch mit „Der vollständige Klauselwortlaut wurde nicht
wörtlich übernommen.“ Bei gekürzten Dokumenten behauptete die Dateizeile außerdem
pauschal, alle Seiten seien im Tenor berücksichtigt.

### Ursache und Diagnose

Die Rückfragelogik suchte im gesamten extrahierten PDF-Text nach beliebigen
Anführungszeichen oder dem Wort `Klausel`. Produktbezeichnungen in typografischen
Anführungszeichen konnten dadurch über mehrere Textabschnitte hinweg als vermeintlicher
Klauselwortlaut erkannt werden. Nummerierte Abschnitte und Wörter wie `Link` oder
`Button` im Vertrag beziehungsweise in einer enthaltenen Datenschutzerklärung lösten
zusätzlich eine falsche Ast-Mehrdeutigkeit aus. Die PDF-Extraktion war korrekt auf
40.000 Zeichen begrenzt, die Oberfläche zeigte aber nur die Gesamtseitenzahl statt
der tatsächlich textlich erfassten Seiten.

### Lösung

Der Inhalt eines hochgeladenen Gesamtvertrags bleibt Kontext, gilt aber nicht mehr
automatisch als Auswahl der konkret beanstandeten Klausel. Ast C fragt bei fehlender
Auswahl deterministisch nach dem vollständigen wortwörtlichen Klauseltext. Die Antwort
wird mit ihrer Topic-ID getrennt vom unvertrauten Dokumentinhalt in den Modellkontext
übernommen und vom nachgelagerten Validator weiterhin wortgleich verlangt. Paarige
deutsche und gerade Anführungszeichen werden nun getrennt erkannt, sodass kurze
Produktnamen keine übergreifenden Scheinklauseln mehr bilden. Klauselantworten dürfen
bis zu 12.000 Zeichen umfassen. Die Dateizeile nennt bei Teiltexten die tatsächlich
erfassten Seiten, beispielsweise `Text aus 8 von 11 Seiten berücksichtigt · gekürzt`.

### Verifikation und verbleibende Grenze

Regressionstests bilden einen mehrteiligen Vertrag mit Produktnamen, Links,
nummerierten Datenschutzabschnitten und gekürztem Dokumenttext nach. Sie prüfen die
deterministische Wortlautfrage, die Bevorzugung der ausdrücklichen Antwort gegenüber
dem PDF-Rohtext und die präzise Seitenanzeige. Der Gesamtvertrag wird weiterhin als
unvertraute Quelle an das Modell übergeben; die fachliche Auswahl der beanstandeten
Klausel trifft die Juristin. Eine im PDF enthaltene Klausel wird nicht automatisch
ausgewählt oder juristisch bewertet.

# Optionale Metadaten blockieren die UE-Erzeugung

### Symptom

Die Minimalansicht brach vor dem Modellaufruf mit „Für einen bestimmten UE-Entwurf
fehlt die genaue Bezeichnung des Schuldners“ ab. Auch Adressatenkreis, Fundstelle,
Rechtsgrundlagen, URL oder Anlagenbezeichnung konnten einen inhaltlich bereits
formulierbaren Entwurf verhindern oder unnötige Rückfragen auslösen.

### Ursache und Diagnose

Frontend, API-Schema, Eingabeaufbereitung und Vollständigkeitsvalidator behandelten
die Schuldnerbezeichnung gleichzeitig als technische und fachliche Pflichtangabe.
Weitere für die spätere Prüfung hilfreiche Metadaten waren mit denjenigen Tatsachen
vermischt, ohne die der eigentliche Verbotskern nicht bestimmt formuliert werden kann.
Die Archivübernahme wiederholte denselben Schuldnerblocker.

### Lösung

Schuldnerbezeichnung, Adressatenkreis, Fundstelle und Rechtsgrundlagen sind in der
Minimalansicht und in der Maske nun optional; eine leere Fall-ID wird intern als
`TENOR-ENTWURF` geführt. Bei Ast A ist auch der Anwendungsbereich nur eine
Empfehlung; bei Ast B gelten URL beziehungsweise Bedienoberfläche und Anlagebezug
ebenfalls als ergänzbar. Fehlen solche Angaben, wird trotzdem erzeugt und genau ein
dezenter Hinweis mit den empfohlenen Ergänzungen ausgegeben. Intern wird für
technische Pflichtfelder `Nicht angegeben` verwendet, ohne dies als Tatsache in den
UE-Text einzubauen. Auch die Archivübernahme bleibt möglich.

Zwingend bleiben nur der eigentliche Verbotskern: eine hinreichende Handlungsbeschreibung
bei Ast A, Bedienfolge und sichtbare Beschriftungen bei Ast B sowie der vollständige
wörtliche Klauseltext bei Ast C. Unbekannte optionale Angaben dürfen vom Modell nicht
erfunden werden.

### Verifikation und verbleibende Grenze

API- und Generatortests erzeugen einen Ast-A-Entwurf ohne Schuldner, Adressatenkreis,
Fundstelle, Rechtsgrundlagen oder Anwendungsbereich und prüfen den zusammengefassten
Hinweis. Ein Rückfragetest stellt sicher, dass Schuldner und Adressatenkreis nicht
mehr abgefragt werden. Die menschliche juristische Freigabe bleibt für jeden Entwurf
erforderlich; der Hinweis ersetzt keine fachliche Ergänzung vor Verwendung.

# UE-Korrekturmodus schlägt gerichtliche Urteilsformel vor

### Symptom

Nach der Übernahme eines UE-Entwurfs bot die Tab-Autovervollständigung als nächsten
Baustein „Die Beklagte wird verurteilt, es zu unterlassen“ an.

### Ursache und Diagnose

Der lokale Korrekturmodus bezog seine Vorschläge weiterhin aus dem historischen
Urteilstenorregister und begann dort mit Verpflichtungsformel und Ordnungsmittelandrohung.
Der neue UE-Generator selbst war davon nicht betroffen.

### Lösung und Verifikation

Die Autovervollständigung überspringt nun die Segmente `verpflichtungsformel` und
`ordnungsmittelandrohung`. Ein Frontendtest weist gerichtliche Verurteilungs- und
Ordnungsmittelformeln in Vorschlägen zurück. Die übrigen sachverhaltsbezogenen
Bausteine des Korrekturmodus bleiben verfügbar.

# Download lieferte ein nachträglich beschädigtes Beweispaket aus

### Symptom

Eine nach der Erfassung veränderte oder beschädigte manifestierte Datei konnte über
den ZIP-Endpunkt weiterhin mit HTTP 200 als reguläres Beweispaket heruntergeladen
werden. Die enthaltene Manifestprüfung hätte die Abweichung zwar nachträglich gezeigt,
der Download selbst wies aber nicht auf den Integritätsbruch hin.

### Ursache und Diagnose

`CaseArchive.build_download` prüfte nur, ob die in `case.json` genannten Artefaktpfade
innerhalb des Fallverzeichnisses lagen. Vor dem Verpacken wurde weder `manifest.json`
gegen die aktuellen Dateien noch dessen Hash gegen `case.json` und
`manifest.sha256` geprüft. `verify_manifest` berücksichtigte außerdem deklarierte
Dateigrößen, Manifeststruktur und doppelte Einträge nicht und konnte bei einer
fehlerhaften Artefaktliste mit einer Ausnahme abbrechen.

### Lösung

Der Download wird nun gesperrt, wenn Manifest, Digestdatei oder der in `case.json`
verankerte Manifest-Hash fehlen beziehungsweise abweichen. Die Manifestprüfung
validiert Version, Hashalgorithmus, SHA-256-Felder, Dateigrößen, eindeutige Labels und
Pfade sowie die Hashkette und liefert Strukturfehler als `valid=False` zurück. Das ZIP
wird über eine fallbezogene temporäre Datei atomar ersetzt; aufgelöste Dateipfade
dürfen das Fallverzeichnis auch über Verknüpfungen nicht verlassen.

### Verifikation und verbleibende Grenze

Regressionstests verändern ein bereits manifestiertes Roh-HTML, manipulieren
Dateigröße und Digestdatei und übergeben ein strukturell ungültiges Manifest. Der
Download antwortet in diesen Fällen mit HTTP 409, während ein unverändertes Paket
weiterhin als gültiges ZIP ausgeliefert wird. Die Prüfung schützt den lokalen
Downloadzeitpunkt; gegen eine gleichzeitige Änderung exakt zwischen Verifikation und
Dateilesen ist keine systemweite Dateisperre eingerichtet. Der isolierte lokale
Demo-Store und die atomare ZIP-Erzeugung begrenzen dieses verbleibende Risiko.

# Archiv-Link im direkt gestarteten BeweisLab führte auf eine FastAPI-404-Seite

### Symptom

Im unter `http://127.0.0.1:8000/beweis-labor` geöffneten BeweisLab führte der
Navigationspunkt „Archiv“ auf `http://127.0.0.1:8000/archiv` und antwortete mit
HTTP 404, obwohl das Archiv im lokal laufenden React-Frontend vorhanden war.

### Ursache und Diagnose

Die BeweisLab-Seitenleiste verwendete für alle Ziele relative Links. Das ist auf der
gemeinsamen Deployment-URL korrekt, weil dort der Reverse Proxy `/archiv` an das
Frontend weitergibt. Beim ausdrücklich unterstützten direkten lokalen FastAPI-Aufruf
blieb der Browser jedoch auf Port 8000. FastAPI stellt nur `/` und `/beweis-labor`
als HTML-Seiten bereit; das React-Archiv antwortete gleichzeitig unter
`http://127.0.0.1:4173/archiv` mit HTTP 200.

### Lösung

Das BeweisLab kennzeichnet die vier React-Navigationsziele jetzt ausdrücklich und
setzt deren Origin ausschließlich bei `127.0.0.1` beziehungsweise `localhost` und
einem direkten Backend-Aufruf auf Port 4173. Auf der gemeinsamen Produktions-URL
bleiben die relativen Links unverändert. Zusätzlich besitzt FastAPI lokale
307-Weiterleitungen für `/hinweise`, `/archiv`, `/neu` und `/tenorhilfe`; sie dienen
als Fallback für direkt eingegebene Backend-URLs und erhalten Query-Parameter.

### Verifikation und verbleibende Grenze

Der Regressionstest prüft alle vier Weiterleitungen sowie einen Archiv-Query-String.
Im Browser führte der Klick aus dem laufenden BeweisLab zu
`http://127.0.0.1:4173/archiv`; Überschrift, Fälle-/Tenore-Reiter und zwei vorhandene
Fälle waren sichtbar. Die Browserkonsole meldete keine Fehler oder Warnungen. Lokal
muss das dokumentierte React-Frontend auf Port 4173 laufen, damit dessen Seiten
verfügbar sind; das reine technische BeweisLab auf Port 8000 bleibt unabhängig davon
weiter nutzbar.

# Decathlon-Beweisvergleich meldet eine Änderung, zeigt aber keinen Unterschied

### Symptom

Nach der manuellen Zuordnung eines aktuellen BeweisLab-Pakets zu einem bereits
vorhandenen Webarchiv-Ausgangsbeweis wurde zwar eine technische Änderung gespeichert.
Die Benachrichtigung führte lokal jedoch auf den nicht verwendeten Port `8080` oder
öffnete nur eine allgemeine Beweiskette mit Paket-IDs und Hashes. Der konkrete
Vorher-/Nachher-Unterschied und die ausgeführten Vergleichsschritte waren nicht
sichtbar.

### Ursache und Diagnose

Der lokale Übergabepfad der BeweisLab-Vorlage stammte aus einer älteren
Frontendkonfiguration und war nicht auf den verbindlichen Vite-Port `4173`
umgestellt worden. Der Backendvergleich speicherte außerdem nur Text-Hashes. Aus
abweichenden Hashes ließ sich zwar ein technischer Status ableiten, aber keine für
die Demo nachvollziehbare Fundstelle anzeigen. Der Klickpfad wartete pauschal 400 ms;
bei einem noch laufenden Fallabruf konnte das Ziel zu diesem Zeitpunkt fehlen.

### Lösung

Die lokale Übergabe verwendet jetzt denselben, zentral in der BeweisLab-Vorlage
ermittelten Frontend-Ursprung auf Port `4173`; auf einer gemeinsamen Deployment-URL
bleibt der Pfad relativ. Bei einem vollständigen, manifestgeprüften Vergleich erzeugt
das Backend zusätzlich höchstens sechs begrenzte wortbasierte Textausschnitte mit
`Vorher · Webarchiv` und `Aktueller Stand`. Methode, Zusammenfassung und Ausschnitte
werden schema-validiert zusammen mit dem rein technischen Vergleich gespeichert.
Die Hinweise-Seite zeigt ein dauerhaftes Pop-up `Differenz erkannt`; dessen Klick
wartet bei Bedarf auf die geladenen Falldaten, öffnet den Fall und fokussiert direkt
die Vergleichsstelle. Dort dokumentiert `Was wurde gemacht?` die Manifestprüfung,
die verglichene Dokumentrolle und die technische Grenze ohne juristische Aussage.

### Verifikation und verbleibende Grenze

Backendtests prüfen geänderte, unveränderte und unvollständige Pakete sowie die
gespeicherten Ausschnitte. Frontendtests prüfen die exakte Pop-up-Beschriftung;
TypeScript-Typprüfung und gezieltes ESLint bestanden. Ein isolierter synthetischer
Decathlon-Demo-Store wurde im Browser vollständig durchlaufen: aktuelles Paket
auswählen, dem vorhandenen Webarchiv-Ausgangsbeweis zuordnen, Pop-up anklicken und
drei sichtbare Vorher-/Nachher-Ausschnitte öffnen; die Browserkonsole blieb ohne
Fehler. Der echte reguläre Abruf sowohl des bisherigen als auch des aktuellen
Decathlon-AGB-Pfads lieferte am 25.08.2026 eine Cloudflare-Blockseite und wurde
korrekt als unvollständiger Schutzbefund gespeichert. Dieser Schutz wird nicht
umgangen und löst bewusst keine scheinbar belastbare Änderungsbenachrichtigung aus.

Damit die Bühnenvorführung nicht vom externen Schutzstatus abhängt, besitzt das
lokale BeweisLab zusätzlich den Button `Decathlon-Demo vorbereiten`. Der zugehörige
POST-Endpunkt ist ausschließlich für `127.0.0.1`, `localhost` und den Testhost
freigeschaltet. Er erzeugt idempotent zwei manifestgeprüfte lokale Pakete. Bei einem
leeren Store wird zuerst der Webarchiv-Demo-Ausgangsstand geöffnet und muss weiterhin
manuell als Ausgangsbeweis zugeordnet werden; anschließend führt ein Link zum
synthetischen aktuellen Stand. Ist – wie im bestehenden Decathlon-Demo-Store – schon
ein echter Webarchiv-Ausgangsbeweis vorhanden, öffnet der Button direkt den aktuellen
synthetischen Demo-Snapshot zur manuellen Zuordnung und zum Vergleich.

Die wiederholten sichtbaren Disclaimer im BeweisLab, im Pop-up, in der
Vergleichsansicht und in der erzeugten Bildvorschau wurden auf Nutzerwunsch entfernt.
Die technische Trennung bleibt über `demo_only`, `demo_notice`, Manifest und
Erfassungstransparenz innerhalb der gespeicherten Beweiskette erhalten; diese
Metadaten werden nicht mehr als Warnbanner in der Oberfläche wiederholt. Der reale
lokale Browser-Smoke-Test startete den Preset
aus dem laufenden BeweisLab, öffnete `demo-decathlon-aktuell`, verglich ihn manuell
mit dem vorhandenen manifestgeprüften Webarchiv-Ausgangsbeweis, zeigte das Pop-up
`Differenz erkannt` und fokussierte nach dem Klick die sechs begrenzten
Vorher-/Nachher-Ausschnitte sowie `Was wurde gemacht?`. Die Browserkonsole enthielt
keine Fehler oder Warnungen.

Auf der zeitlich begrenzten Hetzner-Demo bleibt der Endpoint ebenfalls nur über die
geschützte Frontend-Strecke verwendbar: Caddy verlangt Basic Auth, das Vite-Frontend
leitet `/api` mit geändertem Origin und internem Loopback-Host an FastAPI weiter, und
FastAPI selbst bleibt ausschließlich an `127.0.0.1:8000` gebunden. Eine direkte
öffentliche Freischaltung des Demo-Endpoints oder des Backend-Ports wurde nicht
eingeführt.

# Rechtstextansicht bleibt zugeklappt und Länderwahl gilt als Akkordeon

### Symptom

Nach einem erfolgreichen Scan waren die vollständig zusammengeführten AGB- und
Datenschutz-Druckfassungen nur unter den technischen Details erreichbar. Die direkt
sichtbaren Schaltflächen öffneten stattdessen den letzten Website-Screenshot, auf dem
bei wechselseitig ausschließenden Akkordeons naturgemäß nur ein Abschnitt offen sein
kann. Im Hetzner-Paket für `mirageperfume.com` meldete die Expansionszusammenfassung
außerdem `complete: true`, obwohl `remaining_collapsed_controls: 1` gespeichert war.

### Ursache und Diagnose

Wenn eine Rechtstextseite kein semantisches `main`, `article` oder `[role=main]`
enthielt, fiel die Suche auf den gesamten `body` zurück. Shopify-Seiten bilden ihre
Fußzeile teilweise als `div.footer` statt als echtes `footer`-Element ab. Deshalb
wurden die dortigen Schalter `Deutschland (EUR €)` und `Deutsch` mit
`aria-expanded=false` irrtümlich als Rechtstext-Akkordeons behandelt. Unabhängig
davon berücksichtigte die Berechnung von `complete` die nach allen Klicks noch
vorhandenen geschlossenen Controls nicht. Die bereits korrekt erzeugte abgeleitete
Druckfassung war in der Oberfläche fachlich zu weit hinten einsortiert.

### Lösung

Die Akkordeonsuche schließt jetzt neben semantischer Navigation auch typische
Header-, Footer- und Lokalisierungscontainer aus. `complete` ist nur noch wahr, wenn
nach dem Scan tatsächlich kein zulässiges geschlossenes Control mehr vorhanden ist.
Bei exklusiven Akkordeons bleiben alle nacheinander sichtbar gemachten Texte im
normalisierten Text und in der abgeleiteten Druckfassung erhalten; der visuelle
Browserzustand wird aber ehrlich als teilweise erfasst gekennzeichnet, wenn nicht
alle Abschnitte gleichzeitig offen bleiben.

Im BeweisLab heißen die beiden direkten Einstiege jetzt `AGB aufgeklappt` und
`Datenschutz aufgeklappt`. Sie öffnen die automatisch erzeugte, ausdrücklich als
abgeleitet gekennzeichnete Druckfassung. Nach einem Scan wird die AGB-Druckfassung
bevorzugt automatisch angezeigt. Die unveränderten Website-Screenshots bleiben
getrennt im Menü `Screenshots` erhalten.

### Verifikation und verbleibende Grenze

Eine Chromium-Regression prüft ein exklusives Zwei-Klausel-Akkordeon: Beide Texte
liegen im Paket, ein verbliebenes geschlossenes Control führt aber korrekt zu
`teilweise_erfasst`. Eine zweite Regression prüft eine Shopify-artige
`div.footer`-Länderwahl und bestätigt, dass keine Rechtstextinteraktion protokolliert
wird. Im lokalen Browser öffnete das bestehende manifestierte Decathlon-Paket direkt
`Druckfassung · AGB-Seite`; der Klick auf `Datenschutz aufgeklappt` wechselte zur
Datenschutz-Druckfassung. Browserkonsole und Warnungsprotokoll blieben leer.

Eine Cloudflare-Schutzseite enthält keine erreichbaren Rechtstext-Akkordeons. Sie
kann daher weiterhin nicht aufgeklappt werden und bleibt sichtbar als
`durch_seitenschutz_begrenzt` klassifiziert; die Änderung umgeht keinen Seitenschutz.
# Grey-Mode-Beweispaket ließ sich keinem Fall zuordnen

### Symptom

Nach einer erfolgreichen technischen Erfassung im Grey Mode zeigte das BeweisLab zwar
das getrennt gekennzeichnete Paket, beendete die Fallauswahl aber sofort mit dem Hinweis,
dass Grey-Mode-Pakete nicht übernommen werden könnten. Ein direkter Aufruf des
Zuordnungs-Endpunkts endete ebenfalls mit HTTP 422.

### Ursache und Diagnose

Die Trennung zwischen technischer Grey-Mode-Erfassung und juristischer Modellanalyse war
zu weit umgesetzt: Sowohl das Browser-Frontend als auch `validated_case_evidence`
verboten jede Fallzuordnung. Eine Zuordnung und der bestehende manifestgeprüfte
wortbasierte Vergleich sind jedoch rein technische Metadatenoperationen und lösen keine
juristische KI-Analyse aus.

### Lösung

Technisch geeignete, manifestgültige Grey-Mode-Pakete dürfen jetzt einem Fall derselben
freigegebenen Domain als Ausgangsbeweis zugeordnet oder mit dessen Ausgangsbeweis
technisch verglichen werden. Ausgangsbeweis und Vergleich speichern die Grey-Mode-
Kennzeichnung dauerhaft. Die Oberfläche zeigt dafür auf Nutzerwunsch nur die unbeschriftete
Autorisierungscheckbox neben der URL und keine zusätzlichen Modushinweise. Die getrennte
Paketablage und die Sperre gegen juristische Modellaufrufe bleiben unverändert.

### Verifikation und verbleibende Grenze

Regressionstests ordnen ein Grey-Mode-Paket erfolgreich als Ausgangsbeweis zu und prüfen
die Kennzeichnung bei einem technischen Vergleich. Domain-, Manifest- und
Beweiseignungsprüfung gelten unverändert. Ein nicht technisch geeignetes Paket darf auch
im Grey Mode nicht als Ausgangsbeweis verwendet werden; die Zuordnung ist keine
juristische Bewertung und keine menschliche Freigabe eines Befunds.

# Netto-AGB blockieren den transparent gekennzeichneten BeweisLab-Abruf

### Symptom

Der reale BeweisLab-Lauf vom 26.08.2026 gegen
`https://www.netto-online.de/agb` endete mit einem Schutzbefund. Weder der
normalisierte AGB-Text noch ein AGB-Screenshot konnten als regulärer Beweis einem
Monitoringfall zugeordnet werden. Der direkte Abruf von `robots.txt`, der HTML-AGB
und der statischen AGB-PDF antwortete jeweils mit HTTP 403.

### Ursache und Diagnose

Netto beziehungsweise der vorgeschaltete Zugriffsschutz weist den transparenten
Projekt-User-Agent
`MucLegal-Monitor/0.1 (+https://github.com/Alebabo/MucLegal; public-page compliance monitor)`
ab. Derselbe HTTP-403-Stand wurde mit `Invoke-WebRequest`, im produktiven
BeweisLab und in einem separaten Chromium-Kontext mit dem Projekt-User-Agent
reproduziert. Ein normaler Chromium-Kontext ohne den zusätzlichen Projekt-Token
konnte die HTML-AGB dagegen laden. Damit ist die Ursache kein fehlender AGB-Pfad;
die öffentlich sichtbare Zieladresse `/agb` ist weiterhin korrekt.

### Lösung

Der Projekt-User-Agent wird nicht entfernt und der Seitenschutz nicht umgangen.
Der Netto-Fall wird deshalb nicht für den Live-Demo-Pfad verwendet. Als Ersatz dient
der Müller-Click-&-Collect-Fall: Seine aktuelle AGB-Seite ist mit dem transparenten
Projekt-User-Agent als HTML erreichbar. Der historische Ausgangsstand wird dabei
ausdrücklich als synthetische, aus dem veröffentlichten Urteil transkribierte
Demo-Referenz gekennzeichnet; als historische Fundstelle ist der Wayback-Stand vom
03.07.2025 (`https://web.archive.org/web/20250703135028/https://www.mueller.de/unternehmen/agb/`)
hinterlegt. Der aktuelle Stand wird weiterhin regulär live erfasst.

### Verifikation und verbleibende Grenze

Der Müller-API-Regressionstest bereitet den Fall idempotent vor und ordnet den
historischen Demo-Ausgangsbeweis einmalig zu. Ein realer Live-Lauf erfasst die
Müller-AGB vollständig als Rolle `agb`; der rollenreine technische Vergleich meldet
eine Änderung und erzeugt die bestehende anklickbare Differenzbenachrichtigung.
Ein aktueller Live-Beweis der Netto-AGB ist mit dem vorgeschriebenen transparenten
Projekt-User-Agent weiterhin nicht möglich. Der Netto-Schutzbefund bleibt korrekt
dokumentiert, ist aber nicht Teil des Demo-Ablaufs.

# Vorher-/Nachher-Klauseln sind in der Hinweise-Ansicht zu schmal

### Symptom

Beim Öffnen eines technischen Beweisvergleichs wurden `Vorher · Webarchiv` und
`Aktueller Stand` bereits auf kleinen Bildschirmbreiten nebeneinander dargestellt.
Die geöffnete Hinweiskarte blieb gleichzeitig auf `max-w-3xl` begrenzt. Längere
AGB-Klauseln liefen dadurch in zwei schmalen Spalten und waren nur schwer zu erfassen.

### Ursache und Lösung

Die Spaltenumschaltung orientierte sich mit `sm:grid-cols-2` nur an der gesamten
Viewportbreite, nicht an der tatsächlich nach Seitenleiste und Kartenabständen
verfügbaren Inhaltsbreite. Die Hinweise-Seite darf nun bis `max-w-6xl` wachsen;
geschlossene Hinweise bleiben zentriert auf `max-w-3xl`, nur der geöffnete Fall nutzt
die größere Breite. Der Klauselvergleich wechselt erst ab `xl` in zwei Spalten und
bleibt darunter als gut lesbare Vorher-/Nachher-Folge untereinander. Größere
Innenabstände, 15-Pixel-Text, höhere Zeilenhöhe und Wortumbruch verbessern die
Lesbarkeit zusätzlich.

### Verifikation und verbleibende Grenze

Ein Frontend-Regressionstest sichert breite geöffnete Karten, den späten
Zwei-Spalten-Breakpoint und die lesbare Klauseltypografie. Der Browser-Smoke-Test
prüft die geöffnete Müller-Differenzansicht auf Desktop- und schmaler Breite sowie
Konsole und horizontales Überlaufen. Auf sehr langen Klauseln bleibt die Anzeige
bewusst ausschnittsweise; die Zahl und Länge der Ausschnitte wird weiterhin im
Backend begrenzt.

# Resthinweise und Bildbanner überlagerten den reduzierten Demo-Ablauf

### Symptom

Unter den beiden Demo-Schaltflächen standen weiterhin längere Erläuterungssätze. Bei
einer autorisierten Erfassung wurde außerdem `AUTORISIERTE ERFASSUNG` nachträglich in
Screenshots, normalisierte Texte und die Rechtstext-Druckfassung eingebracht. Dadurch
wichen die abgeleiteten Inhalte sichtbar vom tatsächlich erfassten Stand ab.

### Ursache und Diagnose

Die Hinweise waren als feste `small`-Elemente im BeweisLab-Template hinterlegt. Der
Workflow rief vor der Manifestbildung zusätzlich `_mark_god_mode_bundle` auf; diese
Nachbearbeitung zeichnete einen Bildbanner ein, stellte dem normalisierten Text eine
Kopfzeile voran und fügte der Rechtstext-Druckfassung eine zusätzliche PDF-Seite hinzu.

### Lösung

Die beiden Hinweiszeilen und die zugehörige dynamische Müller-Statuszeile wurden entfernt.
Autorisierte Erfassungen verändern den erfassten Screenshot, den normalisierten Text und
die Rechtstext-Druckfassung nicht mehr. Die technische Trennung bleibt über den separaten
Speicherpfad, `case.json`, die Manifest-Notice und `god_mode_authorization.json` vollständig
erhalten.

### Verifikation und verbleibende Grenze

Regressionstests prüfen, dass die Hinweistexte nicht ausgeliefert werden und ein weißer
synthetischer Screenshot auch nach einer autorisierten Erfassung unverändert weiß bleibt.
Gleichzeitig müssen Manifest und Autorisierungsprotokoll die interne Kennzeichnung weiter
enthalten. Der technische PDF-Prüfbericht kann die Autorisierung weiterhin benennen; die
unveränderten Primär- und Rechtstextartefakte selbst tragen keinen eingebrannten Hinweis.

# `/fälle` in der Tenorschreibhilfe zeigte nur statische Fallback-Fälle

### Symptom

Obwohl im Backend bereits neue Monitoringfälle vorhanden waren, bot der Modus `/fälle`
der Tenorschreibhilfe ausschließlich die fünf statischen Lotto-Demofälle an. Archiv,
Dashboard und Hinweise zeigten dagegen die aktuellen Backendfälle.

### Ursache und Diagnose

Die drei übrigen Ansichten verwendeten bereits `useCaseViews()`. Die Tenorschreibhilfe
filterte weiterhin direkt die Konstante `lottoDemoCases` aus ihrer ersten Umsetzung und
war damit vollständig von `/api/v1/monitoring-cases` getrennt. Zusätzlich lieferte
`useCaseViews()` während des Ladens oder bei einem API-Fehler vorübergehend den Fallback,
obwohl noch gar nicht feststand, dass das Backend keine Fälle enthält.

### Lösung

Die Tenorschreibhilfe verwendet nun ebenfalls `useCaseViews()` und filtert dessen aktuelle
Fallliste. Die Lotto-Demos erscheinen nur nach einem erfolgreich geladenen, tatsächlich
leeren Backend. Während des Ladens und bei einem API-Fehler zeigt `/fälle` einen eigenen
Status statt irreführender Fallback-Daten.

### Verifikation und verbleibende Grenze

Ein Frontend-Regressionstest prüft die Suche in einer übergebenen aktuellen Fallliste.
TypeScript-Prüfung und Browser-End-to-End-Test müssen zusätzlich bestätigen, dass der
vorbereitete Müller-Fall in `/fälle` auswählbar ist und bis zur Tenorerstellung übernommen
wird. Die Auswahl lädt höchstens fünf Suchtreffer; durch Eingabe von Fall-ID, Domain oder
Titel bleibt jeder weitere Backendfall erreichbar.

# BeweisLab verließ die Seite unmittelbar nach einer Scan-Zuordnung

### Symptom

Erkannte ein Vergleich nach der Zuordnung eines Scans eine technische Differenz, wechselte
die Anwendung sofort vom BeweisLab zu `/hinweise`. Die Benachrichtigung erschien erst dort
und musste ein zweites Mal angeklickt werden, um den betroffenen Fall zu öffnen.

### Ursache und Diagnose

Der Erfolgszweig für `technische_aenderung_erkannt` rief unmittelbar die Übergabefunktion
mit `window.location.assign` auf. Im BeweisLab gab es keine eigene, persistente
Vergleichsbenachrichtigung; die Hinweise-Seite behandelte die Übergabe wiederum wie einen
neuen Monitoringhinweis.

### Lösung

Das BeweisLab zeigt die Differenz nun als dauerhaft sichtbare, anklickbare Benachrichtigung
und bleibt nach der Zuordnung auf derselben Seite. Erst der Klick auf die Benachrichtigung
übergibt die Fall-ID an `/hinweise`. Dort wird der passende Fall unmittelbar aufgeklappt
und zur Differenzansicht gescrollt, ohne eine zweite Benachrichtigung einzublenden.

### Verifikation und verbleibende Grenze

Regressionstests sichern das BeweisLab-Popup und die direkte Öffnung des übergebenen Falls.
Der Browser-Smoke-Test prüft zusätzlich, dass die URL nach der Zuordnung unverändert bleibt
und erst der Klick zu `/hinweise` wechselt. Wird die Benachrichtigung geschlossen, bleibt
der Vergleich gespeichert; der Fall ist weiterhin über die Hinweise-Navigation erreichbar.

# Decathlon-Demo verwendete zwei verkürzte Textkonstanten statt der festen Quellen

### Symptom

Der Decathlon-Demofall zeigte zwar eine Wayback-URL und einen aktuellen AGB-Pfad, erzeugte
beide Vergleichsstände intern jedoch nur aus zwei kurzen Textkonstanten. Damit stammte weder
der vollständige Altstand aus der archivierten Seite noch der vollständige neue Stand aus der
vom Nutzer bereitgestellten AGB-PDF.

### Ursache und Diagnose

`decathlon_demo.py` war ursprünglich als vollständig synthetischer, netzunabhängiger
Klickpfad angelegt. Die echte manifestierte Wayback-Erfassung vom 08.10.2024 war zwar im
lokalen Beweisbestand vorhanden, wurde aber nicht als feste Demoquelle eingebunden. Die neue
14-seitige AGB-PDF mit Stand 20.07.2026 war ebenfalls noch kein Repository-Asset.

### Lösung

Die Demo besitzt nun versionierte, feste Quellen: archiviertes HTML, normalisierter Text und
die daraus erzeugte Rechtstext-PDF des Wayback-Stands vom 08.10.2024 sowie die bytegenau
übernommene AGB-PDF vom 20.07.2026. Für den aktuellen Stand wird der Text seitenweise aus
der PDF extrahiert; die Original-PDF bleibt selbst manifestiertes Vergleichsartefakt und wird
im BeweisLab direkt angezeigt. Neue Paket-IDs verhindern, dass ältere verkürzte Demo-Pakete
unbemerkt weiterverwendet werden.

### Verifikation und verbleibende Grenze

Der Regressionstest prüft die beiden maßgeblichen Alt-Klauseln, die geänderten PDF-Klauseln,
14 PDF-Seiten, Byte- und SHA-256-Gleichheit der eingebetteten PDF, Quellenrevision,
Manifestprüfung, ZIP-Download und technische Differenzanzeige. Die Quellen sind für die Demo
eingefroren; sie behaupten keinen späteren Live-Seitenstand und werden nicht automatisch
aktualisiert.
