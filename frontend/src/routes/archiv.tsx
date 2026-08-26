import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";

import { useCaseViews, type CaseView } from "../data/caseViews";
import type { Tone } from "../data/lottoDemoCases";
import {
  listTenorArchiveEntries,
  type TenorArchiveRecord,
  type TenorDecision,
} from "../lib/tenor-api";

export const Route = createFileRoute("/archiv")({
  head: () => ({
    meta: [
      { title: "Archiv – Muc Legal Monitoring" },
      {
        name: "description",
        content: "Übersicht aller erfassten Fälle und gespeicherten Tenore.",
      },
      { property: "og:title", content: "Archiv – Muc Legal Monitoring" },
      {
        property: "og:description",
        content: "Übersicht aller erfassten Fälle und gespeicherten Tenore.",
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
  warning: "Prüfen",
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
  const tenorQuery = useQuery({
    queryKey: ["tenor-archive"],
    queryFn: listTenorArchiveEntries,
  });
  const tenors = tenorQuery.data?.tenors ?? [];
  const [section, setSection] = useState<"faelle" | "tenore">("faelle");
  const [selected, setSelected] = useState<CaseView | null>(null);
  const [selectedTenor, setSelectedTenor] = useState<TenorArchiveRecord | null>(null);

  return (
    <div className="mx-auto max-w-6xl px-8 py-12">
      <h1 className="text-3xl">Archiv</h1>
      <p className="mt-3 max-w-xl text-sm text-muted-foreground">
        {section === "faelle"
          ? `Alle erfassten Fälle in der Übersicht. ${cases.length} Einträge.`
          : `Alle bisher gespeicherten Tenore. ${tenors.length} Einträge.`}
      </p>

      <div
        role="tablist"
        aria-label="Archivbereich"
        className="mt-8 inline-flex border border-foreground"
      >
        <ArchiveTab
          label={`Fälle (${cases.length})`}
          selected={section === "faelle"}
          onClick={() => setSection("faelle")}
        />
        <ArchiveTab
          label={`Tenore (${tenors.length})`}
          selected={section === "tenore"}
          onClick={() => setSection("tenore")}
          divided
        />
      </div>

      {section === "faelle" ? (
        <div className="mt-5 overflow-hidden rounded-2xl border border-border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] table-fixed text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs tracking-wider text-muted-foreground uppercase">
                  <th className="w-[20%] px-3 py-3 font-medium">Fall-ID</th>
                  <th className="w-[25%] px-3 py-3 font-medium">Titel</th>
                  <th className="w-[16%] px-3 py-3 font-medium">Status</th>
                  <th className="w-[15%] px-3 py-3 font-medium">Domain</th>
                  <th className="w-[18%] px-3 py-3 font-medium">Erfasst</th>
                  <th className="w-[6%] px-3 py-3 font-medium">Conf.</th>
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
                    <td className="px-3 py-3 font-mono text-xs text-muted-foreground">
                      <p className="truncate whitespace-nowrap" title={item.fall_id}>
                        {item.fall_id}
                      </p>
                    </td>
                    <td className="px-3 py-3">
                      <p
                        className="truncate whitespace-nowrap font-medium text-card-foreground"
                        title={item.title}
                      >
                        {item.title}
                      </p>
                    </td>
                    <td className="overflow-hidden px-3 py-3">
                      <span
                        className={`inline-flex whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium ${toneBadge[item.tone]}`}
                      >
                        {toneLabel[item.tone]}
                      </span>
                    </td>
                    <td
                      className="truncate whitespace-nowrap px-3 py-3 text-muted-foreground"
                      title={item.domain}
                    >
                      {item.domain}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted-foreground">
                      {formatDateTime(item.found_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted-foreground">
                      {item.confidence === null ? "—" : `${Math.round(item.confidence * 100)} %`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <TenorArchiveTable
          tenors={tenors}
          loading={tenorQuery.isLoading}
          error={tenorQuery.isError}
          onSelect={setSelectedTenor}
        />
      )}

      {selected && <CaseDetail item={selected} onClose={() => setSelected(null)} />}
      {selectedTenor && <TenorDetail item={selectedTenor} onClose={() => setSelectedTenor(null)} />}
    </div>
  );
}

function ArchiveTab({
  label,
  selected,
  onClick,
  divided = false,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  divided?: boolean;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={onClick}
      className={`min-h-10 px-5 text-xs font-medium transition-colors ${divided ? "border-l border-foreground" : ""} ${selected ? "bg-foreground text-background" : "bg-background text-muted-foreground hover:bg-muted"}`}
    >
      {label}
    </button>
  );
}

const decisionLabel: Record<TenorDecision, string> = {
  freigegeben: "Freigegeben",
  abgelehnt: "Abgelehnt",
  weitere_pruefung: "Weitere Prüfung",
};

function tenorStatus(item: TenorArchiveRecord) {
  if (item.decision) return decisionLabel[item.decision];
  return item.source === "minimal" ? "Übernommen" : "Prüfung offen";
}

function TenorArchiveTable({
  tenors,
  loading,
  error,
  onSelect,
}: {
  tenors: TenorArchiveRecord[];
  loading: boolean;
  error: boolean;
  onSelect: (item: TenorArchiveRecord) => void;
}) {
  if (loading) {
    return <p className="mt-8 text-sm text-muted-foreground">Tenorarchiv wird geladen …</p>;
  }
  if (error) {
    return (
      <p role="alert" className="mt-8 text-sm text-danger">
        Das Tenorarchiv konnte nicht geladen werden.
      </p>
    );
  }
  if (!tenors.length) {
    return (
      <div className="mt-5 rounded-2xl border border-border bg-card px-6 py-12 text-center">
        <p className="font-serif text-lg text-foreground">Noch keine Tenore gespeichert.</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Ein Entwurf erscheint hier, sobald er in der Tenorhilfe übernommen wurde.
        </p>
      </div>
    );
  }
  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs tracking-wider text-muted-foreground uppercase">
              <th className="px-5 py-4 font-medium">Fall-ID</th>
              <th className="px-5 py-4 font-medium">Tenor</th>
              <th className="px-5 py-4 font-medium">Status</th>
              <th className="px-5 py-4 font-medium">Gespeichert</th>
            </tr>
          </thead>
          <tbody>
            {tenors.map((item) => (
              <tr
                key={item.tenor_id}
                tabIndex={0}
                onClick={() => onSelect(item)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(item);
                  }
                }}
                className="cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-muted/60"
              >
                <td className="px-5 py-4 font-mono text-xs text-muted-foreground">
                  {item.fall_id}
                </td>
                <td className="max-w-md px-5 py-4">
                  <p className="font-medium text-card-foreground">{item.title}</p>
                  <p className="mt-1 line-clamp-2 font-serif text-xs leading-5 text-muted-foreground">
                    {item.text}
                  </p>
                </td>
                <td className="px-5 py-4">
                  <span className="inline-flex rounded-full bg-muted px-3 py-1 text-xs font-medium text-foreground">
                    {tenorStatus(item)}
                  </span>
                </td>
                <td className="px-5 py-4 text-muted-foreground">
                  {formatDateTime(item.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TenorDetail({ item, onClose }: { item: TenorArchiveRecord; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-foreground/30 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
      role="presentation"
    >
      <article
        className="w-full max-w-4xl rounded-3xl border border-border bg-card p-6 shadow-xl sm:p-10"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={item.title}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs text-muted-foreground">{item.fall_id}</p>
            <h2 className="mt-1 text-2xl tracking-tight text-card-foreground">{item.title}</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              {tenorStatus(item)} · {formatDateTime(item.created_at)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="grid size-10 shrink-0 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="mt-8 border-y border-border py-8">
          <p className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Gespeicherter Tenor
          </p>
          <p className="mt-4 whitespace-pre-wrap font-serif text-lg leading-9 text-foreground">
            {item.text}
          </p>
        </div>

        <dl className="mt-7 grid gap-5 text-sm sm:grid-cols-2">
          <Detail label="Schuldner" value={item.schuldner} />
          <Detail
            label="Erstellung"
            value={`${item.source === "minimal" ? "Minimal" : "Maske"} · ${item.model}`}
          />
          <Detail label="Wissensstand" value={item.reference_version} />
          <Detail
            label="Quellenanker"
            value={item.source_ids.length ? item.source_ids.join(" · ") : "—"}
          />
        </dl>

        <div className="mt-7 rounded-2xl bg-muted p-5">
          <p className="text-xs tracking-wider text-muted-foreground uppercase">Sachverhalt</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground">
            {item.context}
          </p>
        </div>

        <div className="mt-7 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
          <p className="max-w-xl text-xs leading-5 text-muted-foreground">
            Die gespeicherte Fassung bleibt erhalten. Eine Überarbeitung wird als neuer
            Archiveintrag angelegt.
          </p>
          <Link
            to="/tenorhilfe"
            search={{ tenor_id: item.tenor_id }}
            className="inline-flex min-h-10 items-center rounded-full bg-foreground px-5 text-sm font-semibold text-background transition-opacity hover:opacity-85"
          >
            Tenor anpassen
          </Link>
        </div>
      </article>
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
