# MucLegal – vollständiges Funktionshandbuch

Stand: 25.08.2026

Branch: `agent/live-url-ui`

Dokumentationsgrundlage: aktueller Repository- und Arbeitsbaumstand, automatisierte Tests,
verbindliche BeweisLab-Referenzen und aufgezeichnete Entire-Checkpoints.

> **Wichtiger Standhinweis:** Am 25.08.2026 wird die Tenorschreibhilfe parallel auf eine
> UE-konforme Einzelausgabe umgestellt. Dieses Handbuch beschreibt den im aktuellen
> Arbeitsbaum sichtbaren Funktionsstand. Die übrigen Produktpfade werden anhand des
> eingecheckten Codes dokumentiert. Funktionen aus Planungsdokumenten, die im Code nicht
> nachweisbar sind, werden ausdrücklich als Grenze oder Roadmap bezeichnet.

## 1. Kurzbeschreibung

MucLegal ist ein Hackathon-Prototyp zur technischen und juristischen Nachkontrolle von
Unterlassungserklärungen und Unterlassungstenoren. Das System setzt nicht bei der Suche nach
einem unbekannten Erstverstoß an. Ausgangspunkt ist immer ein bereits fachlich festgestellter
Fall, dessen untersagte Praxis künftig beobachtet werden soll.

Die zentrale Produktthese lautet: Ein Verstoß kehrt häufig nicht wortgleich zurück. Er kann
auf eine andere URL, in einen anderen Seitentyp, in ein anderes Element oder in einen anderen
Kanal wandern. Deshalb kombiniert MucLegal:

1. eine strukturierte Erfassung des bekannten Erstverstoßes,
2. eine stabile technische Erfassung öffentlich erreichbarer Webseiten,
3. Normalisierung und Hashvergleich zur Erkennung echter Änderungen,
4. eine klauselscharfe, schema-validierte juristische Vorprüfung,
5. lokale Beweisartefakte mit Prüfsummen und Zeitstempelversuch,
6. eine zwingende menschliche Freigabe.

MucLegal trifft keine autonome rechtliche Entscheidung. Modellbewertungen bleiben
Vorprüfungen. Die endgültige Freigabe liegt bei einem Menschen.

## 2. Zielgruppen und typische Einsatzfälle

### 2.1 Zielgruppen

- Verbraucherzentralen und Wettbewerbsverbände
- Industrie- und Handelskammern
- Kanzleien und Rechtsabteilungen
- sonstige Stellen, die die Umsetzung von Unterlassungsverpflichtungen kontrollieren

### 2.2 Typische Einsatzfälle

- Eine beanstandete Werbeaussage taucht mit anderer Formulierung wieder auf.
- Eine künstliche Verknappung wandert von der Startseite auf eine Produktdetailseite.
- Eine untersagte AGB-Klausel wird sprachlich verändert oder auf eine andere Rechtstextseite
  verschoben.
- Ein erforderlicher Button oder Link fehlt, ist nicht sichtbar, nicht leicht zugänglich,
  führt zum falschen Ziel oder enthält eine zusätzliche Hürde.
- Ein bereits archivierter technischer Ausgangsstand soll mit einer aktuellen Erfassung
  verglichen werden.
- Eine Juristin benötigt einen strukturierten Entwurf für eine Unterlassungserklärung.
- Für einen möglichen Wiederholungsfall soll ein lokales, nachvollziehbares Beweispaket
  erzeugt werden.

## 3. Produktbereiche im Überblick

MucLegal besteht aus zwei fachlich getrennten Hauptbereichen und mehreren unterstützenden
Werkzeugen.

| Bereich | Zweck | Juristische KI | Primäre Oberfläche |
| --- | --- | --- | --- |
| Fallmonitor | Bekannten Erstverstoß erfassen, freigeben und nachverfolgen | nur in der getrennten Kerngleichheitsprüfung | React-Frontend |
| BeweisLab | Öffentliche URL technisch erfassen und lokal beweissicher dokumentieren | nein | FastAPI/Jinja-Seite |
| Tenorschreibhilfe | UE-/Tenorentwurf aus Sachverhalt, Rückfragen und Referenzen erstellen | optional OpenAI/Anthropic, sonst Demo-Fallback | React-Frontend |
| Archiv | Fälle und gespeicherte Tenorfassungen lesen | nein | React-Frontend |
| CLI und Offline-Demo | Pipeline, Eval, Blind Review und Diagnosen reproduzierbar ausführen | optional | Kommandozeile |

Die fachliche Trennung ist wichtig:

- Das **BeweisLab** beantwortet nur: Was konnte technisch erfasst werden, mit welchen
  Artefakten und welchen Grenzen?
- Der **Fallmonitor** beantwortet nach Freigabe und Prüfung: Ist der neue technische Stand
  unverändert, beseitigt, möglicherweise kerngleich oder nicht vollständig prüfbar?
- Eine juristische Modellbewertung darf nie still aus einem Grey-Mode- oder BeweisLab-Lauf
  entstehen.

## 4. Oberflächen und Bedienfunktionen

### 4.1 Gemeinsame Navigation

Die React-Oberfläche und das separat gerenderte BeweisLab verwenden dieselbe visuelle
Navigation. Verfügbar sind:

- `Home` beziehungsweise Dashboard
- `Hinweise`
- `Archiv`
- `Neu hinzufügen`
- `Tenorschreibhilfe`
- `BeweisLab`
- Light-/Dark-Mode
- ein- und ausklappbare Desktop-Seitenleiste

Unter 768 Pixel Breite wird die feste BeweisLab-Seitenleiste ausgeblendet. Das Theme wird im
Browser gespeichert. Das BeweisLab ist technisch eine Jinja-Seite und kopiert die gemeinsame
Shell; es ist kein React-Route-Modul.

### 4.2 Dashboard – Route `/`

Das Dashboard verdichtet Monitoringfälle zu einer schnellen Arbeitsübersicht.

#### Angezeigte Kennzahlen

- neue Hinweise der letzten 24 Stunden
- Zahl kritischer Fälle
- Zahl der Fälle mit offener Prüfung
- Monitoringstatus `Aktiv`, `Demo` oder `Offline`
- Zeitpunkt des letzten bekannten Falls
- ein derzeit aus der UI berechneter Hinweis auf den nächsten Lauf

#### Aktionen

- neuen Fall hinzufügen
- Hinweise öffnen
- Archiv öffnen
- bis zu drei kritische Top-Prioritäten direkt anzeigen

#### Demo- und Fehlerverhalten

Wenn noch keine Backendfälle gespeichert sind, verwendet die Oberfläche klar synthetische
Lotto-Demofälle. Ist das Backend nicht erreichbar, bleibt dieser Demo-Datensatz sichtbar und
die Oberfläche zeigt eine Warnung. Persistierte Backendfälle ersetzen die Demofälle, sobald
sie verfügbar sind.

> Der auf dem Dashboard angezeigte „nächste Lauf“ ist aktuell eine UI-Darstellung und kein
> Nachweis eines dauerhaft laufenden Schedulers.

### 4.3 Hinweise – Route `/hinweise`

Die Hinweise-Seite ist die operative Fallansicht. Jeder Eintrag lässt sich aufklappen.

#### Pro Fall sichtbar

- Prioritätsfarbe und Status
- relative und absolute Zeitangabe
- Falltitel, Fall-ID und Domain
- Erläuterung des Befunds
- Tenor oder Formulierungsvorschlag
- Kontext und Confidence, soweit vorhanden
- Ziel-URL
- Beweisführung mit Fundstelle, Erfassungsstatus und Beweiskette
- rechtliche Einordnung als Vorprüfung
- offene Punkte

#### Menschliche Entscheidungen

Ein neu erfasster Backendfall beginnt mit `weitere_pruefung`. Ein Mensch kann ihn:

- `freigegeben` setzen oder
- `abgelehnt` setzen.

Nur ein freigegebener Fall kann über die Oberfläche einen Monitoringlauf starten. Das Backend
erzwingt diese Bedingung erneut; eine reine Frontend-Manipulation reicht nicht aus.

#### Monitoringlauf

Nach dem Start:

1. erzeugt das Backend eine Lauf-ID,
2. die UI fragt den Laufstatus alle 500 Millisekunden ab,
3. das Polling bleibt bis zu elf Minuten aktiv,
4. nach einem Terminalstatus werden die Fallansichten neu geladen,
5. bei relevanten Änderungen erscheint eine dauerhaft sichtbare Benachrichtigung.

Die zusätzliche Minute gegenüber dem zehnminütigen Scanbudget ist für WARC-, Manifest- und
sonstige Abschlussartefakte vorgesehen. Läuft der Server danach weiter, weist die UI darauf hin,
dass die Hinweise später neu geladen werden sollen.

#### Benachrichtigungen aus Beweisvergleichen

Wird im BeweisLab ein aktueller technischer Stand gegen einen verknüpften Ausgangsbeweis
verglichen, kann die Anwendung die Hinweise-Seite öffnen und eine klickbare Meldung anzeigen.
Der Klick öffnet den betroffenen Fall und scrollt direkt zur Beweisführung. Die Übergabe erfolgt
je nach Origin über `sessionStorage` oder einen kurzlebigen Query-Parameter.

### 4.4 Archiv – Route `/archiv`

Das Archiv besitzt zwei Reiter: `Fälle` und `Tenore`.

#### Fallarchiv

Die Tabelle zeigt:

- Fall-ID
- Titel und Kurzkontext
- Status und Priorität
- Domain
- Erfassungszeitpunkt
- Confidence

Ein Klick öffnet eine Detailansicht mit Zielseite, vollständiger Erklärung, Tenor und
Beweisführung.

#### Tenorarchiv

Das Tenorarchiv führt sowohl Entwürfe der Minimalansicht als auch der strukturierten Maske
zusammen. Angezeigt werden:

- Fall-ID
- Titel und Textauszug
- Strategie beziehungsweise Variante
- Freigabestatus
- Speicherzeitpunkt

Die Detailansicht enthält:

- vollständigen gespeicherten Text
- Schuldner
- Erstellungsmodus und Modell
- Wissens-/Referenzversion
- Quellenanker
- zugrunde liegenden Sachverhalt

Über `Tenor anpassen` wird eine gespeicherte Fassung wieder in die Tenorschreibhilfe geladen.
Eine Überarbeitung überschreibt die alte Fassung nicht, sondern wird als neue Version
beziehungsweise neuer Archiveintrag gespeichert.

### 4.5 Neuen Monitoringfall erfassen – Route `/neu`

MucLegal sucht keine Erstverstöße. Auf dieser Seite erfasst eine Nutzerin einen bereits
festgestellten Fall.

#### Stammdaten

- Fall-ID
- Hauptdomain
- vollständige HTTP(S)-Fundstellen-URL
- Verstoßart `klausel` oder `element`
- Beschreibung des bekannten Erstverstoßes

#### Unterlassung und Prüfumfang

- Unterlassungstenor beziehungsweise erfasstes Element
- konkretes Monitoringziel
- relevante Seitentypen, je Zeile ein Eintrag
- bis zu 20 konkrete Pflicht-Prüf-URLs
- bis zu 20 ausdrücklich nicht umfasste Sachverhalte

`nicht_umfasst` ist ein zentrales Fehlalarm-Gegenmittel. Ein neuer Zustand darf nicht allein
wegen sprachlicher Ähnlichkeit hochgestuft werden, wenn er ausdrücklich außerhalb des
Unterlassungsumfangs liegt.

#### Klauselfall

Bei `klausel` ist der beanstandete wörtliche Klauseltext verpflichtend. Dieser Text dient später
als fachlicher Ausgangspunkt für Klauselsuche und Vergleich.

#### Elementfall

Bei `element` werden erfasst:

- sichtbare Bezeichnung
- alternative Bezeichnungen
- erwartete Funktion oder Ziel-URL
- Fehlerart:
  - `fehlt`
  - `nicht_sichtbar`
  - `nicht_leicht_zugaenglich`
  - `falsches_ziel`
  - `zusaetzliche_huerde`

#### Domainbegrenzung

Optional können erlaubte Subdomains angegeben werden. Das Backend akzeptiert dabei nur die
Hauptdomain oder echte Subdomains davon; beliebige fremde Hosts sind nicht zulässig.

#### Optionaler Ausgangsscreenshot

Die API unterstützt einen lokalen Ausgangsscreenshot als PNG, JPEG oder WebP. Er wird gehasht
und lokal gespeichert. Es gibt keine OCR- oder Vision-Analyse dieses Bildes.

#### Ergebnis der Erfassung

Der Fall wird mit unveränderlich gesetzten Herkunftsmerkmalen gespeichert:

- `erstverstoss_festgestellt_durch: "verbraucherzentrale"`
- `system_detected: false` im API-/Produktverständnis
- Entscheidung zunächst `weitere_pruefung`

### 4.6 Tenorschreibhilfe – Route `/tenorhilfe`

Die Tenorschreibhilfe besitzt eine minimalistische Schreibansicht und eine strukturierte Maske.
Beide sollen denselben menschlichen Freigabegrundsatz erfüllen.

#### 4.6.1 Minimalansicht

Die Minimalansicht ist eine dokumentzentrierte Schreibfläche. Sie unterstützt:

- freie Sachverhaltsbeschreibung
- PDF-Drop beziehungsweise PDF-Auswahl
- browserabhängige Diktierfunktion
- kontextbezogene Rückfragen
- Archivsuche
- Laden und versioniertes Überarbeiten eines bestehenden Tenors
- Übernahme des geprüften Entwurfs in das Archiv

#### Slash-Modi

Ein `/` öffnet eine Tastaturauswahl:

| Befehl | Funktion |
| --- | --- |
| `/sachverhalt` | neuen Sachverhalt beschreiben |
| `/tenor` | vorhandenen Tenor korrigieren oder fortschreiben |
| `/fälle` | synthetische Fälle beziehungsweise Archivhinweise durchsuchen |

Pfeiltasten ändern die Auswahl, Enter übernimmt sie. Backspace am Textanfang kann den Modus
wieder entfernen.

#### Rückfragen

Der Rückfragepfad erzeugt höchstens eine nächste fallbezogene Frage aus dem gesamten bisherigen
Kontext. Unterstützte Antwortarten sind:

- Ja/Nein für echte binäre Tatsachen
- Einzelauswahl mit zwei bis fünf Optionen und Freitextalternative
- Freitext
- Slider nur für tatsächlich begrenzbare tenortragende Zahlen oder Dauern

Jede Frage besitzt eine `topic_id`. Bereits beantwortete oder aus dem Kontext erkennbare Themen
werden entfernt. Ein Ähnlichkeitsvergleich blockiert paraphrasierte Wiederholungen. Ungültige,
irrelevante oder falsch typisierte Modellfragen werden nicht ungeprüft angezeigt.

Im aktuellen UE-Arbeitsstand ordnet die Tenorlogik den Verstoß zusätzlich einem Ast zu:

- **Ast A:** abstraktes, vollständig textlich beschreibbares Verhalten
- **Ast B:** konkretes visuelles oder interaktives Verhalten mit Bedienpfad
- **Ast C:** Klauselverbot mit wörtlichem Klauseltext

Wenn für die Bestimmtheit Informationen fehlen, liefert die API `needs_information` und benennt
die fehlenden Angaben. Sie soll dann keinen verkürzten Entwurf vortäuschen.

#### PDF-Verarbeitung

Ein PDF wird ausschließlich an das lokale Backend gesendet. `pypdf` extrahiert Text
seitenweise. Grenzen:

- maximal 10 MB
- maximal 100 Seiten
- maximal 40.000 extrahierte Zeichen
- maximal 60.000 Zeichen gesamter Modellkontext

Dateiname, Seitenzahl und Seitenmarker werden in den Kontext aufgenommen. Bildbasierte
Scan-PDFs werden nicht per OCR verarbeitet und mit sichtbarem Hinweis abgelehnt, wenn kein
maschinenlesbarer Text vorhanden ist.

#### UE-konforme Entwurfserzeugung

Der aktuelle Arbeitsbaum erzeugt genau einen vollständigen UE-Entwurf. Der Validator verlangt:

- exakter Beginn `…es zu unterlassen,`
- keine Urteilsformel wie `Die Beklagte wird verurteilt` oder `Es wird untersagt`
- keine Ordnungsgeld- oder Ordnungshaftformel
- nur Rechtsgrundlagen, die im Nutzereingang vorhanden waren
- bei Ast C wörtliche Übernahme des Klauseltexts
- bei Ast B Übernahme sichtbarer Beschriftungen und eines vorhandenen Anlagenbezugs
- unveränderte Fall-ID und unveränderten Schuldner
- `freigabe_durch_mensch: null`

Bis zu drei geeignete, geprüfte UE-Beispiele werden nach Ast, Fallgruppe und Textnähe ausgewählt.
Nicht geeignete oder nicht verifizierte Quellen dürfen den Modellinput nicht beeinflussen.

#### Entwurf überarbeiten

Ein archivierter Tenor kann geladen werden. Der Änderungswunsch wird unterhalb des Texts wie eine
Chatnachricht erfasst. Die neue Fassung wird erneut geprüft und als zusätzliche Archivfassung
gespeichert; Provenienz und vorherige Fassung bleiben erhalten.

#### 4.6.2 Strukturierte Maske

Die Maskenansicht führt durch feste Sachverhaltsfelder und erzeugt einen Backendentwurf. Sie
zeigt anschließend eine breite Prüf- und Bearbeitungsansicht. Die menschliche Entscheidung wird
getrennt gespeichert.

Der aktuelle Architekturstand hält aus Rückwärtskompatibilitätsgründen noch ältere
Strategiebezeichner wie `precise` und `neutral` lesbar. Neue UE-konforme Minimalentwürfe verwenden
`complete`.

#### 4.6.3 Modellwahl und Fallback

Die Modellwahl erfolgt ausschließlich im Backend:

1. OpenAI, wenn `OPENAI_API_KEY` gesetzt ist,
2. sonst Anthropic für den älteren Tenorentwurfspfad, wenn `ANTHROPIC_API_KEY` gesetzt ist,
3. sonst ein deterministischer, gekennzeichneter Demo-Fallback.

API-Schlüssel werden nicht an den Browser gesendet. Modellantworten werden gegen ein festes
Schema validiert. Ein Modell darf seine eigene Ausgabe nicht menschlich freigeben.

### 4.7 BeweisLab – Route `/beweis-labor`

Das BeweisLab ist die rein technische Erfassungsoberfläche.

#### Eingabe und Start

- Eingabefeld für eine öffentliche HTTP(S)-URL
- optionale Checkbox `Grey Mode`
- Startknopf
- gestreamter Prüfverlauf

Während des Laufs werden Eingabe, Modus und Startknopf gesperrt. Das Backend streamt
zeilenweise JSON-Nachrichten. Die UI zeigt Zeit, Schritt, Meldung und Erfolg/Warnung/Fehler.

#### Regulärer Modus

Der reguläre Modus:

- prüft und respektiert eine eindeutig untersagende `robots.txt`,
- nutzt den identifizierbaren Projekt-User-Agent,
- versucht zuerst einen direkten HTTP-Abruf,
- aktiviert einen transparenten Browserpfad nur im vorgesehenen Ablauf,
- umgeht keine Login-, Paywall-, CAPTCHA- oder fremden Schutzmechanismen.

Ist `robots.txt` nicht erreichbar, lesbar oder eindeutig auswertbar, darf die Erfassung
fortgesetzt werden. Der Zustand wird als `ungeprueft` mit Grund und Disclaimer dokumentiert und
nie als `geprueft_abruf_erlaubt` ausgegeben.

#### Grey Mode

Das Aktivieren bestätigt eine Berechtigungsgrundlage für Challenge-Infrastruktur sowie eigene,
synthetische oder anderweitig nachweislich autorisierte Ziele. Der Modus:

- erzwingt den Browsermodus,
- darf innerhalb des autorisierten Geltungsbereichs `robots.txt` ignorieren,
- wird in einem separaten Store-/Bundlepfad abgelegt,
- erzeugt `god_mode_authorization.json`,
- wird in UI, Manifest, PDF und ZIP technisch markiert,
- kann nicht als regulärer Ausgangsbeweis in die juristische Monitoringstrecke übernommen werden,
- startet keine KI-Analyse.

Auch Grey Mode erlaubt keine fremden Zugangsdaten, keine Überwindung von Logins oder Paywalls,
kein Lösen von CAPTCHAs, keine Schwachstellenausnutzung und keine Identitätstäuschung.

#### Prüfverlauf

Die Oberfläche kennt unter anderem folgende Schritte:

1. `fetch` – Seite direkt abrufen
2. `browser` – transparenter Browserabruf
3. `normalize` – Text bereinigen
4. `legal_pages` – AGB und Datenschutz suchen
5. `screenshot` – Seitenzustände erfassen
6. `compare` – technischen Stand einordnen
7. `anthropic` – im BeweisLab grundsätzlich übersprungen
8. `warc` – Webarchiv erzeugen
9. `manifest` – Hashliste erzeugen
10. `timestamp` – Zeitstempelversuch

#### Ergebnisanzeige

Nach Abschluss zeigt das BeweisLab:

- technischen Eignungshinweis
- ZIP-Download
- Screenshotgalerien nach Seitenrolle
- direkten AGB- und Datenschutz-Screenshot
- normalisierten Text nach Seitenrolle
- PDF-Druckfassungen expandierter Rechtstexte
- technische Details
- eine sichere Vorschau für Text, JSON, Bilder und PDF
- Download statt Inline-Anzeige für große Binärdateien

Lange Seiten können als Kachelserie angezeigt werden. Die UI bietet Vor/Zurück,
Kachelnummer und den Download des jeweiligen Originals.

#### Zuordnung zu einem Monitoringfall

Ein regulär geeigneter Beweis kann einem Fall derselben Domain zugeordnet werden.

- Hat der Fall noch keinen Ausgangsbeweis, wird der aktuelle Stand unveränderlich als Baseline
  verknüpft.
- Hat der Fall bereits einen Ausgangsbeweis, wird der aktuelle Stand technisch damit verglichen.
- Angefragter und tatsächlich erfasster Host müssen zur Fall-Domain oder einer erlaubten
  Subdomain passen.
- Grey-Mode-Pakete und technisch ungeeignete Aufnahmen werden abgewiesen.

Mögliche Vergleichsergebnisse:

- `technische_aenderung_erkannt`
- `unveraendert_fortbestehend`
- `pruefung_unvollstaendig`

Der Vergleich selbst ist noch keine juristische Kerngleichheitsentscheidung.

## 5. Technische Erfassung im Detail

### 5.1 URL- und Netzwerkschutz

Der HTTP-Fetcher akzeptiert nur öffentliche HTTP(S)-Ziele. Er blockiert:

- ungültige Schemes
- eingebettete Zugangsdaten
- lokale Hostnamen
- Loopback-, private, Link-Local- und andere nicht öffentliche IP-Adressen
- Redirects oder Unterressourcen auf solche Ziele

Die Zieladresse wird vor dem Abruf aufgelöst. Redirects werden erneut geprüft. Die
Produktkonfiguration verwendet standardmäßig zehn Sekunden Timeout und zwei Versuche; der
CLI-Befehl kann Timeout und Versuchszahl begrenzt überschreiben.

Der User-Agent lautet identifizierbar:

`MucLegal-Monitor/0.1 (+https://github.com/Alebabo/MucLegal; public-page compliance monitor)`

### 5.2 `robots.txt`

`robots.txt` wird vor HTTP- und Browserabruf geprüft. Auch neue Origins in Redirects und
Unterressourcen werden erfasst.

Mögliche Zustände:

- `geprueft_abruf_erlaubt`
- `untersagt`
- `ungeprueft`
- im Grey Mode technisch getrennt: Prüfung bewusst nicht maßgeblich

Eine eindeutige Untersagung beendet den regulären Abruf mit manueller Prüfanforderung. Ein 404
bedeutet, dass keine Regel gefunden wurde. Netzwerkfehler, 5xx-Antworten oder unlesbare Regeln
führen zu `ungeprueft`, nicht zu einem falschen Erlaubnisstatus.

### 5.3 Direkter HTTP-Abruf

Der direkte Pfad speichert:

- angefragte und finale URL
- UTC-Zeitpunkt
- HTTP-Status
- Redirectkette
- Response-Header
- unveränderte Responsebytes beziehungsweise Roh-HTML
- Zeichensatzdekodierung
- Fetchmodus
- Robots-Metadaten

401, 403, 407 und 429 werden als manuell prüfungsbedürftig behandelt. Schutz- und
Anmeldeseiten werden zusätzlich anhand des sichtbaren Dokuments, des Status und technischer
Merkmale erkannt. Bloße inaktive CAPTCHA-Skripte sollen keinen Schutzbefund auslösen.

### 5.4 Browsererfassung

Der Browserpfad verwendet Playwright und Chromium.

Transparenzmerkmale:

- `headless=True`
- Projekt-User-Agent
- `navigator.webdriver=true`
- kein Stealth-Paket
- kein Proxy
- kein persistentes Profil
- kein wiederverwendeter Storage-State
- frischer Browserkontext pro Zielseite
- keine übernommenen Clearance-Cookies

Direkt nach `domcontentloaded` werden nach Möglichkeit finale URL, Status, Redirectkette,
Titel, DOM, sichtbarer Text, Dokumentmaße und Browsermetadaten gesichert. Schließt Chromium
später unerwartet, bleiben diese Zwischenartefakte erhalten und der Lauf wird als Teilbefund
klassifiziert.

### 5.5 Cookie-/Consent-Behandlung

Vor einem Screenshot darf höchstens eine eindeutig datensparsame sichtbare Option betätigt
werden, zum Beispiel:

- `Alle ablehnen`
- `Nur notwendige`
- eine eindeutig gleichbedeutende Auswahl

Nie zulässig sind:

- `Alle akzeptieren`
- eine Einwilligung
- das Entfernen eines Overlays per CSS oder JavaScript
- ein generisches `Ablehnen` außerhalb eines eindeutig erkannten Consent-Kontexts

Buttontext, Klassifikation, Zeitpunkt und Ergebnis werden in den Interaktionsartefakten
gespeichert.

### 5.6 Rechtstextsuche

Das BeweisLab sucht getrennt nach:

- Allgemeinen Geschäftsbedingungen
- Datenschutzerklärung

Die Discovery berücksichtigt Links aus dem gespeicherten HTML und bekannte öffentliche
Standardpfade, etwa Shopify-Policy-Pfade. `discovered_url` und `captured_url` bleiben getrennt.
Eine bloße Rechtstextübersicht gilt nicht als Klauselbeweis. Wenn möglich, wird innerhalb
derselben Website die inhaltsreichste konkrete Klauselseite gewählt.

Ausklappbare Klauseln, Tabs und Akkordeons dürfen konservativ expandiert werden, damit der
bereits öffentlich bereitgestellte Text im DOM und in einer Druckfassung vollständig erfasst
wird. Die browsergenerierte PDF-Druckfassung ist als Ableitung gekennzeichnet und keine
Original-PDF der Website.

### 5.7 Schutzbefunde und Fallbacks

Wenn die Hauptseite eine Challenge oder einen anderen Seitenschutz zeigt, trennt das Paket:

- ursprünglich angefragte URL
- blockierte URL
- Schutzart
- tatsächlich erfasste öffentliche Ersatzseite
- Schutz-Screenshot
- geprüfte Rechtstextpfade
- verbleibende manuelle Grenze

Ein Schutzbild wird nicht als erfolgreicher Inhalt hinter dem Schutz ausgegeben. Falls ein
Browser nach einem bereits gespeicherten DOM-Zustand ausfällt, kann MucLegal ein beschriftetes
Bild aus dem gespeicherten HTML erzeugen. Dieses trägt eine Kennzeichnung wie
`http_snapshot_visualized` und ist keine pixelgetreue Live-Browseraufnahme.

### 5.8 Screenshotstrategie

MucLegal versucht zuerst einen echten Full-Page-Screenshot und validiert dessen Abmessungen und
Inhalt. Ist er ungültig, folgt eine Kachelserie:

- Kachelhöhe 2.000 CSS-Pixel
- dokumentierte Überlappung
- Reihenfolge und Y-Bereich je Kachel
- Pixelmaße und Skalierung
- SHA-256 je Datei
- Vollständigkeitsprüfung von 0 bis zur dokumentierten Seitenhöhe

Originale werden nicht verkleinert. Eine WebP-Vorschau ist ausdrücklich nur eine abgeleitete
UI-Datei.

### 5.9 Technische Ergebnisstufen

Jeder BeweisLab-Lauf erhält eine technische Eignung, keine Rechtsbewertung.

| Code | Aussage |
| --- | --- |
| `technisch_verwendbar` | wesentliche technische Artefakte regulär und vollständig vorhanden |
| `eingeschraenkt` | Erfassung vorhanden, aber einzelne Teile unvollständig oder Robots-Status ungeprüft |
| `hinweis` | Schutz-/Fehlerzustand dokumentiert, aber nicht als Inhaltsbeleg verwendbar |
| `nicht_erfassbar` | kein auswertbarer öffentlicher Seitenzustand vorhanden |

Die technische Verwendbarkeit garantiert keine rechtliche Verwertbarkeit.

## 6. Normalisierung, Hash und Änderungserkennung

### 6.1 Zweck der Normalisierung

Ein Roh-HTML-Hash würde sich durch Session-IDs, Cookiebanner, Werbeblöcke oder laufende
Countdowns ständig ändern. MucLegal erzeugt deshalb einen stabileren Vergleichstext.

### 6.2 Verarbeitung

Die Normalisierung umfasst:

- Zeichendekodierung
- Extraktion des Hauptinhalts mit `trafilatura`
- NFKC-Unicode-Normalisierung
- Vereinheitlichung von Leerraum und Zeilen
- eng begrenzte Include-/Exclude-CSS-Selektoren
- Entfernung profilierter flüchtiger Muster
- kanonische Textbildung
- SHA-256 über den normalisierten Text
- Versions- und Konfigurationshash des Normalisierers

Die CSS-Unterstützung ist absichtlich klein. Ein Include-Selektor muss genau einen Knoten
treffen. So bleibt der Normalisierungsweg reproduzierbar.

### 6.3 Baseline und Folgeabruf

Beim ersten kompatiblen Lauf entsteht `baseline_created`. Spätere Läufe vergleichen nur mit
Snapshots derselben Normalisiererversion, Selektorkonfiguration und desselben Fetchmodus.

Mögliche Ergebnisse:

- `baseline_created`
- `unchanged`
- `changed`
- `extraction_failed`

Bei identischem Hash endet der Golden Path ohne juristischen Modellaufruf.

### 6.4 Sicherheitsgates gegen fehlerhafte Extraktion

Eine Änderung darf nicht automatisch als Sachänderung gelten, wenn die Extraktion offenkundig
eingebrochen ist. Der Lauf fordert manuelle Prüfung an, wenn beispielsweise:

- nach einem zuvor langen Dokument weniger als 200 Zeichen übrig bleiben oder
- die Klauselzahl um mehr als 50 Prozent fällt.

### 6.5 Diff und Klauseln

Bei einer echten Änderung erzeugt MucLegal:

- Unified Text Diff
- vorherigen und aktuellen normalisierten Text
- Klauselblöcke
- Klausel-Hashes
- strukturelle Paarung alter und neuer Blöcke

Klauselblöcke werden in begrenzte, inhaltlich zusammenhängende Einheiten geteilt. Das dient der
Lokalisierung einer Änderung, nicht allein der rechtlichen Entscheidung.

## 7. Juristische Vorprüfung und Kerngleichheit

### 7.1 Eingangsdaten

Die Vorprüfung benötigt einen menschlich freigegebenen Tenor beziehungsweise ein strukturiertes
Tenorobjekt mit mindestens:

- Fall-ID und Schuldner
- Unterlassungstext
- charakteristischem Kern der Praxis
- `kerngleich_umfasst`
- `nicht_umfasst`
- Rechtsgrundlagen
- Fundstelle und tatsächlichem Änderungsausschnitt

### 7.2 Vierklassenprüfung

Klauselpaare werden in vier Klassen eingeordnet:

- `beseitigt`
- `kerngleich`
- `neuer_sachverhalt`
- `unsicher`

Der Output enthält nicht nur ein Ja/Nein, sondern Begründung, Confidence, Belegzitat und
Gegenargument. Ein wörtliches Zitat muss im gespeicherten Text auffindbar sein.

### 7.3 Modellreihenfolge und Fallback

- Anthropic Sonnet dient der Gesamtprüfung.
- Anthropic Haiku kann für Klauselpaar-/Vorfilteraufgaben verwendet werden.
- Ohne Netz beziehungsweise API-Schlüssel stehen deterministische Demo-Fixtures zur Verfügung.

Alle Aufrufe sind in `muclegal/llm/` gekapselt. Ungültige Antworten werden gespeichert, aber
nicht als Bewertung freigegeben. Schema- oder Zitatfehler führen zu `unsicher` beziehungsweise
einem sichtbaren Fehler, nicht zu einer stillen positiven Entscheidung.

### 7.4 Wissensbasis

Ein versionierter Wissensausschnitt ergänzt Modellinputs, ohne den eingefrorenen Systemprompt
zu verändern. Er enthält:

- zehn fachliche Leitlinien
- bis zu vier passende Fälle aus einem elf Fälle umfassenden Katalog
- sechzehn erkennbare Klauseltypen
- Status- und Datenlückenhinweise

Die Wissensbasis ist nutzerbereitgestellt und nicht automatisch juristisch freigegeben. Sie darf
keine neue Rechtsgrundlage erfinden und keine Rechtsnachfolge-, Konzern- oder
Vollstreckungsentscheidung automatisieren.

### 7.5 Aggregation und Mensch im Prozess

Mehrere Klauselbefunde werden auf Fallebene aggregiert. Die endgültige menschliche Entscheidung
bleibt separat:

- Modellbefund und Modellmetadaten sind append-only gespeichert.
- `freigabe_durch_mensch` bleibt bis zur bewussten Entscheidung `null`.
- Freigabe, Ablehnung und weitere Prüfung besitzen einen eigenen Zeitstempel.

### 7.6 Aktuelle Trennung der Orchestrierungen

Der Repository-Stand enthält zwei fachlich unterschiedliche Pfade:

1. den vollständigen Einzel-URL-Golden-Path mit Modellprüfung und vollständigem Beweispaket,
2. den fallbezogenen Domainmonitor mit Sitemap-/Linkprüfung und technischer Klassifikation.

Der Domainmonitor setzt seinen `anthropic`-Schritt aktuell auf `skipped`. Er darf deshalb nicht
als vollständige juristische Kerngleichheitsentscheidung dargestellt werden. Seine Stärke ist
die fallbezogene technische Coverage; der Einzel-URL-Pfad bleibt die vollständigere
Kerngleichheits- und Beweiskette.

## 8. Fallbezogener Domainmonitor

### 8.1 Startvoraussetzungen

- gültige `case_id`
- Fall existiert
- Fall ist menschlich freigegeben
- kein zweiter aktiver Lauf

Direkte URL und `case_id` dürfen nicht vermischt werden.

### 8.2 Prüfumfang

Der Domainmonitor prüft innerhalb eines festen Budgets:

- die gemeldete Fundstelle
- alle expliziten Pflicht-URLs des Fallprofils
- eine öffentliche Sitemap, soweit erreichbar
- priorisierte interne Links
- erkannte AGB-/Datenschutzseiten
- öffentliche PDF-Rechtstexte
- bei Elementfällen den gerenderten DOM-Zustand

Automatisch entdeckte Links bleiben in der Coverage sichtbar, gelten aber nicht allein deshalb
als Pflichtziel. Ein blockierter optionaler Navigationsfund darf einen ansonsten vollständigen
Fall nicht pauschal entwerten.

### 8.3 Coverage

`coverage.json` unterscheidet:

- erfolgreich geprüfte Pflichtziele
- optionale Discovery-Ziele
- blockierte oder fehlerhafte Ziele
- Elementprüfung
- Klauselabdeckung
- Schutz- und Browserfallbacks

Fehlt ein Pflichtziel, lautet das Ergebnis `pruefung_unvollstaendig`. Das System darf daraus
keine entlastende Aussage ableiten.

### 8.4 Elementprüfung

Elemente werden anhand sichtbarer und zugänglicher DOM-Eigenschaften gesucht. Geprüft werden
unter anderem:

- Text/Label und Alternativlabels
- Sichtbarkeit
- leichte Zugänglichkeit
- Linkziel oder erwartete Funktion
- zusätzliche Hürden im belegbaren Prüfpfad

Kann der DOM-Inspector nicht zuverlässig arbeiten, gilt die Elementprüfung als unvollständig.
Es gibt keine allgemeine Klickpfad-Automatisierung.

### 8.5 Mögliche Laufstatus

- `referenzzustand_dokumentiert`
- `unveraendert_fortbestehend`
- `beseitigt`
- `kerngleich_wiederaufgetreten`
- `neuer_sachverhalt`
- `unsicher`
- `pruefung_unvollstaendig`
- `failed`

Statusbezeichnungen mit rechtlicher Bedeutung dürfen nur im jeweils tatsächlich implementierten
und freigegebenen Prüfpfad verwendet werden. Bei Schutz, fehlender Coverage oder zu dünner
Extraktion ist `pruefung_unvollstaendig` maßgeblich.

## 9. Beweiskette und Artefakte

### 9.1 Primärartefakte

Je nach technischem Verlauf enthält ein Paket:

- Rohantwort beziehungsweise `raw-response.bin`
- Roh-HTML
- Response-Header
- initiales und nach Interaktion gespeichertes DOM
- sichtbaren Text in mehreren Zuständen
- normalisierten Text
- Klauselindex
- Haupt-, AGB- und Datenschutz-Screenshots
- Screenshotkacheln und Vorschau
- Browser- oder HTML-Druckfassungen
- WARC und CDX

### 9.2 Transparenzartefakte

- `capture_transparency.yaml`
- `screenshot_interactions.json`
- `capture-index.json`
- `page-artifacts-index.json`
- `capture-metrics.json`
- `legal-pages.json`
- `protection-report.json`
- `run-result.json`
- technische Eignungsbewertung
- im Grey Mode zusätzlich `god_mode_authorization.json`

### 9.3 Vergleichs- und Analyseartefakte

- vorheriger normalisierter Text
- Unified Diff
- Modellinput und validierter Modelloutput
- Klauselpaar-Inputs und Vierklassen-Outputs

Diese Analysedateien sind im BeweisLab-UI bewusst nicht als primäre technische Beweise
prominent sichtbar.

### 9.4 WARC/CDX

Der produktive Pfad erzeugt ein WARC aus den exakt gespeicherten Bytes und validiert es mit
`warcio`. Primärsnapshot und WARC tragen getrennte Payload-Hashes. Nur bei Bytegleichheit wird
`capture_relation: exact_payload` ausgewiesen.

Der zusätzliche GNU-Wget-Re-Capture-Test ist unter einzelnen Wget-Versionen sporadisch von
Digestfehlern in Metadata-/Resource-Records betroffen. Dieser Flake darf nicht als erfolgreicher
Produktionsnachweis ausgegeben werden.

### 9.5 Manifest

Das SHA-256-Manifest verknüpft alle vorhandenen Dateien mit:

- relativem Pfad
- Größe
- SHA-256
- Rolle beziehungsweise Artefakttyp

Transparenz- und Interaktionsdateien werden vor der Manifestbildung geschrieben. Eine spätere
Änderung wird dadurch erkennbar. Die Anwendung bietet eine Manifestprüfung an.

### 9.6 RFC-3161-Zeitstempel

Der Manifest-Digest kann über einen RFC-3161-Dienst gestempelt werden. Gespeichert werden:

- Zeitstempelanfrage
- Zeitstempelantwort
- Verifikationsstatus
- Fehler- oder Offlinegrund

Ein Ausfall von freeTSA entwertet lokale Primärbeweise nicht. Er bleibt als Warnung offen.

### 9.7 Wayback Save Page Now

Wayback ist ein optionaler Zusatzdienst. Mit gesetzten Zugangsdaten kann ein Save-Page-Now-
Versuch erfolgen. Ohne `WAYBACK_ACCESS_KEY` und `WAYBACK_SECRET_KEY` wird sofort
`not_configured` dokumentiert.

Ein Wayback-Ausfall ist kein Verlust der lokalen Beweiskette. Replay-URLs werden bei der
Domainzuordnung auf ihre eingebettete Original-URL geprüft; URLs mit eingebetteten
Benutzerinformationen werden nicht als Beweis für die Originaldomain akzeptiert.

### 9.8 PDF-Bericht und ZIP

Der PDF-Bericht fasst Aufnahme, Integrität, technische Grenzen und offene menschliche Prüfung
lesbar zusammen. Das ZIP enthält das vollständige, pfadsicher ausgewählte lokale Paket.

Downloads und Vorschauen werden nur über kontrollierte lokale Endpunkte ausgeliefert. Ein
Artefaktpfad darf nicht auf ein anderes Paket oder aus dem Store heraus zeigen.

## 10. Persistenz und Datenintegrität

### 10.1 Speicherorte

Standardmäßig:

- `.muclegal-ui/reviews.sqlite3` für Entscheidungen und Archive
- `.muclegal-ui/` für Läufe, Fälle und Beweispakete
- getrennte Unterverzeichnisse für reguläre und Grey-Mode-Pakete

Der Pfad kann serverseitig über `MUCLEGAL_STORE` überschrieben werden.

### 10.2 SQLite

SQLite speichert unter anderem:

- Monitoringfälle
- menschliche Fallentscheidungen
- Tenorentwürfe und Entscheidungen
- Tenorarchiv
- Snapshots
- Klauseln
- Modellbefunde
- menschliche Befundfreigaben
- Beweispakete und Status

Für rechtlich relevante Befunde und Beweispakete bestehen Append-only-Regeln. Bestehende
Ausgangsbeweise werden nicht still überschrieben.

### 10.3 Lokale Dateiablage

Rohdaten, Screenshots, WARC, PDF und ZIP bleiben lokal. Sie werden nicht automatisch zu einem
Fremdspeicher hochgeladen. Der Browser erhält keine direkten Dateisystempfade, sondern nur
pfadsichere Download- und Vorschauendpunkte.

## 11. REST-API

Die dokumentierte API liegt unter `/api/v1/`. Einzelne ältere `/api/...`-Aliase bleiben für
Kompatibilität vorhanden. Die lokale OpenAPI-Oberfläche liegt unter `/api/v1/docs`.

### 11.1 Tenor- und PDF-Endpunkte

| Methode | Pfad | Funktion |
| --- | --- | --- |
| `POST` | `/api/v1/tenor-drafts` | schema-validierten Backendentwurf speichern |
| `POST` | `/api/v1/tenor-drafts/{draft_id}/review` | menschliche Tenorentscheidung speichern |
| `POST` | `/api/v1/tenor-proposals` | aktuellen UE-Vorschlag oder fehlende Angaben liefern |
| `POST` | `/api/v1/tenor-questions` | nächste kontextbezogene Rückfrage erzeugen |
| `POST` | `/api/v1/tenor-pdf-text` | Text aus lokal übertragenem PDF extrahieren |
| `POST` | `/api/v1/tenor-archive` | übernommene Tenorfassung speichern |
| `GET` | `/api/v1/tenor-archive` | Tenorarchiv auflisten |

### 11.2 Monitoringfall-Endpunkte

| Methode | Pfad | Funktion |
| --- | --- | --- |
| `POST` | `/api/v1/cases` | bekannten Erstverstoß als Monitoringfall anlegen |
| `GET` | `/api/v1/monitoring-cases` | alle Monitoringfälle auflisten |
| `GET` | `/api/v1/monitoring-cases/{case_id}` | einzelnen Monitoringfall lesen |
| `POST` | `/api/v1/cases/{case_id}/review` | Fall freigeben, ablehnen oder weiter prüfen |
| `POST` | `/api/v1/cases/{case_id}/baseline-evidence` | Ausgangsbeweis zuordnen |
| `POST` | `/api/v1/cases/{case_id}/evidence-comparisons` | neuen Beweis technisch vergleichen |

### 11.3 Lauf-Endpunkte

| Methode | Pfad | Funktion |
| --- | --- | --- |
| `POST` | `/api/v1/runs` | freigegebenen fallbezogenen Lauf starten |
| `GET` | `/api/v1/runs/{run_id}` | Laufstatus abfragen |
| `POST` | `/api/v1/evidence-runs` | direkte BeweisLab-Erfassung starten |
| `POST` | `/api/v1/evidence-runs/stream` | direkte Erfassung mit JSON-Stream starten |
| `GET` | `/api/v1/evidence-runs/{run_id}` | BeweisLab-Laufstatus lesen |

### 11.4 Fall-, Vorschau- und Download-Endpunkte

| Methode | Pfad | Funktion |
| --- | --- | --- |
| `GET` | `/api/v1/cases` | technische Beweisfälle und getrennte Grey-Mode-Liste |
| `GET` | `/api/v1/cases/{case_id}` | Falldetail mit Artefaktmetadaten |
| `GET` | `/api/v1/cases/{case_id}/preview/{label}` | sichere Textvorschau |
| `GET` | `/api/v1/cases/{case_id}/capture/{role}/preview` | Bildvorschau nach Rolle |
| `GET` | `/api/v1/cases/{case_id}/capture/{role}/tiles/{index}` | Screenshotkachel |
| `GET` | `/api/v1/cases/{case_id}/capture/{role}/originals/{index}` | Originalbild |
| `GET` | `/api/v1/cases/{case_id}/capture/{role}/documents/{index}` | PDF-Druckfassung |
| `GET` | `/api/v1/cases/{case_id}/capture/{role}/normalized-text` | normalisierter Rollentext |
| `GET` | `/api/v1/cases/{case_id}/capture/{role}/raw-html` | gespeichertes Rollen-HTML |
| `GET` | `/api/v1/cases/{case_id}/download` | ZIP-Paket erzeugen und laden |

### 11.5 Wichtige API-Regeln

- unbekannte Zusatzfelder werden abgewiesen (`extra="forbid"`)
- Texte werden getrimmt und längenbegrenzt
- Fall- und Lauf-IDs werden pfadsicher validiert
- direkte URL-Läufe und fallbezogene Läufe sind getrennt
- ein zweiter aktiver Lauf wird abgewiesen
- Grey Mode ist nur bei direkter URL-Erfassung zulässig
- menschliche Freigabe wird serverseitig erzwungen
- Fehlerdetails werden für die UI auf sichere, begrenzte Meldungen reduziert

### 11.6 HTML- und Kompatibilitätsrouten

Neben der versionierten API existieren einige ältere oder serverseitig gerenderte Routen. Sie
sind für die aktuelle React-Oberfläche nicht der bevorzugte Vertrag, bleiben aber Teil des
ausführbaren Prototyps.

| Methode | Pfad | Funktion |
| --- | --- | --- |
| `GET` | `/` am FastAPI-Port | ältere Jinja-Ein-Seiten-Ansicht für Fall und Human Review |
| `GET` | `/beweis-labor` | serverseitig gerenderte BeweisLab-Oberfläche |
| `POST` | `/tenor-draft` | älterer Formularpfad für Tenorentwürfe |
| `POST` | `/tenor-review` | älterer Formularpfad für Tenorentscheidungen |
| `POST` | `/review` | ältere menschliche Befundentscheidung |
| `GET` | `/artifact/{label}` | Artefakt des zuletzt geladenen Falls |
| `GET` | `/artifact/{case_id}/{label}` | Artefakt eines archivierten Beweisfalls |
| `GET` | `/favicon.ico` | leerer kompatibler Favicon-Endpunkt |

Zusätzlich spiegeln mehrere unversionierte `/api/...`-Pfade ihre `/api/v1/...`-Entsprechung,
zum Beispiel Runs, Fälle, Vorschauen und Tenorentwürfe. Neue Cliententwicklung soll
ausschließlich die versionierten Routen verwenden.

Wird nur FastAPI auf Port 8000 gestartet, zeigt `/` daher die ältere Jinja-Ansicht. Das aktuelle
Dashboard unter `/` gehört zum React-Frontend auf Port 4173 beziehungsweise zur gemeinsamen
Deployment-URL, die Frontend und Backend passend routet.

## 12. Kommandozeilenfunktionen

Der Einstiegspunkt lautet `muclegal` beziehungsweise `python -m muclegal`.

### 12.1 `check`

Prüft eine einzelne URL mit einem Normalisierungsprofil.

```powershell
python -m muclegal check `
  --url https://example.com/ `
  --profile fixtures/public-smoke-profile.json `
  --store .muclegal `
  --screenshot
```

Optionen:

- `--url`
- `--profile`
- `--store`
- `--timeout`
- `--attempts`
- `--screenshot`

Die JSON-Ausgabe enthält unter anderem aktuellen und vorherigen Hash, Snapshot-IDs, Diffpfad,
Klauselzahl, Extraktionsqualität, Fetchmodus und `needs_review`.

### 12.2 `demo`

Führt den vollständigen Golden Path mit lokalen Fixtures aus.

```powershell
python -m muclegal demo --case kerngleich --store .muclegal-demo
python -m muclegal demo --case nicht-umfasst --store .muclegal-demo
```

Verfügbare Fälle:

- `kerngleich`
- `nicht-umfasst`

Optional kann ein PDF-Berichtspfad angegeben werden.

### 12.3 `eval`

Führt die versionierte Eval-Suite aus.

```powershell
python -m muclegal eval --suite fixtures/eval-suite.json --output output/eval
python -m muclegal eval --suite fixtures/eval-suite.json --output output/eval-live --live
```

Erzeugt:

- `eval-results.json`
- `eval-report.md`

Gemessen werden Schema, erwartete Klasse, Begründung, Gegenargument, Human-Release-Gate sowie
Promptversion und Prompt-Hash. Offline-Fixtures prüfen Determinismus und Verkabelung, nicht die
reale Modellgüte.

### 12.4 `blind-review`

Erzeugt getrennt randomisierte Prüfbögen für zwei Juristinnen, ohne Erwartungswerte und
Modellantworten offenzulegen.

```powershell
python -m muclegal blind-review --suite fixtures/eval-suite.json --output output/legal-review
```

### 12.5 `diagnose-capture`

Prüft Browserlebenszyklus, Ressourcenmessung und synthetische Capture-Szenarien.

```powershell
python -m muclegal diagnose-capture --output output/capture-diagnose
```

Mit `--real` wird zusätzlich die definierte reale Matrix streng sequenziell ausgeführt. Der
Befehl ist opt-in, weil reale Abrufe externe Systeme betreffen.

## 13. Konfiguration und Betrieb

### 13.1 Abhängigkeiten

- Python 3.11 oder neuer
- FastAPI und Uvicorn
- Jinja2
- Playwright/Chromium
- trafilatura und lxml
- Pillow
- psutil
- warcio
- reportlab und pypdf
- optional Anthropic- und OpenAI-SDK

Frontend:

- React 19
- TanStack Start/Router/Query
- TypeScript
- Tailwind CSS
- Radix-basierte UI-Komponenten

### 13.2 Umgebungsvariablen

Wesentliche Variablen:

- `MUCLEGAL_STORE`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `WAYBACK_ACCESS_KEY`
- `WAYBACK_SECRET_KEY`
- optional `MUCLEGAL_OPENAI_TENOR_MODEL`
- im Frontend optional `MUCLEGAL_API_ORIGIN`

`app.py` lädt die lokale `.env` mit `override=True`, damit ein projektspezifischer Schlüssel
einen veralteten geerbten Prozesswert ersetzt. Geheimnisse gehören nie in Browsercode, URLs,
Logs oder das Repository.

### 13.3 Lokaler Start

Backend:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

Der React-Fallmonitor läuft auf Port 4173. `/beweis-labor` wird an das lokale FastAPI-Backend
weitergeleitet.

### 13.4 Lokale BeweisLab-Helfer

```powershell
powershell -ExecutionPolicy Bypass -File scripts/doctor-local-beweislab.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-local-beweislab.ps1
```

Der Doctor prüft die lokale Laufzeit. Der Start bindet standardmäßig nur an `127.0.0.1`.

### 13.5 Temporäre Demo

Eine zeitlich begrenzte ngrok- oder Hetzner-Demo ist nur nach ausdrücklicher Anweisung
vorgesehen. Dabei gelten:

- isolierter Demo-Store
- nur synthetische oder öffentliche Daten
- Schlüssel ausschließlich serverseitig
- soweit verfügbar Zugriffsschutz
- Tunnel nach der Demo beenden
- keine dauerhafte externe Artefaktablage

## 14. Modulübersicht

| Modul/Pfad | Hauptfunktion |
| --- | --- |
| `app.py` | Konfiguration, Adapterwahl und FastAPI-App-Aufbau |
| `muclegal/ui.py` | REST-API, Run-Koordination, Archiv- und Downloadendpunkte |
| `muclegal/live.py` | direkter Golden Path und BeweisLab-Orchestrierung |
| `muclegal/domain_monitor.py` | fallbezogene Domain-/Coverage-Prüfung |
| `muclegal/monitoring_cases.py` | Monitoringfalldaten, Freigaben und Beweisverknüpfung |
| `muclegal/pipeline.py` | Abruf, Normalisierung, Hash, Diff und Snapshotstatus |
| `muclegal/fetch/http.py` | konservativer HTTP-Abruf, Robots- und Netzwerkschutz |
| `muclegal/fetch/playwright.py` | Browsercapture, DOM, Screenshots, PDF und Elementprüfung |
| `muclegal/fetch/consent.py` | datensparsame Cookie-Aktion |
| `muclegal/normalize/core.py` | Extraktion und deterministische Normalisierung |
| `muclegal/normalize/clauses.py` | Klauselsplit, Hashes und Paarung |
| `muclegal/storage/repository.py` | SQLite-Snapshots, Befunde und Append-only-Integrität |
| `muclegal/llm/analyzer.py` | Gesamtprüfung und Modellinput |
| `muclegal/llm/clause_analysis.py` | Vierklassenprüfung pro Klauselpaar |
| `muclegal/llm/classification.py` | strikte Klassifikationsvalidierung |
| `muclegal/llm/schema.py` | juristisches Ergebnisschema |
| `muclegal/llm/tenor.py` | UE-/Tenorinput, Modelle, Validator und Vorschlag |
| `muclegal/llm/tenor_questions.py` | kontextbezogene Rückfragen |
| `muclegal/llm/tenor_examples.py` | verifizierbares UE-Beispielregister und Auswahl |
| `muclegal/llm/monitor_knowledge.py` | versionierter Wissensausschnitt |
| `muclegal/evidence/warc.py` | WARC/CDX-Erzeugung und Validierung |
| `muclegal/evidence/manifest.py` | Hashmanifest und Integritätsprüfung |
| `muclegal/evidence/timestamp.py` | RFC-3161-Anfrage und Verifikation |
| `muclegal/evidence/wayback.py` | optionales Save Page Now |
| `muclegal/evidence/report.py` | PDF-Prüfbericht |
| `muclegal/evidence/suitability.py` | technische Beweiseignung |
| `muclegal/evaluation.py` | Eval-Suite und Qualitätsgates |
| `muclegal/legal_review.py` | verblindete Prüfbögen |
| `muclegal/diagnostics.py` | Browser- und Ressourcen-Diagnose |
| `muclegal/cli.py` | Kommandozeilenoberfläche |
| `frontend/src/routes/` | Dashboard, Hinweise, Archiv, Intake, Tenorhilfe |
| `muclegal/templates/evidence_lab.html` | BeweisLab-Oberfläche und Artefaktviewer |

## 15. Sicherheits- und Rechtsgrenzen

### 15.1 Verbotene beziehungsweise nicht unterstützte Aktionen

- fremde Logins überwinden
- Paywalls umgehen
- CAPTCHAs lösen
- fremde Zugangsdaten verwenden
- Schwachstellen ausnutzen
- Identität oder Browserautomatisierung verschleiern
- persistente Nutzerprofile oder Clearance-Cookies übernehmen
- Primärbeweise über fremde Extraktions-APIs leiten
- Screenshotinhalt per Vision-KI bewerten
- ohne Menschen eine rechtliche Freigabe erteilen

### 15.2 Bewusste Nicht-Ziele

- Login und Benutzerverwaltung
- Rollen und Multi-Tenancy
- großes Multi-View-Dashboard
- Postgres, ORM oder Docker-Compose-Stack
- autonome Rechtsentscheidung
- allgemeine Klickpfad-Automatisierung
- vollautomatische Erstverstoßsuche
- OCR für gescannte PDFs
- produktionsreifer Scheduler-Daemon

### 15.3 Kanäle außerhalb der technischen Abdeckung

Newsletter, Apps, geschlossene Checkouts, Hotlines, Social-Media-Accounts und andere nicht
öffentlich erreichbare Zustände sind nur erfassbar, wenn sie als autorisierte, technisch
zugängliche Belege vorliegen. Das System darf eine nicht geprüfte Fläche nicht als unauffällig
bewerten.

## 16. Bekannte Grenzen und ehrliche Produktdarstellung

1. **Hackathon-Prototyp:** Code und Oberfläche sind auf einen funktionierenden Golden Path
   optimiert, nicht auf vollständigen Produktbetrieb.
2. **Kein dauerhafter Scheduler:** Wiederholte Läufe sind möglich, aber ein verlässlicher
   täglicher Scheduler ist nicht Teil des aktuellen Kernsystems.
3. **Keine URL-/Tagesquote:** Läufe sind seriell, aber es besteht keine persistente harte Grenze
   von genau einem Abruf je URL und Kalendertag.
4. **Domainmonitor ohne juristisches LLM:** Er dokumentiert technische Coverage, ersetzt aber
   nicht die vollständige Vierklassenprüfung des Golden Paths.
5. **Externe Grenzen:** Cloudflare, JavaScript-Challenges, Browserabbrüche, freeTSA und Wayback
   können ausfallen. Das System dokumentiert die Grenze, umgeht sie aber nicht.
6. **Wget-Flake:** Der separate GNU-Wget-WARC-Test kann versionsabhängige Digestfehler zeigen.
7. **Tenorbeispiele:** Referenzen und Wissensdaten sind nicht automatisch juristisch
   freigegeben. Nicht verifizierte Beispiele dürfen nicht als Goldstandard erscheinen.
8. **Tenor-UI im Übergang:** Neue UE-konforme Einzelausgabe und ältere Archivstrategien bestehen
   vorübergehend nebeneinander. Historische Einträge bleiben lesbar.
9. **Kein Visionverständnis:** Ein Screenshot belegt Pixel, wird aber nicht semantisch durch ein
   Modell interpretiert.
10. **Technischer Beleg ist kein Rechtsbeweisurteil:** Vollständigkeit, Authentizität und
    Integrität unterstützen die menschliche Bewertung, ersetzen sie nicht.

## 17. Tests und Verifikation

### 17.1 Backend

```powershell
python -m compileall -q muclegal app.py
python -m pytest -q
```

Die Tests decken unter anderem ab:

- stabile Normalisierung und Hashes
- Countdown-, Cookie- und Werberauschen
- relevante Änderungen und Diffs
- Netz-, HTTP-, Robots-, Login- und CAPTCHA-Grenzen
- Playwright-Capture und Browserabbrüche
- Consent-Ablehnung ohne Zustimmung
- Rechtstextauswahl und expandierte Klauseln
- WARC, Manifest, Timestamp und PDF
- technische Beweiseignung
- Fallaufnahme, Freigabe und Runs
- Beweisbaseline und Vergleich
- Tenor- und LLM-Schemata
- Eval-Gates und Human-Release
- API- und UI-Verträge

### 17.2 Frontend

```powershell
Set-Location frontend
npm run test:minimal
npm run typecheck
npm run lint
npm run build
```

### 17.3 Manueller Smoke-Test

Mindestens zu prüfen:

1. Backend und Frontend starten.
2. `/beweis-labor` öffnen.
3. `https://example.com` regulär erfassen.
4. Prüfverlauf, Eignung, Screenshots, normalisierten Text und technische Details öffnen.
5. ZIP laden und Manifest prüfen.
6. synthetischen Consent-Dialog mit `Alle ablehnen` testen.
7. sicherstellen, dass `Alle akzeptieren` nie betätigt wurde.
8. Fall anlegen, menschlich freigeben und Monitoringlauf starten.
9. Ausgangsbeweis zuordnen und einen Vergleich ausführen.
10. Tenorhilfe einschließlich PDF-Grenzen, Rückfragen, Archiv und Überarbeitung prüfen.

## 18. Empfohlener Demoablauf

Für eine verständliche Hackathon-Demo bietet sich diese Reihenfolge an:

1. Auf dem Dashboard das Problem „Verstoß wandert“ erklären.
2. Unter `Neu hinzufügen` einen bereits bekannten Verstoß erfassen.
3. Unter `Hinweise` die zwingende menschliche Freigabe zeigen.
4. Im BeweisLab eine öffentliche oder synthetische URL technisch erfassen.
5. Screenshot, normalisierten Text, WARC, Manifest und PDF öffnen.
6. Den technischen Stand als Ausgangsbeweis mit dem Fall verknüpfen.
7. Einen geänderten Stand erfassen und technisch vergleichen.
8. Die klickbare Änderungsbenachrichtigung im Fallmonitor öffnen.
9. Kerngleichheitsbegründung, Gegenargument und Unsicherheit zeigen.
10. Abschließend hervorheben, dass `freigabe_durch_mensch` bis zur Entscheidung leer bleibt.

## 19. Zusammenfassung der Kernversprechen

MucLegal bietet im aktuellen Prototyp:

- strukturierte Aufnahme eines bekannten Erstverstoßes
- zwingende menschliche Fallfreigabe
- sichere Erfassung öffentlicher Webseiten
- transparente Robots-, Browser- und Consent-Regeln
- reproduzierbare Normalisierung und Hashvergleiche
- klauselscharfe Änderungslokalisierung
- schema-validierte juristische Vorprüfung im Golden Path
- ausdrückliche `nicht_umfasst`-Abgrenzung
- lokale WARC-/Manifest-/Timestamp-/PDF-Beweiskette
- technische Eignungsbewertung ohne juristische Überdehnung
- Baseline-Zuordnung und technischen Beweisvergleich
- Tenorschreibhilfe mit Referenzen, Rückfragen und versioniertem Archiv
- Offline-Demo, Eval, Blind Review und Diagnosetools

Das wichtigste Sicherheitsversprechen bleibt: **Kein juristischer Befund und kein Tenor wird
allein durch ein Modell wirksam freigegeben.**
