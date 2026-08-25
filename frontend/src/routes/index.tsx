import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowRight,
  Bell,
  CircleHelp,
  Clock3,
  Plus,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useCaseViews, type CaseView } from "../data/caseViews";
import type { Tone } from "../data/lottoDemoCases";

export const Route = createFileRoute("/")({
  loader: () => ({ now: Date.now() }),
  head: () => ({
    meta: [
      { title: "Fallmonitor – Muc Legal Monitoring" },
      {
        name: "description",
        content: "Übersicht über Fälle und Monitoringläufe zu Unterlassungserklärungen.",
      },
      { property: "og:title", content: "Fallmonitor – Muc Legal Monitoring" },
      {
        property: "og:description",
        content: "Übersicht über Fälle und Monitoringläufe zu Unterlassungserklärungen.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

const toneIcon: Record<Tone, LucideIcon> = {
  danger: AlertTriangle,
  success: ShieldCheck,
  warning: CircleHelp,
  neutral: Clock3,
};

const toneLabel: Record<Tone, string> = {
  danger: "Kritisch",
  success: "Erledigt",
  warning: "Prüfung nötig",
  neutral: "Ausstehend",
};

const toneColor: Record<Tone, string> = {
  danger: "text-danger bg-danger/10",
  success: "text-success bg-success/10",
  warning: "text-warning bg-warning/10",
  neutral: "text-muted-foreground bg-muted",
};

function relativeTime(iso: string | null, now = new Date()) {
  if (!iso) return "noch nicht erfasst";
  const mins = Math.max(1, Math.round((now.getTime() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `vor ${mins} Min.`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  return `vor ${Math.round(hours / 24)} Tg.`;
}

function priority(item: CaseView) {
  if (item.tone === "danger") return 0;
  if (item.tone === "warning") return 1;
  if (item.tone === "neutral") return 2;
  return 3;
}

function Index() {
  const { cases, demoMode, isError, isPending } = useCaseViews();
  const { now: nowTimestamp } = Route.useLoaderData();
  const now = new Date(nowTimestamp);
  const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const newCount = cases.filter(
    (item) => item.found_at && new Date(item.found_at) > oneDayAgo,
  ).length;
  const criticalCount = cases.filter((item) => item.tone === "danger").length;
  const inReviewCount = cases.filter(
    (item) => item.tone === "warning" || item.tone === "neutral",
  ).length;
  const lastCase =
    cases
      .map((item) => item.found_at)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1) ?? null;
  const nextCases = [...cases]
    .filter((item) => item.tone !== "success")
    .sort((a, b) => {
      const byPriority = priority(a) - priority(b);
      if (byPriority !== 0) return byPriority;
      return (
        (b.found_at ? new Date(b.found_at).getTime() : 0) -
        (a.found_at ? new Date(a.found_at).getTime() : 0)
      );
    })
    .slice(0, 3);

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
      <header className="flex flex-col gap-5 border-b border-border pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs text-muted-foreground">Muc Legal</p>
          <h1 className="mt-2 text-3xl sm:text-4xl">Fallmonitor</h1>
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground sm:text-base">
            Offene Prüfungen, Beweise und menschliche Entscheidungen auf einen Blick.
          </p>
        </div>
        <Link
          to="/neu"
          className="inline-flex min-h-11 items-center justify-center gap-2 bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Plus className="size-4" strokeWidth={1.75} aria-hidden="true" />
          Neuen Fall anlegen
        </Link>
      </header>

      {isPending ? (
        <DashboardLoading />
      ) : (
        <>
          {(demoMode || isError) && (
            <section
              className={`mt-6 border px-5 py-4 ${
                isError ? "border-danger/40 bg-danger/5" : "border-warning/40 bg-warning/5"
              }`}
              aria-label={isError ? "Verbindungsstatus" : "Demohinweis"}
            >
              <div className="flex items-start gap-3">
                <AlertTriangle
                  className={`mt-0.5 size-5 shrink-0 ${isError ? "text-danger" : "text-warning"}`}
                  strokeWidth={1.75}
                  aria-hidden="true"
                />
                <div>
                  <p className="font-semibold">
                    {isError ? "Keine Verbindung zum Fallbestand" : "Demodaten"}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {isError
                      ? "Die angezeigten Vorgänge sind ausschließlich synthetische Beispiele. Es werden keine aktuellen Falldaten angezeigt."
                      : "Alle angezeigten Vorgänge sind synthetische Beispiele und keine echten Mandats- oder Verbandsfälle."}
                  </p>
                </div>
              </div>
            </section>
          )}

          <section className="mt-8" aria-labelledby="ueberblick-heading">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 id="ueberblick-heading" className="text-xl">
                  Überblick
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Stand:{" "}
                  {now.toLocaleDateString("de-DE", {
                    weekday: "long",
                    day: "2-digit",
                    month: "long",
                    year: "numeric",
                  })}
                </p>
              </div>
              <p className="text-sm text-muted-foreground">
                Letzter erfasster Fall: {relativeTime(lastCase, now)}
              </p>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <MetricCard
                icon={CircleHelp}
                label="Zur Prüfung"
                value={inReviewCount}
                subline="benötigen eine menschliche Entscheidung"
                tone="warning"
                to="/hinweise"
              />
              <MetricCard
                icon={AlertTriangle}
                label="Kritisch"
                value={criticalCount}
                subline="sollten zuerst geprüft werden"
                tone="danger"
                to="/hinweise"
              />
              <MetricCard
                icon={Bell}
                label="Neu"
                value={newCount}
                subline="in den letzten 24 Stunden"
                tone="neutral"
                to="/hinweise"
              />
            </div>
          </section>

          <section className="mt-10" aria-labelledby="next-heading">
            <div className="flex items-end justify-between gap-4">
              <div>
                <h2 id="next-heading" className="text-xl">
                  Als Nächstes
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Die wichtigsten offenen Vorgänge in sinnvoller Reihenfolge.
                </p>
              </div>
              <Link to="/hinweise" className="text-sm font-medium text-primary hover:underline">
                Alle Prüfungen
              </Link>
            </div>

            {nextCases.length === 0 ? (
              <div className="mt-5 border border-border bg-card px-5 py-6">
                <div className="flex items-start gap-3">
                  <ShieldCheck
                    className="mt-0.5 size-5 shrink-0 text-success"
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                  <div>
                    <p className="font-semibold">Keine offenen Prüfungen</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Derzeit wartet kein Fall auf eine menschliche Entscheidung.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <ul className="mt-5 divide-y divide-border border border-border bg-card">
                {nextCases.map((item) => (
                  <PriorityCase key={item.case_id} item={item} now={now} demoMode={demoMode} />
                ))}
              </ul>
            )}
          </section>

          <section className="mt-10" aria-labelledby="shortcuts-heading">
            <h2 id="shortcuts-heading" className="text-xl">
              Schnellzugriff
            </h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <QuickAction
                to="/neu"
                icon={Plus}
                label="Fall anlegen"
                description="Erstverstoß und Prüfumfang erfassen"
              />
              <QuickAction
                to="/hinweise"
                icon={Bell}
                label="Prüfungen öffnen"
                description="Offene menschliche Entscheidungen bearbeiten"
              />
              <QuickAction
                to="/archiv"
                icon={Archive}
                label="Archiv öffnen"
                description="Fälle und übernommene Tenore nachlesen"
              />
            </div>
          </section>

          <footer className="mt-10 flex flex-col gap-2 border-t border-border pt-5 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <span className="inline-flex items-center gap-2">
              <Activity className="size-4" strokeWidth={1.75} aria-hidden="true" />
              {isError
                ? "Fallbestand nicht erreichbar"
                : demoMode
                  ? "Demobetrieb"
                  : "Fallmonitor aktiv"}
            </span>
            <span>
              {cases.length} angezeigte {cases.length === 1 ? "Akte" : "Akten"}
            </span>
          </footer>
        </>
      )}
    </div>
  );
}

function DashboardLoading() {
  return (
    <div className="mt-8 border border-border bg-card px-5 py-8" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <Clock3
          className="size-5 animate-pulse text-muted-foreground"
          strokeWidth={1.75}
          aria-hidden="true"
        />
        <div>
          <p className="font-semibold">Fallbestand wird geladen</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Offene Prüfungen und Entscheidungen werden zusammengestellt.
          </p>
        </div>
      </div>
    </div>
  );
}

function PriorityCase({ item, now, demoMode }: { item: CaseView; now: Date; demoMode: boolean }) {
  const Icon = toneIcon[item.tone];
  return (
    <li>
      <Link
        to="/hinweise"
        className="group grid gap-4 p-5 transition-colors hover:bg-muted/50 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center"
      >
        <span
          className={`grid size-10 place-items-center ${toneColor[item.tone]}`}
          aria-hidden="true"
        >
          <Icon className="size-5" strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="text-xs text-muted-foreground">
              {toneLabel[item.tone]} · {relativeTime(item.found_at, now)}
            </p>
            {demoMode && (
              <span className="border border-warning/40 bg-warning/5 px-2 py-0.5 text-xs text-warning">
                Demofall
              </span>
            )}
          </div>
          <p className="mt-2 line-clamp-2 font-semibold text-card-foreground">{item.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{item.secondary}</p>
        </div>
        <span className="inline-flex items-center gap-2 text-sm font-medium text-primary">
          Prüfen
          <ArrowRight
            className="size-4 transition-transform group-hover:translate-x-1"
            strokeWidth={1.75}
            aria-hidden="true"
          />
        </span>
      </Link>
    </li>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  subline,
  tone,
  to,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  subline: string;
  tone: Tone;
  to: string;
}) {
  return (
    <Link
      to={to}
      aria-label={`${label}: ${value}. ${subline}`}
      className="group flex min-h-36 flex-col justify-between border border-border bg-card p-5 transition-colors hover:bg-muted/50"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-semibold text-card-foreground">{value}</p>
        </div>
        <span className={`grid size-10 shrink-0 place-items-center ${toneColor[tone]}`}>
          <Icon className="size-5" strokeWidth={1.75} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{subline}</p>
    </Link>
  );
}

function QuickAction({
  to,
  icon: Icon,
  label,
  description,
}: {
  to: string;
  icon: LucideIcon;
  label: string;
  description: string;
}) {
  return (
    <Link
      to={to}
      className="group flex items-start gap-4 border border-border bg-card p-5 transition-colors hover:bg-muted/50"
    >
      <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" strokeWidth={1.75} />
      <span>
        <span className="flex items-center gap-2 font-medium text-card-foreground">
          {label}
          <ArrowRight
            className="size-4 transition-transform group-hover:translate-x-1"
            strokeWidth={1.75}
            aria-hidden="true"
          />
        </span>
        <span className="mt-1 block text-sm text-muted-foreground">{description}</span>
      </span>
    </Link>
  );
}
