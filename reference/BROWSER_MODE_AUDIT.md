# Audit des Überprüfungsmodus

Stand: 21.08.2026

## Kurzfazit

Der Überprüfungsmodus tarnt Chromium nicht. Ein Live-Abruf von
`https://postman-echo.com/headers` zeigte den konfigurierten MucLegal-User-Agent;
`navigator.webdriver` war zur Laufzeit `true`. Es wurden keine Stealth-Erweiterungen,
Proxy-Einstellungen, persistenten Profile oder wiederverwendeten Storage-States gefunden.
`robots.txt` wird auch vor dem Browserpfad geprüft. Ist die Datei nicht erreichbar,
nicht lesbar oder nicht eindeutig auswertbar, gilt nicht mehr `fail closed`: Die
Erfassung darf fortfahren, muss den ungeprüften Status aber deutlich in UI und
Beweispaket ausweisen und mit einem Disclaimer zur eigenverantwortlichen Prüfung von
Berechtigung, Nutzungsbedingungen und rechtlicher Zulässigkeit verbinden.

Nach diesem Audit wurde eine eng begrenzte Screenshot-Interaktion ergänzt: Vor einer
Aufnahme darf höchstens eine eindeutig datensparsame Cookie-Option gewählt werden.
Die Aktion wird in `screenshot_interactions.json` dokumentiert und in das Manifest
aufgenommen. Sie ändert nichts am Stealth-, Session-, Proxy- oder robots.txt-Befund.

Ein Prozesspunkt ist noch offen: Die Anwendung serialisiert Prüfläufe, erzwingt aber
keine dauerhafte Obergrenze von einem Abruf je URL und Kalendertag.

## Prüfergebnisse

### 1. Tatsächlich gesendeter User-Agent — bestanden

Der Echo-Endpunkt empfing:

`MucLegal-Monitor/0.1 (+https://github.com/Alebabo/MucLegal; public-page compliance monitor)`

Der Wert wird in `muclegal/fetch/http.py:14` definiert, in
`muclegal/fetch/playwright.py:69` in den frischen Browserkontext übernommen und zur
Laufzeit erneut aus `navigator.userAgent` gelesen.

### 2. Launch-Argumente und Tarnbibliotheken — bestanden

Die Suche nach `AutomationControlled`, `setUserAgent`, `stealth`,
`playwright-extra`, `puppeteer-extra`, `addInitScript`, `evaluateOnNewDocument`,
`proxy`, `storageState`, persistenten Profilen und vergleichbaren Mustern ergab
keinen Tarnungs- oder Proxy-Code. Chromium wird in
`muclegal/fetch/playwright.py:65` nur mit `headless=True` gestartet.

Der Treffer `user_agent=user_agent` in `muclegal/fetch/playwright.py:69` ist die
gewollte Projektkennung, keine Chrome-Imitation.

### 3. `navigator.webdriver` — bestanden

Der Laufzeitwert war `true`. Die Messung erfolgt in
`muclegal/fetch/playwright.py:116` und wird in der Erfassungstransparenz gespeichert.

### 4. `robots.txt` — Vorgabe am 21.08.2026 geändert

Der Browserpfad prüft `robots.txt` vor dem Start in
`muclegal/fetch/http.py:99-103`. Dokumentweiterleitungen werden zusätzlich über den
Request-Guard in `muclegal/fetch/http.py:120` geprüft. Ein Test gegen
`httpbin.org`, dessen `robots.txt` mit HTTP 503 antwortete, wurde vor dem Browserstart
abgebrochen. Dieser Test dokumentiert das frühere `fail closed`-Verhalten, das durch
die neue Vorgabe ersetzt wird: Bei einem 503, Timeout, Netzwerkfehler oder einer nicht
eindeutig auswertbaren `robots.txt` soll die Erfassung fortgesetzt werden. Dabei sind
der konkrete Prüfstatus und die Ursache zu protokollieren; die UI und das Beweispaket
müssen deutlich darauf hinweisen, dass `robots.txt` nicht verlässlich geprüft werden
konnte und der Nutzer Berechtigung, Nutzungsbedingungen und rechtliche Zulässigkeit
eigenverantwortlich prüfen muss. Der Status darf nicht als
`geprueft_abruf_erlaubt` erscheinen.

Eine abrufbare, eindeutig untersagende `robots.txt` wird weiterhin standardmäßig
respektiert. Nur eine ausdrückliche, fallbezogene Nutzeranweisung darf diese Vorgabe
übersteuern; Anweisung, Ziel, Zeitpunkt und Abweichungsart sind nachvollziehbar zu
protokollieren und mit demselben Disclaimer auszugeben. Das schafft keine Erlaubnis
zur Nutzung fremder Zugangsdaten, zur Überwindung von Logins oder Paywalls oder zum
Lösen von CAPTCHAs.

Die Codepfade und Regressionstests müssen auf dieses Sollverhalten umgestellt werden;
bis zu deren erfolgreicher Verifikation darf der Abschnitt nicht als „bestanden“
bewertet werden.

### 4a. God Mode — ausschließlich lokale Demonstration — umgesetzt am 21.08.2026

Ein ausdrücklich aktivierter God Mode erteilt die umfassende technische Vollmacht des
Challenge-Gebers für dessen bereitgestellte Challenge-Infrastruktur sowie für
synthetische, eigene oder anderweitig nachweislich autorisierte Ziele. Innerhalb
dieses Geltungsbereichs sind sämtliche technisch verfügbaren Erfassungs-, Browser-,
Interaktions- und Umgehungsfunktionen erlaubt, einschließlich des Ignorierens von
`robots.txt` und des Überwindens eigens eingerichteter Challenge-Schutzmechanismen.

Die Vollmacht gilt nicht für fremde reale Systeme, für die der Challenge-Geber keine
Verfügungs- oder Autorisierungsbefugnis besitzt. Dort erlaubt sie insbesondere keine
fremden Zugangsdaten, keine Überwindung von Logins oder Paywalls, kein Lösen von
CAPTCHAs, keine Ausnutzung von Schwachstellen und keine Identitätstäuschung.
Aktivierung, Vollmachtsgrundlage, Ziel, freigeschaltete Funktionen und Zeitpunkt
müssen vollständig protokolliert werden.

Alle erzeugten Ansichten und Artefakte tragen sichtbar
`GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR`, werden getrennt von der
regulären Beweisspur gespeichert und dürfen weder als Beweis ausgegeben noch einer
juristischen Kerngleichheitsprüfung zugeführt werden.

Die Implementierung verlangt die ausdrückliche Checkbox `Autorisiert (God Mode)` neben
der URL. Das Anklicken protokolliert die Nutzerbestätigung, dass Vollmacht und Rechtsrahmen
vorab geklärt sind, und erzwingt den Browsermodus. Snapshots liegen unter
`god-mode-snapshots/`, Pakete unter `god-mode-bundles/god-*`; reguläre Falllisten enthalten
sie nicht. `god_mode_authorization.json` hält Zeitpunkt, Ziel, Vollmachtsgrundlage und
freigeschaltete Funktionen vor der Manifestbildung fest. Bilder erhalten einen roten
Banner, normalisierte Texte eine Kopfzeile, das Manifest ein Notice-Feld und PDF sowie ZIP
eine durchgehende Demonstrationskennzeichnung. Der Modus löst weiterhin keine fremden
Logins, Paywalls oder CAPTCHAs und fügt keine Stealth- oder Identitätstäuschung hinzu.

Regressionstests belegen die Trennung, das Ignorieren einer synthetisch untersagenden
robots.txt, die sichtbaren Markierungen und die Checkbox-Weitergabe bis zum Workflow.

### 5. Cookie- und Session-Persistenz — bestanden

Für jeden Aufruf werden Browser und Context neu erzeugt
(`muclegal/fetch/playwright.py:65-67`). Es werden weder `storage_state` noch ein
Profilverzeichnis übergeben. Der Browser wird nach der Aufnahme geschlossen.

Cookie-Banner dürfen nur über `Alle ablehnen`, `Nur notwendige` oder eine eindeutig
gleichbedeutende Option geschlossen werden. Es werden keine Zustimmungen oder
Clearance-Token übernommen; jeder Screenshot läuft weiterhin in einem frischen Context.
Buttontext und Aktionsklasse werden pro Screenshot beweisbar gespeichert.

### 6. Frequenz und Parallelität — teilweise bestanden

Die Ausführung ist seriell: `ThreadPoolExecutor(max_workers=1)` in
`muclegal/ui.py:144` und die aktive Lauf-ID in `muclegal/ui.py:147-193` verhindern
parallele BeweisLab-Läufe.

#### BROWSER-AUDIT-001

- Schweregrad: Mittel (Prozess- und Nachweisrisiko)
- Ort: `muclegal/ui.py:144-193`, `muclegal/live.py:158`
- Nachweis: Es existiert keine persistente URL-/Tages-Sperre. Bei Schutz kann auf
  Browser und anschließend auf mehrere Rechtstext-Kandidaten gewechselt werden. Die
  Screenshotaufnahme ist außerdem eine eigene Navigation.
- Auswirkung: Derselbe Zielzustand kann innerhalb eines Tages mehrfach angefragt
  werden; eine Behauptung „höchstens ein Abruf je URL und Tag“ wäre derzeit falsch.
- Abhilfe: Vor einem Produktivbetrieb eine persistente URL-/UTC-Tagesquote ergänzen
  und Primär-DOM sowie Screenshot nach Möglichkeit in derselben Browsernavigation
  erfassen.
- Aktuelle Mitigation: Nur ein aktiver Lauf; jeder tatsächliche Browserlauf weist
  seine Dokument- und Gesamtrequestzahl im Transparenzartefakt aus.

### 7. Temu-Datensatz — bestanden

Der neu erzeugte Fall trennt:

- angefragte/blockierte URL: `https://www.temu.com/de`
- Schutzart: `JavaScript-Challenge`
- tatsächlich erfasste URL: `https://www.temu.com/de/terms-of-use.html`

Die Felder werden in `muclegal/live.py:602-605` getrennt im Fallobjekt gespeichert
und zusätzlich in `capture_transparency.yaml` aufgenommen.

### 8. IP und Herkunft — bestanden mit Nachweisgrenze

Es gibt keine Proxy-Konfiguration oder Abhängigkeit für Residential-/Rotating-Proxies.
Das Transparenzartefakt weist `proxy: "keiner"` und
`herkunft: "eigene_infrastruktur_ohne_proxy"` aus. Die konkrete öffentliche
Egress-IP wird bewusst nicht in das Beweispaket geschrieben; der Nachweis bezieht
sich auf die geprüfte Konfiguration und den unmittelbaren Laufzeitpfad.

## Neues Beweiselement

Neue BeweisLab-Pakete enthalten `capture_transparency.yaml`. Das Artefakt wird vor
Manifest und Zeitstempel erzeugt und ist damit in die Integritätsprüfung einbezogen.
Es enthält insbesondere User-Agent, `navigator.webdriver`, Automatisierungsflags,
Proxy-, Context- und robots.txt-Status sowie die angefragte und tatsächlich erfasste
URL.
