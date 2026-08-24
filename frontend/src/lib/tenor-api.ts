export type TenorDecision = "freigegeben" | "abgelehnt" | "weitere_pruefung";

export type TenorDraftRequest = {
  fall_id: string;
  schuldner: string;
  fundstelle: string;
  beschreibung: string;
  rechtsgrundlagen: string[];
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
  schuldner: string;
  fundstelle: string;
  context: string;
  fallgruppe: string;
  rechtsgrundlagen: string[];
};

export type TenorProposal = {
  strategy: "precise" | "neutral";
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
  proposals: [TenorProposal, TenorProposal];
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

export function reviewTenorDraft(draftId: string, decision: TenorDecision) {
  return requestJson<TenorDraftRecord>(
    `/api/v1/tenor-drafts/${encodeURIComponent(draftId)}/review`,
    {
      method: "POST",
      body: JSON.stringify({ decision }),
    },
  );
}
