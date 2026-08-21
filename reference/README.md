# Tenorregister — Datenstand 21.08.2026

## Was hier drin ist

| Datei | Inhalt |
|---|---|
| `tenore/T-001` … `T-008.yaml` | 8 annotierte Referenztenore |
| `bausteine.yaml` | 37 Bausteine + 10 deterministische Prüfregeln |
| `verstossprofil.schema.yaml` | Eingabeschema statt Freitext-Sachverhalt |

Alle Dateien sind gültiges YAML (geprüft mit `yaml.safe_load`). Alle Pflichtfelder aus eurem Erfassungsbogen sind bei allen acht Fällen gefüllt.

---

## Belastbarkeit — bitte vor dem Pitch lesen

Der Tenorwortlaut ist **nicht bei allen acht Fällen gleich gut belegt**. Das ist der Punkt, an dem euch ein Juror in der Jury erwischen kann.

| ID | Fall | Tenor am Volltext geprüft? |
|---|---|---|
| T-001 | LG München I, 33 O 15098/22 (WOW, Login-Hürde) | **ja** — gesetze-bayern.de |
| T-002 | OLG München, 6 U 4336/23 e (Sky, versteckter Button) | **ja** — gesetze-bayern.de |
| T-003 | OLG Bamberg, 3 UKl 11/24 e (Eventim, Dark Patterns) | **ja** — gesetze-bayern.de |
| T-004 | LG München I, 33 O 14776/19 (Focus, Cookie-Banner) | **ja** — gesetze-bayern.de |
| T-005 | LG Köln, 31 O 88/11 (P-Konto) | nein — aus eurer Team-Sammlung |
| T-006 | LG Düsseldorf, 12 O 293/22 (Preisanpassung) | nein — **kein Datum, keine Fundstelle** |
| T-007 | OLG Frankfurt, 6 U 206/23 (BahnCard) | nein — Wortlaut hat Auslassungen `[...]` |
| T-008 | OLG Karlsruhe, 6 U 82/22 (Finanzsanierung) | nein — Auslassung + **Datumswiderspruch** |

**Empfehlung:** Die Demo ausschließlich auf T-001 bis T-004 aufbauen. Diese vier sind wörtlich aus der bayerischen Rechtsprechungsdatenbank gezogen und tragen jede Nachfrage.

### Konkrete Aufgaben für morgen

1. **T-006** — Datum und Fundstelle beschaffen oder den Fall aus dem Register nehmen. Ein Tenor ohne Aktenzeichen-Beleg ist genau das, was ihr im Pitch anderen KI-Werkzeugen vorwerft.
2. **T-007** — Antragswortlaut im [Verbandsklagenregister des BfJ](https://www.bundesjustizamt.de/DE/Themen/Verbraucherrechte/VerbandsklageregisterMusterfeststellungsklagenregister/Verbandsklagenregister/Unterlassungsklagen/Klagen/2024/056/UKlag_56_2024_node.html) ziehen, die beiden `[...]` schließen. Das BfJ-Register ist die beste frei zugängliche Quelle für Tenorwortlaute überhaupt — dort wird der Antragswortlaut amtlich bekanntgemacht.
3. **T-008** — Datumswiderspruch klären: Sammlung sagt 08.02.2023, der PDF-Dateiname der Verbraucherzentrale sagt 12.04.2022.
4. **Alle** — `freigabe_jurist: false` steht überall. Die Reichweiten-Annotationen (`kerngleich_umfasst` / `nicht_umfasst`) sind meine Arbeitsbewertung, keine juristische Freigabe. Mindestens die vier Demo-Fälle sollte eine Juristin aus eurem Team durchgehen und das Feld auf `true` setzen.

### Was ich nicht verwendet habe

`Erhebungsbogen_10_Beispiele_Datenschutz_AGB_ausgefuellt.pdf` ist nicht ins Register eingeflossen. Der Grund steht in der Datei selbst: `tenor_text` enthält überall Platzhalter („Konkreten nationalen Tenor einsetzen"), Schuldner sind `[Unternehmen A]` bis `[Unternehmen J]`, und bei den EuGH-Fällen dient das Urteil ausdrücklich nur als materiell-rechtlicher Bezug. Als Trainingsmaterial für ein Werkzeug, dessen Verkaufsargument „kein Vorschlag ohne Herkunft" ist, wäre das ein Eigentor.

### Urheberrecht

Tenorwortlaute deutscher Gerichtsentscheidungen sind amtliche Werke nach § 5 Abs. 1 UrhG und gemeinfrei. Die wörtliche Übernahme ist zulässig und hier auch zwingend — eine paraphrasierte Tenorreferenz wäre wertlos.

---

## Der wichtigste Datensatz: die Sky-Umgehungskette

In `T-002.yaml` unter `umgehungskette` steht das, was euren Pitch trägt. Dasselbe Unternehmen, derselbe Grundverstoß, drei Verfahren:

1. **10.10.2023** — LG München I, 33 O 15098/22: Login-Hürde vor der Bestätigungsseite (WOW). Untersagt.
2. **20.03.2025** — OLG München, 6 U 4336/23 e: Button hinter „Weitere Links einblenden", unter 58 Links (sky.de). Untersagt.
3. **14.07.2026** — LG München I, 33 O 14294/25: Zwei-Button-Lösung „Abo beenden" / „Infos zur Kündigung". Untersagt.

Die Pointe: Der Tenor aus Stufe 2 enthielt **bereits** die Erweiterung „oder inhaltsgleiche Gestaltungen" — und war trotzdem zu eng. Die Formel schützt nur innerhalb desselben Umgehungsmechanismus. Sky hat den Mechanismus gewechselt, nicht die Beschriftung.

Das ist kein konstruiertes Beispiel, sondern dokumentierte Rechtsprechung mit Aktenzeichen. Es belegt genau die These, die ihr aufstellt: **Nicht die Existenz des Tenors ist das Problem, sondern seine Reichweite.**

Als zweiter Beleg dient T-001 gegen T-004: Zwei Tenore desselben Gerichts (LG München I), ein Jahr auseinander. T-001 nennt eine einzelne Domain und einen Ort auf der Seite. T-004 sagt nur „in Telemedien" — technikneutral, und trotzdem bestimmt, weil ein Anlagenbezug folgt. Das ist der Reichweiten-Regler als reales Nebeneinander.

---

## Warum die Bausteinbibliothek 37 Einträge hat und nicht 8

Aus acht Tenoren lassen sich 37 wiederverwendbare Bausteine extrahieren, weil ein Unterlassungstenor hochgradig formelhaft ist. Nur ein Segment ist wirklich fallindividuell:

| Segment | Varianten im Register | Generativ? |
|---|---|---|
| Verpflichtungsformel | 2 | nein |
| Ordnungsmittelandrohung | 6 | nein |
| Adressatenkreis | 5 | nein |
| Anwendungsbereich | 7 | nein |
| **Verbotene Handlung** | **11** | **ja** — nur hier |
| Ausnahmevorbehalt | 2 | nein |
| Konkrete Verletzungsform | 5 | nein |

Praktische Folge: Das Modell wählt aus, es erfindet nicht. Erfundene Normen, erfundene Aktenzeichen und erfundene Formeln sind strukturell ausgeschlossen, nicht durch Prompt-Ermahnung.

Drei Bausteine sind mit `status: vorschlag` und leerem `belegt_in` markiert (B-AB-03b, B-VH-13). Die habe ich aus Entscheidungsgründen konstruiert, nicht aus Tenoren. Sie müssen im UI als Vorschlag gekennzeichnet werden — oder ihr nehmt sie raus.

---

## Die 10 Prüfregeln laufen ohne Modell

In `bausteine.yaml` unter `pruefregeln`. Das ist Prüfschritt 0 der Vollprüfung: reine Bedingungslogik über das Verstoßprofil und die erkannten Bausteine. Kein Modellaufruf, keine Latenz, keine Fehlalarme.

Die vier, die im Pitch am meisten hermachen:

- **R-03** — § 1 UKlaG-Fall ohne Doppelausspruch („verwenden" **und** „sich berufen"). Trifft T-005 und T-006, beide real zu eng. Ohne diesen Baustein bleiben Altverträge unberührt (§ 11 UKlaG). Bei Abo-Verträgen ist der Altvertragsbestand typischerweise ein Vielfaches des Neuzugangs — der Tenor greift also gerade dort nicht, wo der Schaden entsteht.
- **R-06** — Tenor nennt eine Domain, das Verstoßprofil nennt mehrere Kanäle. Trifft T-001, T-002 und T-003.
- **R-08** — Art. 25 DSA als Anspruchsgrundlage. Nach T-003 falsch: Art. 25 DSA ist gegenüber der UGP-Richtlinie subsidiär und wirkt nur über §§ 3 Abs. 2, 4a UWG als Auslegungsmaßstab. Diese Regel fängt einen Fehler, den auch der vzbv im Ausgangsverfahren gemacht hat.
- **R-10** — Dark-Pattern-Tenor mit nur einem Gestaltungsmerkmal. Nach T-003 tragen weder Framing allein noch einmaliges Nagging allein den Tenor; erst die Kombination überschritt die Schwelle. Wer nur ein Merkmal tenoriert, riskiert Teilabweisung mit Kostenfolge.

R-08 und R-10 sind der Beleg dafür, dass das Werkzeug nicht nur formatiert, sondern Rechtsprechungswissen anwendet. Beide sind aus einer einzigen Entscheidung abgeleitet — das ist das Argument dafür, warum acht gut annotierte Fälle mehr wert sind als dreißig oberflächlich erfasste.

---

## Was das Register noch nicht kann

Ehrlich, weil ihr es sonst im Pitch behauptet und dann nachgefragt werdet:

- **Keine Ordnungsmittelbeschlüsse nach § 890 ZPO.** Euer eigener Erfassungsbogen nennt sie als vorrangige Quelle — zu Recht, denn dort hat ein Gericht bereits entschieden, ob eine spätere Handlung noch vom Tenor gedeckt war. Alle `kerngleich_umfasst`-Einträge im Register sind bislang Arbeitsbewertung, keine gerichtlich bestätigte Kerngleichheit. Die Sky-Kette ist der beste Ersatz, weil dort ein neues Erkenntnisverfahren nötig war — was faktisch beweist, dass die Handlung nicht mehr gedeckt war.
- **Keine Unterlassungserklärungen.** Alle acht Fälle sind Urteile. Der praktisch häufigere Fall der Verbraucherzentrale ist die UE. Die ist aber nicht öffentlich — das ist genau der Grund für die Mail an Frau Neumann. Kommt eine Antwort, ist das der wertvollste Zuwachs für das Register.
- **Nur drei Fallgruppen mit mehr als einem Fall.** `kuendigungsbutton` (2), `agb_klausel` (3), Rest je 1. Für den Reichweiten-Vergleich reicht das; für Retrieval nicht.
- **Kein Fall aus 2026 mit wörtlichem Tenor.** LG München I, 33 O 14294/25 (14.07.2026) ist die Stufe 3 der Sky-Kette und wäre der wertvollste Neuzugang. Der Volltext war zum Recherchezeitpunkt noch nicht in der Datenbank.

---

## Woher die Volltexte kommen

Die PDFs auf `vzbv.de` sind **Scans ohne Textebene** — Copy-Paste und automatische Extraktion scheitern daran. Wer dort Tenore abtippt, verliert Stunden.

Nutzt stattdessen:

| Quelle | Wofür |
|---|---|
| `gesetze-bayern.de` | Alle bayerischen Gerichte (LG/OLG München, OLG Bamberg, OLG Nürnberg). Volltext als HTML, Tenor als eigener Abschnitt. Vier von acht Fällen kommen von dort. |
| Verbandsklagenregister BfJ | Antragswortlaut wird amtlich bekanntgemacht — auch für nicht-bayerische Gerichte |
| `rechtsprechung-im-internet.de` | BGH |
| `openlegaldata.io` | gemischt, Lückenfüller |

Über dejure.org findet man die GRUR-RS-Nummer, damit lässt sich das Dokument auf gesetze-bayern.de direkt adressieren:
`https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-<Jahr>-N-<Nummer>`

---

## Aktueller Prototyp

Das Register wird inzwischen durch `scripts/validate.py` beim Frontend-Start und
beim Build geprüft. Die lokale Tenorschreibhilfe unter `/tenorhilfe` komponiert
daraus zwei bearbeitbare Varianten und bietet Bibliotheks-Autofill. Die zehn
deterministischen Regeln aus `bausteine.yaml` sind in `frontend/src/rules.ts`
implementiert; die reduzierte Schreibansicht zeigt sie derzeit nicht als eigene
Befundspalte.

Die reduzierte Benutzerführung, Slash-Modi, inhaltliche Rückfragen, technische
Zuordnung und weiterhin offenen Grenzen stehen in
[`TENORSCHREIBHILFE_IMPLEMENTATION_2026-08-22.md`](TENORSCHREIBHILFE_IMPLEMENTATION_2026-08-22.md).
