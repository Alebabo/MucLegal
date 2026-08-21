import { createFileRoute, Link } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Fallmonitor – MucLegal" },
      {
        name: "description",
        content: "Übersicht über Fälle und Monitoringläufe zu Unterlassungserklärungen.",
      },
      { property: "og:title", content: "Fallmonitor – MucLegal" },
      {
        property: "og:description",
        content: "Übersicht über Fälle und Monitoringläufe zu Unterlassungserklärungen.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="mx-auto max-w-4xl px-8 py-12">
      <h1 className="text-3xl">Fallmonitor</h1>
      <p className="mt-3 max-w-xl text-sm text-muted-foreground">
        Hier entsteht die Übersicht Ihrer Fälle. Nutzen Sie die Seitenleiste, um zwischen den
        Bereichen zu wechseln.
      </p>
      <Link
        to="/neu"
        className="mt-8 inline-flex items-center rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        Neu hinzufügen
      </Link>
    </div>
  );
}
