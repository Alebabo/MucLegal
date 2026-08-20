# Audit des Überprüfungsmodus

Stand: 20.08.2026

## Kurzfazit

Der Überprüfungsmodus tarnt Chromium nicht. Ein Live-Abruf von
`https://postman-echo.com/headers` zeigte den konfigurierten MucLegal-User-Agent;
`navigator.webdriver` war zur Laufzeit `true`. Es wurden keine Stealth-Erweiterungen,
Proxy-Einstellungen, persistenten Profile oder wiederverwendeten Storage-States gefunden.
`robots.txt` wird auch vor dem Browserpfad geprüft und schlägt geschlossen fehl.

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

### 4. `robots.txt` — bestanden

Der Browserpfad prüft `robots.txt` vor dem Start in
`muclegal/fetch/http.py:99-103`. Dokumentweiterleitungen werden zusätzlich über den
Request-Guard in `muclegal/fetch/http.py:120` geprüft. Ein Test gegen
`httpbin.org`, dessen `robots.txt` mit HTTP 503 antwortete, wurde vor dem Browserstart
abgebrochen. Der Pfad arbeitet damit fail-closed.

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
