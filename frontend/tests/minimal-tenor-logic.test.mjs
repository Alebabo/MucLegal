import assert from "node:assert/strict";
import test from "node:test";

import {
  assessCompleteness,
  filterModeCommands,
  inferFallgruppe,
  isTenor,
  nextWrappedIndex,
} from "../src/lib/minimal-tenor-logic.ts";
import { composeDictationText, mergeDictationSegments } from "../src/lib/dictation.ts";
import {
  answeredQuestions,
  composeClarifiedContext,
  composePdfContext,
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

test("accepts a short semantically complete description", () => {
  const result = assessCompleteness(
    "Die irreführende Werbung auf der Website gegenüber Verbrauchern soll künftig unterlassen werden.",
  );
  assert.equal(result.complete, true);
  assert.equal(result.nextQuestion, null);
});

test("recognizes tenor correction input", () => {
  assert.equal(isTenor("Der Beklagten wird untersagt, dies künftig zu tun."), true);
  assert.equal(isTenor("Ein kurzer Sachverhalt"), false);
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
    /Rückfrage:.*\nAntwort: Nein/,
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
  assert.match(clarified, /Antwort: Synthetische Beispiel GmbH/);
});
