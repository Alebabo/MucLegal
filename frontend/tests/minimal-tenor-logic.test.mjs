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
