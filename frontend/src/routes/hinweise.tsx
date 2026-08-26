import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  HelpCircle,
  LoaderCircle,
  Scale,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useCaseViews } from "../data/caseViews";
import type { Tone } from "../data/lottoDemoCases";
import {
  getMonitoringRun,
  monitoringCasesQueryKey,
  reviewMonitoringCase,
  startMonitoringRun,
  type EngineAssessment,
} from "../lib/monitoring-api";
import {
  claimMonitoringChangeNotification,
  EVIDENCE_COMPARISON_NOTIFICATION_KEY,
  EVIDENCE_COMPARISON_NOTIFICATION_QUERY,
  parseStoredEvidenceComparisonNotification,
  type MonitoringChangeNotification,
} from "../lib/monitoring-notifications";

export const Route = createFileRoute("/hinweise")({
  head: () => ({
    meta: [
      { title: "Hinweise – Muc Legal Monitoring" },
      {
        name: "description",
        content:
          "Aktuelle Hinweise aus dem Monitoring als Benachrichtigungen – mit Zeitstempel, Kontext und vollständiger Beweisführung.",
      },
      { property: "og:title", content: "Hinweise – Muc Legal Monitoring" },
      {
        property: "og:description",
        content:
          "Aktuelle Hinweise aus dem Monitoring als Benachrichtigungen – mit Zeitstempel, Kontext und vollständiger Beweisführung.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: HinweisePage,
});

const toneIcon: Record<Tone, typeof Scale> = {
  danger: AlertTriangle,
  success: CheckCircle2,
  warning: HelpCircle,
  neutral: Clock,
};

const toneColor: Record<Tone, string> = {
  danger: "text-danger bg-danger/10",
  success: "text-success bg-success/10",
  warning: "text-warning bg-warning/10",
  neutral: "text-muted-foreground bg-muted",
};

const toneLabel: Record<Tone, string> = {
  danger: "Kritisch",
  success: "In Ordnung",
  warning: "Prüfung nötig",
  neutral: "Ausstehend",
};

const enginePresentation: Record<
  EngineAssessment["classification"],
  {
    label: string;
    summary: string;
    icon: typeof Scale;
    className: string;
    iconClassName: string;
  }
> = {
  kerngleich: {
    label: "Kerngleich",
    summary: "Die Engine stuft den geprüften Stand als kerngleich ein.",
    icon: AlertTriangle,
    className: "border-danger/40 bg-danger/5",
    iconClassName: "bg-danger/10 text-danger",
  },
  nicht_kerngleich: {
    label: "Nicht kerngleich",
    summary: "Die Engine stuft den geprüften Stand als nicht kerngleich ein.",
    icon: CheckCircle2,
    className: "border-success/40 bg-success/5",
    iconClassName: "bg-success/10 text-success",
  },
  unklar: {
    label: "Nicht eindeutig",
    summary: "Die Engine konnte die Kerngleichheit nicht abschließend bestimmen.",
    icon: HelpCircle,
    className: "border-warning/50 bg-warning/5",
    iconClassName: "bg-warning/10 text-warning",
  },
  noch_nicht_bewertet: {
    label: "Noch nicht bewertet",
    summary: "Für den aktuellen Stand liegt noch kein Engine-Befund vor.",
    icon: Clock,
    className: "border-border bg-muted/50",
    iconClassName: "bg-background text-muted-foreground",
  },
};

const notificationToneClass: Record<MonitoringChangeNotification["tone"], string> = {
  danger: "border-danger/40 text-danger",
  success: "border-success/40 text-success",
  warning: "border-warning/50 text-warning",
};

const MONITORING_POLL_INTERVAL_MS = 500;
// The backend domain scan may legitimately use its full ten-minute budget.
// Keep the UI attached for one additional minute so artifact creation can finish.
const MONITORING_POLL_ATTEMPTS = (11 * 60 * 1_000) / MONITORING_POLL_INTERVAL_MS;

const monitoringResultLabel: Record<string, string> = {
  referenzzustand_dokumentiert: "Referenzzustand dokumentiert.",
  unveraendert_fortbestehend: "Ergebnis: kerngleich – die Verletzungsform besteht fort.",
  beseitigt: "Ergebnis: nicht kerngleich – die beanstandete Verletzungsform wurde beseitigt.",
  kerngleich_wiederaufgetreten: "Ergebnis: kerngleich – die Verletzungsform ist wiederaufgetreten.",
  neuer_sachverhalt: "Ergebnis: nicht kerngleich – neuer Sachverhalt.",
  unsicher: "Ergebnis: nicht eindeutig – menschliche Prüfung erforderlich.",
  pruefung_unvollstaendig: "Ergebnis: Prüfung unvollständig – menschliche Prüfung erforderlich.",
  failed: "Die Kerngleichheitsprüfung ist fehlgeschlagen.",
};

function relativeTime(iso: string | null) {
  if (!iso) return "geplant";
  const now = Date.now();
  const mins = Math.max(1, Math.round((now - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `vor ${mins} Min.`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  return `vor ${Math.round(hours / 24)} Tg.`;
}

function formatDateTime(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

function HinweisePage() {
  const { cases } = useCaseViews();
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<string | null>(null);
  const [actionState, setActionState] = useState<Record<string, string>>({});
  const [runningCaseIds, setRunningCaseIds] = useState<Set<string>>(() => new Set());
  const notifiedRunIds = useRef(new Set<string>());
  const pendingEvidenceId = useRef<string | null>(null);

  const openEvidence = useCallback((caseId: string) => {
    pendingEvidenceId.current = caseId;
    setOpenId(caseId);
  }, []);

  useEffect(() => {
    const caseId = pendingEvidenceId.current;
    if (!caseId || openId !== caseId) return;
    const target =
      document.getElementById(`engine-assessment-${caseId}`) ??
      document.getElementById(`differenz-${caseId}`) ??
      document.getElementById(`beweisfuehrung-${caseId}`);
    if (!target) return;
    pendingEvidenceId.current = null;
    window.requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.focus({ preventScroll: true });
    });
  }, [cases, openId]);

  const showChangeNotification = useCallback(
    (runId: string, caseId: string, fallId: string, notification: MonitoringChangeNotification) => {
      toast.custom(
        (toastId) => {
          const Icon = notification.tone === "success" ? CheckCircle2 : AlertTriangle;
          return (
            <div
              className={`flex w-[min(92vw,34rem)] overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-xl ${notificationToneClass[notification.tone]}`}
              role="status"
            >
              <button
                type="button"
                onClick={() => {
                  toast.dismiss(toastId);
                  openEvidence(caseId);
                }}
                className="group flex min-w-0 flex-1 items-start gap-3 p-4 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                aria-label={`${notification.title} in Fall ${fallId}. Hinweis öffnen.`}
              >
                <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-current/10">
                  <Icon className="size-5" strokeWidth={1.75} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-medium text-muted-foreground">
                    Fall {fallId}
                  </span>
                  <span className="mt-0.5 block font-semibold text-card-foreground">
                    {notification.title}
                  </span>
                  <span className="mt-1 block text-sm text-muted-foreground">
                    {notification.description}
                  </span>
                </span>
                <ChevronRight
                  className="mt-2 size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                  strokeWidth={1.75}
                />
              </button>
              <button
                type="button"
                onClick={() => toast.dismiss(toastId)}
                className="grid w-11 shrink-0 place-items-center border-l border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                aria-label="Benachrichtigung schließen"
              >
                <X className="size-4" strokeWidth={1.75} />
              </button>
            </div>
          );
        },
        { duration: Infinity, id: `monitoring-change-${runId}` },
      );
    },
    [openEvidence],
  );

  useEffect(() => {
    const currentUrl = new URL(window.location.href);
    const queryHandoff = currentUrl.searchParams.get(EVIDENCE_COMPARISON_NOTIFICATION_QUERY);
    const raw = window.sessionStorage.getItem(EVIDENCE_COMPARISON_NOTIFICATION_KEY) ?? queryHandoff;
    const stored = parseStoredEvidenceComparisonNotification(raw);
    if (raw) window.sessionStorage.removeItem(EVIDENCE_COMPARISON_NOTIFICATION_KEY);
    if (queryHandoff) {
      currentUrl.searchParams.delete(EVIDENCE_COMPARISON_NOTIFICATION_QUERY);
      window.history.replaceState(window.history.state, "", currentUrl);
    }
    if (!stored) return;
    openEvidence(stored.case_id);
  }, [openEvidence]);

  async function decide(caseId: string, decision: "freigegeben" | "abgelehnt") {
    setActionState((state) => ({ ...state, [caseId]: "Entscheidung wird gespeichert …" }));
    try {
      await reviewMonitoringCase(caseId, decision);
      await queryClient.invalidateQueries({ queryKey: monitoringCasesQueryKey });
      setActionState((state) => ({
        ...state,
        [caseId]: decision === "freigegeben" ? "Fall wurde freigegeben." : "Fall wurde abgelehnt.",
      }));
    } catch (error) {
      setActionState((state) => ({
        ...state,
        [caseId]: error instanceof Error ? error.message : "Entscheidung fehlgeschlagen.",
      }));
    }
  }

  async function startRun(caseId: string, fallId: string) {
    setRunningCaseIds((current) => new Set(current).add(caseId));
    setActionState((state) => ({ ...state, [caseId]: "Monitoringlauf wird gestartet …" }));
    try {
      let run = await startMonitoringRun(caseId);
      setActionState((state) => ({ ...state, [caseId]: run.message }));
      const terminal = new Set([
        "referenzzustand_dokumentiert",
        "unveraendert_fortbestehend",
        "beseitigt",
        "kerngleich_wiederaufgetreten",
        "neuer_sachverhalt",
        "unsicher",
        "pruefung_unvollstaendig",
        "failed",
      ]);
      for (
        let attempt = 0;
        attempt < MONITORING_POLL_ATTEMPTS && !terminal.has(run.status);
        attempt += 1
      ) {
        await new Promise((resolve) => window.setTimeout(resolve, MONITORING_POLL_INTERVAL_MS));
        run = await getMonitoringRun(run.run_id);
        setActionState((state) => ({ ...state, [caseId]: run.message }));
      }
      if (terminal.has(run.status)) {
        await queryClient.refetchQueries({ queryKey: monitoringCasesQueryKey, type: "active" });
        setActionState((state) => ({
          ...state,
          [caseId]: monitoringResultLabel[run.status] ?? run.message,
        }));
        openEvidence(caseId);
        const notification = claimMonitoringChangeNotification(
          run.status,
          run.run_id,
          notifiedRunIds.current,
        );
        if (notification) {
          showChangeNotification(run.run_id, caseId, fallId, notification);
        }
      } else {
        setActionState((state) => ({
          ...state,
          [caseId]: "Der Lauf arbeitet serverseitig weiter. Bitte die Hinweise später neu laden.",
        }));
      }
    } catch (error) {
      setActionState((state) => ({
        ...state,
        [caseId]: error instanceof Error ? error.message : "Monitoringlauf fehlgeschlagen.",
      }));
    } finally {
      setRunningCaseIds((current) => {
        const next = new Set(current);
        next.delete(caseId);
        return next;
      });
    }
  }

  return (
    <div className="min-h-screen bg-background px-6 py-10 sm:px-10">
      <div className="mx-auto max-w-6xl">
        <ul className="space-y-4">
          {cases.map((c) => {
            const Icon = toneIcon[c.tone];
            const isOpen = openId === c.case_id;
            const assessment = enginePresentation[c.engineAssessment.classification];
            const AssessmentIcon = assessment.icon;
            const runPending = runningCaseIds.has(c.case_id);
            return (
              <li
                key={c.case_id}
                className={`mx-auto w-full transition-[max-width] duration-300 ${
                  isOpen ? "max-w-6xl" : "max-w-3xl"
                }`}
              >
                <article
                  className={`group rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md ${
                    isOpen ? "ring-1 ring-ring" : ""
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setOpenId(isOpen ? null : c.case_id)}
                    className="w-full text-left"
                    aria-expanded={isOpen}
                  >
                    <div className="flex items-start gap-4">
                      <span
                        className={`mt-0.5 grid size-10 shrink-0 place-items-center rounded-full ${toneColor[c.tone]}`}
                      >
                        <Icon className="size-5" strokeWidth={1.75} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-medium text-muted-foreground">
                              {toneLabel[c.tone]} · {relativeTime(c.found_at)}
                            </p>
                            <p className="mt-0.5 text-base font-semibold text-card-foreground">
                              {c.title}
                            </p>
                          </div>
                          <ChevronDown
                            className={`size-5 shrink-0 text-muted-foreground transition-transform duration-200 ${
                              isOpen ? "rotate-180" : ""
                            }`}
                          />
                        </div>
                        <p className="mt-1 text-sm text-card-foreground">{c.status}</p>
                        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                          {c.explanation}
                        </p>
                        <p className="mt-3 text-xs text-muted-foreground">
                          {formatDateTime(c.found_at)}
                        </p>
                      </div>
                    </div>
                  </button>

                  {isOpen && (
                    <div className="mt-5 border-t border-border pt-4">
                      <section
                        id={`engine-assessment-${c.case_id}`}
                        className={`scroll-mt-8 rounded-xl border p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${assessment.className}`}
                        aria-labelledby={`engine-assessment-title-${c.case_id}`}
                        tabIndex={-1}
                      >
                        <div className="flex items-start gap-4">
                          <span
                            className={`grid size-11 shrink-0 place-items-center rounded-full ${assessment.iconClassName}`}
                          >
                            <AssessmentIcon className="size-6" strokeWidth={1.8} />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                              Kerngleichheits-Engine
                            </p>
                            <h2
                              id={`engine-assessment-title-${c.case_id}`}
                              className="mt-1 text-2xl font-semibold tracking-tight text-foreground"
                            >
                              {assessment.label}
                            </h2>
                            <p className="mt-1 text-sm font-medium text-foreground">
                              {assessment.summary}
                            </p>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                              {c.engineAssessment.reasoning}
                            </p>
                            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
                              {c.engineAssessment.confidence !== null && (
                                <span>
                                  Sicherheit: {Math.round(c.engineAssessment.confidence * 100)} %
                                </span>
                              )}
                              {c.engineAssessment.assessed_at && (
                                <span>
                                  Bewertet: {formatDateTime(c.engineAssessment.assessed_at)}
                                </span>
                              )}
                              {c.engineAssessment.classification !== "noch_nicht_bewertet" &&
                                c.engineAssessment.freigabe_durch_mensch === null && (
                                  <span>Engine-Vorprüfung · menschliche Freigabe offen</span>
                                )}
                            </div>
                            {c.source === "backend" &&
                              c.decision === "freigegeben" &&
                              c.engineAssessment.classification === "noch_nicht_bewertet" && (
                                <button
                                  type="button"
                                  onClick={() => void startRun(c.case_id, c.fall_id)}
                                  disabled={runPending}
                                  aria-busy={runPending}
                                  className="mt-4 inline-flex min-w-56 items-center justify-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-70"
                                >
                                  {runPending && (
                                    <LoaderCircle
                                      className="size-4 animate-spin"
                                      aria-hidden="true"
                                    />
                                  )}
                                  {runPending
                                    ? "Kerngleichheit wird geprüft …"
                                    : "Kerngleichheit prüfen"}
                                </button>
                              )}
                            {actionState[c.case_id] && (
                              <p
                                className="mt-3 text-sm font-medium text-foreground"
                                role="status"
                                aria-live="polite"
                              >
                                {actionState[c.case_id]}
                              </p>
                            )}
                          </div>
                        </div>
                      </section>

                      <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-5">
                        <p className="text-xs font-medium tracking-wider text-primary uppercase">
                          Tenor / Formulierungsvorschlag
                        </p>
                        <p className="mt-2 font-serif text-base leading-relaxed text-foreground">
                          {c.tenor.formulierung}
                        </p>
                        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                          {c.tenor.hinweis}
                        </p>
                      </div>

                      <div className="mt-4 grid gap-4 sm:grid-cols-2">
                        <div className="rounded-xl bg-muted p-4">
                          <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                            Kontext
                          </p>
                          <p className="mt-1 text-sm text-foreground">{c.secondary}</p>
                        </div>
                        <div className="rounded-xl bg-muted p-4">
                          <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                            Details
                          </p>
                          <ul className="mt-1 space-y-1 text-sm text-foreground">
                            <li>
                              <span className="text-muted-foreground">Fall-ID:</span> {c.fall_id}
                            </li>
                            <li>
                              <span className="text-muted-foreground">Domain:</span> {c.domain}
                            </li>
                            {c.confidence !== null && (
                              <li>
                                <span className="text-muted-foreground">Confidence:</span>{" "}
                                {Math.round(c.confidence * 100)} %
                              </li>
                            )}
                          </ul>
                        </div>
                      </div>

                      <div
                        id={`beweisfuehrung-${c.case_id}`}
                        className="mt-4 scroll-mt-8 rounded-xl border border-border bg-background p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        tabIndex={-1}
                        aria-label={`Beweisführung für Fall ${c.fall_id}`}
                      >
                        <p className="font-serif text-lg tracking-tight text-foreground">
                          Beweisführung
                        </p>

                        {c.latestEvidenceComparison?.status === "technische_aenderung_erkannt" && (
                          <section
                            className="mt-4 rounded-xl border border-warning/40 bg-warning/5 p-4 sm:p-5"
                            aria-labelledby={`differenz-${c.case_id}`}
                            tabIndex={-1}
                          >
                            <p
                              id={`differenz-${c.case_id}`}
                              className="text-xs font-semibold tracking-wider text-warning uppercase"
                            >
                              Differenz erkannt
                            </p>
                            <p className="mt-2 text-sm leading-relaxed text-foreground">
                              {c.latestEvidenceComparison.difference_summary ??
                                "Die gespeicherten Text-Prüfwerte unterscheiden sich."}
                            </p>
                            <div className="mt-4 space-y-4">
                              {(c.latestEvidenceComparison.differences ?? []).map(
                                (difference, index) => (
                                  <article
                                    key={`${difference.change_type}-${index}`}
                                    className="overflow-hidden rounded-lg border border-border bg-card"
                                  >
                                    <p className="border-b border-border px-5 py-3 text-xs font-medium text-muted-foreground">
                                      {difference.label} · Ausschnitt {index + 1}
                                    </p>
                                    <div className="grid gap-px bg-border xl:grid-cols-2">
                                      <div className="min-w-0 bg-danger/5 p-5">
                                        <p className="text-xs font-semibold tracking-wider text-danger uppercase">
                                          Vorher · Webarchiv
                                        </p>
                                        <p className="mt-3 break-words whitespace-pre-wrap text-[15px] leading-7 hyphens-auto text-foreground">
                                          {difference.before || "— Kein entsprechender Text —"}
                                        </p>
                                      </div>
                                      <div className="min-w-0 bg-success/5 p-5">
                                        <p className="text-xs font-semibold tracking-wider text-success uppercase">
                                          Aktueller Stand
                                        </p>
                                        <p className="mt-3 break-words whitespace-pre-wrap text-[15px] leading-7 hyphens-auto text-foreground">
                                          {difference.after || "— Text entfernt —"}
                                        </p>
                                      </div>
                                    </div>
                                  </article>
                                ),
                              )}
                            </div>
                            <div className="mt-4 rounded-lg bg-background p-4">
                              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                                Was wurde gemacht?
                              </p>
                              <ol className="mt-2 space-y-1 text-sm leading-6 text-foreground">
                                <li>
                                  1. Der manuell zugeordnete Webarchiv-Ausgangsbeweis wurde geladen.
                                </li>
                                <li>
                                  2. Beide SHA-256-Manifeste wurden vor dem Vergleich geprüft.
                                </li>
                                <li>
                                  3. Der normalisierte Text der Rolle „
                                  {c.latestEvidenceComparison.compared_role}“ wurde wortbasiert
                                  verglichen.
                                </li>
                                <li>
                                  4. Die abweichenden Ausschnitte wurden rein technisch
                                  gegenübergestellt.
                                </li>
                              </ol>
                              <p className="mt-3 text-xs leading-5 text-muted-foreground">
                                Keine juristische Bewertung: Die Anzeige sagt nichts über
                                Kerngleichheit oder einen Rechtsverstoß aus.
                              </p>
                            </div>
                          </section>
                        )}

                        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                          <div>
                            <dt className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                              Fundstelle
                            </dt>
                            <dd className="mt-1 text-sm text-foreground">
                              {c.evidence.fundstelle}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                              Erfassung
                            </dt>
                            <dd className="mt-1 text-sm text-foreground">{c.evidence.erfassung}</dd>
                          </div>
                        </dl>

                        <p className="mt-5 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                          Beweiskette
                        </p>
                        <ol className="mt-2 space-y-2">
                          {c.evidence.kette.map((step, i) => (
                            <li key={step} className="flex gap-3 text-sm text-foreground">
                              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                                {i + 1}
                              </span>
                              <span className="leading-relaxed">{step}</span>
                            </li>
                          ))}
                        </ol>

                        <div className="mt-5 grid gap-4 sm:grid-cols-2">
                          <div>
                            <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                              Rechtliche Einordnung
                            </p>
                            <p className="mt-1 text-sm leading-relaxed text-foreground">
                              {c.evidence.einordnung}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                              Offene Punkte
                            </p>
                            <p className="mt-1 text-sm leading-relaxed text-foreground">
                              {c.evidence.offen}
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 flex items-center gap-3">
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
                        >
                          Zielseite öffnen
                        </a>
                        <span className="truncate text-xs text-muted-foreground">{c.url}</span>
                      </div>

                      {c.source === "backend" && (
                        <div className="mt-4 border-t border-border pt-4">
                          <p className="text-xs text-muted-foreground">Menschliche Entscheidung</p>
                          <div className="mt-3 flex flex-wrap gap-3">
                            {c.decision === "weitere_pruefung" && (
                              <>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void decide(c.case_id, "freigegeben");
                                  }}
                                  className="bg-primary px-4 py-2 text-sm text-primary-foreground"
                                >
                                  Fall freigeben
                                </button>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void decide(c.case_id, "abgelehnt");
                                  }}
                                  className="border border-border px-4 py-2 text-sm text-foreground"
                                >
                                  Ablehnen
                                </button>
                              </>
                            )}
                            {c.decision === "freigegeben" && (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void startRun(c.case_id, c.fall_id);
                                }}
                                disabled={runPending}
                                aria-busy={runPending}
                                className="inline-flex items-center gap-2 bg-primary px-4 py-2 text-sm text-primary-foreground disabled:cursor-wait disabled:opacity-70"
                              >
                                {runPending && (
                                  <LoaderCircle
                                    className="size-4 animate-spin"
                                    aria-hidden="true"
                                  />
                                )}
                                {runPending ? "Monitoring läuft …" : "Monitoring starten"}
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
