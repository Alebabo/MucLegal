export type MonitoringChangeTone = "danger" | "success" | "warning";

export type MonitoringChangeNotification = {
  title: string;
  description: string;
  tone: MonitoringChangeTone;
};

const CHANGE_NOTIFICATIONS: Record<string, MonitoringChangeNotification> = {
  technische_aenderung_erkannt: {
    title: "Technische Änderung erkannt",
    description: "Der aktuelle Beweis weicht vom Webarchiv-Ausgangsbeweis ab.",
    tone: "warning",
  },
  beseitigt: {
    title: "Änderung erkannt",
    description: "Der beanstandete Zustand wurde nicht mehr gefunden.",
    tone: "success",
  },
  kerngleich_wiederaufgetreten: {
    title: "Kerngleiche Verletzungsform erkannt",
    description: "Der Verstoß ist in kerngleicher Form wiederaufgetreten.",
    tone: "danger",
  },
  neuer_sachverhalt: {
    title: "Neuer Sachverhalt erkannt",
    description: "Der Scan weicht vom Ausgangsbeweis ab und erfordert eine neue Einordnung.",
    tone: "warning",
  },
  unsicher: {
    title: "Änderung erkannt – Prüfung nötig",
    description: "Die mögliche Abweichung muss menschlich geprüft werden.",
    tone: "warning",
  },
};

export const EVIDENCE_COMPARISON_NOTIFICATION_KEY = "muclegal:evidence-comparison-notification:v1";
export const EVIDENCE_COMPARISON_NOTIFICATION_QUERY = "beweisvergleich";

export type StoredEvidenceComparisonNotification = {
  version: 1;
  notification_id: string;
  case_id: string;
  fall_id: string;
  status: "technische_aenderung_erkannt";
};

export function parseStoredEvidenceComparisonNotification(
  value: string | null,
): StoredEvidenceComparisonNotification | null {
  if (!value) return null;
  try {
    const candidate = JSON.parse(value) as Partial<StoredEvidenceComparisonNotification>;
    if (
      candidate.version !== 1 ||
      candidate.status !== "technische_aenderung_erkannt" ||
      typeof candidate.notification_id !== "string" ||
      !candidate.notification_id ||
      typeof candidate.case_id !== "string" ||
      !candidate.case_id ||
      typeof candidate.fall_id !== "string" ||
      !candidate.fall_id
    ) {
      return null;
    }
    return candidate as StoredEvidenceComparisonNotification;
  } catch {
    return null;
  }
}

export function monitoringChangeNotification(status: string): MonitoringChangeNotification | null {
  return CHANGE_NOTIFICATIONS[status] ?? null;
}

export function claimMonitoringChangeNotification(
  status: string,
  runId: string,
  notifiedRunIds: Set<string>,
): MonitoringChangeNotification | null {
  const notification = monitoringChangeNotification(status);
  if (!notification || notifiedRunIds.has(runId)) return null;
  notifiedRunIds.add(runId);
  return notification;
}
