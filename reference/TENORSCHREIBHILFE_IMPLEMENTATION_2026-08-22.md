# Tenorschreibhilfe – Implementierungsstand

Stand: 24.08.2026

Route: `http://127.0.0.1:4173/tenorhilfe`

Branch: `agent/live-url-ui`

## Zielbild

Die Tenorschreibhilfe ist eine minimalistische Schreibfläche für Juristinnen.
Sie komponiert Unterlassungstenore aus einer geprüften Bibliothek, statt einen
vollständigen Tenor frei zu generieren. Kein angezeigter Entwurf kommt ohne
Baustein-IDs und Referenz-IDs aus.

## Bedienung

Die leere Seite beginnt mit dem Hinweis:

> Beschreibe den Sachverhalt oder droppe ein PDF oder diktiere den Sachverhalt …

Der Hinweis verschwindet mit der ersten Eingabe. Upload und Diktat bleiben in
einer festen Fußleiste am unteren Fensterrand. Die Texthöhe wächst mit dem Inhalt;
die Schreibfläche selbst wird nicht verkleinert.

### Slash-Modi

`/` öffnet eine kompakte Inline-Auswahl:

| Befehl         | Wirkung                                          |
| -------------- | ------------------------------------------------ |
| `/sachverhalt` | neuen Sachverhalt erfassen                       |
| `/tenor`       | vorhandenen Tenor korrigieren oder fortschreiben |
| `/fälle`       | Archiv und Hinweise durchsuchen                  |

Pfeil hoch/runter bewegt eine deutlich grau markierte Auswahl. Enter übernimmt
den Modus. Der Modus erscheint danach fett direkt vor der weiteren Eingabe. Er
verhält sich wie ein vorangestelltes Zeichen: Steht der Cursor am Textanfang,
löscht Backspace den Modus.

Im Modus `/fälle` wird während des Tippens in Titel, Fall-ID, Domain und Kurztext
gesucht. Die Ergebnisliste zeigt kompakt nur Titel und Fall-ID. Enter übernimmt
den mit Pfeil hoch/runter grau markierten Treffer. Grundlage ist aktuell der
gemeinsame synthetische Datensatz von Archiv und Hinweisen in
`frontend/src/data/lottoDemoCases.ts`.

### Inhaltliche Rückfragen

Die Minimalansicht bietet nach einer ersten Sachverhaltsbeschreibung den Schritt
`KI-Rückfragen starten`. Der dafür getrennt versionierte OpenAI-Pfad wählt anhand des
eingegebenen Sachverhalts und aller bisherigen Antworten genau eine passende Form:

- Ja/Nein für echte binäre Tatsachenfragen,
- Freitext für offene Sachverhaltsangaben,
- Slider nur für sinnvoll begrenzbare Zahlen oder Abstufungen.

Frage und Antwort bleiben grau eingerückt beziehungsweise als dunkler Antworttext
direkt im Schreibfluss sichtbar. Nach jeder Antwort wird die nächste Rückfrage aus dem
gesamten bisherigen Verlauf erzeugt. Sobald keine weitere Frage erforderlich ist,
werden Sachverhalt, Fragen und Antworten gemeinsam an die unveränderte, eingefrorene
Tenorgenerierung übergeben. Das Rückfrageschema wird serverseitig strikt validiert;
der Browser erhält weiterhin keinen API-Schlüssel.

### Entwurf und Autofill

Ein als Tenor erkannter Text oder der Modus `/tenor` aktiviert nach 800 ms den
Bibliotheks-Autofill. Tab übernimmt ausschließlich den nächsten Baustein gemäß
Segmentreihenfolge; es gibt keine freie Textfortsetzung.

Nach `Generieren` werden genau zwei bearbeitbare Entwürfe angezeigt:

- `Präzise`: enger, auf die konkrete Fundstelle ausgerichtet;
- `Technikneutral`: kerngleicher, kanalneutraler Anwendungsbereich.

Beide Entwürfe werden deterministisch in `frontend/src/tenor-engine.ts`
komponiert. Referenz- und Baustein-IDs stehen unter dem Entwurf.

Die beiden Vorschläge bleiben zunächst kompakt vergleichbar. Ein Klick auf eine
Variante öffnet sie anschließend allein in einer breiten Lese- und
Bearbeitungsansicht. `Beide Entwürfe` führt zum Vergleich zurück;
`Entwurf übernehmen` bleibt eine gesonderte Bestätigung. In der Maskenansicht
verschwindet nach der Erzeugung die Eingabespalte vollständig und der Prüfentwurf
nutzt die gesamte Inhaltsbreite. Der frühere große Erklärungskopf wurde entfernt.

### Tenorarchiv

`Entwurf übernehmen` speichert die gewählte und gegebenenfalls zuvor bearbeitete
Minimal-Fassung zuerst serverseitig in der vorhandenen SQLite-Datei
`.muclegal-ui/reviews.sqlite3`. Erst nach erfolgreicher Speicherung kehrt sie in die
Schreibfläche zurück. Dadurch führt ein Speicherfehler nicht zu einem unbemerkten
Verlust des ausgewählten Texts.

Unter `/archiv` gibt es neben `Fälle` den eigenen Bereich `Tenore`. Er zeigt die
übernommenen Minimal-Fassungen sowie die bereits in derselben Datenbank gespeicherten
Entwürfe aus der strukturierten Maskenansicht, jeweils mit Fall-ID, Variante, Status
und Zeitpunkt. Ein Eintrag öffnet eine breite Leseansicht mit dem vollständigen
Tenor, dem zugrunde liegenden Sachverhalt und vorhandenen Quellenankern. Die API
hierfür lautet `GET/POST /api/v1/tenor-archive`; API-Schlüssel oder Rohantworten des
Modells werden nicht gespeichert.

## Daten und Build-Sicherung

`scripts/unbundle.py` entpackt das ursprüngliche Register aus
`TENORREGISTER_BUNDLE.md`. `scripts/validate.py` prüft anschließend:

- Pflichtfelder aller acht Tenore,
- Existenz aller verwendeten Baustein-IDs,
- Existenz aller Referenzen in `belegt_in`,
- leere `belegt_in`-Listen bei Bausteinen mit `status: vorschlag`.

`frontend/package.json` ruft diese Validierung vor Entwicklung und Build auf und
erzeugt die JSON-Datei für das Frontend. Der Build bricht bei ungültigen Daten.
Beim Laden meldet die Validierung aktuell acht Tenore, 37 Bausteine und vier
Tenore mit `zitat_geprueft: true`.

Die zehn deterministischen Prüfregeln sind in `frontend/src/rules.ts`
implementiert. Die stark reduzierte Schreibansicht zeigt sie derzeit noch nicht
als eigene Befundspalte an.

## Evaluation

`scripts/eval.py` führt Leave-one-out ausschließlich über die vier Fälle mit
geprüftem Zitat aus. Der aktuelle, ungeschönte Stand ist:

| Segment                  |         Treffer |
| ------------------------ | --------------: |
| Adressatenkreis          |     4/4 (100 %) |
| Anwendungsbereich        |       0/5 (0 %) |
| Ausnahmevorbehalt        |       0/2 (0 %) |
| Konkrete Verletzungsform |      2/4 (50 %) |
| Ordnungsmittelandrohung  |       0/4 (0 %) |
| Verbotene Handlung       |       0/5 (0 %) |
| **Gesamt**               | **6/24 (25 %)** |

Der Umgehungstest bestätigt weiterhin: Der domaingebundene T-001 erfasst die
App-Verlagerung nicht, die technikneutrale Komposition mit B-AB-03 dagegen schon.
Die Zwei-Button-Lösung bleibt vom Original T-002 nicht erfasst.

## Ehrliche Grenzen

- Alle acht Fälle tragen `freigabe_jurist: false`; die Annotationen sind
  Arbeitsbewertungen.
- Nur T-001 bis T-004 haben `zitat_geprueft: true`.
- Vorschlagsbausteine ohne Tenorbeleg dürfen nicht wie belegte Formeln erscheinen.
- PDF-Texterkennung ist noch nicht implementiert; der Dateiname wird lokal
  angezeigt, der Inhalt aber nicht extrahiert.
- Die Vollständigkeitsprüfung arbeitet mit sichtbarer Schlüsselwortlogik und kann
  Synonyme übersehen. Sie ist keine juristische Bewertung.
- Die Demo komprimiert die ursprünglich geplanten drei Reichweitenvarianten auf
  eine binäre Auswahl, wie für die aktuelle Benutzerführung festgelegt.
- Die niedrige Leave-one-out-Trefferquote zeigt, dass die Auswahl über die kleine
  Referenzmenge noch nicht belastbar genug für einen Produktiveinsatz ist.
- Das System schlägt vor und begründet. Die Freigabe bleibt menschlich.

## Verifikation

Zuletzt erfolgreich ausgeführt:

```powershell
python scripts\validate.py
cd frontend
npm run typecheck
npm run build
cd ..
python -m compileall -q muclegal app.py
python -m pytest -q
```

Der fokussierte Tenor-Testlauf besteht mit `14 passed`. Im vollständigen Lauf
bestanden `143` Tests; ausschließlich der bereits dokumentierte sporadische
GNU-Wget/warcio-Digest-Test schlug fehl. TypeScript-Prüfung, Frontend-Build und der
Browserablauf von der Entwurfswahl über die Archivspeicherung bis zur Tenor-Leseansicht
waren erfolgreich. Die Routen `/tenorhilfe`, `/archiv` und
`/api/v1/tenor-archive` antworteten lokal erfolgreich.
