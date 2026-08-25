# UX-Bericht aus Sicht einer nicht-technischen Juristin

Stand: 25.08.2026  
Getesteter Commit: `7287ccf` (der Branch wurde während der Prüfung durch den parallel laufenden,
thematisch getrennten Rechtstext-Fix von `08ba5ca` auf diesen Stand vorgerückt)  
Testperspektive: Juristin mit sicherem Verbraucherrechtswissen, aber ohne Kenntnisse zu APIs,
Hashes, Browserautomatisierung oder Softwarebetrieb.

## Kurzurteil

Die fachliche Grundidee ist verständlich und das BeweisLab vermittelt während eines laufenden
Abrufs überraschend gut, was gerade geschieht. Die Anwendung ist aber noch nicht verlässlich
genug für eine unbegleitete juristische Nutzung. Drei Probleme gefährden unmittelbar Vertrauen
oder Beweiszuordnung:

1. Nach Änderung der URL zeigt das BeweisLab weiterhin Download und Ergebnis des vorherigen
   Laufs, ohne den abweichenden Bezug kenntlich zu machen.
2. Ein vollständiger Klauselfall kann in der aktuellen Live-Tenorhilfe mit der internen Meldung
   `nicht_umfasst darf nicht leer sein` scheitern.
3. Ein nicht neu gestarteter Backendprozess kann zur aktuellen Oberfläche inkompatibel sein und
   interne Schemafehler statt eines Entwurfs liefern.

Für eine Juristin lautet die entscheidende Frage nicht „Welche Technik läuft?“, sondern:
„Welcher Fall ist das, welche Unterlage sehe ich, was muss ich jetzt entscheiden und was bewirkt
meine Entscheidung?“ Diese vier Antworten sind noch nicht auf jeder Seite eindeutig sichtbar.

## Testumfang und Ergebnis

### Automatisierte Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Python-Syntax (`compileall`) | bestanden |
| Gesamttests Python | 172 bestanden in 177,21 Sekunden |
| Frontend-Logiktests | 19 bestanden |
| TypeScript-Typprüfung | bestanden |
| ESLint | 0 Fehler, 6 bestehende Fast-Refresh-Warnungen |
| Produktions-Build | bestanden |

Die drei gegenüber dem vorherigen Commit zusätzlichen Python-Tests stammen aus dem parallel
entstandenen Rechtstext-Fix `7287ccf`. Der Bericht verändert dessen Dateien nicht.

### Browserprüfung

Geprüft wurden Desktop und 390 × 844 Pixel auf folgenden Wegen:

- Dashboard, Hinweise und Falldetail;
- Archiv und Tenorarchiv-Reiter;
- neuer Monitoringfall einschließlich leerer Validierung;
- Tenorhilfe in Minimal- und Maskenansicht;
- Slash-Modi, vollständiger Klauselfall, Rückfragen und Generierung;
- BeweisLab einschließlich Grey-Mode-Information, Prüfverlauf, Screenshot und Download;
- vollständige technische Erfassung von `https://example.com`.

Der BeweisLab-Lauf mit `example.com` wurde technisch abgeschlossen und erzeugte lokal Screenshot,
normalisierten Text sowie ein herunterladbares Paket. Außer bei der Tenorgenerierung traten in den
geprüften Kernwegen keine Browser-Konsolenfehler auf.

## P0 – vor einer unbegleiteten Demo beheben

### 1. BeweisLab kann ein altes Beweispaket neben einer neuen URL anzeigen

**Beobachtung:** Nach dem abgeschlossenen Lauf für `https://example.com` wurde nur das URL-Feld auf
`https://example.org` geändert. Der Downloadlink verwies weiterhin auf den alten Lauf
`20260825T110620798643Z-4c83a99c`; auch Screenshot und technische Ergebnisse blieben sichtbar.

**Wirkung auf die Juristin:** Sie kann ein Paket herunterladen und dem falschen Vorgang zuordnen.
Das ist nicht nur unbequem, sondern ein Risiko für die Beweiskette.

**Verbesserung:** Sobald der Inhalt des URL-Felds nicht mehr exakt zur angezeigten Erfassung passt:

- Ergebnisbereich, Zuordnung und Download deaktivieren oder ausblenden;
- deutlich anzeigen: „Die sichtbaren Beweise gehören zu `example.com`. Für `example.org` wurde
  noch keine Erfassung gestartet.“;
- über jedem Ergebnis dauerhaft Ziel-URL, Erfassungszeitpunkt und Lauf-ID zeigen;
- Downloadtext konkretisieren, etwa „Beweispaket für example.com · 25.08.2026, 13:06“.

### 2. Live-Tenorgenerierung scheitert an widersprüchlicher Validierung

**Reproduktion:** Vollständiger Klauselfall mit Schuldner, Vertragsbereich und wörtlichem
Klauseltext; Ast C wurde korrekt erkannt und es war keine Rückfrage nötig. `POST
/api/v1/tenor-proposals` endete dennoch mit HTTP 502 und `nicht_umfasst darf nicht leer sein`.

**Ursache:** Das Modell-JSON-Schema erlaubt für `nicht_umfasst` eine leere Liste. Der nachgelagerte
Validator verbietet sie. Bei einem Sachverhalt ohne belegten Gegenfall hat das Modell korrekt
nichts ergänzt und wurde anschließend zurückgewiesen.

**Verbesserung:** Keine unbelegte Abgrenzung erfinden lassen. Für die UE-Erzeugung eine leere Liste
akzeptieren und in nachgelagerten Monitoringdaten ehrlich als „Keine Abgrenzung belegt“ ausweisen.
Alternativ müsste die Information vor der Generierung ausdrücklich bei der Nutzerin erhoben werden;
das widerspräche hier aber der festgelegten Ast-C-Fragenlogik. Interne Feldnamen dürfen nie als
Fehlermeldung erscheinen. Geeignet wäre: „Der Entwurf konnte nicht vollständig geprüft werden.
Bitte erneut versuchen; Ihre Eingabe bleibt erhalten.“

### 3. Frontend und laufendes Backend können unbemerkt unterschiedliche Versionen haben

**Reproduktion:** Der bereits laufende lokale Backendprozess war vor dem aktuellen Commit gestartet.
Die aktuelle Oberfläche sendete erlaubterweise `fundstelle: null` und `rechtsgrundlagen: []`; der
alte Prozess antwortete mit HTTP 422 und den englischen Pydantic-Meldungen `Input should be a valid
string` und `List should have at least 1 item`.

**Verbesserung:**

- Deployment und lokales Startskript müssen Backend und Frontend immer gemeinsam neu starten;
- beide Dienste liefern eine Build-/Schema-Version, die das Frontend beim Laden vergleicht;
- bei Abweichung keine Generierung anbieten, sondern „Anwendung wurde aktualisiert – bitte einmal
  neu laden“ zeigen;
- API-Validierungsfehler in eine juristische, handlungsorientierte Meldung übersetzen.

## P1 – zentrale Arbeitsabläufe vereinfachen

### 4. Auf Mobilgeräten fehlt die Navigation

Dashboard, Fallanlage und BeweisLab blenden die Seitenleiste vollständig aus, bieten aber weder
Menüschaltfläche noch untere Navigation. Die Nutzerin kann nur über Browser-Zurück oder zufällig
vorhandene Links wechseln. Die Tenorhilfe besitzt zwar „Zurück“, aber keinen Zugang zu Hinweisen,
Archiv oder BeweisLab.

**Verbesserung:** Eine kompakte Kopfzeile mit Logo, aktuellem Bereich und Schaltfläche „Menü“ auf
allen mobilen Seiten. Die fünf Bereiche sollten dieselben deutschen Namen wie am Desktop tragen.

### 5. Fehler der Fallanlage bleiben außerhalb des Sichtbereichs

Wird das lange Formular leer abgesendet, bleibt die Seite bei `scrollY = 1286` und der Fokus auf
„Fall erfassen“. Die ersten Fehlermeldungen stehen weit oberhalb des sichtbaren Bereichs.

**Verbesserung:** Nach fehlgeschlagener Prüfung zum ersten fehlerhaften Feld scrollen, dieses
fokussieren und am Formularende zusätzlich eine kurze Zusammenfassung zeigen: „6 Pflichtangaben
fehlen. Zum ersten Feld.“ Pflichtfelder vorab sichtbar markieren.

### 6. Die Fallanlage verlangt zu viel Systemwissen auf einmal

Begriffe wie Fall-ID, relevante Seitentypen, konkrete Prüf-URLs, `Nicht umfasst` und erlaubte
Subdomains erscheinen gleichzeitig. Eine Juristin versteht die Rechtsbegriffe, aber nicht zwingend,
warum die Anwendung diese technische Aufteilung benötigt.

**Verbesserung:** Mit „Was wurde beanstandet?“ beginnen. Domain aus der URL ableiten, Fall-ID
automatisch vorschlagen und technische Felder erst unter „Prüfumfang genauer festlegen“ einblenden.
Bei Auswahl „Klausel“ nur Klauselwortlaut und Vertragsbereich priorisieren; bei „Seitenelement“ die
passenden Bedien- und URL-Felder zeigen.

### 7. Hinweise erklären den nächsten Schritt nicht eindeutig

Die Seite beginnt ohne Überschrift oder Einleitung direkt mit langen Karten. „Fall freigeben“ kann
bedeuten, dass die Juristin den Rechtsverstoß, den Tenor oder nur das Monitoring freigibt.
„Ablehnen“ ist ebenso offen. Technische Angaben wie Fall-ID und Manifest stehen auf derselben
Ebene wie die menschliche Entscheidung.

**Verbesserung:**

- Überschrift „Zur Prüfung“ und Einleitung „Entscheiden Sie, ob dieser Fall in das Monitoring
  aufgenommen wird“;
- Hauptfrage direkt über den Schaltflächen;
- Beschriftungen „Für Monitoring freigeben“ und „Nicht ins Monitoring aufnehmen“;
- vor Speicherung eine kurze Zusammenfassung der Wirkung;
- technische Beweiskette standardmäßig eingeklappt unter „Technische Nachweise“.

### 8. Alte Urteilsformeln sehen wie aktuelle UE-Vorschläge aus

Im geprüften DAZN-Fall steht weiterhin „DAZN Limited wird untersagt …“. Das ist als historischer
Bestand lesbar, widerspricht aber der neuen UE-Logik und wird unter „Tenor / Formulierungsvorschlag“
ohne Warnung dargestellt.

**Verbesserung:** Alte Einträge nicht migrieren, aber sichtbar kennzeichnen: „Historischer
Monitoringtenor – nicht nach aktueller UE-Vorlage erstellt“. Niemals als aktuelles
Formulierungsvorbild präsentieren.

## P2 – Verständlichkeit und Ruhe verbessern

### 9. Die leere Tenorhilfe ist visuell ruhig, aber zu voraussetzungsvoll

Positiv ist die große, ablenkungsarme Schreibfläche. Für eine neue Nutzerin sind jedoch
„Minimal“, „Maske“, „UE“, Slash-Modi und die nur als blasse Icons sichtbaren Upload-/Diktataktionen
nicht selbsterklärend. Der Platzhalter „droppe ein PDF“ ist unnötiges Denglisch und sehr kontrastarm.

**Verbesserung:**

- Tabs in „Freitext“ und „Strukturierte Eingabe“ umbenennen;
- Platzhalter: „Beschreiben Sie den Verstoß, fügen Sie einen bestehenden Tenor ein oder laden Sie
  einen Vertrag als PDF hoch.“;
- Icons mit sichtbaren Texten „PDF hochladen“ und „Diktieren“;
- unaufdringlicher Hinweis „Tipp: Mit `/` können Sie den Eingabetyp wählen“;
- mobile Kopfzeile zweizeilig und ohne abgeschnittene Oberkante gestalten.

### 10. Ein vollständiger Sachverhalt verlangt einen unnötigen Zwischenschritt

Obwohl beim Klauselbeispiel keine Rückfrage fehlte, musste zuerst „KI-Rückfragen starten“ geklickt
werden; erst danach erschien „Generieren“.

**Verbesserung:** Eine einzige primäre Aktion „Angaben prüfen“. Ist alles vollständig, startet sie
direkt den Entwurf. Fehlt etwas, erscheint genau eine konkrete Frage. Der Begriff „KI“ beschreibt
die Technik, nicht die Aufgabe der Juristin, und sollte aus primären Schaltflächen verschwinden.

### 11. Maskenansicht verwendet interne Astbegriffe

„Fundstelle (bei Ast A/C optional)“ setzt Wissen über die interne Klassifikation voraus.

**Verbesserung:** Kontextabhängig formulieren: „Fundstelle oder URL – bei Klauseln nur angeben,
wenn sie für den Entwurf wichtig ist.“ Ast A/B/C darf als technische Metadaten sichtbar sein,
aber nicht als Bedienvoraussetzung.

### 12. Produktbegriffe sind uneinheitlich

Das React-Frontend nennt den Bereich „Tenorhilfe“, die BeweisLab-Seitenleiste weiterhin
„Tenorschreibhilfe“. Hinzu kommen „Home“, „Quick Actions“, „Dark Mode“, „Grey Mode“ und
„Confidence“.

**Verbesserung:** Ein verbindliches Begriffsglossar verwenden:

| Derzeit | Vorschlag |
| --- | --- |
| Home | Start |
| Quick Actions | Schnellzugriff |
| Dark Mode | Dunkle Ansicht |
| Tenorschreibhilfe | Tenorhilfe |
| Confidence | Einschätzungssicherheit oder Spalte ausblenden, wenn kein Wert vorliegt |
| Grey Mode | Autorisierter Prüfmodus; „Grey Mode“ höchstens als technische Zusatzbezeichnung |

### 13. Demodaten wirken wie echte dringende Fälle

**Status nach Dashboard-Überarbeitung:** im Dashboard umgesetzt. Der Demomodus erhält nun einen
eigenen Hinweisbanner, jeder priorisierte Beispielvorgang die Kennzeichnung „Demofall“ und die
Statuszeile die Bezeichnung „Demobetrieb“. Während des Ladens werden keine vorläufigen
Demozähler mehr als aktuelle Fallzahlen gezeigt.

Wenn keine Backendfälle vorhanden sind, zeigt das Dashboard synthetische Lottofälle, darunter
„Kritisch“ und „sofortige Aktion nötig“. Nur die kleine Statuskarte „Demo“ erklärt den Zustand.

**Verbesserung:** Entweder einen echten Leerzustand zeigen oder jeden synthetischen Fall und die
gesamte Seite mit einem auffälligen, aber ruhigen Banner „Demodaten – keine echten Vorgänge“
kennzeichnen. Demodaten dürfen keine echten Zähler oder Dringlichkeitsmeldungen imitieren.

## Was bereits gut funktioniert

- Die fachlichen Bereiche sind am Desktop in einer stabilen, einfachen Seitenleiste erreichbar.
- Die Tenorhilfe setzt den Fokus direkt in die Schreibfläche.
- Der vollständige Klauselfall wurde korrekt als Ast C erkannt; es erschien keine irrelevante
  Rückfrage.
- Formularfehler werden feldnah und mit deutschen Texten angezeigt.
- Das BeweisLab erklärt während des Laufs in verständlichen Verben: abrufen, aufbereiten,
  Rechtstexte suchen, Ansicht festhalten, Archiv erstellen und Zeitpunkt belegen.
- Der sichere `example.com`-Lauf wurde vollständig abgeschlossen; fehlende AGB- und
  Datenschutzscreenshots waren ehrlich deaktiviert.
- Desktop und Mobilansicht verursachten keinen horizontalen Scrollbalken.

## Empfohlene Reihenfolge für den verbleibenden Arbeitstag

1. BeweisLab-Ergebnis strikt an die eingegebene und erfasste URL binden.
2. Widerspruch zwischen Modell-JSON-Schema und Tenorvalidator beseitigen; verständliche
   Fehlermeldung ergänzen.
3. Gemeinsame Build-Version und sicheren Neustart von Backend/Frontend erzwingen.
4. Mobile Navigation ergänzen und Formularfokus bei Fehlern korrigieren.
5. Freigabehandlungen sprachlich eindeutig machen und historische Tenore kennzeichnen.
6. Begrifflichkeiten vereinheitlichen und erst danach optische Details polieren.

## Lokale Browserartefakte

Die reproduzierenden Screenshots liegen im ignorierten lokalen Ordner `output/playwright/`, unter
anderem:

- `ux-beweislabor-stale-result.png` – neue URL mit altem Ergebnis;
- `ux-current-tenor-result.png` – Live-Validatorfehler;
- `ux-neu-validation-viewport.png` – Fehler bleiben außerhalb des Sichtbereichs;
- `ux-tenor-mobile.png` – mobile Tenorhilfe;
- `ux-hinweis-detail.png` – Entscheidung und technische Beweiskette;
- `ux-beweislabor-complete.png` – erfolgreich abgeschlossener `example.com`-Lauf.
