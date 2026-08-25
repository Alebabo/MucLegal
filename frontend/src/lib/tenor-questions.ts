import type { AnsweredTenorQuestion, TenorPdfExtraction, TenorQuestion } from "./tenor-api";

export const MAX_TENOR_CONTEXT_CHARS = 60_000;

export type ClarificationTurn = {
  question: TenorQuestion;
  answer: string;
};

export function answeredQuestions(turns: ClarificationTurn[]): AnsweredTenorQuestion[] {
  return turns.map((turn) => ({
    topic_id: turn.question.topic_id,
    question: turn.question.text,
    answer: turn.answer,
    answer_type: turn.question.answer_type,
  }));
}

export function composeClarifiedContext(context: string, turns: ClarificationTurn[]) {
  const base = context.trim();
  if (turns.length === 0) return base.slice(0, MAX_TENOR_CONTEXT_CHARS);
  const additions = turns
    .map(
      (turn) =>
        `Thema: ${turn.question.topic_id}\nRückfrage: ${turn.question.text}\nAntwort: ${turn.answer}`,
    )
    .join("\n\n");
  const suffix = `Ergänzende Angaben:\n${additions}`;
  const availableForBase = Math.max(0, MAX_TENOR_CONTEXT_CHARS - suffix.length - 2);
  return `${base.slice(0, availableForBase)}\n\n${suffix}`.slice(0, MAX_TENOR_CONTEXT_CHARS);
}

export function formatPdfExtractionStatus(extraction: TenorPdfExtraction) {
  const pages =
    extraction.extracted_pages === extraction.page_count
      ? `${extraction.page_count} Seiten`
      : `${extraction.extracted_pages} von ${extraction.page_count} Seiten`;
  return `Text aus ${pages} berücksichtigt${extraction.truncated ? " · gekürzt" : ""}`;
}

export function composePdfContext(context: string, extraction: TenorPdfExtraction | null) {
  const userContext = context.trim();
  if (!extraction) return userContext.slice(0, MAX_TENOR_CONTEXT_CHARS);
  const documentContext = [
    `Hochgeladenes Vertragsdokument: ${extraction.filename}`,
    `Umfang: ${extraction.page_count} Seiten; Text aus ${extraction.extracted_pages} Seiten extrahiert.`,
    extraction.truncated
      ? "Hinweis: Der extrahierte Dokumenttext wurde wegen der Längenbegrenzung gekürzt."
      : "",
    "Dokumentinhalt:",
    extraction.text,
  ]
    .filter(Boolean)
    .join("\n");
  const combined = userContext
    ? `Nutzerangaben:\n${userContext}\n\n${documentContext}`
    : documentContext;
  return combined.slice(0, MAX_TENOR_CONTEXT_CHARS);
}

export function formatSliderAnswer(question: TenorQuestion, value: number) {
  const unit = question.slider?.unit?.trim();
  return unit ? `${value} ${unit}` : String(value);
}
