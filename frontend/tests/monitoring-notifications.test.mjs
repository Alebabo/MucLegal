import assert from "node:assert/strict";
import test from "node:test";

import {
  claimMonitoringChangeNotification,
  monitoringChangeNotification,
  parseStoredEvidenceComparisonNotification,
} from "../src/lib/monitoring-notifications.ts";

test("creates a notification for every agreed comparison difference", () => {
  const expected = new Map([
    ["beseitigt", "success"],
    ["kerngleich_wiederaufgetreten", "danger"],
    ["neuer_sachverhalt", "warning"],
    ["unsicher", "warning"],
    ["technische_aenderung_erkannt", "warning"],
  ]);

  for (const [status, tone] of expected) {
    const notification = monitoringChangeNotification(status);
    assert.ok(notification, `${status} should create a notification`);
    assert.equal(notification.tone, tone);
    assert.ok(notification.title.length > 0);
    assert.ok(notification.description.length > 0);
  }
});

test("accepts only the versioned BeweisLab comparison handoff", () => {
  const valid = JSON.stringify({
    version: 1,
    notification_id: "comparison-1",
    case_id: "case-1",
    fall_id: "VZ-DECATHLON-GESAMTBEWEIS-2026",
    status: "technische_aenderung_erkannt",
  });

  assert.deepEqual(parseStoredEvidenceComparisonNotification(valid), JSON.parse(valid));
  assert.equal(parseStoredEvidenceComparisonNotification("not-json"), null);
  assert.equal(
    parseStoredEvidenceComparisonNotification(JSON.stringify({ ...JSON.parse(valid), version: 2 })),
    null,
  );
  assert.equal(
    parseStoredEvidenceComparisonNotification(
      JSON.stringify({ ...JSON.parse(valid), status: "unveraendert_fortbestehend" }),
    ),
    null,
  );
});

test("does not misreport unchanged, reference, incomplete or failed runs as differences", () => {
  for (const status of [
    "unveraendert_fortbestehend",
    "referenzzustand_dokumentiert",
    "pruefung_unvollstaendig",
    "failed",
  ]) {
    assert.equal(monitoringChangeNotification(status), null);
  }
});

test("claims a terminal run notification only once", () => {
  const notifiedRunIds = new Set();

  assert.ok(claimMonitoringChangeNotification("unsicher", "run-123", notifiedRunIds));
  assert.equal(claimMonitoringChangeNotification("unsicher", "run-123", notifiedRunIds), null);
  assert.ok(claimMonitoringChangeNotification("unsicher", "run-456", notifiedRunIds));
});
