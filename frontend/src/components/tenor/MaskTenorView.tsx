import { Check, CircleAlert, LoaderCircle, RotateCcw } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import {
  createTenorDraft,
  reviewTenorDraft,
  type TenorDecision,
  type TenorDraftRecord,
  type TenorDraftRequest,
} from "../../lib/tenor-api";

const tenorSchema = z.object({
  fall_id: z.string().trim().min(1, "Fall-ID ist erforderlich").max(200),
  schuldner: z.string().trim().min(1, "Schuldner ist erforderlich").max(500),
  fundstelle: z.string().trim().url("Bitte eine vollständige HTTP(S)-URL angeben").max(2048),
  beschreibung: z.string().trim().min(1, "Beschreibung ist erforderlich").max(4000),
  rechtsgrundlagen: z.string().trim().min(1, "Mindestens eine belegte Rechtsgrundlage angeben"),
});

type FormValues = z.infer<typeof tenorSchema>;
type FormErrors = Partial<Record<keyof FormValues, string>>;

const initialValues: FormValues = {
  fall_id: "",
  schuldner: "",
  fundstelle: "",
  beschreibung: "",
  rechtsgrundlagen: "§ 5 UWG\n§ 8 Abs. 1 UWG",
};

const fieldClass =
  "w-full border border-border bg-background px-3 py-2.5 font-serif text-sm text-foreground outline-none transition-colors focus:border-foreground";
const labelClass =
  "block text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground";

const decisionLabels: Record<TenorDecision, string> = {
  freigegeben: "Freigegeben",
  abgelehnt: "Abgelehnt",
  weitere_pruefung: "Weitere Prüfung",
};

function splitLegalBases(value: string) {
  return value
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toPayload(values: FormValues): TenorDraftRequest {
  return {
    fall_id: values.fall_id,
    schuldner: values.schuldner,
    fundstelle: values.fundstelle,
    beschreibung: values.beschreibung,
    rechtsgrundlagen: splitLegalBases(values.rechtsgrundlagen),
  };
}

export function MaskTenorView() {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [errors, setErrors] = useState<FormErrors>({});
  const [record, setRecord] = useState<TenorDraftRecord | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reviewing, setReviewing] = useState<TenorDecision | null>(null);

  const set =
    (key: keyof FormValues) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setValues((current) => ({ ...current, [key]: event.target.value }));
    };

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const parsed = tenorSchema.safeParse(values);
    if (!parsed.success) {
      const next: FormErrors = {};
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0]) as keyof FormValues;
        if (!next[key]) next[key] = issue.message;
      }
      setErrors(next);
      return;
    }

    const payload = toPayload(parsed.data);
    if (!payload.rechtsgrundlagen.length) {
      setErrors({ rechtsgrundlagen: "Mindestens eine belegte Rechtsgrundlage angeben" });
      return;
    }

    setErrors({});
    setSubmitError(null);
    setRecord(null);
    setSubmitting(true);
    try {
      setRecord(await createTenorDraft(payload));
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "Der Entwurf konnte nicht erzeugt werden.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function decide(decision: TenorDecision) {
    if (!record) return;
    setReviewing(decision);
    setSubmitError(null);
    try {
      setRecord(await reviewTenorDraft(record.draft_id, decision));
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : "Die Entscheidung konnte nicht gespeichert werden.",
      );
    } finally {
      setReviewing(null);
    }
  }

  function reset() {
    setValues(initialValues);
    setErrors({});
    setRecord(null);
    setSubmitError(null);
  }

  return (
    <div className="min-h-screen px-6 py-10 sm:px-10 lg:px-14">
      <div className="mx-auto max-w-6xl">
        {submitError && (
          <div className="mb-8 flex gap-3 border border-danger bg-danger/10 px-4 py-3" role="alert">
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
            <p className="text-sm">{submitError}</p>
          </div>
        )}

        {record ? (
          <section aria-live="polite" className="mx-auto w-full max-w-5xl">
            <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-3">
              <div>
                <span className="text-xs text-muted-foreground">02</span>
                <h2 className="mt-1 text-xl">Entwurf & Abgrenzung</h2>
              </div>
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => setRecord(null)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Sachverhalt bearbeiten
                </button>
                <button
                  type="button"
                  onClick={reset}
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <RotateCcw className="size-3.5" /> Neu beginnen
                </button>
              </div>
            </div>
            <DraftResult record={record} reviewing={reviewing} onDecision={decide} />
          </section>
        ) : (
          <form onSubmit={onSubmit} noValidate className="mx-auto w-full max-w-3xl">
            <div className="flex items-end justify-between border-b border-border pb-3">
              <div>
                <span className="text-xs text-muted-foreground">01</span>
                <h2 className="mt-1 text-xl">Sachverhalt</h2>
              </div>
              {(record || values.fall_id) && (
                <button
                  type="button"
                  onClick={reset}
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <RotateCcw className="size-3.5" /> Neu beginnen
                </button>
              )}
            </div>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <Field label="Fall-ID" error={errors.fall_id}>
                <input
                  className={fieldClass}
                  value={values.fall_id}
                  onChange={set("fall_id")}
                  placeholder="VZ-2026-0417"
                />
              </Field>
              <Field label="Schuldner" error={errors.schuldner}>
                <input
                  className={fieldClass}
                  value={values.schuldner}
                  onChange={set("schuldner")}
                  placeholder="Beispiel GmbH"
                />
              </Field>
              <Field label="Fundstelle" error={errors.fundstelle} full>
                <input
                  type="url"
                  className={fieldClass}
                  value={values.fundstelle}
                  onChange={set("fundstelle")}
                  placeholder="https://example.com/angebote"
                />
              </Field>
              <Field label="Festgestellter Verstoß" error={errors.beschreibung} full>
                <textarea
                  rows={6}
                  className={fieldClass}
                  value={values.beschreibung}
                  onChange={set("beschreibung")}
                  placeholder="Welche konkrete geschäftliche Praxis wurde festgestellt?"
                />
              </Field>
              <Field
                label="Belegte Rechtsgrundlagen (eine pro Zeile)"
                error={errors.rechtsgrundlagen}
                full
              >
                <textarea
                  rows={3}
                  className={fieldClass}
                  value={values.rechtsgrundlagen}
                  onChange={set("rechtsgrundlagen")}
                />
              </Field>
            </div>

            <div className="mt-7 border-t border-border pt-5">
              <p className="text-xs text-muted-foreground">
                Nur die hier belegten Rechtsgrundlagen dürfen in den Entwurf übernommen werden.
              </p>
              <button
                type="submit"
                disabled={submitting}
                className="mt-4 flex w-full items-center justify-center gap-2 bg-primary px-6 py-3 text-primary-foreground disabled:cursor-wait disabled:opacity-60"
              >
                {submitting && <LoaderCircle className="size-4 animate-spin" />}
                {submitting ? "Entwurf wird erstellt …" : "Prüfentwurf erstellen"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function DraftResult({
  record,
  reviewing,
  onDecision,
}: {
  record: TenorDraftRecord;
  reviewing: TenorDecision | null;
  onDecision: (decision: TenorDecision) => void;
}) {
  const decision = record.decision;
  return (
    <div className="mt-6 border border-foreground">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/50 px-5 py-4">
        <div>
          <span className="text-xs text-muted-foreground">{record.mode.replaceAll("_", " ")}</span>
          <p className="mt-1 font-sans text-sm font-semibold">{record.draft.fall_id}</p>
        </div>
        <span
          className={`border px-3 py-1.5 text-xs ${
            decision === "freigegeben"
              ? "border-success text-success"
              : decision === "abgelehnt"
                ? "border-danger text-danger"
                : "border-foreground text-foreground"
          }`}
        >
          {decision ? decisionLabels[decision] : "Menschliche Prüfung offen"}
        </span>
      </div>

      <div className="space-y-10 px-6 py-8 sm:px-10 lg:px-14">
        <ResultSection title="Tenorentwurf">
          <p className="max-w-4xl font-serif text-lg leading-8 text-foreground">
            {record.draft.entwurf}
          </p>
        </ResultSection>
        <ResultSection title="Charakteristischer Kern">
          <p className="text-sm text-muted-foreground">{record.draft.charakteristischer_kern}</p>
        </ResultSection>
        <ResultList title="Kerngleich umfasst" items={record.draft.kerngleich_umfasst} />
        <ResultList title="Nicht umfasst" items={record.draft.nicht_umfasst} emphasized />
        <ResultList title="Rechtsgrundlagen" items={record.draft.rechtsgrundlagen} />
        {record.draft.offene_fragen.length > 0 && (
          <ResultList title="Offene Fragen" items={record.draft.offene_fragen} />
        )}
      </div>

      <div className="border-t border-foreground px-5 py-5">
        <span className="text-xs text-muted-foreground">03 · Menschlich entscheiden</span>
        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <ReviewButton
            label="Freigeben"
            decision="freigegeben"
            active={decision === "freigegeben"}
            reviewing={reviewing}
            onDecision={onDecision}
            primary
          />
          <ReviewButton
            label="Weitere Prüfung"
            decision="weitere_pruefung"
            active={decision === "weitere_pruefung"}
            reviewing={reviewing}
            onDecision={onDecision}
          />
          <ReviewButton
            label="Ablehnen"
            decision="abgelehnt"
            active={decision === "abgelehnt"}
            reviewing={reviewing}
            onDecision={onDecision}
          />
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          {decision
            ? `Entscheidung gespeichert${record.decided_at ? ` · ${new Date(record.decided_at).toLocaleString("de-DE")}` : ""}.`
            : "Der Entwurf ist noch nicht für das Monitoring aktiviert."}
        </p>
      </div>
    </div>
  );
}

function ReviewButton({
  label,
  decision,
  active,
  reviewing,
  onDecision,
  primary = false,
}: {
  label: string;
  decision: TenorDecision;
  active: boolean;
  reviewing: TenorDecision | null;
  onDecision: (decision: TenorDecision) => void;
  primary?: boolean;
}) {
  const pending = reviewing === decision;
  return (
    <button
      type="button"
      disabled={reviewing !== null}
      onClick={() => onDecision(decision)}
      className={`flex items-center justify-center gap-2 border px-3 py-2.5 text-xs disabled:cursor-wait disabled:opacity-60 ${
        primary ? "border-foreground bg-foreground text-background" : "border-border bg-background"
      }`}
    >
      {pending ? (
        <LoaderCircle className="size-3.5 animate-spin" />
      ) : active ? (
        <Check className="size-3.5" />
      ) : null}
      {label}
    </button>
  );
}

function ResultSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function ResultList({
  title,
  items,
  emphasized = false,
}: {
  title: string;
  items: string[];
  emphasized?: boolean;
}) {
  return (
    <section className={emphasized ? "border-l-2 border-foreground pl-4" : undefined}>
      <h3 className="mb-2 text-xs text-muted-foreground">{title}</h3>
      {items.length ? (
        <ul className="space-y-2 font-serif text-sm text-muted-foreground">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden="true">—</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Keine Angabe im Entwurf.</p>
      )}
    </section>
  );
}

function Field({
  label,
  error,
  full = false,
  children,
}: {
  label: string;
  error: string | undefined;
  full?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={full ? "sm:col-span-2" : undefined}>
      <span className={labelClass}>{label}</span>
      <span className="mt-1.5 block">{children}</span>
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}
