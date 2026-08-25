export type TenorDecision = "freigegeben" | "abgelehnt" | "weitere_pruefung";

export type TenorDraftRequest = {
  fall_id: string;
  schuldner?: string | null;
  fundstelle?: string | null;
  beschreibung: string;
  rechtsgrundlagen?: string[];
  fallgruppe?: string;
  violation_branch?: "A" | "B" | "C" | null;
};

export type TenorDraft = {
  fall_id: string;
  schuldner: string;
  entwurf: string;
  charakteristischer_kern: string;
  kerngleich_umfasst: string[];
  nicht_umfasst: string[];
  rechtsgrundlagen: string[];
  offene_fragen: string[];
  freigabe_durch_mensch: string | null;
};

export type TenorDraftRecord = {
  draft_id: string;
  created_at: string;
  mode: string;
  model: string;
  input: TenorDraftRequest;
  draft: TenorDraft;
  decision: TenorDecision | null;
  decided_at: string | null;
};

export type TenorProposalRequest = {
  fall_id: string;
  schuldner?: string | null;
  fundstelle?: string | null;
  context: string;
  fallgruppe: string;
  rechtsgrundlagen?: string[];
  violation_branch?: "A" | "B" | "C" | null;
};

export type TenorProposal = {
  strategy: "complete";
  title: string;
  text: string;
  source_ids: string[];
  warnings: string[];
  human_approval_required: true;
  freigabe_durch_mensch: null;
};

export type TenorProposalResponse = {
  mode: "live_openai";
  model: string;
  reference_version: string;
  status: "ready" | "needs_information";
  violation_branch: "A" | "B" | "C";
  proposal: TenorProposal | null;
  missing_information: string[];
};

export type TenorArchiveRequest = {
  fall_id: string;
  schuldner: string;
  title: string;
  text: string;
  context: string;
  strategy: "complete";
  model: string;
  reference_version: string;
  source_ids: string[];
};

export type TenorArchiveRecord = Omit<TenorArchiveRequest, "strategy"> & {
  tenor_id: string;
  created_at: string;
  source: "minimal" | "maske";
  strategy: string;
  decision: TenorDecision | null;
  decided_at: string | null;
};

export type TenorQuestionAnswerType = "yes_no" | "text" | "slider" | "single_choice";

export type AnsweredTenorQuestion = {
  topic_id: string;
  question: string;
  answer: string;
  answer_type: TenorQuestionAnswerType;
};

export type TenorQuestionOption = {
  value: string;
  label: string;
};

export type TenorSliderQuestion = {
  minimum: number;
  maximum: number;
  step: number;
  minimum_label: string;
  maximum_label: string;
  unit: string | null;
};

export type TenorQuestion = {
  question_id: string;
  topic_id: string;
  text: string;
  answer_type: TenorQuestionAnswerType;
  placeholder: string | null;
  slider: TenorSliderQuestion | null;
  options: TenorQuestionOption[];
};

export type TenorQuestionResponse = {
  mode: "live_openai";
  model: string;
  ready_to_generate: boolean;
  question: TenorQuestion | null;
  violation_branch: "A" | "B" | "C";
  missing_information: string[];
};

export type TenorPdfExtraction = {
  filename: string;
  text: string;
  page_count: number;
  extracted_pages: number;
  truncated: boolean;
};

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail)) {
        message =
          payload.detail
            .map((item) => item.msg)
            .filter(Boolean)
            .join(" · ") || message;
      }
    } catch {
      // The HTTP status remains visible when the backend returns no JSON detail.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export function createTenorDraft(payload: TenorDraftRequest) {
  return requestJson<TenorDraftRecord>("/api/v1/tenor-drafts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createTenorProposals(payload: TenorProposalRequest) {
  return requestJson<TenorProposalResponse>("/api/v1/tenor-proposals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createTenorQuestion(payload: {
  context: string;
  fallgruppe: string;
  answered_questions: AnsweredTenorQuestion[];
}) {
  return requestJson<TenorQuestionResponse>("/api/v1/tenor-questions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function extractTenorPdf(file: File) {
  return requestJson<TenorPdfExtraction>("/api/v1/tenor-pdf-text", {
    method: "POST",
    headers: {
      "Content-Type": "application/pdf",
      "X-File-Name": encodeURIComponent(file.name),
    },
    body: file,
  });
}

export function saveTenorArchiveEntry(payload: TenorArchiveRequest) {
  return requestJson<TenorArchiveRecord>("/api/v1/tenor-archive", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listTenorArchiveEntries() {
  return requestJson<{ tenors: TenorArchiveRecord[] }>("/api/v1/tenor-archive", {
    method: "GET",
  });
}

export function reviewTenorDraft(draftId: string, decision: TenorDecision) {
  return requestJson<TenorDraftRecord>(
    `/api/v1/tenor-drafts/${encodeURIComponent(draftId)}/review`,
    {
      method: "POST",
      body: JSON.stringify({ decision }),
    },
  );
}
