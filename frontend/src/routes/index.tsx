import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowRight,
  Bell,
  Clock,
  HelpCircle,
  Plus,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useCaseViews } from "../data/caseViews";
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
  success: Activity,
  warning: HelpCircle,
  neutral: Clock,
};

const toneLabel: Record<Tone, string> = {
  danger: "Kritisch",
  success: "In Ordnung",
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
  if (!iso) return "geplant";
  const mins = Math.max(1, Math.round((now.getTime() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `vor ${mins} Min.`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  return `vor ${Math.round(hours / 24)} Tg.`;
}

function formatDateTime(date: Date) {
  return date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

function Index() {
  const { cases, demoMode, isError } = useCaseViews();
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
  const lastRun =
    cases
      .map((item) => item.found_at)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1) ?? null;
  const nextRun = new Date(now.getTime() + 2 * 60 * 60 * 1000);
  const topPriorities = cases
    .filter((item) => item.tone === "danger")
    .sort(
      (a, b) =>
        (b.found_at ? new Date(b.found_at).getTime() : 0) -
        (a.found_at ? new Date(a.found_at).getTime() : 0),
    )
    .slice(0, 3);

  return (
    <div className="mx-auto max-w-5xl px-8 py-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl">Dashboard</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {now.toLocaleDateString("de-DE", {
              weekday: "long",
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </p>
        </div>
        <Link
          to="/neu"
          className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Plus className="size-4" strokeWidth={1.75} />
          Neu hinzufügen
        </Link>
      </div>

      {isError && (
        <p className="mt-5 border border-warning bg-warning/10 px-4 py-3 text-sm text-foreground">
          Das Backend ist gerade nicht erreichbar. Die synthetischen Demofälle bleiben sichtbar.
        </p>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={Bell}
          label="Neue Hinweise"
          value={newCount}
          subline="in den letzten 24 Stunden"
          tone="neutral"
          to="/hinweise"
        />
        <MetricCard
          icon={AlertTriangle}
          label="Kritische Fälle"
          value={criticalCount}
          subline="sofortige Aktion nötig"
          tone="danger"
          to="/hinweise"
        />
        <MetricCard
          icon={HelpCircle}
          label="In Prüfung"
          value={inReviewCount}
          subline="manuelle Klärung offen"
          tone="warning"
          to="/archiv"
        />
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-success/10 text-success">
              <Activity className="size-5" strokeWidth={1.75} />
            </span>
            <div>
              <p className="text-xs text-muted-foreground">Monitoring-Status</p>
              <p className="text-lg font-semibold text-card-foreground">
                {isError ? "Offline" : demoMode ? "Demo" : "Aktiv"}
              </p>
            </div>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Letzter Fall: {relativeTime(lastRun, now)}
          </p>
          <p className="text-xs text-muted-foreground">Nächster Lauf: {formatDateTime(nextRun)}</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-xl">Quick Actions</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <QuickAction to="/neu" icon={Plus} label="Neuen Fall hinzufügen" />
          <QuickAction to="/hinweise" icon={Bell} label="Hinweise ansehen" />
          <QuickAction to="/archiv" icon={Archive} label="Archiv öffnen" />
        </div>
      </div>

      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-xl">Top-Prioritäten</h2>
          <Link to="/hinweise" className="text-sm font-medium text-primary hover:underline">
            Alle ansehen
          </Link>
        </div>
        {topPriorities.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Keine kritischen Fälle vorhanden.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {topPriorities.map((item) => {
              const Icon = toneIcon[item.tone];
              return (
                <li key={item.case_id}>
                  <Link
                    to="/hinweise"
                    className="group flex items-start gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md"
                  >
                    <span
                      className={`mt-0.5 grid size-10 shrink-0 place-items-center rounded-full ${toneColor[item.tone]}`}
                    >
                      <Icon className="size-5" strokeWidth={1.75} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">
                            {toneLabel[item.tone]} · {relativeTime(item.found_at, now)}
                          </p>
                          <p className="mt-0.5 text-base font-semibold text-card-foreground">
                            {item.title}
                          </p>
                        </div>
                        <ArrowRight
                          className="size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1"
                          strokeWidth={1.75}
                        />
                      </div>
                      <p className="mt-1 text-sm text-card-foreground">{item.status}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{item.secondary}</p>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
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
      className="group block rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:shadow-md"
    >
      <div className="flex items-center gap-3">
        <span className={`grid size-10 place-items-center rounded-full ${toneColor[tone]}`}>
          <Icon className="size-5" strokeWidth={1.75} />
        </span>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold text-card-foreground">{value}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">{subline}</p>
    </Link>
  );
}

function QuickAction({ to, icon: Icon, label }: { to: string; icon: LucideIcon; label: string }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4 text-sm font-medium text-card-foreground transition-all hover:bg-muted/60"
    >
      <Icon className="size-5 text-muted-foreground" strokeWidth={1.75} />
      {label}
    </Link>
  );
}
