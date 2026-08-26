import { lottoDemoCases, type DemoCase, type Tone } from "./lottoDemoCases";
import {
  useMonitoringCases,
  type EngineAssessment,
  type MonitoringCase,
} from "../lib/monitoring-api";

export type CaseView = DemoCase & {
  source: "backend" | "demo";
  decision: MonitoringCase["decision"] | null;
  baselineEvidence: MonitoringCase["baseline_evidence"];
  latestEvidenceComparison: MonitoringCase["latest_evidence_comparison"];
  engineAssessment: EngineAssessment;
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

function pendingAssessment(item: MonitoringCase): EngineAssessment {
  const hasComparison = item.latest_evidence_comparison !== null;
  return {
    classification: "noch_nicht_bewertet",
    status: "noch_nicht_bewertet",
    reasoning: hasComparison
      ? "Der technische BeweisLab-Vergleich liegt vor, wurde von der Kerngleichheits-Engine aber noch nicht bewertet."
      : "Für diesen Fall liegt noch kein abgeschlossener Kerngleichheitslauf vor.",
    confidence: null,
    assessed_at: null,
    run_id: null,
    superseded_by_comparison: false,
    freigabe_durch_mensch: null,
  };
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
      kette: [
        ...(item.baseline_evidence
          ? [
              `Manuell zugeordneter Ausgangsbeweis: ${item.baseline_evidence.evidence_case_id} · Manifest ${item.baseline_evidence.manifest_sha256.slice(0, 12)}…`,
            ]
          : []),
        ...(item.latest_evidence_comparison
          ? [
              `Aktueller BeweisLab-Vergleich: ${item.latest_evidence_comparison.current_evidence_case_id} gegen ${item.latest_evidence_comparison.baseline_evidence_case_id} · ${
                item.latest_evidence_comparison.status === "technische_aenderung_erkannt"
                  ? "technische Abweichung erkannt"
                  : item.latest_evidence_comparison.status === "unveraendert_fortbestehend"
                    ? "kein technischer Unterschied erkannt"
                    : "technischer Vergleich unvollständig"
              }`,
            ]
          : []),
        ...targets.map((target) => `Vorgesehenes technisches Prüfziel: ${target}`),
      ],
      einordnung: item.monitoring_target,
      offen:
        item.decision === "weitere_pruefung"
          ? "Menschliche Freigabe des Falls steht aus."
          : item.decision === "freigegeben"
            ? item.baseline_evidence
              ? "Der nächste manuell gestartete Lauf wird mit dem zugeordneten Ausgangsbeweis verglichen."
              : "Technischer Erstlauf kann manuell als systeminterne Referenz gestartet werden."
            : "Fall wurde nicht für das Monitoring freigegeben.",
    },
    source: "backend",
    decision: item.decision,
    baselineEvidence: item.baseline_evidence,
    latestEvidenceComparison: item.latest_evidence_comparison,
    engineAssessment: item.latest_engine_assessment ?? pendingAssessment(item),
  };
}

const demoViews: CaseView[] = lottoDemoCases.map((item) => ({
  ...item,
  source: "demo",
  decision: null,
  baselineEvidence: null,
  latestEvidenceComparison: null,
  engineAssessment: {
    classification:
      item.tone === "danger"
        ? "kerngleich"
        : item.tone === "success"
          ? "nicht_kerngleich"
          : item.tone === "warning"
            ? "unklar"
            : "noch_nicht_bewertet",
    status: item.status,
    reasoning: item.evidence.einordnung,
    confidence: item.confidence,
    assessed_at: item.found_at,
    run_id: null,
    superseded_by_comparison: false,
    freigabe_durch_mensch: null,
  },
}));

export function useCaseViews() {
  const query = useMonitoringCases();
  const backendCases = (query.data ?? []).map(toCaseView);
  const dataLoaded = query.isSuccess;

  return {
    ...query,
    cases: dataLoaded ? (backendCases.length ? backendCases : demoViews) : [],
    demoMode: dataLoaded && backendCases.length === 0,
  };
}
