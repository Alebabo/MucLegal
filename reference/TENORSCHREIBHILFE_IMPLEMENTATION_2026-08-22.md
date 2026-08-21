# Tenorschreibhilfe – Implementierungsstand

Stand: 22.08.2026

Route: `http://127.0.0.1:8080/tenorhilfe`

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

Die Entscheidung basiert nicht mehr auf einer Mindestzeichenanzahl. Die Funktion
`assessCompleteness` prüft deterministisch vier Inhaltsklassen:

1. konkrete Handlung oder Gestaltung,
2. Kanal oder Fundort,
3. betroffene Gruppe,
4. gewünschtes Unterlassen.

Fehlt etwas, erscheint unmittelbar unter der gerade geschriebenen Zeile genau
eine graue Rückfrage. Die Reihenfolge entspricht der Liste oben. Ein kurzer,
inhaltlich vollständiger Satz kann daher den Generieren-Button freischalten; ein
langer, aber unvollständiger Text nicht.

### Entwurf und Autofill

Ein als Tenor erkannter Text oder der Modus `/tenor` aktiviert nach 800 ms den
Bibliotheks-Autofill. Tab übernimmt ausschließlich den nächsten Baustein gemäß
Segmentreihenfolge; es gibt keine freie Textfortsetzung.

Nach `Generieren` werden genau zwei bearbeitbare Entwürfe angezeigt:

- `Präzise`: enger, auf die konkrete Fundstelle ausgerichtet;
- `Technikneutral`: kerngleicher, kanalneutraler Anwendungsbereich.

Beide Entwürfe werden deterministisch in `frontend/src/tenor-engine.ts`
komponiert. Referenz- und Baustein-IDs stehen unter dem Entwurf.

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

Der letzte vollständige Python-Testlauf bestand mit `130 passed`. Die Route
antwortete lokal mit HTTP 200.
