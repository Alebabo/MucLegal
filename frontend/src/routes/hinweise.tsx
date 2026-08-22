import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle, CheckCircle2, ChevronDown, Clock, HelpCircle, Scale } from "lucide-react";
import { useState } from "react";

import { lottoDemoCases, type Tone } from "../data/lottoDemoCases";

export const Route = createFileRoute("/hinweise")({
  head: () => ({
    meta: [
      { title: "Hinweise – MucLegal" },
      {
        name: "description",
        content:
          "Aktuelle Hinweise aus dem Monitoring als Benachrichtigungen – mit Zeitstempel, Kontext und vollständiger Beweisführung.",
      },
      { property: "og:title", content: "Hinweise – MucLegal" },
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

function relativeTime(iso: string | null) {
  if (!iso) return "geplant";
  const now = new Date("2026-08-21T15:29:00Z").getTime();
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
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-background px-6 py-10 sm:px-10">
      <div className="mx-auto max-w-3xl">
        <ul className="space-y-4">
          {lottoDemoCases.map((c) => {
            const Icon = toneIcon[c.tone];
            const isOpen = openId === c.case_id;
            return (
              <li key={c.case_id}>
                <button
                  type="button"
                  onClick={() => setOpenId(isOpen ? null : c.case_id)}
                  className="w-full text-left"
                  aria-expanded={isOpen}
                >
                  <article
                    className={`group rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md ${
                      isOpen ? "ring-1 ring-ring" : ""
                    }`}
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

                    {isOpen && (
                      <div className="mt-5 border-t border-border pt-4">
                        <div className="grid gap-4 sm:grid-cols-2">
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

                        <div className="mt-4 rounded-xl border border-border bg-background p-5">
                          <p className="font-serif text-lg tracking-tight text-foreground">
                            Beweisführung
                          </p>

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
                              <dd className="mt-1 text-sm text-foreground">
                                {c.evidence.erfassung}
                              </dd>
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
                      </div>
                    )}
                  </article>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
