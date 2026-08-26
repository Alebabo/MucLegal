import assert from "node:assert/strict";
import test from "node:test";

import {
  assessCompleteness,
  composeRevisionContext,
  extractLegalBases,
  filterCaseOptions,
  filterModeCommands,
  filterTenorArchiveOptions,
  hasConcreteViolationLocation,
  inferFallgruppe,
  isAllowedUeAutocompleteSegment,
  isTenor,
  nextRequiredIntakeFact,
  nextWrappedIndex,
} from "../src/lib/minimal-tenor-logic.ts";
import { compactArchiveCaseTitle } from "../src/lib/archive-formatting.ts";
import { composeDictationText, mergeDictationSegments } from "../src/lib/dictation.ts";
import { splitAlternativeLabels, splitLineValues } from "../src/lib/monitoring-form.ts";
import {
  answeredQuestions,
  composeClarifiedContext,
  composePdfContext,
  formatPdfExtractionStatus,
  formatSliderAnswer,
} from "../src/lib/tenor-questions.ts";

test("asks for the first missing semantic fact", () => {
  const empty = assessCompleteness("");
  assert.equal(empty.complete, false);
  assert.deepEqual(empty.missing, ["handlung", "kanal", "betroffene", "ziel"]);
  assert.match(empty.nextQuestion, /Handlung/);

  const partial = assessCompleteness("Die Werbung auf der Website richtet sich an Verbraucher.");
  assert.deepEqual(partial.missing, ["ziel"]);
  assert.match(partial.nextQuestion, /unterlassen/);
});

test("keeps commas inside line-based legal qualifications", () => {
  assert.deepEqual(
    splitLineValues(
      "Freistellung nur bei schuldhafter Rechtsverletzung, einschließlich der Entfernung nach Hinweis.\nKeine verschuldensunabhängige Haftung.",
    ),
    [
      "Freistellung nur bei schuldhafter Rechtsverletzung, einschließlich der Entfernung nach Hinweis.",
      "Keine verschuldensunabhängige Haftung.",
    ],
  );
  assert.deepEqual(splitAlternativeLabels("Widerruf, Rückgabe\nRücktritt"), [
    "Widerruf",
    "Rückgabe",
    "Rücktritt",
  ]);
});

test("accepts a short semantically complete description", () => {
  const result = assessCompleteness(
    "Die irreführende Werbung auf der Website gegenüber Verbrauchern soll künftig unterlassen werden.",
  );
  assert.equal(result.complete, true);
  assert.equal(result.nextQuestion, null);
});

test("asks deterministically for exact violation location and specific legal bases", () => {
  const context = "Die Beispiel GmbH wirbt gegenüber Verbrauchern mit einer falschen Frist.";
  const first = nextRequiredIntakeFact(context, "irrefuehrende_werbung", []);
  assert.equal(first?.id, "verstossort");

  const locationAnswer = {
    ...first,
    answer: "Auf der Produktseite https://example.org/angebot startet der Countdown erneut.",
  };
  const second = nextRequiredIntakeFact(context, "irrefuehrende_werbung", [locationAnswer]);
  assert.equal(second?.id, "rechtsgrundlagen");
  const legalAnswer = { ...second, answer: "§ 5 UWG und § 8 Abs. 1 UWG" };
  assert.equal(
    nextRequiredIntakeFact(context, "irrefuehrende_werbung", [locationAnswer, legalAnswer]),
    null,
  );
  assert.deepEqual(extractLegalBases(legalAnswer.answer), ["§ 5 UWG", "§ 8 Abs. 1 UWG"]);
});

test("does not demand a URL for a sufficiently quoted AGB clause", () => {
  assert.equal(
    hasConcreteViolationLocation(
      'Klausel: "Der Vertrag verlängert sich automatisch um zwölf Monate."',
      "agb_klausel",
    ),
    true,
  );
});

test("keeps the original tenor, source context and revision request separate", () => {
  const context = composeRevisionContext(
    "Der Antragsgegnerin wird untersagt, mit einer falschen Frist zu werben.",
    "Bitte technikneutral formulieren und den Countdown ausdrücklich erfassen.",
    "Die Frist auf der Produktseite bestand tatsächlich nicht.",
  );
  assert.match(context, /Bestehender Tenor/);
  assert.match(context, /Ursprünglicher Sachverhalt/);
  assert.match(context, /Änderungswunsch/);
});

test("recognizes tenor correction input", () => {
  assert.equal(isTenor("Der Beklagten wird untersagt, dies künftig zu tun."), true);
  assert.equal(isTenor("Ein kurzer Sachverhalt"), false);
});

test("never suggests judgment or coercive-order formulas in UE correction mode", () => {
  assert.equal(isAllowedUeAutocompleteSegment("verpflichtungsformel"), false);
  assert.equal(isAllowedUeAutocompleteSegment("ordnungsmittelandrohung"), false);
  assert.equal(isAllowedUeAutocompleteSegment("adressatenkreis"), true);
});

test("recognizes common advertising word forms", () => {
  assert.equal(
    inferFallgruppe("Das Unternehmen wirbt mit einem Countdown"),
    "irrefuehrende_werbung",
  );
  assert.equal(inferFallgruppe("Werbung mit falscher Knappheit"), "irrefuehrende_werbung");
  assert.equal(
    assessCompleteness(
      "Die GmbH soll es unterlassen, gegenüber Verbrauchern auf ihrer Website mit einer falschen Frist zu werben.",
    ).complete,
    true,
  );
});

test("treats an uploaded contract as an AGB clause case", () => {
  assert.equal(
    inferFallgruppe(
      "Vertrag mit einer automatischen Laufzeitverlängerung und einer schriftlichen Kündigungsfrist",
      true,
    ),
    "agb_klausel",
  );
});

test("filters slash modes and wraps keyboard selection", () => {
  assert.deepEqual(
    filterModeCommands("ten").map((item) => item.id),
    ["tenor"],
  );
  assert.equal(nextWrappedIndex(2, 3, 1), 0);
  assert.equal(nextWrappedIndex(0, 3, -1), 2);
});

test("filters the current case source supplied by the Tenorhilfe", () => {
  const backendCases = [
    {
      title: "Click & Collect in der Filiale",
      fall_id: "VZ-MUELLER-CLICK-COLLECT-2025",
      domain: "www.mueller.de",
      secondary: "Aktueller technischer Vergleich vorhanden",
    },
  ];

  assert.deepEqual(filterCaseOptions(backendCases, "müller"), backendCases);
  assert.deepEqual(filterCaseOptions(backendCases, "lotto"), []);
});

test("finds archived tenors by Aktenzeichen for the /tenor mode", () => {
  const archive = [
    {
      tenor_id: "tenor-1",
      fall_id: "VZ-MUELLER-2025-0417",
      title: "Müller Click & Collect",
      schuldner: "Müller Handels GmbH & Co. KG",
      text: "Der Schuldnerin wird untersagt, eine Abholfrist irreführend darzustellen.",
    },
    {
      tenor_id: "tenor-2",
      fall_id: "VZ-ANDERS-2026-0002",
      title: "Anderer Fall",
      schuldner: "Beispiel GmbH",
      text: "Ein anderer archivierter Tenor.",
    },
  ];

  assert.deepEqual(filterTenorArchiveOptions(archive, "VZ-MUELLER-2025-0417"), [archive[0]]);
  assert.deepEqual(filterTenorArchiveOptions(archive, "Az. VZ-MUELLER"), [archive[0]]);
  assert.deepEqual(filterTenorArchiveOptions(archive, "müller handels"), [archive[0]]);
  assert.deepEqual(filterTenorArchiveOptions(archive, "abholfrist"), [archive[0]]);
});

test("keeps archive case titles compact and meaningful", () => {
  assert.equal(
    compactArchiveCaseTitle(
      "Historischer Müller-Click-&-Collect-Fall nach dem rechtskräftigen Urteil des OLG Stuttgart.",
      "Technisch prüfen, ob die aktuelle AGB-Fassung weiterhin betroffen ist.",
    ),
    "Müller-Click-&-Collect-Fall",
  );
  assert.equal(
    compactArchiveCaseTitle(
      "Klar gekennzeichneter synthetischer Decathlon-Demofall für die lokale Vorführung der technischen Differenzanzeige.",
      "VZ-DECATHLON-GESAMTBEWEIS-2026",
    ),
    "Synthetischer Decathlon-Demofall",
  );
  assert.match(
    compactArchiveCaseTitle(
      "Ein sehr ausführlicher Falltitel mit zahlreichen zusätzlichen Einzelheiten für das Archiv.",
      "Fallback",
    ),
    /^.{1,47}…$/u,
  );
});

test("replaces cumulative dictation results instead of appending them twice", () => {
  let segments = mergeDictationSegments({}, [
    { index: 0, transcript: "Der erste Satz", isFinal: false },
  ]);
  assert.equal(composeDictationText("Ausgangstext.", segments), "Ausgangstext. Der erste Satz");

  segments = mergeDictationSegments(segments, [
    { index: 0, transcript: "Der erste Satz.", isFinal: true },
  ]);
  assert.equal(composeDictationText("Ausgangstext.", segments), "Ausgangstext. Der erste Satz.");

  segments = mergeDictationSegments(segments, [
    { index: 1, transcript: "Nach der Pause folgt Satz zwei.", isFinal: true },
  ]);
  assert.equal(
    composeDictationText("Ausgangstext.", segments),
    "Ausgangstext. Der erste Satz. Nach der Pause folgt Satz zwei.",
  );
});

test("keeps contextual questions and answers in the generated tenor context", () => {
  const question = {
    question_id: "q-1",
    topic_id: "taeuschungstatsache",
    text: "War die Frist tatsächlich verbindlich?",
    answer_type: "yes_no",
    placeholder: null,
    slider: null,
    options: [],
  };
  const turns = [{ question, answer: "Nein" }];
  assert.deepEqual(answeredQuestions(turns), [
    {
      topic_id: "taeuschungstatsache",
      question: "War die Frist tatsächlich verbindlich?",
      answer: "Nein",
      answer_type: "yes_no",
    },
  ]);
  assert.match(
    composeClarifiedContext("Die Aktion lief online.", turns),
    /Thema: taeuschungstatsache\nRückfrage:.*\nAntwort: Nein/,
  );
});

test("formats slider answers with the AI-selected unit", () => {
  const question = {
    question_id: "q-2",
    topic_id: "quantifizierbare_dauer_oder_anzahl",
    text: "Wie lange lief der Countdown?",
    answer_type: "slider",
    placeholder: null,
    slider: {
      minimum: 0,
      maximum: 30,
      step: 1,
      minimum_label: "kurz",
      maximum_label: "lang",
      unit: "Tage",
    },
    options: [],
  };
  assert.equal(formatSliderAnswer(question, 12), "12 Tage");
});

test("preserves a selected or custom choice with its unique topic", () => {
  const question = {
    question_id: "q-3",
    topic_id: "adressatenkreis",
    text: "An wen richtet sich die Klausel?",
    answer_type: "single_choice",
    placeholder: "Andere Gruppe",
    slider: null,
    options: [
      { value: "verbraucher", label: "Verbraucher" },
      { value: "unternehmer", label: "Unternehmer" },
    ],
  };
  const selected = answeredQuestions([{ question, answer: "Verbraucher" }]);
  const custom = answeredQuestions([{ question, answer: "Vereinsmitglieder" }]);
  assert.equal(selected[0].topic_id, "adressatenkreis");
  assert.equal(selected[0].answer, "Verbraucher");
  assert.equal(custom[0].answer, "Vereinsmitglieder");
  assert.equal(custom[0].answer_type, "single_choice");
});

test("includes extracted contract text and later answers in the tenor context", () => {
  const extraction = {
    filename: "vertrag.pdf",
    text: `Klausel: ${"Verlängerung ".repeat(3_000)}`,
    page_count: 18,
    extracted_pages: 18,
    truncated: false,
  };
  const documentContext = composePdfContext("Der Vertrag gilt für Verbraucher.", extraction);
  assert.match(documentContext, /Hochgeladenes Vertragsdokument: vertrag\.pdf/);
  assert.match(documentContext, /Klausel: Verlängerung/);

  const question = {
    question_id: "q-pdf",
    topic_id: "schuldner",
    text: "Wer verwendet die Klausel?",
    answer_type: "text",
    placeholder: null,
    slider: null,
    options: [],
  };
  const clarified = composeClarifiedContext(documentContext, [
    { question, answer: "Synthetische Beispiel GmbH" },
  ]);
  assert.ok(clarified.length <= 60_000);
  assert.match(clarified, /Thema: schuldner/);
  assert.match(clarified, /Antwort: Synthetische Beispiel GmbH/);
});

test("keeps the exact clause answer after a truncated uploaded contract", () => {
  const extraction = {
    filename: "vertrag.pdf",
    text: "Die Marke „Fit“ gehört zum Tarif „Flex Deal 2026“. ".repeat(1_000),
    page_count: 11,
    extracted_pages: 8,
    truncated: true,
  };
  const documentContext = composePdfContext("", extraction);
  const question = {
    question_id: "q-clause",
    topic_id: "klauselwortlaut",
    text: "Wie lautet die konkret beanstandete Klausel vollständig und wortwörtlich?",
    answer_type: "text",
    placeholder: "Vollständigen Klauselwortlaut hier einfügen",
    slider: null,
    options: [],
  };
  const clause =
    "Das Mitglied kann den Vertrag jederzeit mit einer Frist von vier Wochen kündigen.";
  const clarified = composeClarifiedContext(documentContext, [{ question, answer: clause }]);

  assert.ok(clarified.length <= 60_000);
  assert.match(clarified, /Thema: klauselwortlaut/);
  assert.ok(clarified.endsWith(`Antwort: ${clause}`));
  assert.equal(
    formatPdfExtractionStatus(extraction),
    "Text aus 8 von 11 Seiten berücksichtigt · gekürzt",
  );
  assert.equal(
    formatPdfExtractionStatus({ ...extraction, extracted_pages: 11, truncated: false }),
    "Text aus 11 Seiten berücksichtigt",
  );
});
