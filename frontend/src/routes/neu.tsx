import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/neu")({
  head: () => ({
    meta: [
      { title: "Neu hinzufügen – MucLegal" },
      { name: "description", content: "Einen neuen Fall erfassen und zur Prüfung anlegen." },
      { property: "og:title", content: "Neu hinzufügen – MucLegal" },
      {
        property: "og:description",
        content: "Einen neuen Fall erfassen und zur Prüfung anlegen.",
      },
    ],
  }),
  component: NeuPage,
});

function NeuPage() {
  return (
    <div className="mx-auto max-w-4xl px-8 py-12">
      <h1 className="text-3xl">Neu hinzufügen</h1>
      <p className="mt-3 max-w-xl text-sm text-muted-foreground">
        Hier legen Sie einen neuen Fall an. Das Formular folgt in einem nächsten Schritt.
      </p>
    </div>
  );
}
