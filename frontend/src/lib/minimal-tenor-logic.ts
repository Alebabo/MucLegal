export type WritingMode = "sachverhalt" | "tenor" | "fälle";

export type ModeCommand = {
  id: WritingMode;
  command: string;
  title: string;
  hint: string;
};

export type Completeness = {
  complete: boolean;
  missing: Array<"handlung" | "kanal" | "betroffene" | "ziel">;
  nextQuestion: string | null;
};

export const modeCommands: ModeCommand[] = [
  {
    id: "sachverhalt",
    command: "/sachverhalt",
    title: "Sachverhalt",
    hint: "Einen neuen Verstoß beschreiben",
  },
  {
    id: "tenor",
    command: "/tenor",
    title: "Tenor",
    hint: "Einen bestehenden Tenor korrigieren",
  },
  { id: "fälle", command: "/fälle", title: "Fälle", hint: "Archiv und Hinweise durchsuchen" },
];

export function isTenor(text: string) {
  return /(zu unterlassen|wird verurteilt|ordnungsgeld|zuwiderhandlung|der beklagten wird untersagt)/i.test(
    text,
  );
}

export function inferFallgruppe(text: string) {
  const normalized = text.toLocaleLowerCase("de");
  return /klausel|agb|altvertrag/.test(normalized)
    ? "agb_klausel"
    : /cookie|consent|tracking/.test(normalized)
      ? "consent_gestaltung"
      : /dark pattern|checkout|versicherung/.test(normalized)
        ? "dark_pattern_dsa"
        : /werb|wirb|irreführ/.test(normalized)
          ? "irrefuehrende_werbung"
          : "kuendigungsbutton";
}

export function assessCompleteness(text: string): Completeness {
  const checks = {
    handlung:
      /(kündig|button|schaltfläche|klausel|cookie|consent|tracking|werbung|rabatt|countdown|preis|vertrag|verlänger|versteckt|fehlt|irreführ)/i.test(
        text,
      ),
    kanal:
      /(website|webseite|app|internet|online|domain|checkout|agb|vertrag|schreiben|e-mail|social media|filiale)/i.test(
        text,
      ),
    betroffene: /(verbraucher|kund|nutzer|abonnent|betroffen|privatperson|vertragspartner)/i.test(
      text,
    ),
    ziel: /(unterlassen|künftig|soll|darf nicht|nicht mehr|muss|bereitstellen|entfernen|verbieten|untersagt)/i.test(
      text,
    ),
  };
  const missing = (Object.entries(checks) as Array<[Completeness["missing"][number], boolean]>)
    .filter(([, present]) => !present)
    .map(([name]) => name);
  const nextQuestion = !checks.handlung
    ? "Welche konkrete Handlung oder Gestaltung beanstandest du?"
    : !checks.kanal
      ? "Wo genau tritt der Verstoß auf – zum Beispiel auf einer Website, in einer App oder in einem Vertrag?"
      : !checks.betroffene
        ? "Wer ist davon betroffen – Verbraucher, Kunden oder eine andere Gruppe?"
        : !checks.ziel
          ? "Was genau soll das Unternehmen künftig unterlassen?"
          : null;
  return { complete: missing.length === 0, missing, nextQuestion };
}

export function filterModeCommands(query: string) {
  const normalized = query.toLocaleLowerCase("de");
  return modeCommands.filter((command) =>
    `${command.command} ${command.title}`.toLocaleLowerCase("de").includes(normalized),
  );
}

export function nextWrappedIndex(current: number, length: number, direction: 1 | -1) {
  if (length <= 0) return 0;
  return (current + direction + length) % length;
}
