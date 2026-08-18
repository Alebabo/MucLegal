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

- [ ] Das GitHub-Repository `https://github.com/Alebabo/MucLegal.git` als Arbeitsverzeichnis klonen oder den bestehenden Ordner korrekt mit dem Remote verbinden.
- [ ] Python 3.11+ und eine minimale Projektstruktur einrichten.
- [ ] Eine kontrollierbare öffentliche Demo-URL oder lokale HTTP-Fixture festlegen.
- [ ] Drei HTML-Fixtures anlegen: unverändert, nur flüchtiges Rauschen geändert, rechtlich relevante Aussage geändert.
- [ ] Entscheidungen aus [`reference/FINDINGS.md`](reference/FINDINGS.md) als verbindliche technische Grundlage verwenden.

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

- [ ] HTTP-Abruf mit festem, identifizierbarem User-Agent, Timeout und begrenzten Wiederholungen implementieren.
- [ ] URL, Abrufzeitpunkt, Statuscode, Response-Header und unverändertes HTML speichern.
- [ ] Playwright nur als klar getrennten Fallback für öffentlich sichtbare, clientseitig gerenderte Inhalte vorsehen.
- [ ] Bei CAPTCHA, Login oder Blockseite abbrechen und den Vorgang als manuell zu prüfen markieren.

### 2. Deterministische Normalisierung

- [ ] `trafilatura` in einer fest gepinnten Version verwenden.
- [ ] Extraktion fest konfigurieren: Textausgabe, Präzision bevorzugen, keine Kommentare, keine Links/Bilder/Metadaten, Tabellen behalten, interne Deduplizierung deaktivieren.
- [ ] Vor der Extraktion nur explizit konfigurierte Störelemente über CSS-Selektoren entfernen, etwa Cookie-Banner oder bekannte Navigation.
- [ ] Nach der Extraktion Zeilenenden, Unicode und überflüssige Leerzeichen deterministisch vereinheitlichen.
- [ ] Nur bekannte flüchtige Werte innerhalb eng begrenzter Selektoren durch typisierte Marker ersetzen, zum Beispiel einen Countdown durch `[COUNTDOWN]`.
- [ ] Keine globalen Regeln verwenden, die Preise, Datumsangaben, Verfügbarkeiten oder Werbeaussagen entfernen könnten.
- [ ] Den normalisierten UTF-8-Text mit SHA-256 hashen.

### 3. Snapshots und Vergleich

- [ ] Snapshot-Metadaten in SQLite speichern; große Artefakte als Dateien ablegen.
- [ ] Hash, vorherigen Hash, Pfade zu Rohdaten und normalisiertem Text sowie Zeitpunkte verknüpfen.
- [ ] Bei identischem Hash keine LLM-Prüfung starten.
- [ ] Bei verändertem Hash einen verständlichen Text-Diff erzeugen und zur nächsten Stufe weitergeben.

### Abnahme Bautag 1

- [ ] Zwei Läufe mit identischem HTML erzeugen denselben normalisierten Text und denselben Hash.
- [ ] Ein veränderter Countdown erzeugt weiterhin denselben Hash.
- [ ] Eine veränderte rechtlich relevante Werbeaussage erzeugt einen neuen Hash und einen passenden Diff.
- [ ] Alle drei Fälle sind durch automatisierte Tests mit lokalen Fixtures belegt.
- [ ] Ein kompletter Abruf kann ohne LLM und ohne UI über einen einzelnen Befehl ausgeführt werden.

## Bautag 2 – Juristische Vorprüfung, Beweiskette und Demo

### 4. Strukturierte LLM-Vorprüfung

- [ ] Einen synthetischen Unterlassungstenor und zwei klar beschriftete Demo-Fälle verwenden: `kerngleich_umfasst` und `nicht_umfasst`.
- [ ] Nur Tenor, relevanten Vorher-/Nachher-Ausschnitt und belegte Metadaten an das Modell senden.
- [ ] Ein festes JSON-Schema erzwingen, mindestens mit Ergebnis, Begründung, Tatsachenbasis, Norm-/Zitatstatus, Gegenargument, Unsicherheit und `freigabe_durch_mensch`.
- [ ] Prompt-Regeln umsetzen: Ergebnis zuerst; Tatsachen, Rechtsquelle und Schlussfolgerung trennen; stärkstes Gegenargument nennen; ungeprüfte Fundstellen ausdrücklich markieren.
- [ ] Modellantwort strikt validieren. Ungültige oder fehlende Antworten werden gespeichert, aber nicht als Bewertung ausgegeben.
- [ ] Einen Offline-Demomodus mit gespeicherten, klar als Fixture gekennzeichneten Antworten vorsehen.

### 5. Beweiskette

- [ ] Mit GNU Wget ein WARC samt CDX für die statische Demo-Seite erzeugen.
- [ ] Das WARC mit `warcio check` validieren.
- [ ] Ein Manifest mit SHA-256-Hashes aller wesentlichen Artefakte erzeugen: Roh-HTML, Header, normalisierter Text, Diff, Modellinput und Modelloutput.
- [ ] Den Manifest-Hash über OpenSSL per RFC 3161 stempeln und das Token anschließend lokal verifizieren.
- [ ] Aktuelles TSA-Zertifikat und CA-Kette zusammen mit der Verifikation dokumentieren.
- [ ] Wayback Save Page Now nur als optionale, nicht beweisentscheidende Zusatzquelle verwenden.
- [ ] Einen kleinen, lesbaren Prüfbericht als PDF erzeugen.

### 6. Ein-Seiten-Demo

- [ ] Eine minimale FastAPI/Jinja- oder Streamlit-Ansicht bauen.
- [ ] Auf einer Seite anzeigen: URL, letzter Abruf, Status, Vorher/Nachher-Diff, Modellbewertung, Unsicherheit, Beweisartefakte und Zeitstempelstatus.
- [ ] Eine menschliche Entscheidung `freigegeben`, `abgelehnt` oder `weitere Prüfung` erfassen.
- [ ] Automatische Bewertung und menschliche Freigabe optisch und in den Daten klar trennen.

### Abnahme Bautag 2

- [ ] Der Golden Path läuft vom Abruf bis zum Prüfbericht ohne manuelle Dateibearbeitung durch.
- [ ] Beide juristischen Demo-Fälle liefern schema-valide, nachvollziehbare Ergebnisse.
- [ ] Das WARC ist valide und sämtliche Manifest-Hashes lassen sich erneut berechnen.
- [ ] Der RFC-3161-Zeitstempel wird lokal erfolgreich verifiziert.
- [ ] Die UI zeigt keinen Fall als endgültig entschieden, solange keine menschliche Freigabe vorliegt.
- [ ] Die Demo funktioniert auch dann nachvollziehbar, wenn LLM, freeTSA oder Wayback kurzfristig nicht erreichbar sind.

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
