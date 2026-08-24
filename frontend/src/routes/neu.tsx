import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";

import {
  createMonitoringCase,
  monitoringCasesQueryKey,
  type MonitoringCaseCreate,
} from "../lib/monitoring-api";
import { splitAlternativeLabels, splitLineValues } from "../lib/monitoring-form";

export const Route = createFileRoute("/neu")({
  head: () => ({
    meta: [
      { title: "Neu hinzufügen – Muc Legal Monitoring" },
      { name: "description", content: "Einen neuen Fall erfassen und zur Prüfung anlegen." },
      { property: "og:title", content: "Neu hinzufügen – Muc Legal Monitoring" },
      { property: "og:description", content: "Einen neuen Fall erfassen und zur Prüfung anlegen." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: NeuPage,
});

const caseSchema = z
  .object({
    fall_id: z.string().trim().min(1, "Fall-ID ist erforderlich").max(200),
    domain: z.string().trim().min(1, "Domain ist erforderlich").max(253),
    source_url: z.string().trim().url("Bitte eine vollständige HTTP(S)-URL angeben").max(2048),
    violation_type: z.enum(["klausel", "element"]),
    description: z.string().trim().min(1, "Beschreibung ist erforderlich").max(4000),
    tenor_element: z.string().trim().min(1, "Tenor ist erforderlich").max(8000),
    monitoring_target: z.string().trim().min(1, "Monitoringziel ist erforderlich").max(4000),
    relevant_page_types: z.string().trim().min(1, "Mindestens ein Seitentyp ist erforderlich"),
    target_urls: z.string().max(12000),
    nicht_umfasst: z.string().max(8000),
    clause_text: z.string().max(12000),
    element_label: z.string().max(1000),
    element_labels: z.string().max(4000),
    element_function: z.string().max(2000),
    element_error: z.enum([
      "fehlt",
      "nicht_sichtbar",
      "nicht_leicht_zugaenglich",
      "falsches_ziel",
      "zusaetzliche_huerde",
    ]),
    allowed_subdomains: z.string().max(4000),
  })
  .superRefine((values, context) => {
    if (values.violation_type === "klausel" && !values.clause_text.trim()) {
      context.addIssue({
        code: "custom",
        path: ["clause_text"],
        message: "Beanstandeter Klauseltext ist erforderlich",
      });
    }
    if (values.violation_type === "element") {
      for (const key of ["element_label", "element_function"] as const) {
        if (!values[key].trim())
          context.addIssue({
            code: "custom",
            path: [key],
            message: "Angabe ist für ein Seitenelement erforderlich",
          });
      }
    }
  });

type FormValues = z.infer<typeof caseSchema>;
type FormErrors = Partial<Record<keyof FormValues, string>>;

const initialValues: FormValues = {
  fall_id: "",
  domain: "",
  source_url: "",
  violation_type: "klausel",
  description: "",
  tenor_element: "",
  monitoring_target: "",
  relevant_page_types: "Startseite\nAGB\nDatenschutz",
  target_urls: "",
  nicht_umfasst: "",
  clause_text: "",
  element_label: "",
  element_labels: "",
  element_function: "",
  element_error: "fehlt",
  allowed_subdomains: "",
};

const fieldClass =
  "w-full border border-border bg-background px-3 py-2 font-serif text-sm text-foreground outline-none transition-colors focus:border-foreground";
const labelClass =
  "block text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground";

function toPayload(values: FormValues): MonitoringCaseCreate {
  const clause = values.violation_type === "klausel";
  return {
    fall_id: values.fall_id,
    domain: values.domain,
    source_url: values.source_url,
    violation_type: values.violation_type,
    description: values.description,
    tenor_element: values.tenor_element,
    monitoring_target: values.monitoring_target,
    relevant_page_types: splitLineValues(values.relevant_page_types),
    target_urls: splitLineValues(values.target_urls),
    nicht_umfasst: splitLineValues(values.nicht_umfasst),
    clause_text: clause ? values.clause_text : null,
    element_label: clause ? null : values.element_label,
    element_labels: clause
      ? []
      : splitAlternativeLabels(values.element_labels || values.element_label),
    element_function: clause ? null : values.element_function,
    element_error: clause ? null : values.element_error,
    allowed_subdomains: splitLineValues(values.allowed_subdomains),
  };
}

function NeuPage() {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<FormValues>(initialValues);
  const [errors, setErrors] = useState<FormErrors>({});
  const [saved, setSaved] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const set =
    (key: keyof FormValues) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      const value = event.target.value;
      setValues((current) => ({ ...current, [key]: value }));
    };

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const result = caseSchema.safeParse(values);
    if (!result.success) {
      const next: FormErrors = {};
      for (const issue of result.error.issues) {
        const key = String(issue.path[0]) as keyof FormValues;
        if (!next[key]) next[key] = issue.message;
      }
      setErrors(next);
      setSaved(null);
      return;
    }

    setErrors({});
    setSaved(null);
    setSubmitError(null);
    setSubmitting(true);
    try {
      const created = await createMonitoringCase(toPayload(result.data));
      await queryClient.invalidateQueries({ queryKey: monitoringCasesQueryKey });
      setSaved(created.fall_id);
      setValues(initialValues);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "Der Fall konnte nicht gespeichert werden.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-12">
      <h1 className="text-3xl">Neu hinzufügen</h1>
      <p className="mt-3 max-w-xl text-sm text-muted-foreground">
        Bekannten Erstverstoß und den freizugebenden Monitoringumfang erfassen.
      </p>

      {saved && (
        <div className="mt-6 border border-foreground bg-secondary px-4 py-3">
          <p className="font-serif text-sm">
            Fall <strong>{saved}</strong> wurde gespeichert und liegt zur menschlichen Prüfung
            bereit.
          </p>
        </div>
      )}
      {submitError && (
        <div className="mt-6 border border-danger bg-danger/10 px-4 py-3" role="alert">
          <p className="font-serif text-sm">{submitError}</p>
        </div>
      )}

      <form onSubmit={onSubmit} noValidate className="mt-10 space-y-12">
        <Section title="Stammdaten">
          <Field label="Fall-ID" error={errors.fall_id}>
            <input
              className={fieldClass}
              value={values.fall_id}
              onChange={set("fall_id")}
              placeholder="VZ-2026-0417"
            />
          </Field>
          <Field label="Domain" error={errors.domain}>
            <input
              className={fieldClass}
              value={values.domain}
              onChange={set("domain")}
              placeholder="example.com"
            />
          </Field>
          <Field label="Fundstelle / Ziel-URL" error={errors.source_url} full>
            <input
              className={fieldClass}
              value={values.source_url}
              onChange={set("source_url")}
              placeholder="https://example.com/angebote"
            />
          </Field>
          <Field label="Verstoßart" error={errors.violation_type}>
            <select
              className={fieldClass}
              value={values.violation_type}
              onChange={set("violation_type")}
            >
              <option value="klausel">Klausel</option>
              <option value="element">Seitenelement</option>
            </select>
          </Field>
          <Field label="Beschreibung des bekannten Erstverstoßes" error={errors.description} full>
            <textarea
              rows={4}
              className={fieldClass}
              value={values.description}
              onChange={set("description")}
              placeholder="Was wurde durch die Verbraucherzentrale bereits festgestellt?"
            />
          </Field>
        </Section>

        <Section title="Unterlassung & Prüfumfang">
          <Field label="Unterlassungstenor / erfasstes Element" error={errors.tenor_element} full>
            <textarea
              rows={5}
              className={fieldClass}
              value={values.tenor_element}
              onChange={set("tenor_element")}
              placeholder="Es wird untersagt, …"
            />
          </Field>
          <Field label="Monitoringziel" error={errors.monitoring_target} full>
            <textarea
              rows={3}
              className={fieldClass}
              value={values.monitoring_target}
              onChange={set("monitoring_target")}
              placeholder="Welche konkrete Praxis soll künftig geprüft werden?"
            />
          </Field>
          <Field
            label="Relevante Seitentypen (eine Angabe pro Zeile)"
            error={errors.relevant_page_types}
            full
          >
            <textarea
              rows={3}
              className={fieldClass}
              value={values.relevant_page_types}
              onChange={set("relevant_page_types")}
            />
          </Field>
          <Field
            label="Konkrete Prüf-URLs (optional, eine pro Zeile)"
            error={errors.target_urls}
            full
          >
            <textarea
              rows={3}
              className={fieldClass}
              value={values.target_urls}
              onChange={set("target_urls")}
              placeholder="https://example.com/checkout"
            />
          </Field>
          <Field
            label="Nicht umfasst (eine Abgrenzung pro Zeile)"
            error={errors.nicht_umfasst}
            full
          >
            <textarea
              rows={3}
              className={fieldClass}
              value={values.nicht_umfasst}
              onChange={set("nicht_umfasst")}
              placeholder="Echte befristete Aktion mit belegbarem Enddatum"
            />
          </Field>
        </Section>

        <Section title="Nachweisanlage">
          {values.violation_type === "klausel" ? (
            <Field label="Beanstandeter Klauselwortlaut" error={errors.clause_text} full>
              <textarea
                rows={6}
                className={fieldClass}
                value={values.clause_text}
                onChange={set("clause_text")}
                placeholder="Wortlaut der bereits beanstandeten Klausel"
              />
            </Field>
          ) : (
            <>
              <Field label="Bezeichnung des Elements" error={errors.element_label}>
                <input
                  className={fieldClass}
                  value={values.element_label}
                  onChange={set("element_label")}
                  placeholder="Widerrufsbelehrung"
                />
              </Field>
              <Field label="Alternative Bezeichnungen" error={errors.element_labels}>
                <input
                  className={fieldClass}
                  value={values.element_labels}
                  onChange={set("element_labels")}
                  placeholder="Widerruf, Rückgabe"
                />
              </Field>
              <Field label="Erwartete Funktion / Ziel" error={errors.element_function} full>
                <input
                  className={fieldClass}
                  value={values.element_function}
                  onChange={set("element_function")}
                  placeholder="/widerruf"
                />
              </Field>
              <Field label="Festgestellter Fehler" error={errors.element_error}>
                <select
                  className={fieldClass}
                  value={values.element_error}
                  onChange={set("element_error")}
                >
                  <option value="fehlt">Fehlt</option>
                  <option value="nicht_sichtbar">Nicht sichtbar</option>
                  <option value="nicht_leicht_zugaenglich">Nicht leicht zugänglich</option>
                  <option value="falsches_ziel">Falsches Ziel</option>
                  <option value="zusaetzliche_huerde">Zusätzliche Hürde</option>
                </select>
              </Field>
            </>
          )}
          <Field label="Erlaubte Subdomains (optional)" error={errors.allowed_subdomains} full>
            <textarea
              rows={2}
              className={fieldClass}
              value={values.allowed_subdomains}
              onChange={set("allowed_subdomains")}
              placeholder="shop.example.com"
            />
          </Field>
        </Section>

        <div className="flex items-center justify-between border-t border-border pt-6">
          <p className="text-xs text-muted-foreground">
            Der Fall startet erst nach menschlicher Freigabe.
          </p>
          <button
            type="submit"
            disabled={submitting}
            className="bg-primary px-6 py-3 text-sm text-primary-foreground disabled:cursor-wait disabled:opacity-60"
          >
            {submitting ? "Wird gespeichert …" : "Fall erfassen"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="border-b border-border pb-3 text-xl">{title}</h2>
      <div className="mt-6 grid gap-x-6 gap-y-5 sm:grid-cols-2">{children}</div>
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
