import { createFileRoute } from "@tanstack/react-router";
import { LayoutTemplate, PenLine } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { MaskTenorView } from "../components/tenor/MaskTenorView";
import { MinimalTenorView } from "../components/tenor/MinimalTenorView";

export const Route = createFileRoute("/tenorhilfe")({
  validateSearch: z.object({
    tenor_id: z.string().min(1).optional(),
  }),
  head: () => ({
    meta: [
      { title: "Tenorschreibhilfe – Muc Legal Monitoring" },
      {
        name: "description",
        content:
          "Unterlassungstenor wahlweise in einer strukturierten Maske oder einem minimalen Schreibmodus entwerfen.",
      },
      { property: "og:title", content: "Tenorschreibhilfe – Muc Legal Monitoring" },
      {
        property: "og:description",
        content:
          "Unterlassungstenor wahlweise in einer strukturierten Maske oder einem minimalen Schreibmodus entwerfen.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: TenorhilfePage,
});

type ViewMode = "minimal" | "maske";

function TenorhilfePage() {
  const { tenor_id: tenorId } = Route.useSearch();
  const [view, setView] = useState<ViewMode>("minimal");

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/95 px-6 backdrop-blur sm:px-10">
        <div>
          <span className="text-xs text-muted-foreground">Tenorschreibhilfe</span>
          <p className="mt-0.5 font-sans text-sm font-semibold">
            {view === "minimal"
              ? "Lokale, referenzierte Bausteinvorschläge"
              : "Backend-Entwurf & menschliche Freigabe"}
          </p>
        </div>
        <div
          role="tablist"
          aria-label="Ansicht der Tenorschreibhilfe"
          className="flex border border-foreground"
        >
          <button
            id="tenor-tab-minimal"
            type="button"
            role="tab"
            aria-selected={view === "minimal"}
            aria-controls="tenor-panel-minimal"
            onClick={() => setView("minimal")}
            className={`flex min-h-10 items-center gap-2 px-4 text-xs transition-colors ${
              view === "minimal"
                ? "bg-foreground text-background"
                : "bg-background text-muted-foreground hover:bg-muted"
            }`}
          >
            <PenLine className="size-3.5" />
            Minimal
          </button>
          <button
            id="tenor-tab-maske"
            type="button"
            role="tab"
            aria-selected={view === "maske"}
            aria-controls="tenor-panel-maske"
            onClick={() => setView("maske")}
            className={`flex min-h-10 items-center gap-2 border-l border-foreground px-4 text-xs transition-colors ${
              view === "maske"
                ? "bg-foreground text-background"
                : "bg-background text-muted-foreground hover:bg-muted"
            }`}
          >
            <LayoutTemplate className="size-3.5" />
            Maske
          </button>
        </div>
      </header>

      <section
        id="tenor-panel-minimal"
        role="tabpanel"
        aria-labelledby="tenor-tab-minimal"
        hidden={view !== "minimal"}
      >
        <MinimalTenorView key={tenorId ?? "new"} initialArchiveId={tenorId} />
      </section>
      <section
        id="tenor-panel-maske"
        role="tabpanel"
        aria-labelledby="tenor-tab-maske"
        hidden={view !== "maske"}
      >
        <MaskTenorView />
      </section>
    </div>
  );
}
