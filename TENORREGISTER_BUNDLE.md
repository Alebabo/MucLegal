# TENORREGISTER — GEBÜNDELTE DATENGRUNDLAGE

Stand: 2026-08-21. Alle Dateien in einer Datei zusammengefasst, damit sie in einen
Codex-/Agent-Kontext passen. Jede Datei beginnt mit `===== DATEI: <pfad> =====`.
Zum Entpacken: Blöcke an diesen Markern trennen und unter dem angegebenen Pfad ablegen.

Alle YAML-Blöcke sind mit `yaml.safe_load` validiert.

---

===== DATEI: README.md =====

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

## Nächster Schritt

Das Register ist die Datengrundlage. Was noch fehlt, ist der Kompositions-Prompt, der aus `verstossprofil.schema.yaml` plus `bausteine.yaml` die drei Tenorvarianten baut, und der Vollprüfungs-Prompt mit vorgeschaltetem Prüfschritt 0. Beides kann ich schreiben — sagt Bescheid, wenn ihr so weit seid.


===== DATEI: verstossprofil.schema.yaml =====

# Verstoßprofil — Eingabeschema der Tenorschreibhilfe
# Dies ist die Datenstruktur, die statt eines Freitext-Sachverhalts übergeben wird.
# Sie wird von Hand ausgefüllt ODER aus einem BeweisLab-Paket vorbefüllt.
# Dieselbe Struktur erzeugt am Ende den Prüfauftrag für den Monitor.

$schema: "tenorhilfe/verstossprofil/0.1"

felder:
  profil_id:
    typ: string
    pflicht: true
    beispiel: "V-2026-014"

  schuldner:
    typ: object
    pflicht: true
    felder:
      name: {typ: string, pflicht: true}
      rechtsform: {typ: string, pflicht: false, hinweis: "steuert die Vollstreckungsperson in der Ordnungsmittelandrohung"}
      rolle: {typ: enum, werte: [anbieter, plattform, verwender, vermittler]}

  kanal:
    typ: enum_mehrfach
    pflicht: true
    werte: [website, app, e_mail, social_media, offline]
    steuert: >
      Bei mehr als einem Kanal löst Prüfregel R-06 aus: ein domaingebundener
      Anwendungsbereich (B-AB-02) wäre zu eng, Vorschlag B-AB-03.

  fundort:
    typ: object
    pflicht: true
    felder:
      url: {typ: string}
      seitenrolle: {typ: enum, werte: [startseite, agb, datenschutz, checkout, kontobereich, produktseite, sonstige]}
      abschnitt: {typ: string, beispiel: "§ 5 Vertragslaufzeit"}
      beleg:
        anlage: {typ: string, beispiel: "K3"}
        sha256: {typ: string, hinweis: "aus dem BeweisLab-Manifest"}
        erfasst_am: {typ: date}

  adressat:
    typ: enum
    pflicht: true
    werte: [verbraucher, unternehmer, gemischt]
    steuert: "Auswahl in adressatenkreis. Bei 'gemischt' Vorschlag B-AK-05 (negative Formulierung)."

  vertragstyp:
    typ: enum
    werte: [dauerschuldverhaeltnis, kaufvertrag, dienstvertrag, kein_vertrag]

  fallgruppe:
    typ: enum
    pflicht: true
    werte: [kuendigungsbutton, agb_klausel, dark_pattern_dsa, consent_gestaltung, irrefuehrende_werbung, widerrufsbutton, preisangabe]
    steuert: "Auswahl des Blocks in verbotene_handlung."

  verstoss_modus:
    typ: enum
    pflicht: true
    werte: [fehlt_vollstaendig, vorhanden_unzureichend, irrefuehrend_gestaltet, klausel_verwendet]
    hinweis: >
      Das entscheidende Feld. Die Verbraucherzentrale hat im Hackathon-Vortrag
      ausdrücklich gesagt: es macht einen Unterschied, ob der Button ganz fehlt oder
      falsch umgesetzt ist — dann braucht es einen anderen Tenor. Genau dieses Enum
      steuert die Bausteinauswahl in Segment 5.

  rechtsgrundlage:
    typ: liste_geschlossen
    pflicht: true
    hinweis: >
      Mehrfachauswahl aus einer gepflegten Normliste, KEIN Freitext. Verhindert
      erfundene Normen. Löst Prüfregeln R-03, R-08 und R-09 aus.

  beanstandeter_wortlaut:
    typ: text
    pflicht_wenn: "fallgruppe == agb_klausel"
    hinweis: "WÖRTLICH. Wird unverändert in den Tenor übernommen (B-KV-04)."

  wirkung:
    typ: text
    pflicht: true
    max_saetze: 2
    beispiel: "Die Kündigung wird erst nach einem zusätzlichen Telefonat wirksam."

  gewuenschte_reichweite:
    typ: enum
    pflicht: true
    werte: [konkrete_verletzungsform, kerngleich, inhaltsgleich]
    steuert: "Position des Reichweiten-Reglers; wählt zwischen B-AB-02 / B-AB-03 / B-AB-03b."

  bekannte_umgehungen:
    typ: liste_text
    pflicht: false
    hinweis: >
      Bereits beobachtete Ausweichgestaltungen. Löst Prüfregel R-07 aus und wird
      im Vollprüfungs-Prompt als Testmenge verwendet: „Wäre diese Abwandlung von
      dem formulierten Tenor erfasst?“

ausgaben:
  - name: tenorentwurf
    beschreibung: "Drei Varianten (eng / kerngleich / weit), jede mit Baustein-IDs und Referenz-IDs."
  - name: abgeleitete_pruefmerkmale
    beschreibung: >
      Prüfauftrag für den Monitor. Wird aus den pruefbare_merkmale der verwendeten
      Referenzfälle plus den Slots des Verstoßprofils zusammengesetzt.
    hinweis: >
      Das ist die Systemgeschichte: eine Eingabe, zwei Ausgaben. Der Tenor erzeugt
      seinen eigenen Prüfauftrag.


===== DATEI: bausteine.yaml =====

# Bausteinbibliothek für die Tenorschreibhilfe
# Stand: 2026-08-21
#
# Jeder Baustein ist aus mindestens einem wörtlich erfassten Tenor des Registers
# extrahiert. Kein Baustein ohne belegt_in. Das Modell darf ausschließlich aus
# dieser Bibliothek auswählen und die {{Slots}} füllen — es formuliert keine
# Bausteine frei. Ausnahme: Segment 5 (verbotene Handlung), siehe unten.

meta:
  version: "0.1"
  segmentreihenfolge:
    - ordnungsmittelandrohung   # nur wenn position=eingeschoben
    - verpflichtungsformel
    - adressatenkreis
    - anwendungsbereich
    - verbotene_handlung
    - ausnahmevorbehalt
    - konkrete_verletzungsform
    - ordnungsmittelandrohung   # nur wenn position=nachgestellt
  slot_syntax: "{{name}}"
  regel: >
    Segmente 1-4, 6 und 7 werden ausgewählt, nicht generiert. Nur die verbotene
    Handlung darf das Modell aus dem Verstoßprofil neu formulieren — und auch dann
    nur unter Verwendung eines der Muster aus verbotene_handlung.

# =====================================================================
# SEGMENT: Verpflichtungsformel
# =====================================================================
verpflichtungsformel:
  - id: B-VF-01
    text: "Die Beklagte wird verurteilt, es zu unterlassen,"
    belegt_in: [T-001, T-002, T-003, T-004, T-005, T-006, T-007]
    haeufigkeit: 7
    empfehlung: standard
  - id: B-VF-02
    text: "Der Beklagten wird untersagt,"
    belegt_in: [T-008]
    haeufigkeit: 1
    hinweis: >
      Passivisch. Gleichwertig, aber seltener. Bei nachgestellter
      Ordnungsmittelandrohung (B-OM-06) üblich.

# =====================================================================
# SEGMENT: Ordnungsmittelandrohung (§ 890 ZPO)
# =====================================================================
# DETERMINISTISCHE PRÜFUNG: Fehlt dieses Segment vollständig, ist das ein
# Befund vom Typ fehlender_baustein mit schwere=hoch. Kein Modellaufruf nötig.
ordnungsmittelandrohung:
  - id: B-OM-01
    position: eingeschoben
    text: >
      es bei Vermeidung eines vom Gericht für jeden Fall der Zuwiderhandlung
      festzusetzenden Ordnungsgeldes von bis zu € 250.000,00, ersatzweise Ordnungshaft
      oder Ordnungshaft bis zu sechs Monaten, letztere zu vollziehen an
      {{vollstreckungsperson}},
    slots:
      vollstreckungsperson: "z. B. „ihrem Geschäftsführer“"
    belegt_in: [T-004]
  - id: B-OM-02
    position: eingeschoben
    text: >
      es bei Meidung eines für jeden Fall der Zuwiderhandlung fälligen Ordnungsgeldes
      bis zu € 250.000,00, ersatzweise Ordnungshaft oder Ordnungshaft bis zu sechs
      Monaten, letztere zu vollziehen an {{vollstreckungsperson}},
    slots:
      vollstreckungsperson: "z. B. „den Geschäftsführern der Komplementär GmbH“ / „den Mitgliedern der Geschäftsführung der Komplementärin“"
    belegt_in: [T-001, T-002]
  - id: B-OM-03
    position: eingeschoben
    text: >
      es bei Meidung eines für jeden Fall der Zuwiderhandlung vom Gericht
      festzusetzenden Ordnungsgeldes bis zu EUR 250.000,00, ersatzweise Ordnungshaft,
      oder einer Ordnungshaft bis zu sechs Monaten, wobei die Ordnungshaft an
      {{vollstreckungsperson}} zu vollziehen ist, und insgesamt zwei Jahre nicht
      übersteigen darf,
    slots:
      vollstreckungsperson: "z. B. „ihren jeweiligen gesetzlichen Vertretern“"
    belegt_in: [T-003]
    empfehlung: vollstaendigste
    hinweis: >
      Einzige Variante im Register mit der Zwei-Jahres-Obergrenze der Ordnungshaft
      (§ 890 Abs. 1 S. 2 ZPO). Bei Neuformulierung diese Variante wählen.
  - id: B-OM-04
    position: eingeschoben
    text: >
      unter Androhung eines vom Gericht für jeden Fall der Zuwiderhandlung
      festzusetzenden Ordnungsgeldes bis zu 250.000,00 € — ersatzweise Ordnungshaft —
      oder der Ordnungshaft bis zu sechs Monaten,
    belegt_in: [T-005]
    warnung: >
      Ohne Benennung der Vollstreckungsperson. Bei juristischen Personen ist die
      Benennung erforderlich, weil Ordnungshaft nur gegen natürliche Personen
      vollstreckt werden kann. NICHT als Vorschlag anbieten, sondern nur als
      Referenz führen.
  - id: B-OM-05
    position: eingeschoben
    text: >
      es bei Vermeidung eines für jeden Fall der Zuwiderhandlung festzusetzenden
      Ordnungsgeldes bis zu 250.000,00 €, ersatzweise Ordnungshaft bis zu sechs Monaten
      oder Ordnungshaft bis zu sechs Monaten, zu vollstrecken an
      {{vollstreckungsperson}},
    belegt_in: [T-006]
  - id: B-OM-06
    position: nachgestellt
    text: >
      Der Beklagten wird für jeden Fall der schuldhaften Zuwiderhandlung ein
      Ordnungsgeld bis zu € 250.000,00 (ersatzweise Ordnungshaft bis zu sechs Wochen)
      oder Ordnungshaft bis zu sechs Monaten, zu vollstrecken an
      {{vollstreckungsperson}}, angedroht.
    slots:
      vollstreckungsperson: "z. B. „deren Vorstand“"
    belegt_in: [T-008]
    hinweis: >
      Eigener Tenorabsatz nach dem Verbot. Das Prüfmodul muss beide Anordnungen
      kennen und darf eine nachgestellte Androhung nicht als fehlend melden.

# =====================================================================
# SEGMENT: Adressatenkreis
# =====================================================================
adressatenkreis:
  - id: B-AK-01
    text: "im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern"
    belegt_in: [T-001, T-002, T-003, T-004]
    haeufigkeit: 4
    empfehlung: standard
  - id: B-AK-02
    text: "gegenüber Verbrauchern (§ 13 BGB)"
    belegt_in: [T-007]
    hinweis: >
      Mit Normverweis. Vorzugswürdig bei Klauselfällen, weil das
      Vollstreckungsgericht den Verbraucherbegriff nicht auslegen muss.
  - id: B-AK-03
    text: "im geschäftlichen Verkehr gegenüber Verbrauchern in {{gebiet}}"
    slots:
      gebiet: "z. B. „Deutschland“"
    belegt_in: [T-008]
    hinweis: "Räumliche Begrenzung — relevant bei Anbietern mit Sitz im EU-Ausland."
  - id: B-AK-04
    text: "von Verbrauchern, die {{qualifikation}}"
    slots:
      qualifikation: "z. B. „im Rahmen eines bestehenden Zahlungsdiensterahmenvertrages die Führung eines Pfändungsschutzkontos verlangen“"
    belegt_in: [T-005]
    hinweis: "Qualifizierter Adressatenkreis — verengt bewusst auf eine Fallkonstellation."
  - id: B-AK-05
    text: >
      sofern nicht der Vertrag mit einer Person abgeschlossen wird, die in Ausübung
      ihrer gewerblichen oder selbstständigen beruflichen Tätigkeit handelt (Unternehmer)
    belegt_in: [T-006]
    empfehlung: weiteste
    hinweis: >
      NEGATIVE Formulierung. Wirkt weiter als B-AK-01, weil auch Fälle erfasst werden,
      in denen die Verbrauchereigenschaft streitig ist. Bei Klauselfällen mit
      gemischtem Kundenkreis vorzugswürdig.

# =====================================================================
# SEGMENT: Anwendungsbereich
# =====================================================================
# HIER ENTSTEHT DER HÄUFIGSTE ZU-ENG-FEHLER. Reihenfolge = Reichweite aufsteigend.
anwendungsbereich:
  - id: B-AB-02
    reichweite: eng
    text: >
      auf der Internetseite {{url}}, die den Abschluss von {{vertragsgegenstand}} in
      Form von Dauerschuldverhältnissen auf elektronischem Weg ermöglicht,
    slots:
      url: "konkrete Domain"
      vertragsgegenstand: "z. B. „entgeltlichen Abonnements“ / „kostenpflichtigen Dauerschuldverhältnissen über PAY-TV-Inhalte“"
    belegt_in: [T-001, T-002]
    warnung: >
      Bindet an EINE Domain. Verlagerung in App, auf Subdomain oder Zweitmarke ist
      nicht erfasst. In beiden Belegfällen war der Tenor deshalb zu eng.
      Nur wählen, wenn der Sachverhalt eine Beschränkung erzwingt.
  - id: B-AB-03
    reichweite: technikneutral
    text: "in Telemedien"
    belegt_in: [T-004]
    empfehlung: vorzugswuerdig
    hinweis: >
      Der beste Anwendungsbereichs-Baustein im Register. Keine Domain, keine
      Plattform, keine Seitenrolle. Erfasst Website, App und Smart-TV-Oberfläche.
      Standardvorschlag, wenn der Sachverhalt keine Beschränkung erzwingt.
  - id: B-AB-03b
    reichweite: technikneutral
    text: >
      auf Internetseiten und in Anwendungen, die den Abschluss von Verträgen über
      Dauerschuldverhältnisse auf elektronischem Weg ermöglichen,
    belegt_in: []
    status: vorschlag
    warnung: >
      NICHT AUS EINEM ERFASSTEN TENOR BELEGT. Konstruiert aus B-AB-02 unter Übernahme
      der funktionalen Auslegung des Webseitenbegriffs aus den Entscheidungsgründen
      T-001 Rn. 24. Muss als Vorschlag gekennzeichnet und juristisch freigegeben
      werden, bevor das System ihn ausgibt.
  - id: B-AB-04
    reichweite: mittel
    text: "im Internet unter {{url}} für {{gegenstand}} zu werben bzw. werben zu lassen"
    slots:
      url: "konkrete Domain"
      gegenstand: "z. B. „den Kauf von Tickets“"
    belegt_in: [T-003]
    hinweis: >
      „bzw. werben zu lassen“ erstreckt das Verbot auf Beauftragte und Dienstleister
      (§ 8 Abs. 2 UWG). Wird häufig vergessen und sollte bei jedem Werbefall
      vorgeschlagen werden.
  - id: B-AB-05
    reichweite: ausloesebedingung
    text: "gegenüber Verbrauchern, die {{zustand}}"
    slots:
      zustand: "z. B. „im Warenkorb eine angebotene kostenpflichtige Ticketversicherung nicht ausgewählt haben und den Bestellvorgang über den Button ‚Weiter zur Kasse‘ fortsetzen“"
    belegt_in: [T-003]
    hinweis: >
      Beschreibt den Zustand, in dem das Verbot greift. Nicht der Anwendungsbereich
      im engeren Sinn, sondern eine Auslösebedingung. Bei Prozessgestaltungen
      (Checkout, Kündigungsstrecke) unverzichtbar.
  - id: B-AB-06
    reichweite: mittel
    text: "in Bezug auf Dauerschuldverhältnisse"
    belegt_in: [T-006]
  - id: B-AB-07
    reichweite: eng
    text: "bei {{produkt}}-Verträgen"
    slots:
      produkt: "z. B. „BahnCard“"
    belegt_in: [T-007]
    warnung: "Bindet an ein Produkt. Zweitmarken und Nachfolgeprodukte nicht erfasst."

# =====================================================================
# SEGMENT: Verbotene Handlung
# =====================================================================
# Das einzige Segment, in dem das Modell aus dem Verstoßprofil neu formulieren darf.
# Auswahl erfolgt über fallgruppe + verstoss_modus.
verbotene_handlung:

  kuendigungsbutton:
    - id: B-VH-11
      verstoss_modus: [vorhanden_unzureichend, fehlt_vollstaendig]
      text: >
        die gesetzlich vorgeschriebene Kündigungsschaltfläche nicht unmittelbar
        und/oder leicht zugänglich vorzuhalten
      belegt_in: [T-002]
      hinweis: "Abstrakter Teil am Gesetzeswortlaut des § 312k Abs. 2 S. 4 BGB."
    - id: B-VH-11b
      verstoss_modus: [vorhanden_unzureichend]
      text: >
        sondern so, dass {{umgehungsmechanismus}} oder inhaltsgleiche Gestaltungen
        die Schaltfläche „{{beschriftung}}“ sichtbar wird
      slots:
        umgehungsmechanismus: "z. B. „erst nach Klick auf ‚Weitere Links einblenden‘“"
        beschriftung: "z. B. „Kündigen“"
      belegt_in: [T-002]
      warnung: >
        „oder inhaltsgleiche Gestaltungen“ schützt nur innerhalb DESSELBEN
        Umgehungsmechanismus. In T-002 hat die Beklagte danach den Mechanismus
        gewechselt (Zwei-Button-Lösung) und ein drittes Verfahren war nötig.
        Wenn der Sachverhalt es zulässt, den Erfolg statt des Mechanismus beschreiben.
    - id: B-VH-12
      verstoss_modus: [vorhanden_unzureichend]
      text: >
        {{ort}} einen Link „{{beschriftung}}“ bereit zu stellen, der nach Betätigung
        nicht unmittelbar zu einer Bestätigungsseite führt
      slots:
        ort: "z. B. „im Footer der Startseite“"
        beschriftung: "Linktext"
      belegt_in: [T-001]
      warnung: >
        Doppelt verengt: Ort UND Beschriftung. Eine Verlagerung des Links an eine
        andere Stelle beendet die Tenorwirkung. Nur wählen, wenn der Ort tragend ist.
    - id: B-VH-13
      verstoss_modus: [vorhanden_unzureichend]
      text: >
        eine Kündigung nur nach vorheriger Anmeldung mit Zugangsdaten zu ermöglichen,
        ohne zugleich eine Kündigung allein durch Angabe von Namen und weiteren
        gängigen Identifizierungsmerkmalen wie Anschrift und/oder Geburtsdatum anzubieten
      belegt_in: []
      status: vorschlag
      quelle_der_formulierung: "T-001, Entscheidungsgründe Rn. 27 — nicht aus dem Tenor"
      warnung: "NICHT TENORIERT GEWESEN. Als Vorschlag kennzeichnen, juristisch freigeben."

  dark_pattern:
    - id: B-VH-21
      verstoss_modus: [irrefuehrend_gestaltet]
      text: >
        ein Fenster einzublenden, in dem die Verbraucher noch einmal zu einer
        Entscheidung über {{gegenstand}} aufgefordert werden
      slots:
        gegenstand: "z. B. „die Ticketversicherung“"
      belegt_in: [T-003]
      warnung: >
        Erfasst nur ein „eingeblendetes Fenster“. Eine als eigene Seite ausgeführte
        Zwischenaufforderung ist wortlautmäßig etwas anderes. Erwägen:
        „ein Fenster einzublenden oder eine Zwischenseite anzuzeigen“.
      kombinationsregel: >
        Nach T-003 tragen weder Framing allein noch einmaliges Nagging allein den
        Tenor. Erst die Kombination mit einem angstauslösenden Ablehnungstext
        überschritt die Erheblichkeitsschwelle. Ein Dark-Pattern-Tenor muss die
        Kombination beschreiben — sonst droht Teilabweisung mit Kostenfolge.

  consent_gestaltung:
    - id: B-VH-31
      verstoss_modus: [irrefuehrend_gestaltet]
      text: >
        für die domainübergreifende Aufzeichnung und Auswertung des Nutzerverhaltens
        zu Analyse- und Marketingzwecken Informationen auf dem Endgerät des Nutzers zu
        speichern oder auf Informationen zuzugreifen, die bereits im Endgerät der
        Nutzer hinterlegt sind
      belegt_in: [T-004]
      hinweis: >
        Bewusst technologieoffen formuliert. Das Gericht hat das ausdrücklich
        gebilligt (Rn. 79: Auswechselbarkeit der Tracking-Technologien).

  agb_klausel:
    - id: B-VH-41
      verstoss_modus: [klausel_verwendet]
      text: "die Unterzeichnung einer Vereinbarung zu fordern, in der es heißt:"
      belegt_in: [T-005]
    - id: B-VH-42
      verstoss_modus: [klausel_verwendet]
      text: >
        die nachfolgende oder eine inhaltsgleiche Klausel zu verwenden
      belegt_in: [T-006, T-007]
      empfehlung: pflicht
      hinweis: "„oder eine inhaltsgleiche Klausel“ ist die Kerngleichheits-Erweiterung."
    - id: B-VH-43
      verstoss_modus: [klausel_verwendet]
      text: "oder sich auf eine solche Klausel zu berufen"
      belegt_in: [T-007]
      empfehlung: pflicht
      hinweis: >
        DER DOPPELAUSSPRUCH. Ohne ihn bleiben Altverträge unberührt (§ 11 UKlaG).
        Fehlt in T-005 und T-006 — in beiden Fällen als zu eng bewertet.

  irrefuehrende_werbung:
    - id: B-VH-51
      verstoss_modus: [irrefuehrend_gestaltet]
      text: "mit {{aussage}} zu werben"
      slots:
        aussage: "die beanstandete Werbeaussage, möglichst wörtlich"
      belegt_in: [T-008]

# =====================================================================
# SEGMENT: Ausnahmevorbehalt
# =====================================================================
ausnahmevorbehalt:
  - id: B-AV-01
    text: >
      sofern die Speicherung oder der Endgerätezugriff für den Betrieb der Website
      nicht unbedingt notwendig ist
    belegt_in: [T-004]
  - id: B-AV-02
    text: >
      ohne vor Beginn des Nutzungsvorgangs eine informierte und freiwillige
      Einwilligung der Nutzer einzuholen
    belegt_in: [T-004]
    hinweis: >
      Negative Tatbestandsvoraussetzungen aus dem Gesetzeswortlaut sind nach T-004
      Rn. 78 unschädlich für die Bestimmtheit, SOLANGE der übrige Antrag durch einen
      Anlagenbezug konkretisiert ist. Ohne Anlagenbezug wird der Tenor angreifbar.

# =====================================================================
# SEGMENT: Konkrete Verletzungsform
# =====================================================================
# DETERMINISTISCHE PRÜFUNG: Fehlt dieses Segment, ist das ein Befund vom Typ
# fehlender_baustein mit schwere=hoch, sofern die verbotene Handlung abstrakt
# formuliert ist (§ 253 Abs. 2 Nr. 2 ZPO).
konkrete_verletzungsform:
  - id: B-KV-01
    text: "wenn dies geschieht wie in Anlage {{anlage}} dargestellt"
    belegt_in: [T-004]
  - id: B-KV-02
    text: "wenn dies geschieht wie in Anlage {{anlage}}"
    belegt_in: [T-001]
  - id: B-KV-03
    text: "wenn dies geschieht wie nachstehend abgebildet:"
    belegt_in: [T-002, T-003]
    hinweis: >
      Abbildung wird in den Tenor eingebettet. Bei Gestaltungsfällen die robusteste
      Variante, weil die Verletzungsform Bestandteil des Titels wird und im
      Ordnungsmittelverfahren nicht erst aus der Akte gezogen werden muss.
    empfehlung: bei_gestaltungsfaellen
  - id: B-KV-04
    text: "[wörtlicher Klauseltext im Tenor]"
    belegt_in: [T-005, T-006, T-007]
    hinweis: "Bei Klauselfällen ersetzt der Klauselwortlaut die Anlage."
  - id: B-KV-05
    text: "wie geschehen in {{fundstelle}} (Anlage {{anlage}})"
    slots:
      fundstelle: "z. B. „im Schreiben der Beklagten vom 12.04.2021“"
    belegt_in: [T-008]
    hinweis: >
      Die klassische „wie geschehen“-Formel des § 8 UWG-Tenors. Bindet das Verbot an
      die festgestellte Verletzungsform und beseitigt Bestimmtheitsbedenken.

# =====================================================================
# DETERMINISTISCHE PRÜFREGELN (Prüfschritt 0, kein Modellaufruf)
# =====================================================================
pruefregeln:
  - id: R-01
    bedingung: "kein Baustein aus ordnungsmittelandrohung vorhanden"
    befund_typ: fehlender_baustein
    schwere: hoch
    meldung: >
      Ordnungsmittelandrohung nach § 890 ZPO fehlt. Ohne sie ist der Titel nicht
      unmittelbar vollstreckbar; die Androhung müsste nachträglich beantragt werden.
  - id: R-02
    bedingung: "ordnungsmittelandrohung vorhanden, aber ohne Vollstreckungsperson UND Schuldner ist juristische Person"
    befund_typ: unbestimmt
    schwere: mittel
    meldung: >
      Ordnungshaft kann nur gegen natürliche Personen vollstreckt werden. Bei
      juristischen Personen ist die Vollstreckungsperson zu benennen (vgl. B-OM-03).
    referenz: [T-005]
  - id: R-03
    bedingung: "rechtsgrundlage enthält § 1 UKlaG oder § 2 UKlaG UND fallgruppe = agb_klausel UND B-VH-43 fehlt"
    befund_typ: zu_eng
    schwere: hoch
    meldung: >
      Doppelter Verbotsausspruch fehlt. Untersagt ist nur das Verwenden, nicht das
      Sich-Berufen. Altverträge bleiben unberührt (§ 11 UKlaG).
    referenz: [T-007, T-005, T-006]
    vorschlag: "oder sich auf eine solche Klausel zu berufen"
  - id: R-04
    bedingung: "fallgruppe = agb_klausel UND B-VH-42 fehlt"
    befund_typ: zu_eng
    schwere: hoch
    meldung: >
      Formel „oder eine inhaltsgleiche Klausel“ fehlt. Der Tenor hängt am wörtlichen
      Klauseltext; eine sprachliche Umformulierung rutscht durch.
    referenz: [T-005]
  - id: R-05
    bedingung: "verbotene Handlung ist abstrakt formuliert UND kein Baustein aus konkrete_verletzungsform vorhanden"
    befund_typ: unbestimmt
    schwere: hoch
    meldung: >
      Abstrakter Verbotsteil ohne Bezug auf die konkrete Verletzungsform. Ein
      gesetzeswiederholender Antrag genügt § 253 Abs. 2 Nr. 2 ZPO in der Regel nicht.
    referenz: [T-004]
  - id: R-06
    bedingung: "anwendungsbereich enthält eine konkrete Domain UND verstoss_profil.kanal enthält mehr als einen Kanal"
    befund_typ: zu_eng
    schwere: hoch
    meldung: >
      Der Tenor nennt eine einzelne Internetseite, der Sachverhalt umfasst aber
      mehrere Kanäle. Verlagerung in die App oder auf eine andere Domain wäre nicht
      erfasst.
    referenz: [T-001, T-002, T-003]
    vorschlag_baustein: B-AB-03
  - id: R-07
    bedingung: "anwendungsbereich enthält eine konkrete Domain UND verstoss_profil.bekannte_umgehungen ist nicht leer"
    befund_typ: zu_eng
    schwere: hoch
    meldung: >
      Es sind bereits Umgehungen dokumentiert. Ein domaingebundener Anwendungsbereich
      erfasst diese voraussichtlich nicht.
    referenz: [T-002]
  - id: R-08
    bedingung: "rechtsgrundlage enthält „Art. 25 DSA“ als anspruchsgrundlage"
    befund_typ: normbezug
    schwere: hoch
    meldung: >
      Art. 25 DSA ist gegenüber der UGP-Richtlinie subsidiär (Art. 25 Abs. 2 DSA).
      Bei geschäftlichen Handlungen gegenüber Verbrauchern ist der Anspruch auf
      §§ 3 Abs. 2, 4a Abs. 1 S. 2 Nr. 3 UWG zu stützen; Art. 25 DSA wirkt nur als
      Auslegungsmaßstab.
    referenz: [T-003]
  - id: R-09
    bedingung: "rechtsgrundlage enthält „§ 25 TTDSG“"
    befund_typ: normbezug
    schwere: niedrig
    meldung: >
      Das TTDSG wurde zum 14.05.2024 in TDDDG umbenannt. Aktuelle Bezeichnung: § 25 TDDDG.
    referenz: [T-004]
  - id: R-10
    bedingung: "fallgruppe = dark_pattern UND nur ein Gestaltungsmerkmal beschrieben"
    befund_typ: ueberdehnt
    schwere: mittel
    meldung: >
      Nach T-003 tragen weder farbliche Hervorhebung allein noch einmaliges
      Nachfragen allein einen Unterlassungstenor. Die Kombination beschreiben,
      sonst droht Teilabweisung mit Kostenfolge.
    referenz: [T-003]


===== DATEI: tenore/T-001.yaml =====

id: T-001
quelle: urteil
gericht_az: "LG München I, 33 O 15098/22"
datum: "2023-10-10"
fundstelle_url: "https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-2023-N-36681"
fundstelle_zusatz: "GRUR-RS 2023, 36681; MMR 2024, 813. Volltext-PDF (Scan): https://www.vzbv.de/sites/default/files/2023-12/LG%20M%C3%BCnchen%20I_10.10.2023.pdf"
rechtskraeftig: true
rechtskraft_hinweis: >
  Berufung zum OLG München (6 U 4292/23 e) wurde von der Beklagten am 27.12.2023
  zurückgenommen.
parteien:
  klaeger: "Verbraucherzentrale Bundesverband e.V. (vzbv)"
  beklagte: "Sky Deutschland Fernsehen GmbH & Co. KG (Streamingdienst WOW)"
zitat_geprueft: true
zitat_quelle: "gesetze-bayern.de, Volltext, abgerufen 2026-08-21"

# --- Was war der Fall ---
sachverhalt: >
  Die Beklagte bietet über ihre Internetseite kostenpflichtige Streaming-Abonnements an.
  Am unteren Rand der Startseite befand sich ein Link „... Abo kündigen“. Nach dessen
  Betätigung gelangte der Nutzer nicht auf eine Bestätigungsseite, sondern auf eine
  Unterseite, auf der E-Mail-Adresse und PIN/Passwort abgefragt wurden. Erst nach
  erfolgreicher Anmeldung war eine Kündigung möglich.
fallgruppe: kuendigungsbutton
verstoss_modus: vorhanden_unzureichend
kanal:
  - website
rechtsgrundlage:
  - norm: "§ 2 Abs. 1 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 312k Abs. 2 BGB"
    funktion: anspruchsbegruendend
  - norm: "§ 8 Abs. 3 Nr. 3 UWG i.V.m. § 4 UKlaG"
    funktion: aktivlegitimation
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

# --- Der Tenor (wörtlich) ---
tenor_text: >
  I. Die Beklagte wird verurteilt, es bei Meidung eines für jeden Fall der
  Zuwiderhandlung fälligen Ordnungsgeldes bis zu € 250.000,00 ersatzweise,
  Ordnungshaft oder Ordnungshaft bis zu 6 Monaten, letztere zu vollziehen an den
  Geschäftsführern der Komplementär GmbH, im Rahmen geschäftlicher Handlungen
  gegenüber Verbrauchern zu unterlassen, auf der Internetseite https://www....de,
  die den Abschluss von entgeltlichen Abonnements in Form von Dauerschuldverhältnissen
  auf elektronischem Weg ermöglicht, im Footer der Startseite einen Link
  „... Abo kündigen“ bereit zu stellen, der nach Betätigung nicht unmittelbar zu einer
  Bestätigungsseite führt, wenn dies geschieht wie in Anlage K 1.
verletzungsform_anlage: "Anlage K 1 (Ablichtung der Internetseite)"

# --- Warum der Tenor so aussieht (Lernmaterial) ---
tenor_bausteine:
  - text: "es bei Meidung eines für jeden Fall der Zuwiderhandlung fälligen Ordnungsgeldes
      bis zu € 250.000,00 ersatzweise, Ordnungshaft oder Ordnungshaft bis zu 6 Monaten,
      letztere zu vollziehen an den Geschäftsführern der Komplementär GmbH"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-02
  - text: "im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern zu unterlassen"
    funktion: adressatenkreis
    baustein_id: B-AK-01
  - text: "auf der Internetseite https://www....de, die den Abschluss von entgeltlichen
      Abonnements in Form von Dauerschuldverhältnissen auf elektronischem Weg ermöglicht"
    funktion: anwendungsbereich
    baustein_id: B-AB-02
    anmerkung: >
      Kritisch eng: benennt EINE konkrete Domain. Vgl. Feld nachtraeglich_bewertet.
  - text: "im Footer der Startseite einen Link „... Abo kündigen“ bereit zu stellen, der
      nach Betätigung nicht unmittelbar zu einer Bestätigungsseite führt"
    funktion: verbotene_handlung
    baustein_id: B-VH-12
    anmerkung: >
      Doppelt verengt: Ort (Footer der Startseite) UND Beschriftung des Links.
  - text: "wenn dies geschieht wie in Anlage K 1"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-02

# --- Reichweite ---
kerngleich_umfasst:
  - beschreibung: "Link im Footer der Startseite, der auf eine Login-Maske mit
      E-Mail + Passwort führt, aber anders beschriftet ist (z. B. „Vertrag beenden“)"
    begruendung: >
      Die Beschriftung ist im Tenor durch „...“ anonymisiert; tragendes Element ist,
      dass der Link nicht unmittelbar zur Bestätigungsseite führt.
    sicherheit: mittel
  - beschreibung: "Link im Footer, der auf eine Zwischenseite mit Abfrage einer
      Kundennummer führt, bevor die Bestätigungsseite erscheint"
    begruendung: >
      Auch hier führt der Link nicht unmittelbar zur Bestätigungsseite; die
      Zwischenschaltung ist die untersagte Handlung.
    sicherheit: mittel

nicht_umfasst:
  - beschreibung: "Kündigungsschaltfläche führt unmittelbar auf eine Bestätigungsseite,
      auf der Name, Anschrift und Geburtsdatum eingegeben werden können"
    begruendung: "Erfüllt alle tragenden Elemente; genau der vom Gericht geforderte Zustand."
    sicherheit: hoch
  - beschreibung: "Der Kündigungslink wird aus dem Footer entfernt und stattdessen nur
      im eingeloggten Kundenbereich angeboten"
    begruendung: >
      Der Tenor untersagt eine Handlung „im Footer der Startseite“. Das vollständige
      Fehlen des Links im Footer ist zwar ein eigenständiger Verstoß gegen § 312k
      Abs. 2 S. 4 BGB, aber von DIESEM Tenor nicht erfasst — neuer Sachverhalt.
    sicherheit: hoch
  - beschreibung: "Login-Hürde in der Mobil-App des Anbieters"
    begruendung: >
      Der Tenor ist auf „die Internetseite https://www....de“ begrenzt. Die
      Entscheidungsgründe (Rn. 24) legen den Webseitenbegriff zwar funktional weit aus
      und beziehen Apps ein — der Tenor selbst tut dies nicht.
    sicherheit: mittel
  - beschreibung: "Login-Hürde auf einer anderen Domain desselben Konzerns"
    begruendung: "Der Tenor nennt eine einzelne Internetseite."
    sicherheit: hoch

# --- Lernsignal aus der Praxis ---
nachtraeglich_bewertet:
  zu_eng: ja
  hinweis: >
    Dieser Tenor ist an drei Stellen enger als der Sachverhalt es erzwingt:
    (1) eine einzelne Domain statt technikneutraler Formulierung,
    (2) „im Footer der Startseite“ statt ortsunabhängig,
    (3) die konkrete Linkbeschriftung.
    Auffällig ist der Kontrast zu den Entscheidungsgründen: Rn. 24 stellt ausdrücklich
    fest, dass der Webseitenbegriff funktional zu verstehen ist und auch Apps und
    Smart-TV-Oberflächen umfasst. Diese Weite ist im Tenor nicht abgebildet.
    Für vergleichbare Fälle: Anwendungsbereich technikneutral fassen
    (vgl. B-AB-03) und die Ortsangabe weglassen.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

# --- Brücke zum Monitor ---
pruefbare_merkmale:
  - merkmal: "Kündigungslink im Footer der Startseite vorhanden"
    pruefung: "DOM-Suche nach Linktext mit /kündig|Abo beenden|Vertrag beenden/i im <footer>"
    automatisierbar: true
  - merkmal: "Ziel des Links ist keine Login-Maske"
    pruefung: "Link folgen, Zielseite auf <input type=password> und Felder mit
      name/id ~ /pass|pin|login/ prüfen"
    automatisierbar: true
  - merkmal: "Zielseite ist eine Bestätigungsseite i.S.d. § 312k Abs. 2 S. 3 Nr. 1 BGB"
    pruefung: "Eingabefelder für Name, Anschrift und/oder Geburtsdatum vorhanden;
      Bestätigungsschaltfläche vorhanden"
    automatisierbar: true
  - merkmal: "Kündigung ohne Login tatsächlich durchführbar"
    pruefung: "manuell — Absenden erzeugt Rechtsfolge, nicht automatisiert testbar"
    automatisierbar: false

sicherheit: hoch
uneinigkeit: null
geprueft_von: "Claude (Recherche + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false

===== DATEI: tenore/T-002.yaml =====

id: T-002
quelle: urteil
gericht_az: "OLG München, 6 U 4336/23 e"
datum: "2025-03-20"
fundstelle_url: "https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-2025-N-5520"
fundstelle_zusatz: "GRUR-RR 2025, 302; NJW-RR 2025, 817; MMR 2025, 639. Vorinstanz: LG München I, 12 O 4127/23 vom 16.11.2023."
rechtskraeftig: true
parteien:
  klaeger: "Verbraucherzentrale NRW e.V."
  beklagte: "Sky Deutschland Fernsehen GmbH & Co. KG (sky.de)"
zitat_geprueft: true
zitat_quelle: "gesetze-bayern.de, Volltext, abgerufen 2026-08-21"

# --- Was war der Fall ---
sachverhalt: >
  Auf der Startseite war am unteren Bildrand eine graue Schaltfläche „Weitere Links
  einblenden“ platziert. Erst nach Klick darauf erschienen 58 Links zu Themen wie
  „Angebote & Pakete“ oder „Live Sport“; unterhalb davon fand sich in kleinerer,
  grauer Schrift die Schaltfläche „Kündigen“ — in derselben Zeile wie „Impressum“,
  „Kontakt“, „Datenschutz & Cookies“, „Nutzungsbedingungen“ und „AGB“.
fallgruppe: kuendigungsbutton
verstoss_modus: vorhanden_unzureichend
kanal:
  - website
rechtsgrundlage:
  - norm: "§ 3 Abs. 1 Nr. 1 UKlaG i.V.m. § 2 Abs. 1 S. 1, Abs. 2 Nr. 1 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 312k Abs. 2 S. 4 BGB"
    funktion: anspruchsbegruendend
  - norm: "§ 5 UKlaG i.V.m. § 13 Abs. 3 UWG"
    funktion: abmahnkostenerstattung
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

# --- Der Tenor (wörtlich, Ziffer I.1.1) ---
tenor_text: >
  Die Beklagte wird verurteilt, es bei Meidung eines Ordnungsgeldes von bis zu
  250.000,00 €, ersatzweise Ordnungshaft oder Ordnungshaft bis zu sechs Monaten,
  Ordnungshaft zu vollstrecken an den Mitgliedern der Geschäftsführung der
  Komplementärin, im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern künftig
  zu unterlassen, auf der Webseite https://www.s....de, über die Verbraucher
  kostenpflichtige Dauerschuldverhältnisse über PAY-TV-Inhalte auf elektronischem Weg
  abschließen können, die gesetzlich vorgeschriebene Kündigungsschaltfläche nicht
  unmittelbar und/oder leicht zugänglich vorzuhalten, sondern so, dass erst nach Klick
  auf „Weitere Links einblenden“ oder inhaltsgleiche Gestaltungen die Schaltfläche
  „Kündigen“ sichtbar wird, wie nachfolgend abgebildet: [Bildschirmabbildung im Urteil]
verletzungsform_anlage: "In den Tenor eingebettete Bildschirmabbildung"

teilabweisung:
  vorhanden: true
  beschreibung: >
    Das LG hatte zusätzlich einen Verstoß gegen § 312k Abs. 2 S. 2 BGB (gute Lesbarkeit)
    bejaht. Das OLG hat das aufgehoben: Maßstab sei die Kündigungsschaltfläche
    ISOLIERT betrachtet, nicht der Vergleich mit der auffälligeren
    Vertragsabschluss-Schaltfläche (Rn. 20-23). Kostenfolge: § 92 Abs. 1 S. 2 ZPO,
    Kosten gegeneinander aufgehoben.
  lehre_fuer_tenorierung: >
    Ein zusätzlich geltend gemachtes Merkmal, das nicht durchdringt, kostet die Hälfte
    der Kosten. „Gut lesbar“ nur dann in den Antrag aufnehmen, wenn die Schaltfläche
    für sich genommen schlecht lesbar ist — nicht im Vergleich zum Bestellbutton.

# --- Warum der Tenor so aussieht ---
tenor_bausteine:
  - text: "es bei Meidung eines Ordnungsgeldes von bis zu 250.000,00 €, ersatzweise
      Ordnungshaft oder Ordnungshaft bis zu sechs Monaten, Ordnungshaft zu vollstrecken
      an den Mitgliedern der Geschäftsführung der Komplementärin"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-02
  - text: "im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern künftig zu unterlassen"
    funktion: adressatenkreis
    baustein_id: B-AK-01
  - text: "auf der Webseite https://www.s....de, über die Verbraucher kostenpflichtige
      Dauerschuldverhältnisse über PAY-TV-Inhalte auf elektronischem Weg abschließen können"
    funktion: anwendungsbereich
    baustein_id: B-AB-02
  - text: "die gesetzlich vorgeschriebene Kündigungsschaltfläche nicht unmittelbar
      und/oder leicht zugänglich vorzuhalten"
    funktion: verbotene_handlung
    baustein_id: B-VH-11
    anmerkung: >
      Abstrakter Teil, orientiert am Gesetzeswortlaut des § 312k Abs. 2 S. 4 BGB.
  - text: "sondern so, dass erst nach Klick auf „Weitere Links einblenden“ oder
      inhaltsgleiche Gestaltungen die Schaltfläche „Kündigen“ sichtbar wird"
    funktion: verbotene_handlung
    baustein_id: B-VH-11b
    anmerkung: >
      Konkretisierender Teil. Der Zusatz „oder inhaltsgleiche Gestaltungen“ ist die
      Kerngleichheits-Erweiterung — der wichtigste Baustein dieses Tenors.
  - text: "wie nachfolgend abgebildet"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-03

# --- Reichweite ---
kerngleich_umfasst:
  - beschreibung: "Kündigungsbutton hinter einer Schaltfläche „Mehr anzeigen“ oder
      „Alle Links“ versteckt"
    begruendung: >
      „oder inhaltsgleiche Gestaltungen“ erfasst funktional gleichwertige
      Aufklapp-Mechanismen unabhängig von der Beschriftung.
    sicherheit: hoch
  - beschreibung: "Kündigungsbutton hinter einem Akkordeon- oder Burger-Menü,
      das nicht auf die Kündigungsmöglichkeit hindeutet"
    begruendung: >
      Tragendes Element ist nach Rn. 27, dass der Nutzer die Kündigungsmöglichkeit
      unter der allgemein gehaltenen Bezeichnung nicht erwartet.
    sicherheit: mittel
  - beschreibung: "Kündigungsbutton sofort sichtbar, aber am Ende von 58 gleichartigen
      Links platziert"
    begruendung: >
      Zweifelhaft. Der Tenor knüpft an „erst nach Klick ... sichtbar wird“ an. Fehlt
      der Klick, greift der konkretisierende Teil nicht mehr. Ordnungsmittelverfahren
      mit offenem Ausgang.
    sicherheit: niedrig

nicht_umfasst:
  - beschreibung: "Zwei nebeneinander platzierte, sofort sichtbare Schaltflächen
      „Abo beenden“ und „Infos zur Kündigung“, die zu unterschiedlichen Zielen führen"
    begruendung: >
      Die Schaltfläche ist sofort sichtbar, es fehlt am Merkmal „erst nach Klick ...
      sichtbar wird“. Der Verstoß liegt hier in der Uneindeutigkeit der Beschriftung —
      ein anderes Tatbestandsmerkmal.
    sicherheit: hoch
    belegt_durch: "LG München I, 33 O 14294/25 vom 14.07.2026 — neues Verfahren nötig"
  - beschreibung: "Kündigungsschaltfläche in kleiner, grauer Schrift, aber sofort sichtbar"
    begruendung: >
      Das OLG hat den Lesbarkeitsvorwurf ausdrücklich abgewiesen (Rn. 23).
    sicherheit: hoch
  - beschreibung: "Kündigungsbutton fehlt vollständig"
    begruendung: >
      Der Tenor untersagt eine bestimmte Art des Vorhaltens, nicht das Fehlen.
      Praktisch würde man argumentieren, dass das Fehlen erst recht erfasst ist —
      dafür fehlt hier aber der Wortlaut.
    sicherheit: mittel

# --- Lernsignal aus der Praxis: DER Referenzfall ---
nachtraeglich_bewertet:
  zu_eng: ja
  hinweis: >
    Dieser Tenor enthält bereits die Erweiterung „oder inhaltsgleiche Gestaltungen“
    und war trotzdem zu eng. Die Beklagte gestaltete den Kündigungsweg daraufhin um:
    Der Button war nun sofort sichtbar, aber neben ihm stand eine zweite, ähnlich
    benannte Schaltfläche („Abo beenden“ vs. „Infos zur Kündigung“), die zu Telefon,
    Chat und WhatsApp führte. Die Verbraucherzentrale NRW musste erneut klagen und
    gewann erneut (LG München I, 33 O 14294/25 vom 14.07.2026).
    LEHRE: „inhaltsgleiche Gestaltungen“ wirkt nur innerhalb desselben
    Umgehungsmechanismus. Es schützt gegen andere Aufklapp-Beschriftungen, nicht
    gegen einen anderen Mechanismus. Wer nur die Sichtbarkeit tenoriert, lässt die
    Eindeutigkeit der Beschriftung offen.
    EMPFEHLUNG für vergleichbare Fälle: Anwendungsbereich technikneutral (B-AB-03) und
    verbotene Handlung am Erfolg statt am Mechanismus ausrichten — „ohne dass die zur
    elektronischen Kündigung führende Schaltfläche für den durchschnittlichen
    Verbraucher ohne erheblichen Aufwand und eindeutig als solche erkennbar ist“.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

umgehungskette:
  - stufe: 1
    az: "LG München I, 33 O 15098/22 (10.10.2023)"
    gestaltung: "Login-Hürde vor der Bestätigungsseite (WOW)"
    ausgang: "untersagt, rechtskräftig"
  - stufe: 2
    az: "OLG München, 6 U 4336/23 e (20.03.2025)"
    gestaltung: "Button hinter „Weitere Links einblenden“, unter 58 Links (sky.de)"
    ausgang: "untersagt, rechtskräftig"
  - stufe: 3
    az: "LG München I, 33 O 14294/25 (14.07.2026)"
    gestaltung: "Zwei-Button-Lösung „Abo beenden“ / „Infos zur Kündigung“; Kündigungsgrund als Pflichtfeld"
    ausgang: "untersagt"

umgehungskette_hinweis: >
    Dasselbe Unternehmen, dreimal derselbe Grundverstoß, drei Verfahren.
    Das ist der Beleg dafür, dass die Reichweite des Tenors — nicht seine
    Existenz — das Problem ist. Dieser Datensatz ist der stärkste Beleg im
    gesamten Register.

# --- Brücke zum Monitor ---
pruefbare_merkmale:
  - merkmal: "Kündigungsschaltfläche ohne vorherigen Klick sichtbar"
    pruefung: "Nach Seitenaufruf DOM auf Element mit Text /kündig/i prüfen, das ohne
      JS-Interaktion sichtbar ist (getComputedStyle: display != none, visibility != hidden)"
    automatisierbar: true
  - merkmal: "Kein Aufklapp-Element zwischen Einstieg und Kündigungsschaltfläche"
    pruefung: "Prüfen, ob das Element Nachfahre eines Containers mit aria-expanded='false',
      <details> ohne open, oder eines per Klick eingeblendeten Wrappers ist"
    automatisierbar: true
  - merkmal: "Anzahl konkurrierender Links in unmittelbarer Umgebung"
    pruefung: "Anzahl <a>-Elemente im selben Footer-Container zählen; Schwelle
      dokumentieren, nicht als Verstoß werten"
    automatisierbar: true
  - merkmal: "Nur eine Schaltfläche adressiert die Kündigung"
    pruefung: "Alle Elemente mit Text /kündig|abo beenden|vertrag beenden/i zählen und
      ihre Ziel-URLs vergleichen. Mehr als eine mit unterschiedlichem Ziel = Prüfhinweis"
    automatisierbar: true
    herkunft: "Aus der Umgehung Stufe 3 abgeleitet, nicht aus dem Tenor selbst"

sicherheit: hoch
uneinigkeit: null
geprueft_von: "Claude (Recherche + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false


===== DATEI: tenore/T-003.yaml =====

id: T-003
quelle: urteil
gericht_az: "OLG Bamberg, 3 UKl 11/24 e"
datum: "2025-02-05"
fundstelle_url: "https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-2025-N-6221"
fundstelle_zusatz: "GRUR-RR 2025, 238; CR 2025, 470; VuR 2025, 225. PDF (Scan): https://www.vzbv.de/sites/default/files/2025-03/OLG%20Bamberg_05.02.2025.pdf"
rechtskraeftig: false
rechtskraft_hinweis: "Revision nicht zugelassen; Verfahren beim BGH unter I ZR 56/25 anhängig. Vor Verwendung Verfahrensstand prüfen."
parteien:
  klaeger: "Verbraucherzentrale Bundesverband e.V. (vzbv)"
  beklagte: "CTS Eventim AG & Co. KGaA"
zitat_geprueft: true
zitat_quelle: "gesetze-bayern.de, Volltext, abgerufen 2026-08-21"

# --- Was war der Fall ---
sachverhalt: >
  Im Warenkorb wurde eine kostenpflichtige Ticketversicherung zentriert und mit blauem
  Hintergrund hervorgehoben angeboten. Wählte der Besteller sie nicht aus und klickte
  auf „Weiter zur Kasse“, öffnete sich ein Pop-up, in dem der Abschluss erneut empfohlen
  wurde. Zur Auswahl standen ein weiß unterlegter Button „ich trage das volle Risiko“
  und ein blau unterlegter Button mit dem Versicherungsangebot.
fallgruppe: dark_pattern_dsa
verstoss_modus: irrefuehrend_gestaltet
kanal:
  - website
rechtsgrundlage:
  - norm: "§ 2 Abs. 1 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 3 Abs. 2 UWG"
    funktion: anspruchsbegruendend
  - norm: "§ 4a Abs. 1 S. 2 Nr. 3, S. 3 UWG"
    funktion: anspruchsbegruendend
  - norm: "Art. 25 Abs. 1, Abs. 3 DSA (VO (EU) 2022/2065)"
    funktion: auslegungsmassstab
    anmerkung: >
      WICHTIG: Das Gericht hat Art. 25 DSA gerade NICHT unmittelbar angewendet
      (Bereichsausnahme Art. 25 Abs. 2 DSA zugunsten der UGP-RL). Art. 25 DSA wirkt
      nur über § 3 Abs. 2 und § 4a UWG als Auslegungsmaßstab. Wer § 2 Abs. 2 Nr. 57
      UKlaG i.V.m. Art. 25 DSA als Anspruchsgrundlage in den Tenor schreibt, liegt
      nach dieser Entscheidung falsch.
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

# --- Der Tenor (wörtlich, Ziffer 1) ---
tenor_text: >
  Die Beklagte wird verurteilt, es bei Meidung eines für jeden Fall der Zuwiderhandlung
  vom Gericht festzusetzenden Ordnungsgeldes bis zu EUR 250.000,00, ersatzweise
  Ordnungshaft, oder einer Ordnungshaft bis zu sechs Monaten, wobei die Ordnungshaft an
  ihren jeweiligen gesetzlichen Vertretern zu vollziehen ist, und insgesamt zwei Jahre
  nicht übersteigen darf, zu unterlassen, im Rahmen geschäftlicher Handlungen gegenüber
  Verbrauchern im Internet unter https://www.eventim.de für den Kauf von Tickets zu
  werben bzw. werben zu lassen und in diesem Zusammenhang gegenüber Verbrauchern, die im
  Warenkorb eine angebotene kostenpflichtige Ticketversicherung nicht ausgewählt haben
  und den Bestellvorgang über den Button „Weiter zur Kasse“ fortsetzen, ein Fenster
  einzublenden, in dem die Verbraucher noch einmal zu einer Entscheidung über die
  Ticketversicherung aufgefordert werden, wenn dies geschieht wie nachstehend abgebildet:
  [Bildschirmabbildung im Urteil]
verletzungsform_anlage: "In den Tenor eingebettete Bildschirmabbildung (Anlage K 2 / K 6)"

teilabweisung:
  vorhanden: true
  beschreibung: >
    Der erste Klageantrag — das Angebot der Ticketversicherung im Warenkorb blau
    hervorzuheben (Anlage K 1 / K 5) — wurde ABGEWIESEN. Das Gericht bejahte zwar ein
    „Framing“ i.S.v. Art. 25 Abs. 3 lit. a DSA (Rn. 32), verneinte aber die
    Erheblichkeitsschwelle (Rn. 38): Der Ticketerwerb nehme grafisch mehr Raum ein,
    die Alternative sei ohne Weiteres wahrnehmbar. Kosten gegeneinander aufgehoben.
  lehre_fuer_tenorierung: >
    Farbliche Hervorhebung allein trägt keinen Unterlassungstenor. Auch wiederholte
    Nachfrage allein trägt ihn nicht (Rn. 45: „sanftes Nagging“). Erst die KOMBINATION
    aus Nagging, Framing und dem angstauslösenden Ablehnungstext „ich trage das volle
    Risiko“ überschritt die Schwelle (Rn. 50). Ein Dark-Pattern-Tenor muss deshalb
    die Kombination beschreiben, nicht das Einzelmerkmal.

# --- Warum der Tenor so aussieht ---
tenor_bausteine:
  - text: "es bei Meidung eines für jeden Fall der Zuwiderhandlung vom Gericht
      festzusetzenden Ordnungsgeldes bis zu EUR 250.000,00, ersatzweise Ordnungshaft,
      oder einer Ordnungshaft bis zu sechs Monaten, wobei die Ordnungshaft an ihren
      jeweiligen gesetzlichen Vertretern zu vollziehen ist, und insgesamt zwei Jahre
      nicht übersteigen darf"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-03
    anmerkung: "Vollständigste Variante im Register — mit Zwei-Jahres-Obergrenze."
  - text: "im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern"
    funktion: adressatenkreis
    baustein_id: B-AK-01
  - text: "im Internet unter https://www.eventim.de für den Kauf von Tickets zu werben
      bzw. werben zu lassen"
    funktion: anwendungsbereich
    baustein_id: B-AB-04
    anmerkung: >
      „bzw. werben zu lassen“ erfasst Beauftragte und Dienstleister —
      vgl. § 8 Abs. 2 UWG. Wichtiger Baustein, wird oft vergessen.
  - text: "gegenüber Verbrauchern, die im Warenkorb eine angebotene kostenpflichtige
      Ticketversicherung nicht ausgewählt haben und den Bestellvorgang über den Button
      „Weiter zur Kasse“ fortsetzen"
    funktion: anwendungsbereich
    baustein_id: B-AB-05
    anmerkung: "Auslösebedingung — beschreibt den Zustand, in dem das Verbot greift."
  - text: "ein Fenster einzublenden, in dem die Verbraucher noch einmal zu einer
      Entscheidung über die Ticketversicherung aufgefordert werden"
    funktion: verbotene_handlung
    baustein_id: B-VH-21
  - text: "wenn dies geschieht wie nachstehend abgebildet"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-03
    anmerkung: >
      Hier trägt die Abbildung die volle Last. Ohne sie wäre der Tenor nach der
      eigenen Begründung des Gerichts zu weit, weil einmaliges Nachfragen für sich
      genommen zulässig ist.

# --- Reichweite ---
kerngleich_umfasst:
  - beschreibung: "Pop-up mit demselben Aufbau, aber Ablehnungstext „ich verzichte auf
      jeden Schutz“"
    begruendung: >
      Tragend ist nach Rn. 50 die angstauslösende Wirkung des Ablehnungstextes in
      Verbindung mit dem Nagging, nicht die konkrete Wortwahl.
    sicherheit: mittel
  - beschreibung: "Dasselbe Pop-up für ein anderes Zusatzprodukt (z. B. Garantieverlängerung)
      mit angstauslösendem Ablehnungstext"
    begruendung: >
      Der Tenor nennt ausdrücklich „Ticketversicherung“. Ein anderes Produkt ist vom
      Wortlaut nicht erfasst.
    sicherheit: niedrig
    hinweis: "Eher nicht_umfasst — als Uneinigkeitsfall geführt."

nicht_umfasst:
  - beschreibung: "Blaue Hervorhebung des Versicherungsangebots im Warenkorb ohne Pop-up"
    begruendung: >
      Ausdrücklich abgewiesen (Rn. 39). Framing allein überschreitet die
      Erheblichkeitsschwelle nicht.
    sicherheit: hoch
  - beschreibung: "Einmaliges Pop-up mit neutralem Ablehnungstext („Nein, danke“) und
      gleich großen Buttons"
    begruendung: >
      Rn. 45: einmaliges Nachfragen ist zulässig. Rn. 47: gleich große Alternativen
      sind kein unzulässiges Framing. Ohne den angstauslösenden Text fehlt das
      tragende Element.
    sicherheit: hoch
  - beschreibung: "Dasselbe Pop-up in der Eventim-App"
    begruendung: "Der Tenor nennt „im Internet unter https://www.eventim.de“."
    sicherheit: hoch
  - beschreibung: "Pop-up erscheint erst nach dem Klick auf „Zur Kasse“ auf einer
      Folgeseite statt als eingeblendetes Fenster"
    begruendung: >
      Der Tenor untersagt, „ein Fenster einzublenden“. Eine eigenständige Zwischenseite
      ist wortlautmäßig etwas anderes — Umgehungsrisiko.
    sicherheit: mittel

# --- Lernsignal ---
nachtraeglich_bewertet:
  zu_eng: ja
  hinweis: >
    Zwei erkennbare Verengungen:
    (1) „im Internet unter https://www.eventim.de“ — App und weitere Domains
        (eventim.ch, .at, White-Label-Shops) sind nicht erfasst.
    (2) „ein Fenster einzublenden“ — eine als eigene Seite ausgeführte
        Zwischenaufforderung ist wortlautmäßig kein eingeblendetes Fenster.
    Für vergleichbare Fälle: technikneutraler Anwendungsbereich (B-AB-03) und
    „ein Fenster oder eine Zwischenseite einzublenden oder anzuzeigen“.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

# --- Brücke zum Monitor ---
pruefbare_merkmale:
  - merkmal: "Interstitial nach Klick auf „Weiter zur Kasse“ ohne ausgewählte Versicherung"
    pruefung: "Warenkorb befüllen, Versicherungs-Checkbox nicht setzen, Button klicken,
      auf neu erscheinendes Element mit role=dialog / z-index-Overlay prüfen"
    automatisierbar: true
  - merkmal: "Ablehnungs-Button trägt angstauslösenden Text"
    pruefung: "Text des Ablehnungs-Buttons gegen Wortliste prüfen (Risiko, Verzicht,
      ungeschützt, volle Haftung). Nur Prüfhinweis, keine automatische Wertung"
    automatisierbar: true
    hinweis: "Die rechtliche Wertung bleibt zwingend beim Menschen."
  - merkmal: "Optische Gleichwertigkeit der beiden Auswahl-Buttons"
    pruefung: "Bounding-Box-Fläche und Kontrastverhältnis beider Buttons vergleichen"
    automatisierbar: true
  - merkmal: "Anzahl der Nachfragen im Bestellprozess"
    pruefung: "manuell — vollständiger Bestellprozess bis zur Zahlung erforderlich"
    automatisierbar: false

sicherheit: hoch
uneinigkeit: >
  Bei „Dasselbe Pop-up für ein anderes Zusatzprodukt“ ist vertretbar, dies als
  kerngleich zu behandeln (Schutzzweck) oder als neuen Sachverhalt (Wortlaut).
  Uneinigkeit bewusst stehen gelassen, sicherheit auf niedrig gesetzt.
geprueft_von: "Claude (Recherche + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false


===== DATEI: tenore/T-004.yaml =====

id: T-004
quelle: urteil
gericht_az: "LG München I, 33 O 14776/19"
datum: "2022-11-29"
fundstelle_url: "https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-2022-N-39300"
fundstelle_zusatz: "GRUR-RS 2022, 39300; MMR 2023, 222; ZD 2023, 223; K&R 2023, 220. PDF (Scan): https://www.vzbv.de/sites/default/files/2023-01/LG%20M%C3%BCnchen%20I_29.11.2022.pdf"
rechtskraeftig: unbekannt
rechtskraft_hinweis: "Vor Verwendung Verfahrensstand prüfen."
parteien:
  klaeger: "Verbraucherzentrale Bundesverband e.V. (vzbv)"
  beklagte: "BurdaForward GmbH (www.focus.de), Rubrumberichtigung von Focus Online Group GmbH"
zitat_geprueft: true
zitat_quelle: "gesetze-bayern.de, Volltext, abgerufen 2026-08-21"

# --- Was war der Fall ---
sachverhalt: >
  Beim Aufruf des Nachrichtenportals erschien eine Consent Management Platform nach dem
  Standard IAB TCF 2.0. Auf der ersten Ebene standen nur „Akzeptieren“ (blau hervorgehoben)
  und „Einstellungen“ zur Verfügung; eine Ablehnung war erst auf der zweiten Ebene
  möglich, wo „Alle Akzeptieren“ erneut hervorgehoben und „alle ablehnen“ unauffällig
  gestaltet war. Der TC String wurde als Cookie auf dem Endgerät gespeichert und diente
  der domainübergreifenden Nachverfolgung.
fallgruppe: consent_gestaltung
verstoss_modus: irrefuehrend_gestaltet
kanal:
  - website
rechtsgrundlage:
  - norm: "§ 2 Abs. 1 S. 1, Abs. 2 S. 1 Nr. 11 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 25 TTDSG"
    funktion: anspruchsbegruendend
    anmerkung: >
      Heute § 25 TDDDG (Umbenennung des TTDSG zum 14.05.2024). Bei Neuformulierung
      die aktuelle Normbezeichnung verwenden.
  - norm: "Art. 4 Nr. 11, Art. 7 DSGVO"
    funktion: auslegungsmassstab
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

# --- Der Tenor (wörtlich, Ziffer I) ---
tenor_text: >
  I. Die Beklagte wird verurteilt, es bei Vermeidung eines vom Gericht für jeden Fall der
  Zuwiderhandlung festzusetzenden Ordnungsgeldes von bis zu € 250.000,00, ersatzweise
  Ordnungshaft oder Ordnungshaft bis zu sechs Monaten, letztere zu vollziehen an ihrem
  Geschäftsführer, zu unterlassen, im Rahmen geschäftlicher Handlungen gegenüber
  Verbrauchern in Telemedien für die domainübergreifende Aufzeichnung und Auswertung des
  Nutzerverhaltens zu Analyse- und Marketingzwecken Informationen auf dem Endgerät des
  Nutzers zu speichern oder auf Informationen zuzugreifen, die bereits im Endgerät der
  Nutzer hinterlegt sind, sofern die Speicherung oder der Endgerätezugriff für den
  Betrieb der Website nicht unbedingt notwendig ist, ohne vor Beginn des Nutzungsvorgangs
  eine informierte und freiwillige Einwilligung der Nutzer für den Zugriff auf deren
  Endgeräte oder Endgeräteinformationen einzuholen, wenn dies geschieht wie in
  Anlage K 58 dargestellt.
verletzungsform_anlage: "Anlage K 58 (Gesamtausdruck der CMP, 142 Bildschirmansichten)"

teilabweisung:
  vorhanden: true
  beschreibung: >
    Klageanträge 2 (Informationspflichten) und 3 (Art. 26 Abs. 2 S. 2 DSGVO,
    gemeinsame Verantwortlichkeit) wurden abgewiesen. Kosten: Kläger ¾, Beklagte ¼.
  lehre_fuer_tenorierung: >
    Wer eine Klage auf § 25 TTDSG/TDDDG stützt, kann darauf keine eigenständigen
    Informationspflichten stützen. Die Anträge kosteten ¾ der Kosten. Anspruchsgrundlage
    und Antragsumfang müssen zusammenpassen.

# --- Bausteine ---
tenor_bausteine:
  - text: "es bei Vermeidung eines vom Gericht für jeden Fall der Zuwiderhandlung
      festzusetzenden Ordnungsgeldes von bis zu € 250.000,00, ersatzweise Ordnungshaft
      oder Ordnungshaft bis zu sechs Monaten, letztere zu vollziehen an ihrem Geschäftsführer"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-01
  - text: "im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern"
    funktion: adressatenkreis
    baustein_id: B-AK-01
  - text: "in Telemedien"
    funktion: anwendungsbereich
    baustein_id: B-AB-03
    anmerkung: >
      TECHNIKNEUTRAL. Der beste Anwendungsbereichs-Baustein im gesamten Register:
      keine Domain, keine Plattform, keine Seitenrolle. Erfasst Website, App und
      Smart-TV-Oberfläche gleichermaßen. Vorbild für Fälle, in denen der Sachverhalt
      keine Beschränkung auf eine Domain erzwingt.
  - text: "für die domainübergreifende Aufzeichnung und Auswertung des Nutzerverhaltens
      zu Analyse- und Marketingzwecken Informationen auf dem Endgerät des Nutzers zu
      speichern oder auf Informationen zuzugreifen, die bereits im Endgerät der Nutzer
      hinterlegt sind"
    funktion: verbotene_handlung
    baustein_id: B-VH-31
  - text: "sofern die Speicherung oder der Endgerätezugriff für den Betrieb der Website
      nicht unbedingt notwendig ist"
    funktion: ausnahmevorbehalt
    baustein_id: B-AV-01
    anmerkung: >
      Negative Tatbestandsvoraussetzung, aus dem Gesetzeswortlaut übernommen.
      Nach Rn. 78 unschädlich für die Bestimmtheit, solange der übrige Antrag
      hinreichend konkretisiert ist.
  - text: "ohne vor Beginn des Nutzungsvorgangs eine informierte und freiwillige
      Einwilligung der Nutzer für den Zugriff auf deren Endgeräte oder
      Endgeräteinformationen einzuholen"
    funktion: ausnahmevorbehalt
    baustein_id: B-AV-02
  - text: "wenn dies geschieht wie in Anlage K 58 dargestellt"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-01

bestimmtheit_lehre: >
  Rn. 77-79 ist die wichtigste Passage im Register zum Thema Bestimmtheit:
  Ein abstrakt formulierter Verbotsteil ist zulässig, WENN er durch Bezugnahme auf die
  konkrete Verletzungsform (hier: Anlage K 58) präzisiert wird. Diese Zweiteilung —
  abstrakte Handlungsbeschreibung PLUS konkreter Anlagenbezug — ist die Bauform, mit der
  ein Tenor gleichzeitig weit und bestimmt sein kann. Das Gericht begründet die Weite
  ausdrücklich mit der Auswechselbarkeit der Tracking-Technologien (Rn. 79).

# --- Reichweite ---
kerngleich_umfasst:
  - beschreibung: "CMP eines anderen Anbieters mit demselben zweistufigen Aufbau
      (Ablehnen erst auf zweiter Ebene)"
    begruendung: >
      Tragendes Element ist nach Rn. 112 die fehlende Freiwilligkeit wegen des
      Mehraufwands für die Ablehnung, nicht der konkrete CMP-Anbieter.
    sicherheit: mittel
  - beschreibung: "Andere Tracking-Technologie (Fingerprinting statt Cookie) bei
      unverändertem Einwilligungsmechanismus"
    begruendung: >
      Der Tenor benennt bewusst keine konkrete Technologie; Rn. 79 begründet das mit
      der Auswechselbarkeit.
    sicherheit: hoch

nicht_umfasst:
  - beschreibung: "Ablehnen-Button gleichrangig auf der ersten Ebene, Speicherung
      erst nach aktiver Zustimmung"
    begruendung: "Freiwilligkeit gegeben; alle tragenden Elemente entfallen."
    sicherheit: hoch
  - beschreibung: "PUR-Abo-Modell (Einwilligung oder Bezahlung)"
    begruendung: >
      Anderer Sachverhalt; die Freiwilligkeitsfrage stellt sich unter anderen
      Vorzeichen. Nicht Gegenstand dieses Verfahrens.
    sicherheit: mittel
  - beschreibung: "Unzureichende Informationen in der Datenschutzerklärung"
    begruendung: >
      Ausdrücklich abgewiesen (Klageanträge 2 und 3). § 25 TTDSG statuiert nach
      Auffassung der Kammer keine eigenständigen Informationspflichten.
    sicherheit: hoch

nachtraeglich_bewertet:
  zu_eng: nein
  hinweis: >
    Dieser Tenor ist im Anwendungsbereich vorbildlich weit („in Telemedien“) und im
    Verbotsteil durch den Anlagenbezug bestimmt. Er ist das positive Gegenstück zu
    T-001 und T-002 und sollte im System als Vorbild für den Reichweiten-Slider
    „kerngleich“ hinterlegt sein.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

# --- Brücke zum Monitor ---
pruefbare_merkmale:
  - merkmal: "Ablehnen-Option auf der ersten Ebene des Consent-Banners vorhanden"
    pruefung: "Im Banner-Container nach Button mit Text /ablehnen|nur notwendig|reject/i
      suchen, ohne vorherige Interaktion"
    automatisierbar: true
  - merkmal: "Optische Gleichrangigkeit von Zustimmen und Ablehnen"
    pruefung: "Fläche, Hintergrundfarbe und Kontrastverhältnis beider Buttons vergleichen"
    automatisierbar: true
  - merkmal: "Keine nicht-notwendigen Cookies vor Interaktion"
    pruefung: "Frischer Browserkontext, Seite laden, keine Interaktion, document.cookie
      und Storage gegen Liste bekannter Tracker abgleichen"
    automatisierbar: true
  - merkmal: "Keine Drittanbieter-Requests vor Interaktion"
    pruefung: "Netzwerkmitschnitt vor erster Interaktion, Third-Party-Domains auflisten"
    automatisierbar: true
  - merkmal: "Bewertung, ob ein Cookie technisch notwendig ist"
    pruefung: "manuell — rechtliche Wertung, nicht automatisierbar"
    automatisierbar: false

sicherheit: hoch
uneinigkeit: null
geprueft_von: "Claude (Recherche + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false


===== DATEI: tenore/T-005.yaml =====

id: T-005
quelle: urteil
gericht_az: "LG Köln, 31 O 88/11"
datum: "2011-08-04"
fundstelle_url: "https://de.openlegaldata.io/case/lg-koln-2011-08-04-31-o-8811"
rechtskraeftig: unbekannt
rechtskraft_hinweis: "Vor Verwendung Verfahrensstand prüfen. Alter Fall — Rechtslage zum P-Konto hat sich seit 2011 geändert (§ 850k ZPO a.F., heute §§ 899 ff. ZPO)."
parteien:
  klaeger: "Verbraucherschutzverband"
  beklagte: "Kreditinstitut"
zitat_geprueft: teilweise
zitat_quelle: >
  Übernommen aus der Team-Sammlung „Tenore_Beispiele” (Google Doc). Wortlaut stimmt mit
  der dort angegebenen Quelle openlegaldata.io überein, wurde aber im Rahmen dieser
  Recherche nicht am Volltext gegengeprüft. VOR DEM PITCH GEGENPRÜFEN.

sachverhalt: >
  Das beklagte Kreditinstitut verlangte von Verbrauchern, die im Rahmen eines
  bestehenden Zahlungsdiensterahmenvertrages die Führung eines Pfändungsschutzkontos
  verlangten, die Unterzeichnung einer Vereinbarung über einen Wechsel des Kontomodells
  mit einem Pauschalpreis von 17,50 EUR monatlich.
fallgruppe: agb_klausel
verstoss_modus: klausel_verwendet
kanal:
  - offline
  - website
rechtsgrundlage:
  - norm: "§ 1 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 850k ZPO (a.F.)"
    funktion: anspruchsbegruendend
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

tenor_text: >
  Die Beklagte wird unter Androhung eines vom Gericht für jeden Fall der Zuwiderhandlung
  festzusetzenden Ordnungsgeldes bis zu 250.000,00 € - ersatzweise Ordnungshaft - oder
  der Ordnungshaft bis zu 6 Monaten verurteilt, es zu unterlassen, von Verbrauchern, die
  im Rahmen eines bestehenden Zahlungsdiensterahmenvertrages von der Beklagten die
  Führung eines Pfändungsschutzkontos im Sinne von § 850k ZPO verlangen, die
  Unterzeichnung einer Vereinbarung zu fordern, in der es heißt:
  „Der Kontoinhaber und die Bank vereinbaren weiterhin einen Wechsel des Kontomodells
  für das o.g. Kontokorrentkonto. Das Kontokorrentkonto wird künftig im Kontomodell
  P-Konto geführt. Das Kontomodell P-Konto weist folgende wesentliche Merkmale auf:
  Pauschalpreis 17,50 € monatlich (…)"
verletzungsform_anlage: "Klauselwortlaut im Tenor selbst"

tenor_bausteine:
  - text: "unter Androhung eines vom Gericht für jeden Fall der Zuwiderhandlung
      festzusetzenden Ordnungsgeldes bis zu 250.000,00 € - ersatzweise Ordnungshaft -
      oder der Ordnungshaft bis zu 6 Monaten"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-04
    anmerkung: "Ohne Benennung der Vollstreckungsperson — schwächste Variante im Register."
  - text: "von Verbrauchern, die im Rahmen eines bestehenden Zahlungsdiensterahmenvertrages
      von der Beklagten die Führung eines Pfändungsschutzkontos im Sinne von § 850k ZPO
      verlangen"
    funktion: adressatenkreis
    baustein_id: B-AK-04
  - text: "die Unterzeichnung einer Vereinbarung zu fordern, in der es heißt: [Klauseltext]"
    funktion: verbotene_handlung
    baustein_id: B-VH-41
  - text: "[wörtlicher Klauseltext]"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-04
    anmerkung: >
      Bei Klauselfällen ersetzt der wörtliche Klauseltext die Anlage. Das ist die
      typische Bauform des Klausel-Tenors.

kerngleich_umfasst:
  - beschreibung: "Identische Klausel mit anderem Pauschalpreis"
    begruendung: >
      Zweifelhaft. Der Preis ist Teil des zitierten Wortlauts. OHNE die Formel
      „oder eine inhaltsgleiche Klausel” (vgl. T-006) ist der Tenor auf den
      wörtlichen Text begrenzt.
    sicherheit: niedrig
  - beschreibung: "Sprachlich umformulierte Klausel mit demselben Regelungsgehalt"
    begruendung: >
      Nach allgemeinen Grundsätzen erfasst ein Klausel-Tenor auch inhaltsgleiche
      Klauseln (§ 11 UKlaG-Rechtsprechung). Der Tenor selbst sagt das aber nicht.
    sicherheit: niedrig

nicht_umfasst:
  - beschreibung: "P-Konto-Umstellung ohne Entgeltvereinbarung"
    begruendung: "Der beanstandete Regelungsgehalt entfällt vollständig."
    sicherheit: hoch
  - beschreibung: "Entgeltklausel gegenüber Unternehmern"
    begruendung: "Der Tenor ist auf Verbraucher begrenzt."
    sicherheit: hoch
  - beschreibung: "Berufen auf die Klausel in Altverträgen"
    begruendung: >
      Der Tenor untersagt nur, die Unterzeichnung zu FORDERN. Das Berufen auf
      bereits unterzeichnete Vereinbarungen ist nicht erfasst — vgl. den doppelten
      Verbotsausspruch in T-006.
    sicherheit: mittel

nachtraeglich_bewertet:
  zu_eng: ja
  hinweis: >
    Zwei Lücken:
    (1) Kein doppelter Verbotsausspruch (Verwenden UND Berufen) — Altverträge bleiben
        unberührt. Vgl. T-006 und § 11 UKlaG.
    (2) Keine Formel „oder eine inhaltsgleiche Klausel” — der Tenor hängt am
        wörtlichen Klauseltext einschließlich des konkreten Betrags. Eine Änderung
        des Preises auf 17,90 € könnte bereits durchrutschen.
    Beides sind heute Standardbausteine (B-VH-42, B-VH-43) und sollten bei jedem
    Klauselfall geprüft werden.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

pruefbare_merkmale:
  - merkmal: "Entgeltklausel für P-Konto in Preis- und Leistungsverzeichnis"
    pruefung: "Volltextsuche im PLV-PDF nach /P-Konto|Pfändungsschutzkonto/ und
      benachbarten Betragsangaben"
    automatisierbar: true
  - merkmal: "Formulartext der Umstellungsvereinbarung"
    pruefung: "manuell — Formular in der Regel nicht öffentlich abrufbar"
    automatisierbar: false

sicherheit: mittel
uneinigkeit: null
geprueft_von: "Claude (Übernahme aus Team-Sammlung + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false


===== DATEI: tenore/T-006.yaml =====

id: T-006
quelle: urteil
gericht_az: "LG Düsseldorf, 12 O 293/22"
datum: null
datum_hinweis: "Verkündungsdatum in der Team-Sammlung nicht angegeben — VOR DEM PITCH ERGÄNZEN."
fundstelle_url: null
fundstelle_hinweis: "Keine Fundstelle in der Team-Sammlung. Suchpfad: Verbandsklagenregister BfJ, openlegaldata.io, dejure.org."
rechtskraeftig: unbekannt
parteien:
  klaeger: "Verbraucherschutzverband"
  beklagte: "Anbieter von Fitness-/Mitgliedschaftsverträgen (im Tenor als „F.” anonymisiert)"
zitat_geprueft: teilweise
zitat_quelle: >
  Übernommen aus der Team-Sammlung „Tenore_Beispiele” (Google Doc). NICHT am Volltext
  gegengeprüft, weil keine Fundstelle vorlag. VOR DEM PITCH GEGENPRÜFEN ODER AUS DER
  DEMO NEHMEN.

sachverhalt: >
  Die Beklagte verwendete in Dauerschuldverhältnissen gegenüber Verbrauchern eine
  Preisanpassungsklausel, die eine Änderung der Mitgliedsgebühr nach billigem Ermessen
  anhand nicht beeinflussbarer äußerer Umstände vorsah.
fallgruppe: agb_klausel
verstoss_modus: klausel_verwendet
kanal:
  - website
rechtsgrundlage:
  - norm: "§ 1 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 307 BGB"
    funktion: anspruchsbegruendend
    anmerkung: "Aus der Team-Sammlung nicht belegt — beim Gegenprüfen verifizieren."
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

tenor_text: >
  es bei Vermeidung eines für jeden Fall der Zuwiderhandlung festzusetzenden
  Ordnungsgeldes bis zu 250.000,00 €, ersatzweise Ordnungshaft bis zu sechs Monaten oder
  Ordnungshaft bis zu sechs Monaten, zu vollstrecken an den Geschäftsführern der
  Beklagten, in Bezug auf Dauerschuldverhältnisse (M.) die Verwendung folgender und/oder
  dieser inhaltsgleicher Klauseln zu unterlassen, sofern nicht der Vertrag mit einer
  Person abgeschlossen wird, die in Ausübung ihrer gewerblichen oder selbstständigen
  beruflichen Tätigkeit handelt (Unternehmer): [wörtlicher Klauseltext zur Anpassung
  der Mitgliedsgebühr]
verletzungsform_anlage: "Klauselwortlaut im Tenor selbst"

tenor_bausteine:
  - text: "es bei Vermeidung eines für jeden Fall der Zuwiderhandlung festzusetzenden
      Ordnungsgeldes bis zu 250.000,00 €, ersatzweise Ordnungshaft bis zu sechs Monaten
      oder Ordnungshaft bis zu sechs Monaten, zu vollstrecken an den Geschäftsführern
      der Beklagten"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-05
  - text: "sofern nicht der Vertrag mit einer Person abgeschlossen wird, die in Ausübung
      ihrer gewerblichen oder selbstständigen beruflichen Tätigkeit handelt (Unternehmer)"
    funktion: adressatenkreis
    baustein_id: B-AK-05
    anmerkung: >
      NEGATIVE Formulierung des Adressatenkreises: nicht „gegenüber Verbrauchern”,
      sondern „außer gegenüber Unternehmern”. Wirkt weiter, weil auch Fälle erfasst
      werden, in denen die Verbrauchereigenschaft streitig ist.
  - text: "in Bezug auf Dauerschuldverhältnisse (M.)"
    funktion: anwendungsbereich
    baustein_id: B-AB-06
  - text: "die Verwendung folgender und/oder dieser inhaltsgleicher Klauseln zu unterlassen"
    funktion: verbotene_handlung
    baustein_id: B-VH-42
    anmerkung: >
      „und/oder dieser inhaltsgleicher Klauseln” ist die Kerngleichheits-Erweiterung
      für Klauselfälle. Vergleiche T-005, wo sie fehlt.
      ACHTUNG: Der Doppelausspruch („oder sich auf eine solche Klausel zu berufen”)
      fehlt hier — siehe nachtraeglich_bewertet.
  - text: "[wörtlicher Klauseltext]"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-04

kerngleich_umfasst:
  - beschreibung: "Sprachlich umformulierte Preisanpassungsklausel mit demselben
      Anpassungsmechanismus"
    begruendung: "Ausdrücklich von „und/oder dieser inhaltsgleicher Klauseln” erfasst."
    sicherheit: hoch
  - beschreibung: "Dieselbe Klausel in einem anderen Produkt derselben Beklagten,
      sofern Dauerschuldverhältnis"
    begruendung: "Der Anwendungsbereich nennt Dauerschuldverhältnisse, nicht ein Produkt."
    sicherheit: mittel

nicht_umfasst:
  - beschreibung: "Preisanpassungsklausel mit konkret bezifferten, überprüfbaren
      Anpassungsparametern und Sonderkündigungsrecht"
    begruendung: "Der beanstandete Ermessensspielraum entfällt."
    sicherheit: mittel
  - beschreibung: "Berufen auf die Klausel in bereits geschlossenen Altverträgen"
    begruendung: >
      Der Tenor untersagt nur die VERWENDUNG. Ohne den Doppelausspruch bleibt die
      Berufung auf Altverträge unberührt.
    sicherheit: hoch
  - beschreibung: "Verwendung gegenüber Unternehmern"
    begruendung: "Ausdrücklich ausgenommen."
    sicherheit: hoch

nachtraeglich_bewertet:
  zu_eng: ja
  hinweis: >
    Der Tenor enthält die Inhaltsgleichheits-Formel, aber NICHT den doppelten
    Verbotsausspruch. Untersagt ist nur das „Verwenden”, nicht das „Sich-darauf-Berufen”.
    Folge: Alle bereits geschlossenen Verträge behalten die Klausel praktisch, weil die
    Beklagte sich weiterhin darauf berufen kann. Bei Fitness- und Abo-Verträgen ist der
    Bestand an Altverträgen typischerweise um ein Vielfaches größer als der Neuzugang —
    der Tenor greift also gerade dort nicht, wo der Schaden entsteht.
    Vgl. T-007 (OLG Frankfurt), wo beides tenoriert wurde.
    STANDARDPRÜFUNG für jeden § 1 UKlaG-Fall: Sind BEIDE Bausteine B-VH-42 und
    B-VH-43 enthalten?
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

pruefbare_merkmale:
  - merkmal: "Preisanpassungsklausel in den aktuellen AGB"
    pruefung: "AGB-Seite abrufen, Volltextsuche nach /billige[ms] Ermessen|anpassen|
      Mitgliedsgebühr ändern/, Fundstellen extrahieren"
    automatisierbar: true
  - merkmal: "Bewertung der Inhaltsgleichheit einer geänderten Klausel"
    pruefung: "manuell — juristische Wertung"
    automatisierbar: false

sicherheit: niedrig
uneinigkeit: null
geprueft_von: "Claude (Übernahme aus Team-Sammlung + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false


===== DATEI: tenore/T-007.yaml =====

id: T-007
quelle: urteil
gericht_az: "OLG Frankfurt am Main, 6 U 206/23"
datum: "2024-12-18"
fundstelle_url: "https://www.bundesjustizamt.de/DE/Themen/Verbraucherrechte/VerbandsklageregisterMusterfeststellungsklagenregister/Verbandsklagenregister/Unterlassungsklagen/Klagen/2024/056/UKlag_56_2024_node.html"
fundstelle_hinweis: >
  Amtliche Bekanntmachung im Verbandsklagenregister des Bundesamts für Justiz.
  Dort wird der Antragswortlaut öffentlich bekanntgemacht — die beste frei zugängliche
  Quelle für Tenorwortlaute überhaupt.
rechtskraeftig: unbekannt
parteien:
  klaeger: "Verbraucherzentrale Thüringen e.V."
  beklagte: "DB Fernverkehr AG"
zitat_geprueft: teilweise
zitat_quelle: >
  Übernommen aus der Team-Datei „Unterlassungstenore Referenzsammlung.md”. Der Wortlaut
  enthält Auslassungen ([...]). Am Volltext des Verbandsklagenregisters GEGENPRÜFEN und
  Auslassungen schließen.

sachverhalt: >
  Die Beklagte verwendete bei BahnCard-Verträgen gegenüber Verbrauchern eine Klausel,
  nach der sich die BahnCard automatisch um ein weiteres Jahr verlängert, wenn sie nicht
  sechs Wochen vor Laufzeitende schriftlich gekündigt wird.
fallgruppe: agb_klausel
verstoss_modus: klausel_verwendet
kanal:
  - website
rechtsgrundlage:
  - norm: "§ 1 UKlaG"
    funktion: anspruchsgrundlage
  - norm: "§ 309 Nr. 9 BGB"
    funktion: anspruchsbegruendend
    anmerkung: "Beim Gegenprüfen verifizieren; auch § 307 BGB und § 13 BGB kommen in Betracht."
  - norm: "§ 11 UKlaG"
    funktion: wirkung_altvertraege
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

tenor_text: >
  Die Beklagte wird verurteilt, es [...] zu unterlassen, bei BahnCard-Verträgen [...]
  die nachfolgende oder eine inhaltsgleiche Klausel gegenüber Verbrauchern (§ 13 BGB)
  zu verwenden oder sich auf eine solche Klausel zu berufen:
  „Sie wird automatisch um ein weiteres Jahr verlängert, wenn sie nicht 6 Wochen vor
  Laufzeitende schriftlich gekündigt wird."
tenor_luecken: >
  Zwei Auslassungen: (1) die Ordnungsmittelandrohung, (2) eine Präzisierung nach
  „bei BahnCard-Verträgen”. Beide im Verbandsklagenregister nachtragen.
verletzungsform_anlage: "Klauselwortlaut im Tenor selbst"

tenor_bausteine:
  - text: "[Ordnungsmittelandrohung — im vorliegenden Auszug ausgelassen]"
    funktion: ordnungsmittelandrohung
    baustein_id: null
    anmerkung: "LÜCKE — nachtragen."
  - text: "gegenüber Verbrauchern (§ 13 BGB)"
    funktion: adressatenkreis
    baustein_id: B-AK-02
    anmerkung: >
      Mit Normverweis. Präziser als das bloße „gegenüber Verbrauchern”, weil im
      Vollstreckungsverfahren der Verbraucherbegriff nicht mehr auslegungsbedürftig ist.
  - text: "bei BahnCard-Verträgen"
    funktion: anwendungsbereich
    baustein_id: B-AB-07
  - text: "die nachfolgende oder eine inhaltsgleiche Klausel [...] zu verwenden"
    funktion: verbotene_handlung
    baustein_id: B-VH-42
  - text: "oder sich auf eine solche Klausel zu berufen"
    funktion: verbotene_handlung
    baustein_id: B-VH-43
    anmerkung: >
      DER DOPPELAUSSPRUCH. Der wichtigste Einzelbaustein für § 1 UKlaG-Fälle.
      Ohne ihn bleiben Altverträge unberührt (§ 11 UKlaG). Fehlt in T-005 und T-006.
  - text: "„Sie wird automatisch um ein weiteres Jahr verlängert, wenn sie nicht
      6 Wochen vor Laufzeitende schriftlich gekündigt wird.“"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-04

kerngleich_umfasst:
  - beschreibung: "Verlängerung um zwölf Monate statt um ein Jahr"
    begruendung: "Inhaltlich identisch; von „oder eine inhaltsgleiche Klausel” erfasst."
    sicherheit: hoch
  - beschreibung: "Kündigungsfrist auf einen Monat verkürzt, automatische Verlängerung
      um ein Jahr bleibt"
    begruendung: >
      Tragendes Element ist die automatische Jahresverlängerung. Ob die Fristverkürzung
      die Inhaltsgleichheit entfallen lässt, hängt vom Grund der Unwirksamkeit ab —
      beim Gegenprüfen der Entscheidungsgründe klären.
    sicherheit: mittel
  - beschreibung: "Beibehaltung der Klausel in laufenden BahnCard-Verträgen und
      Abrechnung der Verlängerung"
    begruendung: "Ausdrücklich erfasst durch „oder sich auf eine solche Klausel zu berufen”."
    sicherheit: hoch

nicht_umfasst:
  - beschreibung: "Automatische Verlängerung auf unbestimmte Zeit mit monatlicher
      Kündigungsmöglichkeit"
    begruendung: >
      Entspricht der gesetzlichen Vorgabe des § 309 Nr. 9 BGB n.F.; der beanstandete
      Regelungsgehalt entfällt.
    sicherheit: hoch
  - beschreibung: "Dieselbe Klausel in einem anderen Produkt der Beklagten
      (z. B. Abo-Ticket)"
    begruendung: "Der Anwendungsbereich nennt „bei BahnCard-Verträgen”."
    sicherheit: mittel
  - beschreibung: "Dieselbe Klausel gegenüber Geschäftskunden"
    begruendung: "Auf Verbraucher i.S.d. § 13 BGB begrenzt."
    sicherheit: hoch

nachtraeglich_bewertet:
  zu_eng: nein
  hinweis: >
    Strukturell der beste Klausel-Tenor im Register: Doppelausspruch (verwenden UND
    berufen) plus Inhaltsgleichheits-Formel plus Verbraucherbegriff mit Normverweis.
    Einzige erkennbare Verengung: die Bindung an ein einzelnes Produkt
    („bei BahnCard-Verträgen”). Ob das im konkreten Fall geboten war, lässt sich ohne
    die Entscheidungsgründe nicht beurteilen.
    Dieser Tenor sollte im System die Vorlage für die Fallgruppe agb_klausel sein.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

pruefbare_merkmale:
  - merkmal: "Verlängerungsklausel in den aktuellen Beförderungsbedingungen"
    pruefung: "AGB-/BB-Seite abrufen, Suche nach /verlängert sich|automatisch um ein
      (weiteres )?Jahr|zwölf Monate/"
    automatisierbar: true
  - merkmal: "Darstellung der Laufzeit im Bestellprozess"
    pruefung: "Produktseite und Checkout auf Laufzeit- und Verlängerungsangaben prüfen"
    automatisierbar: true
  - merkmal: "Berufen auf die Klausel gegenüber Bestandskunden"
    pruefung: >
      manuell — nur über Verbraucherbeschwerden feststellbar. Zugleich der
      praktisch wichtigste Prüfpunkt, weil dort der Doppelausspruch wirkt.
    automatisierbar: false

sicherheit: mittel
uneinigkeit: null
geprueft_von: "Claude (Übernahme aus Team-Sammlung + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false


===== DATEI: tenore/T-008.yaml =====

id: T-008
quelle: urteil
gericht_az: "OLG Karlsruhe, 6 U 82/22"
datum: "2023-02-08"
datum_hinweis: >
  In der Team-Sammlung steht als Urteilsdatum der 08.02.2023, der PDF-Dateiname der
  Verbraucherzentrale nennt jedoch den 12.04.2022. Widerspruch — beim Gegenprüfen klären.
fundstelle_url: "https://www.verbraucherzentrale.de/sites/default/files/2023-02/olg_karlsruhe_12.4.2022_az._6_u_82-22.pdf"
rechtskraeftig: unbekannt
parteien:
  klaeger: "Verbraucherzentrale Baden-Württemberg e.V."
  beklagte: "Anbieter von Finanzsanierungsleistungen"
zitat_geprueft: teilweise
zitat_quelle: >
  Übernommen aus der Team-Datei „Unterlassungstenore Referenzsammlung.md”. Enthält eine
  Auslassung ([...]) im Anwendungsbereich. Am PDF gegenprüfen.

sachverhalt: >
  Die Beklagte warb gegenüber Verbrauchern in einem Anschreiben mit einer in Euro
  bezifferten „Finanzsanierung” und der Behauptung, diese sei ab sofort für den
  Verbraucher „verfügbar”.
fallgruppe: irrefuehrende_werbung
verstoss_modus: irrefuehrend_gestaltet
kanal:
  - offline
kanal_hinweis: >
  Werbeschreiben, kein Webseitenbezug. Für den Umsetzungsmonitor nur bedingt geeignet
  (vgl. Erfassungsbogen: „Ungeeignet: Werbebriefe”). Im Register bleibt der Fall, weil
  er die Standardbauform des § 8 UWG-Tenors mit „wie geschehen”-Bezug zeigt.
rechtsgrundlage:
  - norm: "§ 8 Abs. 1, Abs. 3 Nr. 3 UWG"
    funktion: anspruchsgrundlage
  - norm: "§ 5 UWG"
    funktion: anspruchsbegruendend
    anmerkung: "Beim Gegenprüfen verifizieren."
  - norm: "§ 890 ZPO"
    funktion: ordnungsmittelandrohung

tenor_text: >
  Der Beklagten wird untersagt, im geschäftlichen Verkehr gegenüber Verbrauchern in
  Deutschland [...] mit einer in Euro bezifferten „Finanzsanierung” und der Behauptung
  zu werben, diese sei ab sofort für den Verbraucher „verfügbar”, wie geschehen im
  Schreiben der Beklagten [...] vom 12.04.2021 (Anlage K 2).

  Der Beklagten wird für jeden Fall der schuldhaften Zuwiderhandlung [...] ein
  Ordnungsgeld bis zu € 250.000,00 (ersatzweise Ordnungshaft bis zu 6 Wochen) oder
  Ordnungshaft bis zu 6 Monaten, zu vollstrecken an deren Vorstand, angedroht.
verletzungsform_anlage: "Anlage K 2 (Schreiben vom 12.04.2021)"

tenor_bausteine:
  - text: "Der Beklagten wird untersagt"
    funktion: verpflichtungsformel
    baustein_id: B-VF-02
    anmerkung: >
      Passivische Variante. Im Register überwiegt „Die Beklagte wird verurteilt,
      es zu unterlassen" (B-VF-01).
  - text: "im geschäftlichen Verkehr gegenüber Verbrauchern in Deutschland"
    funktion: adressatenkreis
    baustein_id: B-AK-03
    anmerkung: "Mit räumlicher Begrenzung — relevant bei Anbietern im EU-Ausland."
  - text: "mit einer in Euro bezifferten „Finanzsanierung” und der Behauptung zu werben,
      diese sei ab sofort für den Verbraucher „verfügbar”"
    funktion: verbotene_handlung
    baustein_id: B-VH-51
  - text: "wie geschehen im Schreiben der Beklagten [...] vom 12.04.2021 (Anlage K 2)"
    funktion: konkrete_verletzungsform
    baustein_id: B-KV-05
    anmerkung: >
      „wie geschehen” ist die klassische Formel des § 8 UWG-Tenors. Sie bindet das
      Verbot an die festgestellte Verletzungsform und beseitigt
      Bestimmtheitsbedenken nach § 253 Abs. 2 Nr. 2 ZPO.
  - text: "für jeden Fall der schuldhaften Zuwiderhandlung [...] ein Ordnungsgeld bis zu
      € 250.000,00 (ersatzweise Ordnungshaft bis zu 6 Wochen) oder Ordnungshaft bis zu
      6 Monaten, zu vollstrecken an deren Vorstand, angedroht"
    funktion: ordnungsmittelandrohung
    baustein_id: B-OM-06
    anmerkung: >
      ABWEICHENDE BAUFORM: Die Androhung steht als eigener Tenorabsatz NACH dem
      Verbot, nicht eingeschoben. Beides ist zulässig; das System sollte beide
      Anordnungen kennen und nicht die eine als Fehler der anderen melden.

kerngleich_umfasst:
  - beschreibung: "Dasselbe Anschreiben mit anderem Betrag"
    begruendung: >
      Der Tenor nennt keinen konkreten Betrag, sondern „eine in Euro bezifferte
      Finanzsanierung". Der Betrag ist also gerade nicht tragend.
    sicherheit: hoch
  - beschreibung: "Dieselbe Aussage mit „steht Ihnen ab sofort zur Verfügung” statt
      „verfügbar”"
    begruendung: >
      Der „wie geschehen”-Bezug bindet an die konkrete Verletzungsform. Ob eine
      sprachliche Variante noch kerngleich ist, entscheidet das
      Ordnungsmittelverfahren.
    sicherheit: mittel

nicht_umfasst:
  - beschreibung: "Werbung mit einer Finanzsanierung ohne Verfügbarkeitsbehauptung"
    begruendung: "Der Tenor verlangt die Kombination beider Elemente."
    sicherheit: hoch
  - beschreibung: "Dieselbe Aussage auf der Website statt im Anschreiben"
    begruendung: >
      Der „wie geschehen”-Bezug nennt ein Schreiben. Ein Medienwechsel dürfte einen
      neuen Sachverhalt darstellen.
    sicherheit: mittel
  - beschreibung: "Dieselbe Werbung gegenüber Unternehmern"
    begruendung: "Auf Verbraucher begrenzt."
    sicherheit: hoch

nachtraeglich_bewertet:
  zu_eng: unklar
  hinweis: >
    Der „wie geschehen”-Bezug auf ein einzelnes Schreiben ist die enge, aber sichere
    Bauform. Bei einem Medienwechsel (Website, E-Mail, Social Media) greift der Tenor
    voraussichtlich nicht. Ob das eine Verengung ist, hängt davon ab, ob der Anbieter
    zum Zeitpunkt der Klage nur postalisch geworben hat — das lässt sich ohne den
    Volltext nicht beurteilen.
  bewertet_von: "Arbeitsbewertung, juristisch nicht freigegeben"

pruefbare_merkmale:
  - merkmal: "Verfügbarkeitsbehauptung in Werbematerial"
    pruefung: "manuell — Anschreiben nicht öffentlich abrufbar; Zugang nur über
      Verbraucherbeschwerden"
    automatisierbar: false
  - merkmal: "Vergleichbare Aussage auf der Website des Anbieters"
    pruefung: "Volltextsuche nach /Finanzsanierung/ in Verbindung mit
      /ab sofort|verfügbar|steht.{0,20}zur Verfügung/"
    automatisierbar: true
    anmerkung: "Läge außerhalb des Tenors — dient der Erkennung eines NEUEN Sachverhalts."

sicherheit: mittel
uneinigkeit: null
geprueft_von: "Claude (Übernahme aus Team-Sammlung + Erstannotation)"
geprueft_am: "2026-08-21"
freigabe_jurist: false
