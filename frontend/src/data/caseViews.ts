import { lottoDemoCases, type DemoCase, type Tone } from "./lottoDemoCases";
import { useMonitoringCases, type MonitoringCase } from "../lib/monitoring-api";

export type CaseView = DemoCase & {
  source: "backend" | "demo";
  decision: MonitoringCase["decision"] | null;
};

const decisionPresentation: Record<
  MonitoringCase["decision"],
  { tone: Tone; status: string; secondary: string }
> = {
  freigegeben: {
    tone: "neutral",
    status: "Monitoring freigegeben",
    secondary: "Der nächste technische Prüflauf kann gestartet werden",
  },
  abgelehnt: {
    tone: "success",
    status: "Nicht für das Monitoring freigegeben",
    secondary: "Der Fall wurde nach menschlicher Prüfung geschlossen",
  },
  weitere_pruefung: {
    tone: "warning",
    status: "Menschliche Prüfung erforderlich",
    secondary: "Freigabe durch eine Juristin steht noch aus",
  },
};

function titleFor(item: MonitoringCase) {
  const firstLine = item.monitoring_target.split(/\r?\n/)[0]?.trim();
  return firstLine || item.fall_id;
}

function toCaseView(item: MonitoringCase): CaseView {
  const presentation = decisionPresentation[item.decision];
  const targets = item.target_urls.length ? item.target_urls : [item.source_url];
  const scope = item.relevant_page_types.join(", ");
  const exclusions = item.nicht_umfasst.length
    ? `Nicht umfasst: ${item.nicht_umfasst.join("; ")}`
    : "Keine zusätzlichen Abgrenzungen erfasst.";

  return {
    case_id: item.case_id,
    fall_id: item.fall_id,
    domain: item.domain,
    title: titleFor(item),
    status: presentation.status,
    secondary: presentation.secondary,
    tone: presentation.tone,
    found_at: item.created_at,
    url: item.source_url,
    confidence: null,
    explanation: item.description,
    tenor: {
      formulierung: item.tenor_element,
      hinweis: exclusions,
    },
    evidence: {
      fundstelle: item.source_url,
      erfassung: `${item.violation_type === "klausel" ? "Klausel" : "Seitenelement"} · Prüfumfang: ${scope}`,
      kette: targets.map((target) => `Vorgesehenes technisches Prüfziel: ${target}`),
      einordnung: item.monitoring_target,
      offen:
        item.decision === "weitere_pruefung"
          ? "Menschliche Freigabe des Falls steht aus."
          : item.decision === "freigegeben"
            ? "Technischer Monitoringlauf kann manuell gestartet werden."
            : "Fall wurde nicht für das Monitoring freigegeben.",
    },
    source: "backend",
    decision: item.decision,
  };
}

const demoViews: CaseView[] = lottoDemoCases.map((item) => ({
  ...item,
  source: "demo",
  decision: null,
}));

export function useCaseViews() {
  const query = useMonitoringCases();
  const backendCases = (query.data ?? []).map(toCaseView);

  return {
    ...query,
    cases: backendCases.length ? backendCases : demoViews,
    demoMode: backendCases.length === 0,
  };
}
