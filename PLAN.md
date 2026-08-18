# MucLegal – Umsetzungsplan

## Ziel

In zwei Bautagen entsteht ein durchgängiger, vorführbarer Golden Path:

1. Eine öffentliche Webseite wird rechtmäßig abgerufen.
2. Relevanter Text wird deterministisch normalisiert und gehasht.
3. Eine echte inhaltliche Änderung wird von flüchtigem Seitenrauschen unterschieden.
4. Ein Sprachmodell bewertet die Änderung anhand eines vorgegebenen Unterlassungstenors.
5. Die Beweismittel werden nachvollziehbar archiviert und für die menschliche Freigabe angezeigt.

Das System trifft keine abschließende juristische Entscheidung. Jede Bewertung bleibt bis zur Prüfung bei `freigabe_durch_mensch: null`.

## Verbindliche Leitplanken

- Nur öffentlich erreichbare Seiten abrufen; `robots.txt` und angemessene Abrufraten beachten.
- Keine Logins, Paywalls, CAPTCHAs oder sonstigen Schutzmaßnahmen umgehen.
- Rohdaten und Beweismittel selbst speichern; externe Dienste nur ergänzend verwenden.
- Gleicher relevanter Input muss byteidentischen normalisierten Output und denselben SHA-256-Hash ergeben.
- Keine Abhängigkeit übernehmen, wenn die benötigte Funktion in ungefähr 30 verständlichen Zeilen stabil nachgebaut werden kann.
- Kein automatischer Vollzug: Das Ergebnis ist eine Entscheidungshilfe für einen Menschen.

## Vorbereitung – maximal 1 Stunde

- [x] Das GitHub-Repository `https://github.com/Alebabo/MucLegal.git` als Arbeitsverzeichnis klonen oder den bestehenden Ordner korrekt mit dem Remote verbinden.
- [x] Python 3.11+ und eine minimale Projektstruktur einrichten.
- [x] Eine kontrollierbare öffentliche Demo-URL oder lokale HTTP-Fixture festlegen.
- [x] Drei HTML-Fixtures anlegen: unverändert, nur flüchtiges Rauschen geändert, rechtlich relevante Aussage geändert.
- [x] Entscheidungen aus [`reference/FINDINGS.md`](reference/FINDINGS.md) als verbindliche technische Grundlage verwenden.

## Zielstruktur

```text
muclegal/
  fetch/          # HTTP- und optional Playwright-Abruf
  normalize/      # Extraktion, Nachbereinigung, stabiler Text
  storage/        # Snapshots, Metadaten, SQLite
  llm/            # strukturierte juristische Vorprüfung
  evidence/       # WARC, Manifest, Zeitstempel, PDF
tests/
fixtures/
app.py            # eine kleine Prüf- und Freigabeansicht
```

## Bautag 1 – Abruf, Normalisierung und Änderungserkennung

### 1. Abruf und Rohdaten sichern

- [x] HTTP-Abruf mit festem, identifizierbarem User-Agent, Timeout und begrenzten Wiederholungen implementieren.
- [x] URL, Abrufzeitpunkt, Statuscode, Response-Header und unverändertes HTML speichern.
- [x] Playwright nur als klar getrennten Fallback für öffentlich sichtbare, clientseitig gerenderte Inhalte vorsehen.
- [x] Bei CAPTCHA, Login oder Blockseite abbrechen und den Vorgang als manuell zu prüfen markieren.

### 2. Deterministische Normalisierung

- [x] `trafilatura` in einer fest gepinnten Version verwenden.
- [x] Extraktion fest konfigurieren: Textausgabe, Präzision bevorzugen, keine Kommentare, keine Links/Bilder/Metadaten, Tabellen behalten, interne Deduplizierung deaktivieren.
- [x] Vor der Extraktion nur explizit konfigurierte Störelemente über CSS-Selektoren entfernen, etwa Cookie-Banner oder bekannte Navigation.
- [x] Nach der Extraktion Zeilenenden, Unicode und überflüssige Leerzeichen deterministisch vereinheitlichen.
- [x] Nur bekannte flüchtige Werte innerhalb eng begrenzter Selektoren durch typisierte Marker ersetzen, zum Beispiel einen Countdown durch `[COUNTDOWN]`.
- [x] Keine globalen Regeln verwenden, die Preise, Datumsangaben, Verfügbarkeiten oder Werbeaussagen entfernen könnten.
- [x] Den normalisierten UTF-8-Text mit SHA-256 hashen.

### 3. Snapshots und Vergleich

- [x] Snapshot-Metadaten in SQLite speichern; große Artefakte als Dateien ablegen.
- [x] Hash, vorherigen Hash, Pfade zu Rohdaten und normalisiertem Text sowie Zeitpunkte verknüpfen.
- [x] Bei identischem Hash keine LLM-Prüfung starten.
- [x] Bei verändertem Hash einen verständlichen Text-Diff erzeugen und zur nächsten Stufe weitergeben.

### Abnahme Bautag 1

- [x] Zwei Läufe mit identischem HTML erzeugen denselben normalisierten Text und denselben Hash.
- [x] Ein veränderter Countdown erzeugt weiterhin denselben Hash.
- [x] Eine veränderte rechtlich relevante Werbeaussage erzeugt einen neuen Hash und einen passenden Diff.
- [x] Alle drei Fälle sind durch automatisierte Tests mit lokalen Fixtures belegt.
- [x] Ein kompletter Abruf kann ohne LLM und ohne UI über einen einzelnen Befehl ausgeführt werden.

## Bautag 2 – Juristische Vorprüfung, Beweiskette und Demo

### 4. Strukturierte LLM-Vorprüfung

- [x] Einen synthetischen Unterlassungstenor und zwei klar beschriftete Demo-Fälle verwenden: `kerngleich_umfasst` und `nicht_umfasst`.
- [x] Nur Tenor, relevanten Vorher-/Nachher-Ausschnitt und belegte Metadaten an das Modell senden.
- [x] Ein festes JSON-Schema erzwingen, mindestens mit Ergebnis, Begründung, Tatsachenbasis, Norm-/Zitatstatus, Gegenargument, Unsicherheit und `freigabe_durch_mensch`.
- [x] Prompt-Regeln umsetzen: Ergebnis zuerst; Tatsachen, Rechtsquelle und Schlussfolgerung trennen; stärkstes Gegenargument nennen; ungeprüfte Fundstellen ausdrücklich markieren.
- [x] Modellantwort strikt validieren. Ungültige oder fehlende Antworten werden gespeichert, aber nicht als Bewertung ausgegeben.
- [x] Einen Offline-Demomodus mit gespeicherten, klar als Fixture gekennzeichneten Antworten vorsehen.

### 5. Beweiskette

- [x] Mit GNU Wget ein WARC samt CDX für die statische Demo-Seite erzeugen.
- [x] Das WARC mit `warcio check` validieren.
- [x] Ein Manifest mit SHA-256-Hashes aller wesentlichen Artefakte erzeugen: Roh-HTML, Header, normalisierter Text, Diff, Modellinput und Modelloutput.
- [x] Den Manifest-Hash über OpenSSL per RFC 3161 stempeln und das Token anschließend lokal verifizieren.
- [x] Aktuelles TSA-Zertifikat und CA-Kette zusammen mit der Verifikation dokumentieren.
- [x] Wayback Save Page Now nur als optionale, nicht beweisentscheidende Zusatzquelle verwenden.
- [x] Einen kleinen, lesbaren Prüfbericht als PDF erzeugen.

### 6. Ein-Seiten-Demo

- [x] Eine minimale FastAPI/Jinja- oder Streamlit-Ansicht bauen.
- [x] Auf einer Seite anzeigen: URL, letzter Abruf, Status, Vorher/Nachher-Diff, Modellbewertung, Unsicherheit, Beweisartefakte und Zeitstempelstatus.
- [x] Eine menschliche Entscheidung `freigegeben`, `abgelehnt` oder `weitere Prüfung` erfassen.
- [x] Automatische Bewertung und menschliche Freigabe optisch und in den Daten klar trennen.

### Abnahme Bautag 2

- [x] Der Golden Path läuft vom Abruf bis zum Prüfbericht ohne manuelle Dateibearbeitung durch.
- [x] Beide juristischen Demo-Fälle liefern schema-valide, nachvollziehbare Ergebnisse.
- [x] Das WARC ist valide und sämtliche Manifest-Hashes lassen sich erneut berechnen.
- [x] Der RFC-3161-Zeitstempel wird lokal erfolgreich verifiziert.
- [x] Die UI zeigt keinen Fall als endgültig entschieden, solange keine menschliche Freigabe vorliegt.
- [x] Die Demo funktioniert auch dann nachvollziehbar, wenn LLM, freeTSA oder Wayback kurzfristig nicht erreichbar sind.

## Testmatrix

| Fall | Erwartung |
|---|---|
| Identisches HTML zweimal | gleicher normalisierter Text, gleicher Hash, kein LLM-Aufruf |
| Nur Countdown geändert | gleicher Hash |
| Cookie-Banner hinzugefügt | gleicher Hash, sofern der konfigurierte Selektor greift |
| Preis oder Werbeaussage geändert | neuer Hash und sichtbarer Diff |
| HTTP-Fehler oder Timeout | nachvollziehbarer Fehlerstatus, kein alter Inhalt als neuer Snapshot |
| CAPTCHA oder Login-Seite | Abbruch und Kennzeichnung zur manuellen Prüfung |
| Ungültige Modellantwort | keine juristische Bewertung, Validierungsfehler gespeichert |
| TSA nicht erreichbar | Artefakte und lokaler Hash bleiben vollständig, Zeitstempelstatus offen |

## Bewusste Kürzungen

Für den Hackathon werden nicht gebaut: Authentifizierung, Mandantenfähigkeit, allgemeines Dashboard, komplexe Job-Queue, automatische Browserinteraktionen, visuelle Bilderkennung, Notification-Plugins, pywb-Integration und eine automatische abschließende Rechtsentscheidung.

## Drei größte Risiken und Gegenmittel

1. **Instabile Normalisierung:** Fixture-Tests zuerst schreiben und nur selektorspezifische Rauschfilter zulassen.
2. **Nicht verfügbare externe Dienste:** LLM-, TSA- und Wayback-Schritte als getrennte Adapter mit gespeichertem Offline-Demopfad bauen.
3. **Zu breite Demo:** Genau eine URL, einen Tenor und zwei bewertete Änderungen vollständig umsetzen; weitere Quellen erst nach bestandener End-to-End-Abnahme ergänzen.

## Definition of Done

Das Projekt ist für die Hackathon-Demo fertig, wenn eine vorführbare URL zweimal verarbeitet werden kann, flüchtiges Rauschen keinen Alarm auslöst, eine relevante Textänderung erkannt und strukturiert vorgeprüft wird und alle verwendeten Artefakte mit Hash, WARC und überprüfbarem Zeitstempel für eine menschliche Entscheidung bereitstehen.
