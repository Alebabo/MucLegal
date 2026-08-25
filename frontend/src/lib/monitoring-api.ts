import { useQuery } from "@tanstack/react-query";

export type CaseDecision = "freigegeben" | "abgelehnt" | "weitere_pruefung";
export type ViolationType = "klausel" | "element";

export type BaselineEvidence = {
  evidence_case_id: string;
  requested_url: string;
  captured_url: string;
  captured_at: string;
  manifest_sha256: string;
  attached_at: string;
  attached_by: "menschliche_zuordnung_im_beweislab";
  demo_only?: boolean;
  demo_notice?: string;
};

export type EvidenceComparison = {
  comparison_id: string;
  status: "technische_aenderung_erkannt" | "unveraendert_fortbestehend" | "pruefung_unvollstaendig";
  baseline_evidence_case_id: string;
  current_evidence_case_id: string;
  baseline_requested_url: string;
  current_requested_url: string;
  baseline_manifest_sha256: string;
  current_manifest_sha256: string;
  baseline_text_sha256: string | null;
  current_text_sha256: string | null;
  compared_role: string;
  compared_at: string;
  comparison_method?: "manifestgepruefter_wortbasierter_textvergleich";
  difference_summary?: string;
  differences?: Array<{
    change_type: "replace" | "delete" | "insert";
    label: string;
    before: string;
    after: string;
  }>;
  demo_only?: boolean;
  demo_notice?: string;
  technical_only: true;
};

export type MonitoringCase = {
  case_id: string;
  fall_id: string;
  domain: string;
  source_url: string;
  violation_type: ViolationType;
  description: string;
  tenor_element: string;
  monitoring_target: string;
  relevant_page_types: string[];
  target_urls: string[];
  nicht_umfasst: string[];
  clause_text: string | null;
  element_label: string | null;
  element_labels: string[];
  element_function: string | null;
  element_error: string | null;
  allowed_subdomains: string[];
  decision: CaseDecision;
  created_at: string;
  decided_at: string | null;
  baseline_evidence: BaselineEvidence | null;
  latest_evidence_comparison: EvidenceComparison | null;
};

export type MonitoringCaseCreate = Omit<
  MonitoringCase,
  | "case_id"
  | "decision"
  | "created_at"
  | "decided_at"
  | "baseline_evidence"
  | "latest_evidence_comparison"
>;

export type MonitoringRun = {
  run_id: string;
  status: string;
  message: string;
  current_step: string;
  result_available: boolean;
};

type CaseListResponse = {
  cases: MonitoringCase[];
};

export const monitoringCasesQueryKey = ["monitoring-cases"] as const;

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // The status code remains a useful error when no JSON body is available.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export function useMonitoringCases() {
  return useQuery({
    queryKey: monitoringCasesQueryKey,
    queryFn: async () => (await requestJson<CaseListResponse>("/api/v1/monitoring-cases")).cases,
    enabled: typeof window !== "undefined",
    retry: 1,
    staleTime: 5_000,
  });
}

export function createMonitoringCase(payload: MonitoringCaseCreate) {
  return requestJson<MonitoringCase>("/api/v1/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reviewMonitoringCase(caseId: string, decision: CaseDecision) {
  return requestJson<MonitoringCase>(`/api/v1/cases/${encodeURIComponent(caseId)}/review`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

export function startMonitoringRun(caseId: string) {
  return requestJson<MonitoringRun>("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId }),
  });
}

export function getMonitoringRun(runId: string) {
  return requestJson<MonitoringRun>(`/api/v1/runs/${encodeURIComponent(runId)}`);
}
