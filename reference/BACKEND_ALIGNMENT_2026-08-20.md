# Backend-Debug- und Alignment-Bericht

Stand: 20.08.2026. Bewertet wurden ausschließlich Backend, Datenmodell und Logik. Eine fehlende
oder unfertige Oberfläche wird nicht als Mangel gewertet. Maßstab sind `AGENTS.md`, der
Challenge-Kontext vom 20.08.2026 und der im Repository beschriebene Golden Path.

## Kurzurteil

Der ursprüngliche Einzel-URL-Golden-Path ist technisch belastbar und weitgehend challenge-konform.
Der später hinzugefügte fallbezogene Domain-Monitor ist dagegen noch nicht als kanonischer
Produktpfad geeignet: Er durchsucht Sitemap und interne Links, umgeht dabei die LLM-basierte
Kerngleichheitsprüfung und erzeugt nur einen Teil der vorgesehenen Beweiskette. Vor dem Frontend
muss deshalb entschieden werden, welcher der beiden Pfade der verbindliche API-Vertrag ist.

Technischer Stand nach den Bugfixes:

- 68 von 68 Tests bestanden unter Python 3.13.13.
- Beide Offline-Demos (`kerngleich`, `nicht-umfasst`) liefen vollständig durch.
- WARC, Manifest, RFC-3161 und PDF wurden in beiden Demo-Pfaden erzeugt; TSA-Status `verified`.
- Die 12-Fälle-Offline-Eval bestand alle technischen Gates.
- Blind-Review-Pakete für zwei Juristinnen wurden reproduzierbar erzeugt.
- Alle Python-Module wurden erfolgreich kompiliert; `pip check` meldet keine defekten Abhängigkeiten.

## Alignment mit der Challenge

| Anforderung | Status | Befund |
|---|---|---|
| Konkreten bekannten Verstoß analysieren | Grün/Gelb | Manueller Fall-Intake ist vorhanden. Der Einzel-URL-Pfad analysiert Änderungen gegen einen Tenor; der fallbezogene Domain-Pfad nutzt nur exakten Treffer und String-Ähnlichkeit. |
| Präzisen Unterlassungstenor unterstützen | Grün | Strukturierter, schema-validierter Tenorentwurf mit separater menschlicher Freigabe ist implementiert. |
| Untersagte Praxis strukturiert dokumentieren | Grün | Tenor, konkrete Praxis, erfasste und nicht erfasste Varianten sowie lokale Artefakte sind vorhanden. `nicht_umfasst` ist im Golden Path berücksichtigt. |
| Inhalte regelmäßig prüfen | Gelb | Wiederholte Läufe sind möglich, aber `next_check_at`, tägliche Fälligkeit und ein Scheduler-/Task-Scheduler-Einstieg fehlen. Aktuell muss ein Lauf manuell/API-seitig ausgelöst werden. |
| Erneute oder kerngleiche Verstöße erkennen | Grün/Gelb | Vierklassen-Klauselprüfung ist im Einzel-URL-Pfad vorhanden. Der fallbezogene Hauptpfad überspringt sie und kann `neuer_sachverhalt` nicht belastbar gegen `nicht_umfasst` abgrenzen. |
| Nachweise bereitstellen | Grün/Gelb | Der Golden Path erzeugt Rohsnapshot, Header, Screenshot, WARC/CDX, Manifest, RFC-3161, Wayback-Status und PDF. Der Domain-Pfad erzeugt WARC/Manifest, aber keinen RFC-3161-Zeitstempel, keinen PDF-Bericht und keine Wayback-Sicherung. |
| Juristin nicht ersetzen | Grün | Modelloutputs bleiben bei `freigabe_durch_mensch: null`; Fall- und Tenorfreigaben sind getrennte menschliche Aktionen. |
| Keine Erstverstoß-Suche | Grün/Gelb | Der Fall muss manuell angelegt werden. Das anschließende automatische Domain-Crawling geht dennoch über den dokumentierten Einzel-URL-Prüfumfang hinaus. |

## Alignment mit der Vier-Stufen-Architektur

### Stufe 1 – Abruf, Normalisierung, Hash

Status: **Grün**.

Der konservative HTTP-Abruf, `robots.txt`, Blockseitenabbruch, unveränderte lokale Rohdaten,
deterministische Normalisierung, versionskompatible Hashvergleiche und Extraktions-Sicherheitsgates
sind umgesetzt und getestet. Bei unverändertem Hash endet der Einzel-URL-Pfad ohne Modellaufruf.

### Stufe 2 – Passage-Vorfilter

Status: **Gelb**.

Klauselsplit und deterministische Zuordnung lokalisieren Änderungen. Ein echter Embedding-Vorfilter
ist nicht implementiert. Für die Hackathon-Demo ist die deterministische Zuordnung vertretbar, darf
im Pitch aber nicht als Embedding-Stufe bezeichnet werden.

### Stufe 3 – Kerngleichheitsprüfung

Status: **Grün im Golden Path, Rot im Domain-Pfad**.

Der Einzel-URL-Pfad kapselt Anthropic-Aufrufe in `muclegal/llm/`, erzwingt Schemas, prüft
wörtliche Fundstellen und fällt bei ungültigen Antworten auf `unsicher` zurück. Die App verwendet
bei vorhandenem Schlüssel Sonnet für die Gesamtprüfung und Haiku für Klauselpaare. Der über
`case_id` gestartete Domain-Pfad ruft dagegen kein LLM auf und klassifiziert per exaktem Treffer
beziehungsweise `SequenceMatcher`. Gerade die zentrale Frage `kerngleich` versus
`neuer_sachverhalt` bleibt dort unbeantwortet.

### Stufe 4 – Beweispaket

Status: **Grün im Golden Path, Gelb im Domain-Pfad**.

Die lokale Primärbeweisspur ist im Golden Path vollständig und prüfbar. Der Domain-Pfad erzeugt
WARC und Manifest bereits für normale Läufe, aber nicht das vollständige Paket. Außerdem wird
Stufe 4 derzeit bei jeder relevanten Textänderung erzeugt, nicht erst nach einem bestätigten
Treffer. Das ist beweisfreundlich, weicht aber von der vorgesehenen Kosten- und Eskalationslogik ab.

## Behobene Backendfehler

1. Der Fall-Intake akzeptierte `example.org/pfad` ohne `http://` oder `https://`. Der spätere Abruf
   scheiterte dadurch erst asynchron. Fundstellen müssen jetzt vollständige HTTP(S)-URLs sein.
2. `allowed_subdomains` akzeptierte beliebige fremde Hosts. Jetzt sind nur die Hauptdomain und
   echte Subdomains davon zulässig.
3. Eine Elementprüfung ohne funktionierenden DOM-Inspector konnte in den Coverage-Metadaten als
   vollständig erscheinen. Sie endet jetzt fail-closed mit `pruefung_unvollstaendig`.
4. Der Run-Coordinator zeigte WARC und Manifest des Domain-Pfads als `skipped`, obwohl sie erzeugt
   wurden. Die Statuswerte spiegeln jetzt Erfolg beziehungsweise Warnung korrekt wider.
5. `lxml` wird direkt importiert, war aber nur transitiv vorhanden. Die direkte, gepinnte
   Runtime-Abhängigkeit ist nun im Paketvertrag deklariert.
6. GNU Wget legte sein internes Laufprotokoll als zusätzliche WARC-Records ab; deren Digests
   waren unter Wget 1.25.0 sporadisch nicht valide. Das nicht beweisrelevante Wget-Protokoll wird
   nun nicht mehr in das WARC eingebettet; Request, Response, CDX und strikte Validierung bleiben.

## Offene Punkte vor dem Frontend

### P0 – Kanonischen Backendpfad festlegen

Der Frontend-Vertrag darf nicht gleichzeitig auf zwei fachlich verschiedene Orchestrierungen
zeigen. Empfohlen ist für den Hackathon der bereits vollständige Einzel-URL-Golden-Path:

`freigegebener Fall + genaue Fundstelle -> Hashvergleich -> Passage -> Vierklassenprüfung -> Beweispaket`

Der Domain-Monitor sollte bis nach der Demo deaktiviert oder klar als Roadmap/experimenteller
Zusatzpfad gekennzeichnet werden. Das entspricht auch dem dokumentierten Scope „eine von der
Juristin festgelegte URL; kein Domain-Crawling“.

### P0 – Tenor pro Monitoringfall binden

Ein `MonitoringCase` speichert aktuell nur `tenor_element`, nicht den freigegebenen vollständigen
Tenor einschließlich `kerngleich_umfasst` und insbesondere `nicht_umfasst`. Damit kann der
fallbezogene Pfad die zentrale juristische Abgrenzung nicht durchführen. Jeder Lauf braucht eine
unveränderliche Referenz auf genau die menschlich freigegebene Tenorversion.

### P1 – Regelmäßige Wiedervorlage

Für das belegte Hauptnutzen fehlen mindestens `next_check_at`, letzter erfolgreicher Lauf,
konservative Frequenz und ein idempotenter CLI/API-Einstieg für fällige Fälle. Dafür genügt ein
externer Windows Task Scheduler/Cron; ein eigener Scheduler-Daemon ist nicht nötig.

### P1 – Vierklassen-Eval als maßgebliche Eval ausweisen

Die aktuelle 12-Fälle-Eval misst noch das ältere Aggregatschema
`kerngleich_umfasst | nicht_umfasst | unklar`. Die klauselscharfen Klassen
`beseitigt | kerngleich | neuer_sachverhalt | unsicher` sind zwar implementiert, aber nicht als
eigenständige Confusion Matrix und Fehlalarm-Gate ausgewertet. Vor allem `neuer_sachverhalt`
gegen `kerngleich` und ausdrücklich `nicht_umfasst` braucht juristische Blindfälle.

### P1 – Beweispaket erst nach Eskalationsentscheidung

Für die tägliche Kostenlogik sollte Stufe 1 kostenlos enden, Stufe 3 nur bei Kandidaten laufen und
Stufe 4 erst nach bestätigtem Treffer beziehungsweise bewusster menschlicher Anforderung starten.
Das vollständige Paket bei jeder Änderung ist technisch korrekt, aber nicht die beschriebene
Eskalationslogik.

## Nicht als Backendmangel gewertet

- Login, Rollen, Mandantenfähigkeit und Dashboard fehlen absichtlich.
- Vision-/Screenshot-Analyse fehlt absichtlich; Screenshots dienen nur als Beleg.
- Checkout-, App-, Newsletter-, Hotline- und Instagram-Fälle sind als Blindspots zu benennen.
- Die UI-Gestaltung ist nicht Gegenstand dieser Abnahme.
- Offene Rechtsfragen und Aktenzeichen wurden in dieser technischen Prüfung nicht materiell
  verifiziert und dürfen bis zur Primärquellenprüfung nicht als gesichert präsentiert werden.

## Go/No-Go

**Go für Backend-Golden-Path und Offline-Demo.**

**No-Go für den fallbezogenen Domain-Pfad als zentrale Produktdemo**, solange er die
Kerngleichheitsprüfung überspringt und kein vollständiger Tenor pro Fall gebunden ist. Das Frontend
sollte erst auf einen vereinheitlichten API-Pfad gesetzt werden; sonst visualisiert es einen
fachlich schwächeren Prozess als den bereits vorhandenen Golden Path.
