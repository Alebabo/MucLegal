# Leitfaden: Backend-Flow für die Kerngleichheitsprüfung

Stand: 21.08.2026  
Zweck: Verbindlicher Zielablauf für den Hackathon-Prototypen. Das BeweisLab bleibt eine
rein technische Erfassung. Die juristische Kerngleichheitsprüfung läuft ausschließlich in
einem menschlich freigegebenen Monitoringfall.

## 1. Zielbild

Der kanonische Ablauf lautet:

```text
Fall anlegen
→ vollständigen Tenor menschlich freigeben
→ verbindliche Prüf-URLs festlegen
→ technischen Ausgangszustand erfassen und menschlich als Baseline bestätigen
→ fälligen Lauf starten
→ pro URL abrufen, normalisieren und hashen
→ bei identischem Fall-Hash ohne Modellaufruf beenden
→ bei Änderung geänderte Klauseln fallweit lokalisieren
→ Haiku-Vorfilter beziehungsweise Klauselklassifikation
→ Sonnet-Gesamtprüfung gegen den freigegebenen Tenor
→ Schema- und Zitatprüfung
→ menschliche Befundentscheidung
→ bei Bestätigung Beweispaket aus den bereits gesicherten Bytes erzeugen
```

Das System entscheidet niemals selbst verbindlich, ob eine Vertragsstrafe verwirkt ist oder
eine neue Abmahnung erfolgen soll.

## 2. Strikte Trennung der Komponenten

### BeweisLab

Das BeweisLab beantwortet nur:

- Welche öffentliche URL wurde wann und wie abgerufen?
- Welche Rohbytes, Header, DOM-Zustände, Texte und Bilder wurden gespeichert?
- Sind Manifest, WARC und Zeitstempel technisch prüfbar?
- Welche technischen Grenzen oder Schutzseiten lagen vor?

Es beantwortet nicht, ob der Inhalt kerngleich ist.

### Fallmonitor

Der Fallmonitor beantwortet vorbereitend:

- Hat sich der freigegebene Prüfumfang technisch geändert?
- Welche Passage ist hinzugekommen, entfallen, verändert oder auf eine andere URL gewandert?
- Verwirklicht der neue Zustand möglicherweise weiterhin den rechtlichen Kern des Tenors?
- Greift eine ausdrücklich dokumentierte `nicht_umfasst`-Abgrenzung?

Jeder juristische Befund bleibt bis zur menschlichen Entscheidung offen.

## 3. Verbindliche Eingangsdaten

Ein Monitoringfall darf erst aktiviert werden, wenn folgende Daten vollständig und menschlich
freigegeben sind:

```json
{
  "case_id": "interne-technische-id",
  "fall_id": "VZ-2024-0417",
  "tenor_version_id": "tenor-v3",
  "tenor_sha256": "...",
  "tenor": "...",
  "verbotene_praxis": "...",
  "kerngleich_umfasst": ["Countdown", "Restmengenanzeige", "nur heute"],
  "nicht_umfasst": ["echte befristete Aktion mit belegbarem Enddatum"],
  "rechtsgrundlage": ["§ 5 UWG", "§ 8 Abs. 1 UWG"],
  "target_urls": ["https://example.de/", "https://example.de/angebote"],
  "normalization_profile": {
    "normalizer_version": "2",
    "selector_config_hash": "..."
  },
  "approved_by": "menschliche Kennung",
  "approved_at": "2026-08-21T12:00:00Z"
}
```

Verbindliche Regeln:

1. Gespeichert wird der vollständige freigegebene Tenor, nicht nur ein einzelnes
   `tenor_element`.
2. Der Lauf referenziert eine unveränderliche Tenorversion mit Hash.
3. `nicht_umfasst` ist ein Pflichtfeld; eine bewusst leere Liste ist zulässig, muss aber
   ausdrücklich freigegeben sein.
4. `target_urls` sind der maßgebliche Prüfumfang. Allgemeines Domain-Crawling ist nicht der
   kanonische Produktpfad.
5. Neu entdeckte URLs werden nicht still in den Prüfumfang übernommen. Sie werden als
   Erweiterungsvorschlag gespeichert und erst nach menschlicher Freigabe überwacht.

## 4. Baseline richtig anlegen

Die bekannte verbotene Praxis und die technische Baseline sind zwei verschiedene Dinge:

- Die verbotene Praxis beschreibt, was vom Tenor erfasst werden soll.
- Die Baseline beschreibt den ersten technisch erfassten Zustand nach Einrichtung des Falls.

Eine Erstaufnahme darf deshalb nicht allein durch ihren ersten Hash automatisch als
ordnungsgemäßer Referenzzustand gelten.

### Baseline-Ablauf

1. Jede freigegebene Ziel-URL wird mit den normalen Robots-, HTTP- und Browserregeln erfasst.
2. Rohbytes, Header, normalisierter Text, Klauseln und technische Metadaten werden gespeichert.
3. Für jede URL wird ein Baseline-Kandidat erzeugt.
4. Eine Juristin bestätigt anschließend einen der Zustände:
   - `baseline_beseitigt`: beanstandete Praxis im dokumentierten Prüfumfang nicht vorhanden,
   - `baseline_fortbestehend`: Praxis besteht weiterhin,
   - `baseline_unsicher`: Zustand reicht nicht für eine belastbare Referenz.
5. Nur `baseline_beseitigt` oder ein ausdrücklich als fortbestehend dokumentierter Zustand darf
   als aktive Vergleichsbasis verwendet werden.

Ohne freigegebene Baseline lautet der Laufstatus `baseline_freigabe_offen`; es gibt noch keine
automatische Kerngleichheitsmeldung.

## 5. Stufe 1: Abruf, Normalisierung und Hash

Für jede `target_url`:

1. URL kanonisieren: Scheme und Host normalisieren, Fragment entfernen, bekannte
   Trackingparameter entfernen, Pfad stabilisieren.
2. `robots.txt` prüfen und den Status dokumentieren.
3. Direkten HTTP-Abruf durchführen; Browser nur nach den festgelegten Fallbackregeln nutzen.
4. Rohantwort und Header unverändert lokal speichern.
5. Sichtbaren Inhalt deterministisch normalisieren.
6. Klauseln mit stabiler Ordinal-, Überschriften- und Hashinformation speichern.
7. Kompatible Vorgängeraufnahme ausschließlich über folgende Identität bestimmen:
   - `case_id`,
   - kanonische Ziel-URL,
   - Tenorversion,
   - Normalisiererversion,
   - Selektorkonfigurations-Hash,
   - vergleichbarer Abrufmodus.

Zusätzlich wird ein deterministischer Fall-Hash gebildet:

```text
case_state_sha256 = SHA-256(
  sortierte Liste aus
  canonical_url + role + normalized_sha256 + capture_completeness
)
```

### Früher Ausstieg

Ist der Fall-Hash gegenüber der aktiven Baseline beziehungsweise dem letzten erfolgreichen Lauf
identisch:

- Status `unveraendert`,
- kein Anthropic-Aufruf,
- kein neues vollständiges Beweispaket,
- lediglich technisches Laufprotokoll und letzter erfolgreicher Prüfzeitpunkt.

Ausnahme: War die Baseline als `baseline_fortbestehend` markiert, lautet das Ergebnis
`unveraendert_fortbestehend`; dies darf nicht als unauffällig dargestellt werden.

## 6. Qualitätsgate vor jeder Modellprüfung

Eine technische Änderung ist noch kein juristischer Kandidat. Vor dem LLM-Aufruf müssen diese
Gates bestanden sein:

- keine leere oder offensichtlich zu kurze Extraktion nach zuvor langem Dokument,
- kein Klauselabfall um mehr als 50 Prozent ohne erklärbaren Dokumentwechsel,
- kein reiner Schutz-, Login-, CAPTCHA- oder Netzwerkfehler,
- vollständige Erfassung aller verbindlichen Ziel-URLs oder genaue Kennzeichnung der Lücke,
- normalisierter Vorher- und Nachhertext vorhanden,
- Abrufmodi fachlich vergleichbar.

Bei einem Fehlschlag lautet der Status `pruefung_unvollstaendig` oder `technisch_unsicher`.
Ein solcher Lauf darf nicht als `beseitigt` oder `nicht_umfasst` ausgegeben werden.

## 7. Stufe 2: Änderungen fallweit lokalisieren

Die Änderungssuche darf nicht URL-isoliert bleiben, weil die Verletzungsform wandern kann.

### Klauselindex

Alle Klauseln des vorherigen und aktuellen Fallzustands werden jeweils mit folgenden Feldern
indexiert:

```json
{
  "url": "https://example.de/angebote",
  "role": "main",
  "ordinal": 12,
  "heading_path": "Angebote > Aktion",
  "text": "Nur noch heute verfügbar",
  "clause_sha256": "..."
}
```

### Paarung

1. Unveränderte Klausel-Hashes werden ausgeschlossen.
2. Entfernte und hinzugefügte Klauseln werden zuerst innerhalb derselben Überschrift gepaart.
3. Danach erfolgt eine fallweite Paarung über alle freigegebenen URLs anhand von:
   - Textähnlichkeit,
   - Überschriftensemantik,
   - Seitentyp,
   - Nähe zu zuvor tenor-relevanten Klauseln.
4. Ein Paar mit verschiedener URL erhält `movement_detected: true`.
5. Nicht sicher paarbare Klauseln bleiben eigenständige Hinzufügungs- oder Entfernungsfälle.

String-Ähnlichkeit lokalisiert Kandidaten, entscheidet aber niemals über Kerngleichheit.

## 8. Stufe 3: Vierklassenprüfung

Jedes relevante Klauselpaar wird gegen exakt die freigegebene Tenorversion geprüft.

### Klassen

| Klasse | Bedeutung |
|---|---|
| `beseitigt` | Die frühere tenor-relevante Praxis fehlt; im freigegebenen Prüfumfang wurde keine funktional entsprechende aktuelle Praxis gefunden. |
| `kerngleich` | Wortlaut, URL, Ebene oder Darstellungsform können abweichen, der aktuelle Zustand verwirklicht aber denselben rechtlichen und tatsächlichen Wirkungsmechanismus. |
| `neuer_sachverhalt` | Es liegt eine Änderung vor, die nicht vom freigegebenen Tenor erfasst ist; eine Übereinstimmung mit `nicht_umfasst` ist hierfür ein starkes Signal. Dies ist keine allgemeine Rechtmäßigkeitsbewertung. |
| `unsicher` | Tatsachenbasis, Zuordnung, Reichweite des Tenors oder Modellantwort reichen nicht für eine belastbare Vorprüfung. |

### Modellreihenfolge

1. Deterministische Klauselpaarung und Relevanzfilterung.
2. Haiku verarbeitet nur die minimierten Klauselpaare und ordnet sie dem Tenorkern,
   `kerngleich_umfasst` oder `nicht_umfasst` zu.
3. Sonnet erstellt die Gesamtprüfung ausschließlich für echte Kandidaten beziehungsweise
   unsichere Fälle.
4. Die eingefrorenen Prompts, Modellbezeichner und Prompt-Hashes werden nicht verändert.

### Pflichtinput pro Klauselpaar

- Fall-ID und unveränderliche Tenorversions-ID,
- vollständiger Tenor,
- verbotener Kern,
- `kerngleich_umfasst`,
- besonders `nicht_umfasst`,
- alte und neue Klausel,
- alte und neue URL sowie Rollen,
- Kennzeichen `movement_detected`,
- belegter Abrufzeitpunkt und Snapshot-Hash.

Screenshots, Roh-HTML, Header und WARC werden nicht an das Modell übertragen.

### Pflichtoutput

Jede Klauselklassifikation enthält genau:

```json
{
  "classification": "kerngleich",
  "tenor_element_id": "TENOR-KERN",
  "confidence": "mittel",
  "evidence_quote": "Nur noch heute verfügbar",
  "reasoning": "Andere Darstellung, aber derselbe künstliche Zeitdruck."
}
```

Die Gesamtbewertung enthält Ergebnis, Begründung, Tatsachenbasis, Rechtsquellenstatus,
stärkstes Gegenargument, Unsicherheit, Confidence und zwingend
`freigabe_durch_mensch: null`.

## 9. Validierung und Fail-closed-Verhalten

Vor der Persistenz wird geprüft:

1. exakt das erwartete JSON-Schema, keine Zusatzfelder,
2. zulässige Klasse und Confidence,
3. bekannte `tenor_element_id`,
4. nichtleere Begründung,
5. `evidence_quote` kommt wörtlich im alten oder neuen Klauseltext vor,
6. Promptversion, Prompt-Hash, Modell und Modus sind gespeichert,
7. `freigabe_durch_mensch` ist `null`.

Bei Modellfehler, Timeout, ungültigem JSON, unbekanntem Tenorelement oder erfundenem Zitat wird
nicht wiederholt geraten. Das Ergebnis lautet `unsicher` mit niedriger Confidence und konkretem
Validierungsfehler.

## 10. Aggregation auf Fallebene

Die Aggregation erfolgt deterministisch:

1. Mindestens eine valide Klasse `kerngleich` → `kerngleich_kandidat`.
2. Sonst mindestens eine Klasse `unsicher` → `unsicher`.
3. Sonst nur `beseitigt` und/oder `neuer_sachverhalt` → `kein_kerngleicher_treffer`.
4. Technische Unvollständigkeit hat Vorrang vor einer Entlastung → `pruefung_unvollstaendig`.

Der Fallstatus darf nicht allein aufgrund eines hohen Similarity-Scores
`kerngleich_wiederaufgetreten` werden.

## 11. Menschliche Entscheidung

Ein Modellbefund erzeugt einen unveränderlichen Prüfungskandidaten. Danach entscheidet eine
Juristin separat:

```json
{
  "finding_id": "...",
  "decision": "bestaetigt_kerngleich | verworfen | neue_abmahnung | offen",
  "comment": "...",
  "decided_by": "...",
  "decided_at": "..."
}
```

Modellfelder werden durch die Entscheidung nicht überschrieben. Die menschliche Entscheidung
wird als eigener Audit-Datensatz angehängt.

## 12. Stufe 4: Beweispaket

Bei einem bestätigten Treffer oder auf ausdrückliche menschliche Anforderung wird das Paket aus
den bereits im Änderungslauf gespeicherten Bytes erzeugt. Es darf keine neue, möglicherweise
abweichende Webaufnahme als Ersatz durchgeführt werden.

Das Paket enthält mindestens:

- Rohantwort und Header der relevanten URL,
- normalisierten Vorher- und Nachhertext,
- Klauselpaar und Diff,
- Screenshots der relevanten Rollen,
- WARC/CDX aus exakt den gespeicherten Antwortbytes,
- Modellinput, validierten Output und Analysemetadaten,
- menschliche Entscheidung,
- SHA-256-Manifest und Verifikation,
- RFC-3161-Status,
- PDF-Bericht und lokales ZIP.

Für eine zeitliche Serie sollte jedes reguläre Manifest den Hash des vorherigen regulären
Manifests desselben Falls als `previous_manifest_sha256` enthalten. God-Mode-Pakete und technisch
ungeeignete Hinweispakete werden niemals in diese reguläre Kette aufgenommen.

## 13. Empfohlene Zustandsmaschine

```text
entwurf
→ fall_freigegeben
→ baseline_erfasst
→ baseline_freigabe_offen
→ aktiv
→ unveraendert
  | unveraendert_fortbestehend
  | pruefung_unvollstaendig
  | aenderung_kandidat
→ kerngleich_kandidat | kein_kerngleicher_treffer | unsicher
→ menschliche_pruefung_offen
→ bestaetigt | verworfen | offen
→ beweispaket_erzeugt
```

## 14. Pseudocode des kanonischen Laufs

```python
def run_case(case_id):
    case = load_approved_case(case_id)
    tenor = load_immutable_approved_tenor(case.tenor_version_id)
    baseline = load_human_approved_baseline(case_id)

    current = capture_all(case.target_urls)
    if not current.coverage_complete:
        return persist_status("pruefung_unvollstaendig", current)

    if current.case_state_sha256 == baseline.case_state_sha256:
        status = (
            "unveraendert_fortbestehend"
            if baseline.legal_state == "fortbestehend"
            else "unveraendert"
        )
        return persist_status(status, current)

    pairs = pair_changed_clauses_across_case(baseline, current)
    candidates = deterministic_relevance_filter(pairs, tenor)
    if not candidates:
        return persist_status("kein_relevanter_textwechsel", current)

    clause_findings = classify_with_haiku(candidates, tenor)
    validated = validate_all_or_mark_unsure(clause_findings)
    aggregate = aggregate_deterministically(validated, current.coverage)

    if aggregate in {"kerngleich_kandidat", "unsicher"}:
        overall = analyze_with_sonnet(validated, tenor)
        aggregate = validate_or_mark_unsure(overall)

    finding = persist_immutable_finding(aggregate, validated, human_release=None)
    return await_human_decision(finding)
```

## 15. Umsetzung im bestehenden Repository

Priorisierte Änderungen:

1. `MonitoringCase` an eine vollständige, freigegebene Tenorversion binden.
2. Einen freigegebenen Baseline-Datensatz pro Fall und URL einführen.
3. `CaseDomainMonitor` nicht mehr als juristischen Entscheider verwenden. Seine Discovery kann
   höchstens technische Kandidaten liefern.
4. Den vorhandenen Golden Path aus `pipeline.py`, `clause_diff.py` und `llm/` über `case_id`
   aufrufen.
5. Klauselpaarung von URL-lokal auf fallweit erweitern und URL-Wanderung dokumentieren.
6. `nicht_umfasst` tatsächlich in jeden Modellinput und jede Aggregation einbeziehen.
7. Stufe 4 erst nach menschlicher Bestätigung oder ausdrücklicher Paketanforderung ausführen.
8. Manifestketten pro Fall verbinden; God Mode strikt getrennt halten.

## 16. Mindesttests vor dem Feature-Freeze

- Erstaufnahme kann ohne menschliche Baselinefreigabe nicht automatisch entlasten.
- Identischer Fall-Hash führt zu keinem Modellaufruf.
- Verstoß wandert von Startseite zu PDP: `movement_detected=true` und Kerngleichheitskandidat.
- Wortlaut ändert sich stark, Wirkungsmechanismus bleibt gleich: `kerngleich`.
- Echte befristete Aktion mit belegbarem Enddatum: `neuer_sachverhalt` wegen `nicht_umfasst`.
- Gelöschte Klausel ohne Ersatz im gesamten Prüfumfang: `beseitigt`.
- Fehlende verbindliche URL: niemals `beseitigt`, sondern `pruefung_unvollstaendig`.
- Ungültiger Modelloutput oder erfundenes Zitat: `unsicher`.
- `freigabe_durch_mensch` bleibt in jedem Modelloutput `null`.
- Bestätigter Treffer erzeugt WARC aus exakt den gespeicherten Bytes.
- Manifestprüfung und RFC-3161-Verifikation bestehen; vorheriger Manifest-Hash ist verkettet.
- God-Mode- oder Schutzbefundpakete gelangen weder in die Kerngleichheitsprüfung noch in die
  reguläre Manifestkette.

## 17. Abnahmeregel

Der Backend-Flow ist erst fertig, wenn dieser vollständige Weg funktioniert:

```text
menschlich freigegebener Fall
→ menschlich freigegebene Baseline
→ unveränderter Lauf ohne LLM
→ geänderter Lauf mit URL-Wanderung
→ schema-valide Vierklassenprüfung unter Beachtung von nicht_umfasst
→ freigabe_durch_mensch bleibt null
→ menschliche Bestätigung
→ Beweispaket aus exakt den bereits gesicherten Bytes
→ Manifest- und Zeitstempelprüfung
```

Ein reiner Stringvergleich, ein Similarity-Schwellwert oder ein Domain-Crawl erfüllt diese
Abnahme ausdrücklich nicht.
