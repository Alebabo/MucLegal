# Frontend-Demofälle: Lotto

Stand: 21.08.2026
Zweck: Hardcodierte Beispieldaten für den Frontend-Designprozess

## Wichtiger Hinweis

Alle Unternehmen, Domains, Sachverhalte, Screenshots, Entscheidungen und Zeitangaben in
dieser Datei sind vollständig synthetisch. Sie beziehen sich auf keinen realen
Lotterieanbieter und enthalten keine Aussage über tatsächlich geltendes
Glücksspielrecht oder einen realen Rechtsverstoß.

Die Beispiele dienen ausschließlich dazu, UI-Zustände des MucLegal-Prototyps zu
gestalten. Eine Bezeichnung wie `kerngleich` stellt innerhalb dieser Datei nur den
gewünschten Demo-Zustand dar. Die abschließende Entscheidung bleibt immer einem
Menschen vorbehalten.

## 1. Gemeinsames Demo-Szenario

Fiktives Unternehmen:

```text
Glückswerk Lotterie Demo GmbH
```

Fiktive Domain:

```text
lotto-demo.test
```

Gemeldeter Erstverstoß:

> Auf einer Aktionsseite wurde ein Jackpot-Zusatztipp mit einem Countdown und der
> Aussage „Nur heute verfügbar“ beworben. Nach Ablauf startete der Countdown erneut,
> obwohl die beworbene Tagesfrist tatsächlich nicht bestand.

Synthetischer Unterlassungstenor:

> Es wird untersagt, für die entgeltliche Teilnahme an einem Lotterie-Zusatztipp mit
> einer zeitlich befristeten Verfügbarkeit zu werben, wenn die angegebene Frist
> tatsächlich nicht besteht oder nach ihrem Ablauf ohne erkennbaren neuen
> Sachgrund fortgesetzt wird.

Charakteristischer Kern:

```text
künstliche zeitliche Dringlichkeit bei einem kostenpflichtigen Lotto-Zusatztipp
```

Kerngleich umfasste Demo-Varianten:

- ein nach Ablauf erneut startender Countdown;
- die über mehrere Tage wiederholte Aussage „Nur heute“;
- eine angeblich nur kurzfristig verfügbare Jackpot-Vervielfachung;
- eine nicht belegte künstliche Verknappung von Tippscheinen.

Ausdrücklich nicht umfasste Demo-Gegenfälle:

- ein echter und technisch eingehaltener Annahmeschluss vor einer Ziehung;
- eine einmalige Sonderziehung mit veröffentlichtem, belegbarem Endzeitpunkt;
- eine zutreffende Restplatzangabe bei einer tatsächlich begrenzten Lotterie;
- ein neutraler Hinweis auf den regulären Ziehungszeitpunkt ohne zusätzlichen
  künstlichen Kaufdruck.

## 2. Empfohlenes Frontend-View-Model

Das folgende View-Model verbindet ein weitgehend backendkonformes `case`-Objekt mit
einem für Karten und Detailansichten praktischen `last_run`-Objekt.

`last_run` wird vom Backend derzeit nicht genau in dieser zusammengesetzten Form
geliefert. Für den Designprozess kann es trotzdem so hardcodiert werden. Bei der
späteren Integration wird es aus dem Monitoringfall und dem letzten Run aufgebaut.

```js
export const lottoDemoCases = [
  {
    case: {
      case_id: "lotto-countdown-reset",
      fall_id: "VZ-LOTTO-2026-001",
      domain: "lotto-demo.test",
      source_url: "https://lotto-demo.test/jackpot-plus",
      violation_type: "klausel",
      description:
        "Der kostenpflichtige Jackpot-Plus-Zusatztipp wurde mit einem Countdown beworben, der nach Ablauf erneut startete.",
      tenor_element:
        "Es wird untersagt, für einen Lotterie-Zusatztipp mit einer tatsächlich nicht bestehenden zeitlichen Verfügbarkeit zu werben.",
      monitoring_target:
        "Zurücksetzende Countdown-Anzeigen und wiederholte Kurzfrist-Werbung für Jackpot-Plus erkennen.",
      relevant_page_types: [
        "Startseite",
        "Jackpot-Seite",
        "Tippschein",
        "Checkout"
      ],
      target_urls: [
        "https://lotto-demo.test/jackpot-plus",
        "https://lotto-demo.test/tippschein"
      ],
      nicht_umfasst: [
        "Echter Annahmeschluss vor einer Ziehung",
        "Einmalige Sonderziehung mit belegbarem Endzeitpunkt"
      ],
      clause_text:
        "Nur heute: Jackpot Plus sichern – Angebot endet in 14:59 Minuten",
      element_label: null,
      element_labels: [],
      element_function: null,
      element_error: null,
      allowed_subdomains: [],
      screenshot_path: null,
      screenshot_sha256: null,
      erstverstoss_festgestellt_durch: "verbraucherzentrale",
      decision: "freigegeben",
      created_at: "2026-08-15T09:10:00Z",
      decided_at: "2026-08-15T11:35:00Z"
    },
    last_run: {
      run_id: "run-lotto-001",
      status: "kerngleich_wiederaufgetreten",
      label: "Möglicherweise kerngleicher Verstoß",
      tone: "danger",
      found_at: "2026-08-21T07:45:00Z",
      url: "https://lotto-demo.test/tippschein",
      fundstelle:
        "Jackpot Plus nur noch 08:42 Minuten verfügbar",
      classification: "kerngleich",
      confidence: 0.91,
      explanation:
        "Der Countdown erscheint nun auf dem Tippschein statt auf der Aktionsseite, erzeugt aber denselben künstlichen Zeitdruck und startete nach Ablauf erneut.",
      strongest_counterargument:
        "Der Anbieter könnte behaupten, dass nach Ablauf jeweils eine neue, getrennt beschlossene Aktion begonnen habe.",
      uncertainty:
        "Der tatsächliche Kampagnenwechsel und die serverseitige Laufzeit müssen menschlich überprüft werden.",
      human_release: null,
      evidence_available: true
    }
  },

  {
    case: {
      case_id: "lotto-real-draw-deadline",
      fall_id: "VZ-LOTTO-2026-002",
      domain: "lotto-demo.test",
      source_url: "https://lotto-demo.test/samstagsziehung",
      violation_type: "klausel",
      description:
        "Frühere Aktionsfristen für kostenpflichtige Zusatztipps wurden nach Ablauf fortgesetzt.",
      tenor_element:
        "Untersagt ist die Werbung mit einer nur scheinbar bestehenden Frist für einen Zusatztipp.",
      monitoring_target:
        "Beworbene Aktionsfristen von regulären Annahmeschlüssen unterscheiden.",
      relevant_page_types: [
        "Ziehungsseite",
        "Tippschein"
      ],
      target_urls: [
        "https://lotto-demo.test/samstagsziehung"
      ],
      nicht_umfasst: [
        "Technisch eingehaltener Annahmeschluss vor der Samstagsziehung"
      ],
      clause_text:
        "Teilnahme nur bis Samstag, 18:00 Uhr",
      element_label: null,
      element_labels: [],
      element_function: null,
      element_error: null,
      allowed_subdomains: [],
      screenshot_path: null,
      screenshot_sha256: null,
      erstverstoss_festgestellt_durch: "verbraucherzentrale",
      decision: "freigegeben",
      created_at: "2026-08-14T12:20:00Z",
      decided_at: "2026-08-14T14:00:00Z"
    },
    last_run: {
      run_id: "run-lotto-002",
      status: "beseitigt",
      label: "Kein erfasster Wiederholungsverstoß",
      tone: "success",
      found_at: "2026-08-21T06:30:00Z",
      url: "https://lotto-demo.test/samstagsziehung",
      fundstelle:
        "Annahmeschluss Samstag, 18:00 Uhr – Ziehung um 19:25 Uhr",
      classification: "neuer_sachverhalt",
      confidence: 0.93,
      explanation:
        "Der angegebene Zeitpunkt ist als regulärer Annahmeschluss dokumentiert und wurde im synthetischen Verlauf technisch eingehalten.",
      strongest_counterargument:
        "Auch ein realer Annahmeschluss könnte durch die Gestaltung übermäßig dramatisiert werden.",
      uncertainty:
        "Die Bewertung der konkreten Gestaltung bleibt einer menschlichen Prüfung vorbehalten.",
      human_release: null,
      evidence_available: true
    }
  },

  {
    case: {
      case_id: "lotto-limited-tickets",
      fall_id: "VZ-LOTTO-2026-003",
      domain: "lotto-demo.test",
      source_url: "https://lotto-demo.test/sonderziehung",
      violation_type: "klausel",
      description:
        "Eine angeblich knappe Anzahl verfügbarer Tippscheine erzeugte zusätzlichen Teilnahmedruck.",
      tenor_element:
        "Untersagt ist eine künstliche Verknappung, wenn die behauptete Begrenzung tatsächlich nicht besteht.",
      monitoring_target:
        "Restplatz- und Restmengenanzeigen für Sonderziehungen prüfen.",
      relevant_page_types: [
        "Sonderziehungsseite",
        "Checkout"
      ],
      target_urls: [
        "https://lotto-demo.test/sonderziehung",
        "https://lotto-demo.test/sonderziehung/checkout"
      ],
      nicht_umfasst: [
        "Zutreffende Restplatzangabe bei einer tatsächlich begrenzten Lotterie"
      ],
      clause_text:
        "Nur noch 250 Tippscheine verfügbar",
      element_label: null,
      element_labels: [],
      element_function: null,
      element_error: null,
      allowed_subdomains: [],
      screenshot_path: null,
      screenshot_sha256: null,
      erstverstoss_festgestellt_durch: "verbraucherzentrale",
      decision: "freigegeben",
      created_at: "2026-08-17T08:40:00Z",
      decided_at: "2026-08-17T13:15:00Z"
    },
    last_run: {
      run_id: "run-lotto-003",
      status: "unsicher",
      label: "Menschliche Prüfung erforderlich",
      tone: "warning",
      found_at: "2026-08-21T08:05:00Z",
      url: "https://lotto-demo.test/sonderziehung",
      fundstelle:
        "Fast ausverkauft – nur noch 96 Tipps verfügbar",
      classification: "unsicher",
      confidence: 0.56,
      explanation:
        "Die Anzeige erzeugt eine dem Erstverstoß ähnliche Verknappungswirkung. Es fehlen jedoch belastbare Daten zur tatsächlichen Gesamtzahl und zum aktuellen Verkauf.",
      strongest_counterargument:
        "Die Restplatzangabe kann auf einem realen, technisch aktuellen Kontingent beruhen.",
      uncertainty:
        "Kontingent- und Verkaufsdaten müssen menschlich angefordert und geprüft werden.",
      human_release: null,
      evidence_available: true
    }
  },

  {
    case: {
      case_id: "lotto-rules-link",
      fall_id: "VZ-LOTTO-2026-004",
      domain: "lotto-demo.test",
      source_url: "https://lotto-demo.test/jackpot-wochen",
      violation_type: "element",
      description:
        "Die Teilnahmebedingungen der Jackpot-Wochen waren auf der Aktionsseite nicht leicht zugänglich.",
      tenor_element:
        "Die Teilnahmebedingungen müssen auf der Aktionsseite sichtbar und ohne zusätzliche Hürde erreichbar sein.",
      monitoring_target:
        "Sichtbarkeit, Zugänglichkeit und Linkziel der Teilnahmebedingungen prüfen.",
      relevant_page_types: [
        "Aktionsseite",
        "Footer"
      ],
      target_urls: [
        "https://lotto-demo.test/jackpot-wochen",
        "https://lotto-demo.test/teilnahmebedingungen"
      ],
      nicht_umfasst: [
        "Direkt sichtbarer und funktionsfähiger Link zu den Teilnahmebedingungen"
      ],
      clause_text: null,
      element_label: "Teilnahmebedingungen",
      element_labels: [
        "Teilnahmebedingungen",
        "Spielregeln",
        "Aktionsbedingungen"
      ],
      element_function: "/teilnahmebedingungen",
      element_error: "nicht_leicht_zugaenglich",
      allowed_subdomains: [],
      screenshot_path: null,
      screenshot_sha256: null,
      erstverstoss_festgestellt_durch: "verbraucherzentrale",
      decision: "freigegeben",
      created_at: "2026-08-18T10:25:00Z",
      decided_at: "2026-08-18T15:10:00Z"
    },
    last_run: {
      run_id: "run-lotto-004",
      status: "pruefung_unvollstaendig",
      label: "Prüfumfang nicht vollständig",
      tone: "warning",
      found_at: "2026-08-21T08:55:00Z",
      url: "https://lotto-demo.test/jackpot-wochen",
      fundstelle: null,
      classification: null,
      confidence: null,
      explanation:
        "Die Aktionsseite wurde erfasst. Die verbindliche Zielseite der Teilnahmebedingungen war während des Laufs technisch nicht erreichbar.",
      strongest_counterargument: null,
      uncertainty:
        "Aus der unvollständigen Erfassung darf weder auf Beseitigung noch auf Fortbestehen geschlossen werden.",
      human_release: null,
      evidence_available: true
    }
  },

  {
    case: {
      case_id: "lotto-bonus-pending",
      fall_id: "VZ-LOTTO-2026-005",
      domain: "lotto-demo.test",
      source_url: "https://lotto-demo.test/willkommensbonus",
      violation_type: "klausel",
      description:
        "Der Willkommens-Zusatztipp wurde über mehrere Tage mit der Aussage ‚Nur heute gratis‘ beworben.",
      tenor_element:
        "Untersagt ist die Werbung mit einem nur scheinbar auf einen Tag begrenzten Bonus.",
      monitoring_target:
        "Wiederholte Tagesfrist für den Willkommens-Zusatztipp erkennen.",
      relevant_page_types: [
        "Landingpage",
        "Registrierung"
      ],
      target_urls: [
        "https://lotto-demo.test/willkommensbonus"
      ],
      nicht_umfasst: [
        "Tatsächlich nur an einem Kalendertag angebotener Bonus"
      ],
      clause_text:
        "Nur heute: Willkommens-Zusatztipp gratis",
      element_label: null,
      element_labels: [],
      element_function: null,
      element_error: null,
      allowed_subdomains: [],
      screenshot_path: null,
      screenshot_sha256: null,
      erstverstoss_festgestellt_durch: "verbraucherzentrale",
      decision: "weitere_pruefung",
      created_at: "2026-08-21T09:20:00Z",
      decided_at: null
    },
    last_run: null
  }
];
```

## 3. Kartenansicht: empfohlene Kurztexte

| Fall | Statuszeile | Sekundärtext | Ton |
|---|---|---|---|
| Jackpot-Countdown | Möglicherweise kerngleicher Verstoß | Countdown auf neuer Ebene erneut gestartet | Gefahr |
| Echter Annahmeschluss | Kein erfasster Wiederholungsverstoß | Annahmeschluss technisch eingehalten | Erfolg |
| Begrenzte Tippscheine | Menschliche Prüfung erforderlich | Kontingentdaten fehlen | Warnung |
| Teilnahmebedingungen | Prüfumfang nicht vollständig | Zielseite war nicht erreichbar | Warnung |
| Willkommensbonus | Freigabe ausstehend | Monitoring wurde noch nicht gestartet | Neutral |

## 4. Detailansicht: Jackpot-Countdown

Dieser Fall eignet sich als zentrale Pitch-Demo, weil der Verstoß sichtbar „wandert“:

```text
Erstverstoß:
Aktionsseite → „Nur heute“ mit zurücksetzendem Countdown

Neue Fundstelle:
Tippschein → „Jackpot Plus nur noch 08:42 Minuten verfügbar“

Juristische Demo-Frage:
Andere URL und andere Formulierung – aber derselbe künstliche Zeitdruck?
```

Empfohlene UI-Blöcke:

### Befund

```text
Möglicherweise kerngleicher Verstoß
Confidence: 91 %
Menschliche Freigabe: ausstehend
```

### Ursprünglicher Verstoß

```text
Nur heute: Jackpot Plus sichern – Angebot endet in 14:59 Minuten
```

### Aktuelle Fundstelle

```text
Jackpot Plus nur noch 08:42 Minuten verfügbar
```

### Begründung

```text
Der Countdown erscheint nun auf dem Tippschein statt auf der ursprünglichen
Aktionsseite. Die Formulierung hat sich geändert, die erzeugte künstliche zeitliche
Dringlichkeit ist nach dem Demo-Fallprofil jedoch gleich geblieben.
```

### Stärkstes Gegenargument

```text
Der Anbieter könnte behaupten, dass nach Ablauf jeweils eine neue, getrennt
beschlossene Aktion begonnen habe.
```

### Offene menschliche Prüfung

```text
Zu prüfen sind der tatsächliche Kampagnenwechsel, die serverseitige Laufzeit und die
Frage, ob ein realer neuer Sachgrund für die Fortsetzung bestand.
```

## 5. BeweisLab-Demozustände im Lotto-Design

Die folgenden Daten eignen sich für die technische BeweisLab-Ansicht. Sie sind von
den juristischen Monitoringfällen getrennt.

```js
export const lottoEvidenceDemoResults = [
  {
    case_id: "lotto-evidence-complete",
    url: "https://lotto-demo.test/jackpot-plus",
    status: "completed",
    capture_completeness: "vollstaendig_erfasst",
    evidence_suitability: "regulaer",
    evidence_suitability_notice: null,
    robots_txt_status: "geprueft_abruf_erlaubt",
    god_mode: false,
    technical_result: {
      code: "technisch_verwendbar",
      label: "Als technischer Beleg verwendbar",
      tone: "success",
      what_was_found:
        "Die öffentliche Jackpot-Seite und die wesentlichen technischen Artefakte wurden regulär erfasst.",
      meaning:
        "Die Aufnahme ist technisch nachvollziehbar; sie enthält noch keine juristische Kerngleichheitsentscheidung.",
      next_action:
        "Beweispaket herunterladen und Inhalt sowie Verwendung menschlich prüfen."
    },
    warnings: []
  },

  {
    case_id: "lotto-evidence-robots-unchecked",
    url: "https://lotto-demo.test/sonderziehung",
    status: "completed_with_warnings",
    capture_completeness: "teilweise_erfasst",
    evidence_suitability: "nicht_beweisgeeignet",
    evidence_suitability_notice:
      "robots.txt konnte nicht verlässlich geprüft werden. Berechtigung, Nutzungsbedingungen und rechtliche Zulässigkeit sind eigenverantwortlich zu prüfen.",
    robots_txt_status: "ungeprueft",
    god_mode: false,
    technical_result: {
      code: "eingeschraenkt",
      label: "Nur eingeschränkt verwendbar",
      tone: "warning",
      what_was_found:
        "Die Sonderziehungsseite wurde technisch erfasst, robots.txt konnte aber nicht verlässlich geprüft werden.",
      meaning:
        "Die vorhandenen Dateien bleiben prüfbar, sind jedoch nicht als regulärer Beweis eingeordnet.",
      next_action:
        "Berechtigung und rechtliche Zulässigkeit prüfen und fehlende Ansichten bei Bedarf manuell sichern."
    },
    warnings: [
      "robots.txt konnte nicht verlässlich geprüft werden."
    ]
  },

  {
    case_id: "lotto-evidence-protected",
    url: "https://lotto-demo.test/tippschein",
    status: "completed_with_warnings",
    capture_completeness: "durch_seitenschutz_begrenzt",
    evidence_suitability: "nicht_beweisgeeignet",
    evidence_suitability_notice:
      "Der sichtbare Schutzzustand ist kein Beleg für den dahinterliegenden Tippschein.",
    robots_txt_status: "geprueft_abruf_erlaubt",
    god_mode: false,
    protection_type: "JavaScript-Challenge",
    technical_result: {
      code: "hinweis",
      label: "Nicht als Beleg verwendbar – nur Hinweis",
      tone: "danger",
      what_was_found:
        "Der Tippschein zeigte dem automatischen Browser eine JavaScript-Challenge. Der sichtbare Schutzzustand wurde gespeichert.",
      meaning:
        "Die Aufnahme belegt nur den Schutz- oder Fehlerzustand, nicht den dahinterliegenden Seiteninhalt.",
      next_action:
        "Den öffentlich sichtbaren Zustand zusätzlich durch einen Menschen sichern."
    },
    warnings: [
      "Die angefragte Tippschein-Seite konnte nicht inhaltlich erfasst werden."
    ]
  },

  {
    case_id: "god-lotto-evidence-demo",
    url: "https://challenge-lotto-demo.test",
    status: "completed_with_warnings",
    capture_completeness: "vollstaendig_erfasst",
    evidence_suitability: "nicht_juristisch_verwertbar",
    evidence_suitability_notice:
      "GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR",
    robots_txt_status: "geprueft_abruf_untersagt",
    god_mode: true,
    god_mode_notice:
      "GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR",
    technical_result: {
      code: "hinweis",
      label: "Nicht als Beleg verwendbar – nur Hinweis",
      tone: "danger",
      what_was_found:
        "Eine ausdrücklich autorisierte technische Demonstrationsaufnahme der synthetischen Lotto-Challenge wurde erstellt.",
      meaning:
        "Das Paket ist strikt von regulären Beweisen getrennt und nicht für eine juristische Verwendung bestimmt.",
      next_action:
        "Für einen regulären Nachweis das Ziel ohne God Mode erneut erfassen."
    },
    warnings: [
      "GOD MODE – NUR DEMONSTRATION – NICHT JURISTISCH VERWERTBAR"
    ]
  }
];
```

## 6. Sinnvolle Artefakte für die Hardcode-Vorschau

Für den vollständigen Jackpot-Countdown-Fall kann diese reduzierte Artefaktliste
verwendet werden:

```js
export const lottoDemoArtifacts = [
  {
    label: "screenshot",
    title: "Jackpot-Seite",
    group: "Beweis",
    kind: "image",
    available: true,
    preview_available: true,
    size: 1482200,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  },
  {
    label: "normalized_text",
    title: "Normalisierter Text",
    group: "Abruf",
    kind: "text",
    available: true,
    preview_available: true,
    size: 18342,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  },
  {
    label: "diff",
    title: "Änderung zur vorherigen Aufnahme",
    group: "Abruf",
    kind: "text",
    available: true,
    preview_available: true,
    size: 2240,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  },
  {
    label: "capture_transparency",
    title: "Erfassungstransparenz",
    group: "Abruf",
    kind: "text",
    available: true,
    preview_available: true,
    size: 5380,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  },
  {
    label: "warc",
    title: "WARC",
    group: "Beweis",
    kind: "binary",
    available: true,
    preview_available: false,
    size: 2984010,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  },
  {
    label: "manifest",
    title: "Manifest",
    group: "Beweis",
    kind: "text",
    available: true,
    preview_available: true,
    size: 8942,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  },
  {
    label: "timestamp_response",
    title: "TSA-Antwort",
    group: "Beweis",
    kind: "binary",
    available: false,
    preview_available: false,
    size: null,
    status: "failed",
    status_reason: "Der externe Zeitstempeldienst war nicht erreichbar."
  },
  {
    label: "report",
    title: "PDF-Bericht",
    group: "Bericht",
    kind: "pdf",
    available: true,
    preview_available: true,
    size: 184320,
    status: "available",
    status_reason: "Im lokalen Beweispaket vorhanden."
  }
];
```

## 7. Empfohlene Reihenfolge für eine Design-Demo

1. Fallliste mit fünf Lotto-Fällen öffnen.
2. Den offenen Fall `Willkommensbonus` zeigen und menschlich freigeben.
3. Den Fall `Jackpot-Countdown` öffnen.
4. Erstverstoß und neue Fundstelle nebeneinander zeigen.
5. Begründung, Gegenargument und Unsicherheit einblenden.
6. Sichtbar machen, dass `human_release` noch `null` ist.
7. Zur Beweisansicht wechseln und Screenshot, Diff, Manifest und PDF öffnen.
8. Danach den echten Annahmeschluss als positiven Gegenfall zeigen.
9. Abschließend einen unvollständigen Schutzfall darstellen, damit die UI keine
   falsche Sicherheit vermittelt.

Der überzeugendste Pitch-Moment ist der Wechsel von der ursprünglichen Aktionsseite
zum neuen Countdown auf dem Tippschein: Der Text ist anders und die URL ist anders,
aber die zu prüfende Wirkung ist gleich geblieben.
