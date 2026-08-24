export type Tone = "danger" | "success" | "warning" | "neutral";

export type DemoCase = {
  case_id: string;
  fall_id: string;
  domain: string;
  title: string;
  status: string;
  secondary: string;
  tone: Tone;
  found_at: string | null;
  url: string;
  confidence: number | null;
  explanation: string;
  tenor: {
    formulierung: string;
    hinweis: string;
  };
  evidence: {
    fundstelle: string;
    erfassung: string;
    kette: string[];
    einordnung: string;
    offen: string;
  };
};

export const lottoDemoCases: DemoCase[] = [
  {
    case_id: "lotto-countdown-reset",
    fall_id: "VZ-LOTTO-2026-001",
    domain: "lotto-demo.test",
    title: "Jackpot-Countdown",
    status: "Möglicherweise kerngleicher Verstoß",
    secondary: "Countdown auf neuer Ebene erneut gestartet",
    tone: "danger",
    found_at: "2026-08-21T07:45:00Z",
    url: "https://lotto-demo.test/tippschein",
    confidence: 0.91,
    explanation:
      "Jackpot Plus nur noch 08:42 Minuten verfügbar – derselbe künstliche Zeitdruck, neue Seite.",
    tenor: {
      formulierung:
        "Der Antragsgegnerin wird untersagt, im geschäftlichen Verkehr für die Teilnahme an Lotterieprodukten mit einem zeitlich begrenzten Countdown zu werben, wenn der angezeigte Ablaufzeitpunkt keinem tatsächlichen Annahmeschluss entspricht, wie geschehen auf lotto-demo.test/tippschein am 21.08.2026.",
      hinweis:
        "Kerngleiche Wiederholung – Formulierung an den Tenor der bestehenden Unterlassungserklärung angelehnt.",
    },
    evidence: {
      fundstelle: "Countdown-Widget im Tippschein-Header, sichtbar ohne Login",
      erfassung:
        "Automatisierter Lauf, Screenshot + DOM-Snapshot, zwei Abrufe im Abstand von 30 Minuten",
      kette: [
        "07:45 Uhr: Countdown zeigt 08:42 Minuten Restzeit",
        "08:15 Uhr: erneuter Abruf, Countdown erneut bei 09:58 Minuten",
        "DOM-Attribut data-countdown-reset=true in beiden Snapshots",
        "Kein Bezug zu einem realen Annahmeschluss im Seitenquelltext",
      ],
      einordnung:
        "Wiederholung eines bereits untersagten Musters (künstlicher Zeitdruck) auf einer neuen Unterseite – kerngleich im Sinne der Unterlassungserklärung.",
      offen:
        "Wurde der Countdown durch Caching verfälscht? Gegencheck mit frischer Session empfohlen.",
    },
  },
  {
    case_id: "lotto-real-draw-deadline",
    fall_id: "VZ-LOTTO-2026-002",
    domain: "lotto-demo.test",
    title: "Echter Annahmeschluss",
    status: "Kein erfasster Wiederholungsverstoß",
    secondary: "Annahmeschluss technisch eingehalten",
    tone: "success",
    found_at: "2026-08-21T06:30:00Z",
    url: "https://lotto-demo.test/samstagsziehung",
    confidence: 0.93,
    explanation:
      "Annahmeschluss Samstag, 18:00 Uhr – Ziehung um 19:25 Uhr, dokumentiert und eingehalten.",
    tenor: {
      formulierung:
        "Kein Tenorvorschlag – die Zeitangabe entspricht einem realen Annahmeschluss; eine Unterlassungsforderung ist nicht veranlasst.",
      hinweis: "Nur zur Dokumentation; Fall als geprüft und unauffällig ablegen.",
    },
    evidence: {
      fundstelle: "Ziehungsseite Samstagsziehung, Abschnitt „Annahmeschluss“",
      erfassung: "Automatisierter Lauf, Screenshot + Abgleich mit veröffentlichtem Ziehungsplan",
      kette: [
        "Angezeigter Annahmeschluss: Samstag 18:00 Uhr",
        "Veröffentlichte Ziehung: Samstag 19:25 Uhr",
        "Zeitangabe über drei Abrufe hinweg unverändert",
        "Keine Countdown-Elemente im DOM",
      ],
      einordnung:
        "Zeitliche Angabe entspricht einem realen, überprüfbaren Ereignis – kein künstlicher Zeitdruck, kein kerngleicher Verstoß erfasst.",
      offen: "Keine offenen Punkte.",
    },
  },
  {
    case_id: "lotto-limited-tickets",
    fall_id: "VZ-LOTTO-2026-003",
    domain: "lotto-demo.test",
    title: "Begrenzte Tippscheine",
    status: "Menschliche Prüfung erforderlich",
    secondary: "Kontingentdaten fehlen",
    tone: "warning",
    found_at: "2026-08-21T08:05:00Z",
    url: "https://lotto-demo.test/sonderziehung",
    confidence: 0.56,
    explanation: "Fast ausverkauft – nur noch 96 Tipps verfügbar. Gesamtkontingent unbelegt.",
    tenor: {
      formulierung:
        "Der Antragsgegnerin wird untersagt, mit Angaben zu einer begrenzten Anzahl verfügbarer Tippscheine (z. B. „nur noch 96 Tipps verfügbar“) zu werben, ohne das Gesamtkontingent anzugeben, sofern die Restmenge nicht überprüfbar ist.",
      hinweis: "Entwurf steht unter Vorbehalt der Auskunft zum Gesamtkontingent.",
    },
    evidence: {
      fundstelle: "Sonderziehungsseite, Badge „Fast ausverkauft“",
      erfassung: "Automatisierter Lauf, Screenshot; Kontingent-Endpunkt nicht öffentlich",
      kette: [
        "Badge zeigt: nur noch 96 Tipps verfügbar",
        "Kein Gesamtkontingent auf der Seite oder in den Bedingungen genannt",
        "Wert sank über zwei Abrufe von 96 auf 91",
        "Keine Datenquelle zur Verifikation der Restmenge auffindbar",
      ],
      einordnung:
        "Knappheitsangabe ohne belegbare Bezugsgröße. Ob eine irreführende Angabe vorliegt, hängt von der tatsächlichen Kontingentierung ab.",
      offen:
        "Auskunft zum Gesamtkontingent erforderlich; ohne diese ist keine abschließende Bewertung möglich.",
    },
  },
  {
    case_id: "lotto-rules-link",
    fall_id: "VZ-LOTTO-2026-004",
    domain: "lotto-demo.test",
    title: "Teilnahmebedingungen",
    status: "Prüfumfang nicht vollständig",
    secondary: "Zielseite war nicht erreichbar",
    tone: "warning",
    found_at: "2026-08-21T08:55:00Z",
    url: "https://lotto-demo.test/jackpot-wochen",
    confidence: null,
    explanation:
      "Die verbindliche Zielseite der Teilnahmebedingungen war während des Laufs nicht erreichbar.",
    tenor: {
      formulierung:
        "Der Antragsgegnerin wird aufgegeben, die verlinkten Teilnahmebedingungen während der Laufzeit der Aktion dauerhaft abrufbar zu halten.",
      hinweis: "Vorläufig – erst nach erfolgreichem erneutem Abruf inhaltlich schärfen.",
    },
    evidence: {
      fundstelle: "Verlinkung „Teilnahmebedingungen“ auf der Aktionsseite Jackpot-Wochen",
      erfassung: "Automatisierter Lauf; Zielseite antwortete mit HTTP 503",
      kette: [
        "Link im Footer der Aktionsseite vorhanden",
        "Abruf der Zielseite: HTTP 503 (drei Versuche)",
        "Kein Cache-Stand der Bedingungen verfügbar",
        "Aktionsbedingungen daher nicht inhaltlich geprüft",
      ],
      einordnung:
        "Der Prüfumfang ist unvollständig. Aus der Nichterreichbarkeit allein folgt kein Verstoß.",
      offen: "Erneuter Abruf der Bedingungen; danach inhaltliche Prüfung nachholen.",
    },
  },
  {
    case_id: "lotto-bonus-pending",
    fall_id: "VZ-LOTTO-2026-005",
    domain: "lotto-demo.test",
    title: "Willkommensbonus",
    status: "Freigabe ausstehend",
    secondary: "Monitoring wurde noch nicht gestartet",
    tone: "neutral",
    found_at: null,
    url: "https://lotto-demo.test/willkommensbonus",
    confidence: null,
    explanation:
      "„Nur heute: Willkommens-Zusatztipp gratis“ – Fall wartet auf menschliche Freigabe.",
    tenor: {
      formulierung:
        "Der Antragsgegnerin wird untersagt, mit der Angabe „Nur heute“ für einen Willkommens-Zusatztipp zu werben, wenn das Angebot tatsächlich über den beworbenen Tag hinaus verfügbar ist.",
      hinweis:
        "Entwurf – Freigabe des Monitorings abwarten, Verfügbarkeitsnachweis über mehrere Tage erforderlich.",
    },
    evidence: {
      fundstelle: "Aktionsbanner „Willkommens-Zusatztipp gratis“",
      erfassung: "Erfassung angelegt, Monitoring noch nicht gestartet",
      kette: [
        "Fall manuell angelegt",
        "Kein automatisierter Abruf erfolgt",
        "Keine Screenshots vorhanden",
      ],
      einordnung:
        "Noch keine Bewertung – der Fall wartet auf menschliche Freigabe des Monitorings.",
      offen: "Freigabe durch die zuständige Juristin erforderlich.",
    },
  },
];
