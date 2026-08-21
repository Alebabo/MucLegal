import registerJson from "./generated/tenorregister.json";
import type {
  BuildingBlock,
  Draft,
  Profile,
  ReferenceTenor,
  ReviewFeature,
  Width,
} from "./tenor-types";

type Register = {
  meta: { segmentreihenfolge?: string[] };
  bausteine: BuildingBlock[];
  pruefregeln: Array<{
    id: string;
    meldung: string;
    schwere: string;
    referenz?: string[];
    vorschlag?: string;
    vorschlag_baustein?: string;
  }>;
  tenore: ReferenceTenor[];
};

export const register = registerJson as Register;

const blocks = new Map(register.bausteine.map((block) => [block.id, block]));

export function getBlock(id: string): BuildingBlock {
  const block = blocks.get(id);
  if (!block) throw new Error(`Unbekannter Baustein ${id}`);
  return block;
}

function normalize(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function fill(text: string, values: Record<string, string>): string {
  return normalize(text).replace(/\{\{([^}]+)}}/g, (_, key: string) => values[key] ?? `[${key}]`);
}

function addressBlock(profile: Profile): string {
  if (profile.adressat === "gemischt") return "B-AK-05";
  if (profile.fallgruppe === "agb_klausel") return "B-AK-02";
  return "B-AK-01";
}

function actionBlocks(profile: Profile): string[] {
  const normalizedGroup =
    profile.fallgruppe === "dark_pattern_dsa" ? "dark_pattern" : profile.fallgruppe;
  const candidates = register.bausteine.filter(
    (block) =>
      block.segment === "verbotene_handlung" &&
      block.fallgruppe === normalizedGroup &&
      (!block.verstoss_modus || block.verstoss_modus.includes(profile.verstossModus)) &&
      block.status !== "vorschlag",
  );
  if (profile.fallgruppe === "kuendigungsbutton") {
    return candidates
      .filter((block) => block.id === "B-VH-11" || block.id === "B-VH-11b")
      .map((block) => block.id);
  }
  if (profile.fallgruppe === "agb_klausel") {
    return candidates
      .filter((block) => block.id === "B-VH-42" || block.id === "B-VH-43")
      .map((block) => block.id);
  }
  return candidates.slice(0, 1).map((block) => block.id);
}

function concreteBlock(profile: Profile): string {
  if (profile.fallgruppe === "agb_klausel") return "B-KV-04";
  if (profile.fallgruppe === "irrefuehrende_werbung") return "B-KV-05";
  return profile.fallgruppe === "consent_gestaltung" ? "B-KV-01" : "B-KV-03";
}

function applicationBlock(width: Width): string {
  return width === "eng" ? "B-AB-02" : width === "kerngleich" ? "B-AB-03" : "B-AB-03b";
}

function renderBlock(block: BuildingBlock, profile: Profile): string {
  const values: Record<string, string> = {
    vollstreckungsperson: profile.rechtsform.toLowerCase().includes("ag")
      ? "ihrem Vorstand"
      : "ihrer Geschäftsführung",
    url: profile.url || "https://www.beispiel.de",
    vertragsgegenstand:
      profile.vertragstyp === "dauerschuldverhaeltnis" ? "entgeltlichen Abonnements" : "Verträgen",
    umgehungsmechanismus: "erst nach Betätigung eines Aufklapp-Elements",
    beschriftung: "Kündigen",
    anlage: profile.anlage || "K 1",
    gegenstand: "den kostenpflichtigen Zusatzschutz",
    aussage: profile.beanstandeterWortlaut || "einer irreführenden Verfügbarkeitsbehauptung",
    fundstelle: profile.url || "der beanstandeten Werbung",
    gebiet: "Deutschland",
    produkt: profile.vertragstyp || "Verbraucher",
    zustand: "den Bestellvorgang ohne Auswahl der Zusatzleistung fortsetzen",
    qualifikation: "den Vertrag zu privaten Zwecken schließen",
  };
  if (block.id === "B-KV-04")
    return profile.beanstandeterWortlaut || "[beanstandeter Klauselwortlaut]";
  return fill(block.text, values);
}

export function composeDraft(profile: Profile, width: Width): Draft {
  const selected = [
    "B-VF-01",
    "B-OM-03",
    addressBlock(profile),
    applicationBlock(width),
    ...actionBlocks(profile),
    ...(profile.fallgruppe === "consent_gestaltung" ? ["B-AV-01", "B-AV-02"] : []),
    concreteBlock(profile),
  ];

  if (!actionBlocks(profile).length) {
    return {
      width,
      text: "Kein geprüfter Baustein passt zu dieser Kombination aus Fallgruppe und Verstoßmodus.",
      blockIds: [],
      referenceIds: [],
      unsupported: true,
    };
  }

  const rendered = selected.map((id) => ({
    block: getBlock(id),
    text: renderBlock(getBlock(id), profile),
  }));
  const vf = rendered.find((item) => item.block.segment === "verpflichtungsformel")?.text ?? "";
  const om = rendered.find((item) => item.block.segment === "ordnungsmittelandrohung")?.text ?? "";
  const rest = rendered.filter(
    (item) => !["verpflichtungsformel", "ordnungsmittelandrohung"].includes(item.block.segment),
  );
  const text = normalize(`${vf} ${om} ${rest.map((item) => item.text).join(" ")}.`);
  const referenceIds = [...new Set(selected.flatMap((id) => getBlock(id).belegt_in))].sort();
  return { width, text, blockIds: selected, referenceIds, unsupported: false };
}

export function coverageGaps(width: Width): Array<{ text: string; referenceId: string }> {
  const t1 = register.tenore.find((tenor) => tenor.id === "T-001");
  const t2 = register.tenore.find((tenor) => tenor.id === "T-002");
  const appGap = t1?.nicht_umfasst.find((item) => /Mobil-App/i.test(item.beschreibung));
  const mechanismGap = t2?.nicht_umfasst.find((item) =>
    /Zwei nebeneinander|Zwei-Button/i.test(item.beschreibung),
  );
  if (width === "eng") {
    return [
      { text: appGap?.beschreibung ?? "Verlagerung in die Mobil-App", referenceId: "T-001" },
      { text: mechanismGap?.beschreibung ?? "Zwei-Button-Lösung", referenceId: "T-002" },
    ];
  }
  return [
    {
      text: mechanismGap?.beschreibung ?? "Wechsel auf eine Zwei-Button-Lösung",
      referenceId: "T-002",
    },
  ];
}

export function deriveReviewFeatures(profile: Profile, draft: Draft): ReviewFeature[] {
  const relevant = register.tenore.filter(
    (tenor) =>
      draft.referenceIds.includes(tenor.id) &&
      (tenor.fallgruppe === profile.fallgruppe || ["T-001", "T-002"].includes(tenor.id)),
  );
  const features: ReviewFeature[] = [];
  const seen = new Set<string>();
  for (const tenor of relevant) {
    for (const feature of tenor.pruefbare_merkmale) {
      if (seen.has(feature.merkmal)) continue;
      seen.add(feature.merkmal);
      features.push({ ...feature, referenzId: tenor.id });
    }
  }
  features.push({
    merkmal: `Erfassung in den gewählten Kanälen: ${profile.kanal.join(", ")}`,
    pruefung: "Je Kanal denselben rechtlichen Erfolg prüfen; Kanalwechsel getrennt dokumentieren.",
    automatisierbar: false,
    referenzId: "Profil",
  });
  return features.slice(0, 7);
}

export function nextAutofillBlock(profile: Profile, acceptedIds: string[]): BuildingBlock | null {
  const draft = composeDraft(profile, "kerngleich");
  const nextId = draft.blockIds.find((id) => !acceptedIds.includes(id));
  return nextId ? getBlock(nextId) : null;
}
