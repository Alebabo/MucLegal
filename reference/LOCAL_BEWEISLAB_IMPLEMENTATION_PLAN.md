# Umsetzungsplan: BeweisLab zuverlässig lokal betreiben

Stand: 20.08.2026  
Status: **zur Umsetzung durch den nächsten Agenten**  
Zieltermin für einen stabilen Hackathon-Stand: vor dem Feature-Freeze am 25.08.2026

## 1. Verbindliche Zielentscheidung

Das BeweisLab wird ausschließlich lokal betrieben. Erfassung, Browser, Beweisdateien,
Vorschauen und Downloads laufen auf einem lokalen Windows-Rechner unter
`http://127.0.0.1:8000/beweis-labor`.

Der Umsetzungsschnitt entfernt die frühere Hosting-Laufzeit vollständig aus Code,
Abhängigkeiten, Konfiguration und Dokumentation. Retention, Legal Hold, Falllöschung,
Löschzertifikate und Änderungen an Append-only-Triggern sind ausdrücklich zurückgestellt.

Der Folge-Agent soll nicht nur Einzelpatches für Temu oder IKEA ergänzen, sondern den
Erfassungsweg so umbauen, dass jeder Lauf reproduzierbar einen der folgenden Zustände liefert:

1. `vollstaendig_erfasst`: Rohantwort, gerendertes DOM, vollständiger Text und vollständige
   Bildserie sind vorhanden.
2. `teilweise_erfasst`: genau benannte Artefakte und Grenzen sind vorhanden.
3. `durch_seitenschutz_begrenzt`: Schutzart, angefragte URL, tatsächlich erfasste URL,
   Schutzbild und zulässige Ersatzquellen sind getrennt dokumentiert.
4. `technisch_fehlgeschlagen`: Fehlerphase und vorhandene Zwischenartefakte bleiben erhalten;
   der Lauf wird niemals irrtümlich als erfolgreiche Aufnahme dargestellt.

„Fehlerfrei“ bedeutet hier: kein stiller Datenverlust, keine weiße oder abgeschnittene Aufnahme
ohne Kennzeichnung, kein falscher Erfolgsstatus und ein deterministischer Fehlerdatensatz bei
externen Grenzen. Es bedeutet nicht, CAPTCHA, Login, Paywall oder Bot-Schutz zu umgehen.

## 2. Harte Grenzen

- `robots.txt` wird vor HTTP- **und** Browser-Abruf geprüft. Ist die Datei nicht
  erreichbar, lesbar oder eindeutig auswertbar, wird mit deutlich ausgewiesenem
  ungeprüftem Status und Disclaimer fortgefahren. Eine eindeutige Untersagung wird
  standardmäßig respektiert und nur auf ausdrückliche, fallbezogene Nutzeranweisung
  mit protokollierter Abweichung und Disclaimer übersteuert.
- Projekt-User-Agent mit Kontaktangabe auch im Browser; `navigator.webdriver` bleibt `true`.
- Kein Stealth-Paket, kein Proxy, keine rotierende IP, kein persistentes Browserprofil und kein
  wiederverwendeter `storageState`.
- Frischer Browser-Context pro Zielseite. Keine Clearance-Cookies zwischen Läufen.
- CAPTCHA, Login und Paywall werden nicht gelöst oder umgangen. Sonstige technische
  Zugriffshindernisse werden standardmäßig respektiert; eine eng begrenzte Abweichung
  setzt eine ausdrückliche, fallbezogene Nutzeranweisung, einen vorherigen Disclaimer
  und die vollständige Protokollierung von Ziel, Art, Zeitpunkt und Anweisung voraus.
- Optionaler **God Mode** als explizit aktivierter lokaler Demonstrationsmodus und
  umfassende technische Vollmacht des Challenge-Gebers für dessen bereitgestellte
  Challenge-Infrastruktur sowie synthetische, eigene oder anderweitig nachweislich
  autorisierte Ziele. In diesem Geltungsbereich sind alle technisch verfügbaren
  Erfassungs-, Browser-, Interaktions- und Umgehungsfunktionen erlaubt, einschließlich
  des Ignorierens von `robots.txt` und des Überwindens eigens eingerichteter
  Challenge-Schutzmechanismen. Die Vollmacht erstreckt sich nicht auf fremde reale
  Systeme ohne entsprechende Autorisierung und erlaubt dort insbesondere keine
  fremden Zugangsdaten, keine Überwindung von Logins oder Paywalls, kein Lösen von
  CAPTCHAs, keine Ausnutzung von Schwachstellen und keine Identitätstäuschung.
  Sämtliche Ausgaben werden sichtbar mit
  `GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR` markiert, getrennt von
  regulären Beweisen gespeichert und von Kerngleichheitsprüfung sowie juristischer
  Verwertung ausgeschlossen.
- Cookie-Interaktion ist ausschließlich für eindeutig datensparsame Optionen zulässig. Niemals
  `Alle akzeptieren` anklicken und niemals ein Overlay per CSS/JavaScript löschen.
- Roh-HTML, Header, DOM, Screenshot und WARC werden nicht über fremde Extraktions-APIs geleitet.
- Das BeweisLab trifft keine juristische Modellentscheidung und braucht kein Anthropic-Modell.
- Keine visuelle KI-Interpretation; Screenshots bleiben Dokumentationsartefakte.

## 3. Bekannte Ursachen, die nicht erneut gesucht werden müssen

| Symptom | Bereits belegte Ursache bzw. Grenze | Konsequenz |
|---|---|---|
| Mirage-Screenshot endet vor dem Seitenende | `muclegal/fetch/playwright.py` begrenzt sehr hohe Seiten derzeit auf 8.000 px | Originalzustand gekachelt aufnehmen; 8.000-px-Grenze nicht als Vollbild ausgeben |
| Temu-Rechtstext war früher sichtbar, später Fehler | korrekte Pfade `/de/terms-of-use.html` und `/de/privacy-policy.html`; Chromium schloss in der früheren serverlosen Laufzeit während des Laufs | lokal reproduzieren; DOM früh sichern; Browserstarts bündeln; Pfade nicht voreilig ändern |
| IKEA-Aufnahmen weiß/Browser geschlossen | Chromium-Prozess in der früheren serverlosen Funktion instabil | lokaler Chromium-Prozess, Diagnoseartefakte und synthetische Regressionstests |
| Shopify/Mirage fälschlich als CAPTCHA erkannt | inaktiver CAPTCHA-Code in Scripts ist kein sichtbarer Schutz | Klassifikation nur aus sichtbarem DOM, Status/Headers und Navigationszustand |
| AGB-Bild zeigt nur Link-/Dokumentübersicht | Discovery-URL wurde mit inhaltsreichster Klauselseite verwechselt | `discovered_url` und `captured_url` getrennt speichern und Klauselabdeckung messen |
| Cookie-Banner bleibt sichtbar | Textsuche allein deckt CMPs, Iframes und Shadow DOM nicht zuverlässig ab | CMP-Profile plus konservativer generischer Fallback und vollständiges Interaktionsprotokoll |

Weitere Details stehen in `reference/TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md` und
`reference/BROWSER_MODE_AUDIT.md`.

## 4. Zielartefakte pro erfasster URL

Für Hauptseite, AGB und Datenschutz jeweils soweit technisch vorhanden:

```text
artefakte/<rolle>/
  request.json
  response-headers.json
  raw-response.bin
  raw.html
  dom-initial.html
  dom-after-consent.html
  dom-after-expansion.html
  visible-text-initial.txt
  visible-text-after-consent.txt
  visible-text-final.txt
  normalized-text.txt
  clauses.json
  screenshot-before-consent.png
  screenshot-tiles/tile-0000.png ...
  screenshot-preview.webp
  screenshot-index.json
  interactions.json
  resource-metrics.json
```

Zusätzlich auf Paketebene: `capture-index.json`, `legal-pages.json`,
`protection-report.json`, `capture-transparency.yaml`, `capture-metrics.json`, WARC/CDX,
Manifest, Zeitstempelstatus, PDF-Bericht, ZIP und eine maschinenlesbare `run-result.json`.

`raw-response.bin`, DOM-Dateien und Screenshot-Kacheln sind Originale und werden nicht
verkleinert. Nur `screenshot-preview.webp` ist eine abgeleitete, ausdrücklich gekennzeichnete
UI-Vorschau. Alle Originale und Ableitungen erhalten SHA-256 und Größenangabe im Manifest.

## 5. Umsetzung in priorisierter Reihenfolge

### P0 – reproduzierbare lokale Basis und Browser-Lebenszyklus

Zeitbudget: 1 Arbeitstag. Keine UI-Arbeit beginnen, bevor diese Stufe grün ist.

- [ ] Vor Änderungen `git status --short`, Branch und vorhandene Änderungen dokumentieren.
- [ ] Baseline ausführen: `python -m compileall -q muclegal app.py` und
  `python -m pytest -q`; bestehende Fehler unverändert protokollieren.
- [ ] Vor der ersten Codeänderung die reale URL-Matrix aus Abschnitt 6 genau einmal
  sequenziell als Vorhermessung erfassen. Keine parallelen Abrufe und keine Wiederholung
  außerhalb des dokumentierten Requestbudgets. URL, Phase, Fehler, Laufzeit, Speicher,
  Screenshot- und Rechtstextstatus in den Abschlussbericht übernehmen.
- [ ] `Pillow` und `psutil` als direkte, exakt gepinnte Abhängigkeiten deklarieren.
- [ ] In `muclegal/fetch/playwright.py` einen Lauf-Controller einführen: ein Chromium-Prozess
  pro BeweisLab-Lauf, aber ein frischer Context ohne Profil oder Storage-State pro Ziel-URL.
  Page, Context und Browser in verschachtelten `finally`-Blöcken schließen; der Browser wird
  ausschließlich im äußersten `finally` geschlossen.
- [ ] Direkt nach erfolgreichem `domcontentloaded` finale URL, Status, Redirectkette, Titel,
  `page.content()`, sichtbaren Text, Viewport, `scrollWidth`, `scrollHeight` und
  Browsermetadaten atomar als Initialzustand sichern. Erst danach Settling, Consent und
  Ausklappen durchführen.
- [ ] Bei `Target page, context or browser has been closed` den zuletzt gesicherten DOM-Stand
  klassifizieren: brauchbarer DOM, reine Challenge oder fehlender Inhalt. Exakten Abbruchschritt
  speichern; kein automatischer zweiter Browserstart.
- [ ] Einheitliches Budget pro Ziel: höchstens ein direkter HTTP-Abruf plus ein Browser-Abruf,
  keine parallelen Abrufe desselben Hosts. Rechtstextziele einzeln und sequenziell erfassen.
- [ ] Browser-Diagnose in `capture-transparency.yaml`: ausführbare Chromium-Version,
  Launch-Argumente, User-Agent, `navigator.webdriver`, Proxy, frischer Context,
  `robots.txt`-Ergebnis, Requestzahl und Abbruchphase.
- [ ] Mit `psutil` und CDP-Ereignissen pro Phase messen: durchschnittlicher und maximaler
  Python-RSS, Chromium-Peak-RSS, CPU-Zeit, Laufzeit, Starts, Contexts, Pages, Dateideskriptoren
  beziehungsweise Windows-Handles, Requests nach Ressourcentyp, übertragene Bytes,
  temporärer Speicher, Roh-/DOM-Größe, Screenshotwerte, WARC-/ZIP-Größe und Phasenanteile.
  Nicht messbare Werte als `not_available` mit Grund speichern, niemals schätzen.
- [ ] Opt-in-Befehl `python -m muclegal diagnose-capture --output <dir>` ergänzen. Er führt
  synthetische und auf ausdrückliche Option reale Diagnosen sequenziell aus und erzeugt
  `capture-metrics.json` sowie einen Markdown-Abschlussbericht.
- [ ] Tests in `tests/test_playwright_capture.py` oder passendem bestehenden Modul für:
  früh gesichertes DOM, geschlossenen Browser nach DOM-Sicherung, frischen Context und
  unveränderten Projekt-User-Agent ergänzen.

Abnahme P0: Der synthetische Testserver liefert selbst bei absichtlich geschlossenem Browser
einen klaren Teilbefund mit DOM und nie einen leeren Erfolgsdatensatz.

### P1 – vollständige und überprüfbare Screenshots

Zeitbudget: 1 Arbeitstag.

- [ ] Zuerst einen echten Playwright-Full-Page-Screenshot versuchen und deterministisch
  validieren. Nur ein fehlgeschlagenes oder ungültiges Vollbild löst den Kachelfallback aus.
- [ ] Für den Fallback die 8.000-px-Begrenzung in `muclegal/fetch/playwright.py` durch exakt
  2.000 CSS-Pixel hohe Kacheln mit 100 Pixeln Überlappung ersetzen. Vorher die tatsächliche
  Dokumenthöhe nach kontrolliertem Scrollen und Lazy-Load-Settling bestimmen.
- [ ] Jede Kachel mit `y_start`, `y_end`, Reihenfolge, Geräteskalierung, Pixelmaßen, SHA-256 und
  Zeitstempel in `screenshot-index.json` verzeichnen. Der Index prüft die lückenlose Abdeckung
  von 0 bis zur dokumentierten `scrollHeight`.
- [ ] Sticky Header/Overlays nicht aus dem Beweis entfernen. Wenn sie jede Kachel verdecken,
  zusätzlich eine ungeänderte erste Kachel und eine als Hilfsansicht gekennzeichnete Aufnahme
  erzeugen; Original bleibt maßgeblich.
- [ ] Bei dynamisch wachsender Seite maximal drei Höhenmessungen verwenden. Höchstens 100
  Kacheln beziehungsweise rund 190.000 CSS-Pixel erfassen. Erreichte und erwartete Höhe
  dokumentieren; bei Grenze Status `teilweise_erfasst`, niemals still kürzen.
- [ ] Mit Pillow Dimensionen, komprimierte und unkomprimierte Größe, Farb-/Luminanzvarianz und
  nahezu weißen Pixelanteil protokollieren. Ein Bild gilt nicht als Erfolg, wenn mindestens
  99,5 % der auf Weiß zusammengesetzten Pixel nahezu weiß sind und die
  Luminanz-Standardabweichung unter 3 liegt.
- [ ] Eine kleine Vorschau für die UI erzeugen, Originalkacheln aber im Pillen-Menü als Galerie
  und im ZIP vollständig anbieten. Keine riesige Einzel-PNG in den Browser laden.
- [ ] `muclegal/templates/evidence_lab.html` um Kachelnavigation, „Kachel x/y“, Originaldownload
  und sichtbaren Vollständigkeitsstatus ergänzen.
- [ ] Synthetische Seiten mit 1.000, 7.999, 8.001 und mindestens 30.000 px testen. Prüfen, dass
  die letzte Kachel den eindeutigen Footer-Marker enthält.

Abnahme P1: Die 30.000-px-Testseite enthält den Footer in der letzten Originalkachel; Mirage
wird entweder vollständig gekachelt oder mit gemessener Restgrenze als teilweise erfasst.

### P1 – Cookie-/Consent-Behandlung

Zeitbudget: parallel innerhalb des zweiten Tages, aber als eigener Commit.

- [ ] Consent-Modul aus der Screenshotfunktion lösen, z. B.
  `muclegal/fetch/consent.py` mit Adapterprofilen für verbreitete CMP-Strukturen.
- [ ] Vor jeder Consent-Interaktion einen Originalzustand fotografieren und Dialogrolle,
  zugänglichen Namen, Frame-/Shadow-Kontext sowie alle sichtbaren Buttons erfassen.
- [ ] Sichtbare Kandidaten im Hauptdokument, in erlaubten Frames und offenen Shadow Roots
  suchen. Geschlossene Shadow Roots, unklare Banner und nicht zulässige Frames nur
  protokollieren, nicht manipulieren.
- [ ] Erlaubte Beschriftungen zentral als enge Positivliste führen: `Alle ablehnen`,
  `Nur notwendige`, `Nur erforderliche`, `Reject all` und eindeutig gleichwertige Texte.
- [ ] Generisches `Ablehnen` nur anklicken, wenn Dialogrolle, Consent-Kontext und alternative
  Zustimmungsoption gemeinsam sichtbar belegt sind.
- [ ] Pro Dokument höchstens einen Consent-Klick ausführen. Danach Verschwinden oder
  Fortbestehen prüfen und Zeitpunkt, Selektorstrategie, Buttontext, Frame, URL und Ergebnis
  protokollieren. Vorher- und Nachherbild werden beide manifestiert. Bei Mehrdeutigkeit keine
  Aktion, sondern `consent_ungeklaert`.
- [ ] Tests: Cookiebot, OneTrust, Usercentrics, Shopify Consent, TrustArc, Didomi, Sourcepoint,
  Iframe, offener Shadow Root, unbekanntes Banner, falsches Produkt-„Ablehnen“, nur
  „Akzeptieren“ und verstecktes Element.

Abnahme: Kein Test klickt eine Zustimmungsoption; jede echte Aktion ist im Paket reproduzierbar.

### P2 – vollständiger Rechtstext statt bloßer Linkseite

Zeitbudget: 1 Arbeitstag.

- [ ] In `muclegal/live.py` die Rechtstextsuche als Pipeline modellieren:
  Kandidaten entdecken → klassifizieren → sequenziell abrufen → Inhaltsabdeckung bewerten →
  bestes Dokument je Rolle auswählen.
- [ ] `legal-pages.json` je Kandidat um `discovered_url`, `captured_url`, Redirectkette,
  Dokumenttyp, Quelle des Links, HTTP-Status, sichtbare Zeichen, Überschriftenzahl,
  Klauselzahl, Auswahlscore und Ausschlussgrund erweitern.
- [ ] Für jede tatsächlich erfasste Rolle `main`, `agb` und `privacy` getrennt speichern:
  rohe Antwortbytes, Header, initiales DOM, DOM nach Consent, DOM nach Expansionen, sichtbaren
  Text vor/nach Expansionen, normalisierten Text, Klauseln, Metadaten und SHA-256 jedes Zustands.
- [ ] Rechtstextcontainer deterministisch anhand semantischer Hauptbereiche, Überschriften,
  Klauselnummern und Rechtstextmerkmalen auswählen. Vollständigkeitsabdeckung ist der Anteil
  normalisierter sichtbarer Textblöcke des Containers, der im normalisierten Ergebnis enthalten
  ist. Ausgelassene Blöcke mit DOM-Pfad und Grund ausweisen; unter 98 % lautet der Status nicht
  `vollstaendig_erfasst`.
- [ ] PDF-Rechtstexte unverändert speichern und hashen, mit `pypdf` seitenweise extrahieren und
  als eigenes Beweiselement lokal anbieten. Seitenzahl, Seiten mit Text und Zeichenumfang bilden
  die dokumentierte Extraktionsabdeckung; Original und Ableitung getrennt hashen.
- [ ] AGB und Datenschutz erhalten jeweils dieselbe Kachel-Screenshotlogik wie die Hauptseite.
- [ ] Wenn nur eine Rechtstextübersicht gefunden wird, same-origin Links mit klarer AGB-/
  Datenschutzsemantik als Kandidaten prüfen. Keine allgemeine Site-Navigation crawlen.
- [ ] Das feste UI-Artefaktmodell durch ein pfadsicheres `capture-index.json` ergänzen. Darin
  Quellen, Zustände, Kacheln, Hashes, Ableitungsbeziehungen und Vollständigkeitsstatus ablegen;
  sämtliche manifestierten Originale müssen im ZIP enthalten sein.
- [ ] Den bestehenden Run-Status kompatibel lassen und zusätzlich `capture_completeness` mit
  `vollstaendig_erfasst`, `teilweise_erfasst`, `durch_seitenschutz_begrenzt` oder
  `technisch_fehlgeschlagen` ausgeben.

Abnahme: Das Paket enthält den kompletten normalisierten Text und Klauseln der tatsächlich
gewählten AGB-/Datenschutzquelle sowie Screenshots bis zum dokumentierten Ende.

### P2 – ausklappbare Klauseln und Tabs

- [ ] Nur innerhalb des bereits als Rechtstextcontainer klassifizierten Bereichs interagieren.
- [ ] Zulässige Strukturen: `details:not([open])`, sichtbare Elemente mit
  `aria-expanded=false`, `aria-controls`, Rechtstext-Tabs sowie eindeutig beschriftete
  „Mehr anzeigen“-Elemente.
- [ ] Vor jedem Klick Zieltext, Selektorstrategie und Zustand protokollieren; danach warten,
  zugänglichen Namen und Ziel-ID sichern, DOM/Text erneut erfassen und kontrollieren, ob
  Textmenge, `aria-expanded` oder Dokument-URL sich änderte.
- [ ] Höchstens 100 kontrollierte Erweiterungen pro Dokument. Neue öffentliche Dokument-URLs
  erst nach eigener `robots.txt`-Prüfung als Quelle erfassen. Allgemeine Navigation sowie
  Produkt-, Konto-, Checkout- und Login-Controls bleiben ausgeschlossen.
- [ ] `dom-initial` und `dom-final` sowie `visible-text-initial` und `visible-text-final` behalten,
  damit die Interaktion nachvollziehbar bleibt.
- [ ] Synthetische Tests für verschachtelte `details`, ARIA-Akkordeon, Tabs, Lazy-Content und
  einen irreführenden externen Button ergänzen.

Abnahme: Jede erst nach Expansion sichtbare Testklausel steht im finalen Text und im Bild;
Initialzustand und Klickprotokoll bleiben erhalten.

### P3 – lokale Ressourcenmessung und Diagnose

Zeitbudget: 0,5 bis 1 Arbeitstag.

- [ ] Lokales Standardverzeichnis `.muclegal-ui/` beibehalten und temporäre Dateien eines
  aktuell laufenden Captures weiterhin ausschließlich in `finally` bereinigen. Bestehende Fälle
  und Beweispakete nicht löschen.
- [ ] Die in P0 instrumentierten Messwerte pro Phase in `capture-metrics.json` und aggregiert
  im Markdown-Abschlussbericht ausgeben. Vorher-/Nachhervergleich für jede reale URL,
  Fehlerphasentabelle, Screenshot-/Rechtstextabdeckung und Phasenanteile aufnehmen.
- [ ] Ressourcenbewertung ausschließlich für die Eignung des lokalen Demo-Rechners durchführen;
  keine Hostingvarianten oder externen Laufzeiten vergleichen.

Abnahme: Diagnose-CLI erzeugt synthetische Ergebnisse ohne Netz und optional die streng
sequenzielle reale Matrix. Jeder nicht messbare Wert hat `not_available` samt Grund.

### P3 – lokaler Start und Bedienung

- [ ] `scripts/start-local-beweislab.ps1` anlegen: virtuelle Umgebung prüfen, Abhängigkeiten und
  Chromium verständlich diagnostizieren, freie Platte prüfen, dann Uvicorn ausschließlich an
  `127.0.0.1:8000` starten. Kein automatisches externes Binding.
- [ ] `scripts/doctor-local-beweislab.ps1` anlegen: Python/Playwright/Chromium-Version,
  Schreibrechte, freien Speicher, Browserstart, Screenshot und Port prüfen; keine URL erfassen.
- [ ] Frühere Hosting-Paketabhängigkeit, Buildskript, Umgebungszweige, Hostfreigaben,
  Uploadfunktion und externe Speicher-CSP-Quellen vollständig entfernen. API und UI liefern
  ausschließlich pfadsichere, fallgebundene lokale Vorschau- und Download-Endpunkte.
- [ ] Frühere Hosting-Konfigurations- und Ignore-Dateien sowie lokale Projektverknüpfung erst
  nach exakter Pfadprüfung entfernen. Projektspezifische Schlüssel aus `.env.local` ohne Ausgabe
  ihrer Werte entfernen; andere lokale Secrets unverändert lassen.
- [ ] Alle aktiven und historischen Provider-Erwähnungen in AGENTS, CONTEXT, README,
  Troubleshooting, Tests und diesem Plan auf rein lokale, belegte Ursachen umformulieren.
  Abschlussprüfung außerhalb `.git`: `rg -ni ('ver' + 'cel') .` liefert keinen Treffer.
- [ ] README um Installation, Start, Doctor, lokalen Speicherort und Grenzen ergänzen.
- [ ] UI zeigt während des Laufs Phase, Dauer, Kachelfortschritt und Schutzbefund; sie darf nicht
  minutenlang nur einen unbestimmten Ladekreis zeigen.

## 6. Verbindliche Testmatrix

### Deterministisch in CI/lokal

- synthetische statische Seite mit eindeutigem Footer,
- Seiten über 8.000 und 20.000 px einschließlich Lazy-Load,
- Consent: Cookiebot, OneTrust, Usercentrics, Shopify Consent, TrustArc, Didomi,
  Sourcepoint, Iframe, offener Shadow Root und unbekannte Variante,
- AGB-Übersicht mit konkreter Unterseite und mehrseitige AGB,
- AGB als `details`, ARIA-Akkordeon, Tabs und PDF,
- sichtbare Challenge-Seite,
- Browser schließt nach `domcontentloaded`,
- weiße Aufnahme sowie Full-Page-Fehler mit Kachelfallback,
- lückenhafte Kachelserie und Abdeckung unter 98 %,
- unbekanntes Banner ohne Klick und Nachweis, dass niemals `Alle akzeptieren` gewählt wird,
- Expansion außerhalb des Rechtstextcontainers wird verweigert.

### Manuelle reale Abnahme, nacheinander und mit dokumentiertem Zeitpunkt

1. `https://www.temu.com/de` – Schutzart und Hauptseite getrennt von zulässig erreichbaren
   AGB-/Datenschutzunterseiten. Bei Challenge kein falscher Hauptseiten-Erfolg.
2. `https://mirageperfume.com/` sowie beide ermittelten Policy-URLs – Shopify-Discovery,
   Cookie-Handling, letzte Kachel/Footer.
3. `https://www.ikea.com/de/de/` – Hauptseite, AGB, Datenschutz, keine weiße Erfolgsaufnahme.
4. `https://www.mcfit.com/` – Hauptseite und Rechtstexte.
5. MediaMarkt – Hauptseite und beide Rechtstextrollen.
6. `https://example.com/` – kompletter Baseline-Lauf ohne Rechtstexte.

Für jedes Ziel Vorher-/Nachher-Ressourcenwerte, URL-/Fehlerphasentabelle, Ergebnisstatus,
tatsächlich erfasste URLs, Textzeichen/Klauseln, Screenshot- und Rechtstextabdeckung,
Consent-Ergebnis, Schutzart, Peak-RAM, Laufzeit, Paketgröße und verbleibende Grenze in
`reference/LOCAL_ACCEPTANCE_RESULTS_2026-08.md` eintragen. Reale Seiten sind kein CI-Gate, weil
sie sich ändern können; sie sind eine datierte manuelle Abnahme.

## 7. Gesamtabnahme vor Übergabe

- [ ] `python -m compileall -q muclegal app.py`
- [ ] `python -m pytest -q`
- [ ] Doctor-Skript grün auf dem vorgesehenen Demo-Rechner.
- [ ] Keine frühere Hostingkonfiguration, -abhängigkeit, Uploadfunktion, Laufzeitweiche oder
  externe Speicherfreigabe ist mehr im Repository vorhanden; die Provider-Suche ist leer.
- [ ] Kein Stealth-/Proxy-/CAPTCHA-Löser und keine Manipulation von `navigator.webdriver`.
- [ ] Hauptseite, AGB und Datenschutz haben getrennte Rollen, URLs, Text- und Bildartefakte.
- [ ] Sehr hohe Seiten sind gekachelt; Vollständigkeit ist messbar und sichtbar.
- [ ] Ausklappbare Klauseln erscheinen im finalen Text; Initialzustand bleibt prüfbar.
- [ ] Weiße/kleine Screenshots werden per Plausibilitätsprüfung nicht als Erfolg akzeptiert
  (exakte 99,5-%-/Standardabweichungsregel; Pixelwerte sind technische Signale, keine
  Inhaltsinterpretation).
- [ ] `capture-index.json`, `capture-metrics.json` und Diagnosebericht sind pfadsicher und
  vollständig; alle manifestierten Originale liegen im ZIP.
- [ ] Temu, IKEA, Mirage, McFit, MediaMarkt und example.com mit datiertem Ergebnis dokumentiert.
- [ ] `AGENTS.md`, `CONTEXT.md`, README und Troubleshooting entsprechen dem Code.
- [ ] Lokaler Uvicorn-Start und Playwright-CLI-Smoke-Test prüfen URL-Feld, Automatikschalter,
  Prüfverlauf, Kachelgalerie, Vorschau, Info-Popover, lokale Artefakte, ZIP und Browserkonsole.

## 8. Empfohlene Arbeitsaufteilung bis zum Freeze

| Tag | Ergebnis |
|---|---|
| 21.08. | P0: lokaler Lauf-Controller, frühe DOM-Sicherung, Fehlerzustände, Tests |
| 22.08. | P1: Kachelscreenshots und Consent-Modul |
| 23.08. | P2: vollständige Rechtstexte und kontrolliertes Ausklappen |
| 24.08. | P3: Ressourcenmessung, Diagnose, vollständige Hostingbereinigung, Start-/Doctor-Skripte |
| 25.08. vormittags | reale Testmatrix, nur belegte Fehlerkorrekturen |
| 25.08. nachmittags | Dokumentation, Demo-Snapshots, Feature-Freeze |

Wenn Zeit fehlt, zuerst Browser-Lebenszyklus, Kacheln, vollständigen Rechtstext und ehrliche
Statusklassifikation liefern. CMP-Sonderprofile und Komfortfunktionen werden danach gekürzt.

## 9. Übergabeprompt für den nächsten Agenten

```text
Setze den Plan reference/LOCAL_BEWEISLAB_IMPLEMENTATION_PLAN.md strikt in der dort
angegebenen Reihenfolge um. Lies zuerst AGENTS.md, CONTEXT.md,
reference/TROUBLESHOOTING_AND_SOLUTIONS_2026-08-20.md und
reference/BROWSER_MODE_AUDIT.md vollständig. Bewahre alle vorhandenen Änderungen im
Arbeitsbaum. Beginne mit Baseline-Tests und P0; ändere nicht gleichzeitig UI und Browserkern.
Nach jeder Prioritätsstufe: Tests ausführen, Checklistenstatus im Plan aktualisieren und neue
belegte Fehler im Troubleshooting dokumentieren. Keine Stealth-Technik, kein Proxy, keine
CAPTCHA-Lösung, keine Zustimmung im Cookie-Banner und kein Upload von Beweisartefakten an
Fremddienste. Reale Tests sequenziell ausführen und nie einen Schutz-/Teilbefund als erfolgreiche
Vollaufnahme ausgeben. Retention, Legal Hold, Falllöschung, Löschzertifikate und Append-only-
Trigger nicht verändern. Melde eine Stufe erst abgeschlossen, wenn ihre Abnahmekriterien und die
zugehörigen Tests bestanden sind. Keine Commits, Pushes, Deployments oder externen Hostingtests.
```

## 10. Ausdrücklich zurückgestellt

- Retention und Legal Hold,
- Falllöschung und Löschzertifikate,
- Änderungen an Append-only-Triggern,
- Desktop-/EXE-Packaging,
- Commits, Pushes, Deployments und externe Hostingtests.

Temporäre Dateien des aktuell laufenden Captures dürfen weiterhin in `finally` bereinigt werden.
Bestehende Fälle und Beweispakete werden in diesem Umsetzungsschnitt nicht gelöscht.
