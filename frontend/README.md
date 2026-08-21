# MucLegal-Frontend

Lokales TanStack-Start-Frontend für den Fallmonitor, das BeweisLab und die
Tenorschreibhilfe. Die Oberfläche ist ein Hackathon-Prototyp und wird nicht
öffentlich bereitgestellt.

## Lokal starten

Das Python-Backend läuft auf Port 8000:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Das Frontend läuft getrennt auf Port 8080:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 8080
```

Beim Start validiert `predev` das Tenorregister und erzeugt
`src/generated/tenorregister.json`. Eine fehlerhafte Referenzdatei verhindert
damit den Start. Die Tenorschreibhilfe ist anschließend unter
`http://127.0.0.1:8080/tenorhilfe` erreichbar.

## Tenorschreibhilfe

Die Seite ist als weiße, ablenkungsfreie Schreibfläche umgesetzt. Eine Eingabe
kann als Sachverhalt, vorhandener Tenor oder Fallauswahl begonnen werden. PDF und
Browser-Diktat sind über die feste Leiste am unteren Rand erreichbar.

Slash-Modi:

- `/sachverhalt`: einen neuen Verstoß beschreiben;
- `/tenor`: einen vorhandenen Tenor einfügen oder mit Bibliotheks-Autofill
  weiterschreiben;
- `/fälle`: die gemeinsamen Demofälle aus Archiv und Hinweisen nach Name oder
  Fall-ID filtern.

Nach `/` lässt sich das kompakte Menü mit Pfeil hoch/runter bedienen; Enter
übernimmt die markierte Zeile. Der aktive Modus steht als fetter Inline-Präfix
vor der Eingabe. Befindet sich der Cursor am Textanfang, entfernt Backspace den
Modus wieder.

Auch die Treffer unter `/fälle` lassen sich mit Pfeil hoch/runter durchlaufen.
Enter übernimmt den jeweils grau markierten Fall.

Die Rückfragen hängen nicht von der Textlänge ab. Der lokale deterministische
Vollständigkeitscheck prüft, ob der Text folgende vier Inhalte erkennen lässt:

1. beanstandete Handlung oder Gestaltung,
2. Ort beziehungsweise Kanal,
3. betroffene Personengruppe,
4. gewünschte künftige Unterlassung.

Es wird immer nur zur ersten noch fehlenden Information direkt unter dem
geschriebenen Text nachgefragt. Sobald die Eingabe vollständig wirkt, erscheint
`Generieren`. Danach stehen genau zwei bearbeitbare Entwürfe zur Wahl:
`Präzise` und `Technikneutral`.

## Fachliche Sicherungen

- Der Entwurf wird aus Bausteinen des geprüften Registers komponiert.
- Verwendete Baustein- und Referenz-IDs bleiben am Entwurf sichtbar.
- Die technikneutrale Variante ist keine automatische juristische Freigabe.
- Vorschlagsbausteine ohne Tenorbeleg bleiben als solche in den Daten markiert.
- Die Freigabe bleibt immer menschlich.

Aktuelle Grenzen:

- Die Inhaltserkennung ist eine transparente Schlüsselwortheuristik, kein
  juristisches Sprachmodell.
- Hochgeladene PDFs werden lokal angenommen, aber noch nicht per OCR oder
  Textextraktion ausgewertet.
- Autofill schlägt ausschließlich den nächsten Bibliotheksbaustein vor.
- Die Fallauswahl verwendet derzeit synthetische Lotto-Demofälle.
- Die beiden Entwürfe sind Demo-Kompositionen und keine Rechtsberatung.

## Wichtige Dateien

```text
src/routes/tenorhilfe.tsx        Schreibfläche und Interaktion
src/tenor-engine.ts              deterministische Komposition und Autofill
src/rules.ts                     zehn deterministische Prüfregeln
src/tenor-types.ts               Frontend-Datenmodell
src/generated/tenorregister.json validierte Build-Eingabe
../reference/bausteine.yaml      Bausteinbibliothek und Prüfregeln
../reference/tenore/             acht annotierte Referenztenore
../scripts/validate.py           Referenz- und Build-Validierung
../scripts/eval.py               Leave-one-out-Evaluation
```

## Verifikation

```powershell
python ..\scripts\validate.py
npm run typecheck
npm run build
python ..\scripts\eval.py
```

Für die gesamte Anwendung zusätzlich im Repository-Stamm:

```powershell
python -m compileall -q muclegal app.py
python -m pytest -q
```
