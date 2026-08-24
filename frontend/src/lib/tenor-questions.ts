import type { AnsweredTenorQuestion, TenorQuestion } from "./tenor-api";

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
  if (turns.length === 0) return base;
  const additions = turns
    .map((turn) => `Rückfrage: ${turn.question.text}\nAntwort: ${turn.answer}`)
    .join("\n\n");
  return `${base}\n\nErgänzende Angaben:\n${additions}`.slice(0, 4_000);
}

export function formatSliderAnswer(question: TenorQuestion, value: number) {
  const unit = question.slider?.unit?.trim();
  return unit ? `${value} ${unit}` : String(value);
}
