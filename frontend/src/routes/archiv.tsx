import { createFileRoute } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useState } from "react";

import { useCaseViews, type CaseView } from "../data/caseViews";
import type { Tone } from "../data/lottoDemoCases";

export const Route = createFileRoute("/archiv")({
  head: () => ({
    meta: [
      { title: "Archiv – Muc Legal Monitoring" },
      {
        name: "description",
        content: "Übersicht aller erfassten Fälle mit Status, Domain, Zeitpunkt und Confidence.",
      },
      { property: "og:title", content: "Archiv – Muc Legal Monitoring" },
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
  const { cases } = useCaseViews();
  const [selected, setSelected] = useState<CaseView | null>(null);

  return (
    <div className="mx-auto max-w-6xl px-8 py-12">
      <h1 className="text-3xl">Archiv</h1>
      <p className="mt-3 max-w-xl text-sm text-muted-foreground">
        Alle erfassten Fälle in der Übersicht. {cases.length} Einträge.
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
              {cases.map((item) => (
                <tr
                  key={item.case_id}
                  onClick={() => setSelected(item)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelected(item);
                    }
                  }}
                  className="cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-muted/60"
                >
                  <td className="px-5 py-4 font-mono text-xs text-muted-foreground">
                    {item.fall_id}
                  </td>
                  <td className="px-5 py-4">
                    <p className="font-medium text-card-foreground">{item.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{item.secondary}</p>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${toneBadge[item.tone]}`}
                    >
                      {toneLabel[item.tone]}
                    </span>
                    <p className="mt-1 text-xs text-muted-foreground">{item.status}</p>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">{item.domain}</td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {formatDateTime(item.found_at)}
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {item.confidence === null ? "—" : `${Math.round(item.confidence * 100)} %`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <CaseDetail item={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function CaseDetail({ item, onClose }: { item: CaseView; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-foreground/30 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-2xl rounded-3xl border border-border bg-card p-8 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={item.title}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs text-muted-foreground">{item.fall_id}</p>
            <h2 className="mt-1 text-2xl tracking-tight text-card-foreground">{item.title}</h2>
            <span
              className={`mt-3 inline-flex rounded-full px-3 py-1 text-xs font-medium ${toneBadge[item.tone]}`}
            >
              {toneLabel[item.tone]}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="grid size-9 shrink-0 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted"
          >
            <X className="size-5" />
          </button>
        </div>

        <p className="mt-5 text-sm leading-relaxed text-foreground">{item.explanation}</p>
        <dl className="mt-6 grid gap-4 rounded-2xl bg-muted p-5 text-sm sm:grid-cols-2">
          <Detail label="Status" value={item.status} />
          <Detail label="Kontext" value={item.secondary} />
          <Detail label="Domain" value={item.domain} />
          <Detail label="Erfasst" value={formatDateTime(item.found_at)} />
          <Detail
            label="Confidence"
            value={item.confidence === null ? "—" : `${Math.round(item.confidence * 100)} %`}
          />
          <div className="min-w-0">
            <dt className="text-xs tracking-wider text-muted-foreground uppercase">Zielseite</dt>
            <dd className="mt-1 truncate">
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                {item.url}
              </a>
            </dd>
          </div>
        </dl>

        <div className="mt-6 rounded-2xl border border-primary/20 bg-primary/5 p-5">
          <p className="text-xs font-medium tracking-wider text-primary uppercase">
            Tenor / Formulierungsvorschlag
          </p>
          <p className="mt-2 font-serif text-base leading-relaxed text-foreground">
            {item.tenor.formulierung}
          </p>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{item.tenor.hinweis}</p>
        </div>

        <div className="mt-6 rounded-2xl border border-border p-5">
          <p className="font-serif text-lg tracking-tight text-foreground">Beweisführung</p>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <Detail label="Fundstelle" value={item.evidence.fundstelle} />
            <Detail label="Erfassung" value={item.evidence.erfassung} />
          </dl>
          <p className="mt-5 text-xs tracking-wider text-muted-foreground uppercase">Beweiskette</p>
          <ol className="mt-2 space-y-2">
            {item.evidence.kette.map((step, index) => (
              <li key={step} className="flex gap-3 text-sm text-foreground">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                  {index + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs tracking-wider text-muted-foreground uppercase">
                Rechtliche Einordnung
              </p>
              <p className="mt-1 text-sm leading-relaxed text-foreground">
                {item.evidence.einordnung}
              </p>
            </div>
            <div>
              <p className="text-xs tracking-wider text-muted-foreground uppercase">
                Offene Punkte
              </p>
              <p className="mt-1 text-sm leading-relaxed text-foreground">{item.evidence.offen}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs tracking-wider text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-1 text-foreground">{value}</dd>
    </div>
  );
}
