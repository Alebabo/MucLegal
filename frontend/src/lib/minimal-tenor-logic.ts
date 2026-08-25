export type WritingMode = "sachverhalt" | "tenor" | "fälle";

export type SearchableCase = {
  title: string;
  fall_id: string;
  domain: string;
  secondary: string;
};

function normalizeCaseSearch(value: string) {
  return value
    .trim()
    .toLocaleLowerCase("de")
    .replaceAll("ä", "ae")
    .replaceAll("ö", "oe")
    .replaceAll("ü", "ue")
    .replaceAll("ß", "ss");
}

export function filterCaseOptions<T extends SearchableCase>(cases: T[], query: string, limit = 5) {
  const normalizedQuery = normalizeCaseSearch(query);
  return cases
    .filter((item) =>
      normalizeCaseSearch(
        `${item.title} ${item.fall_id} ${item.domain} ${item.secondary}`,
      ).includes(normalizedQuery),
    )
    .slice(0, limit);
}

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

export type RequiredIntakeFactId = "verstossort" | "rechtsgrundlagen";

export type RequiredIntakeFact = {
  id: RequiredIntakeFactId;
  question: string;
  placeholder: string;
};

export type RequiredIntakeAnswer = RequiredIntakeFact & { answer: string };

const requiredIntakeFacts: Record<RequiredIntakeFactId, RequiredIntakeFact> = {
  verstossort: {
    id: "verstossort",
    question:
      "Wo genau liegt der Verstoß – an welcher Fundstelle und welche konkrete Aussage, Gestaltung oder Funktion ist dort beanstandet?",
    placeholder:
      "Zum Beispiel: Produktseite unter https://…; der Countdown startet nach Ablauf erneut.",
  },
  rechtsgrundlagen: {
    id: "rechtsgrundlagen",
    question: "Welche spezifischen Rechtsgrundlagen kommen nach deiner Prüfung in Betracht?",
    placeholder: "Zum Beispiel: § 5 UWG und § 8 Abs. 1 UWG – oder: noch rechtlich zu prüfen.",
  },
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

export function isAllowedUeAutocompleteSegment(segment: string) {
  return !["verpflichtungsformel", "ordnungsmittelandrohung"].includes(segment);
}

export function inferFallgruppe(text: string, uploadedContract = false) {
  const normalized = text.toLocaleLowerCase("de");
  return /klausel|agb|altvertrag|vertragsbedingung/.test(normalized) ||
    (uploadedContract &&
      /vertrag|vereinbarung|laufzeit|kündigungsfrist|schriftform/.test(normalized))
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
      /(kündig|button|schaltfläche|klausel|cookie|consent|tracking|werb|rabatt|countdown|preis|vertrag|verlänger|versteckt|fehlt|irreführ)/i.test(
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

export function hasConcreteViolationLocation(text: string, fallgruppe: string) {
  if (/Hochgeladenes Vertragsdokument:/i.test(text)) return true;
  if (fallgruppe === "agb_klausel") {
    return /[„‚"].{8,}[“‘"]|\bklausel\s*:\s*.{8,}/is.test(text);
  }
  return (
    /https?:\/\//i.test(text) ||
    /\b(?:auf|in|unter|bei)\s+(?:der|dem|den|einer|einem)?\s*(?:website|webseite|app|produktseite|checkout|newsletter|anschreiben|filiale|warenkorb|bestellprozess)\b/i.test(
      text,
    )
  );
}

export function hasSpecificLegalBasis(text: string) {
  return /(?:§{1,2}\s*\d+[a-z]?(?:\s*Abs\.\s*\d+)?|Art\.\s*\d+[a-z]?)\s*(?:UWG|BGB|UKlaG|TDDDG|DSGVO|DSA|ZPO|TMG)/i.test(
    text,
  );
}

export function nextRequiredIntakeFact(
  text: string,
  fallgruppe: string,
  answers: RequiredIntakeAnswer[],
): RequiredIntakeFact | null {
  const answered = new Set(answers.map((item) => item.id));
  if (!answered.has("verstossort") && !hasConcreteViolationLocation(text, fallgruppe)) {
    return requiredIntakeFacts.verstossort;
  }
  const combined = `${text}\n${answers.map((item) => item.answer).join("\n")}`;
  if (!answered.has("rechtsgrundlagen") && !hasSpecificLegalBasis(combined)) {
    return requiredIntakeFacts.rechtsgrundlagen;
  }
  return null;
}

export function extractLegalBases(text: string) {
  const matches = text.match(
    /(?:§{1,2}\s*\d+[a-z]?(?:\s*Abs\.\s*\d+)?|Art\.\s*\d+[a-z]?)\s*(?:UWG|BGB|UKlaG|TDDDG|DSGVO|DSA|ZPO|TMG)/gi,
  );
  return [...new Set((matches ?? []).map((item) => item.replace(/\s+/g, " ").trim()))];
}

export function composeRevisionContext(tenor: string, instruction: string, originalContext = "") {
  return [
    "Bestehender Tenor, der überarbeitet werden soll:",
    tenor.trim(),
    originalContext.trim() ? `Ursprünglicher Sachverhalt:\n${originalContext.trim()}` : "",
    `Änderungswunsch:\n${instruction.trim()}`,
  ]
    .filter(Boolean)
    .join("\n\n");
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
