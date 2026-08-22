import { createFileRoute } from "@tanstack/react-router";

import { lottoDemoCases, type Tone } from "../data/lottoDemoCases";

export const Route = createFileRoute("/archiv")({
  head: () => ({
    meta: [
      { title: "Archiv – MucLegal" },
      {
        name: "description",
        content: "Übersicht aller erfassten Fälle mit Status, Domain, Zeitpunkt und Confidence.",
      },
      { property: "og:title", content: "Archiv – MucLegal" },
      {
        property: "og:description",
        content: "Übersicht aller erfassten Fälle mit Status, Domain, Zeitpunkt und Confidence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ArchivPage,
});

const toneBadge: Record<Tone, string> = {
  danger: "bg-danger/10 text-danger",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  neutral: "bg-muted text-muted-foreground",
};

const toneLabel: Record<Tone, string> = {
  danger: "Kritisch",
  success: "In Ordnung",
  warning: "Prüfung nötig",
  neutral: "Ausstehend",
};

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

function ArchivPage() {
  return (
    <div className="mx-auto max-w-6xl px-8 py-12">
      <h1 className="text-3xl">Archiv</h1>
      <p className="mt-3 max-w-xl text-sm text-muted-foreground">
        Alle erfassten Fälle in der Übersicht. {lottoDemoCases.length} Einträge.
      </p>

      <div className="mt-8 overflow-hidden rounded-2xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs tracking-wider text-muted-foreground uppercase">
                <th className="px-5 py-4 font-medium">Fall-ID</th>
                <th className="px-5 py-4 font-medium">Titel</th>
                <th className="px-5 py-4 font-medium">Status</th>
                <th className="px-5 py-4 font-medium">Domain</th>
                <th className="px-5 py-4 font-medium">Erfasst</th>
                <th className="px-5 py-4 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {lottoDemoCases.map((c) => (
                <tr
                  key={c.case_id}
                  className="border-b border-border last:border-0 transition-colors hover:bg-muted/60"
                >
                  <td className="px-5 py-4 font-mono text-xs text-muted-foreground">{c.fall_id}</td>
                  <td className="px-5 py-4">
                    <p className="font-medium text-card-foreground">{c.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{c.secondary}</p>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${toneBadge[c.tone]}`}
                    >
                      {toneLabel[c.tone]}
                    </span>
                    <p className="mt-1 text-xs text-muted-foreground">{c.status}</p>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">{c.domain}</td>
                  <td className="px-5 py-4 text-muted-foreground">{formatDateTime(c.found_at)}</td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {c.confidence === null ? "—" : `${Math.round(c.confidence * 100)} %`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
