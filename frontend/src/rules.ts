import { getBlock, register } from "./tenor-engine";
import type { Finding, Profile } from "./tenor-types";

type RuleRecord = {
  id: string;
  meldung: string;
  schwere: Finding["schwere"];
  referenz?: string[];
  vorschlag?: string;
  vorschlag_baustein?: string;
};

function record(id: string): RuleRecord {
  const found = register.pruefregeln.find((item) => item.id === id);
  if (!found) throw new Error(`Prüfregel ${id} fehlt im Register.`);
  return found as RuleRecord;
}

function finding(id: string, overrides: Partial<Finding> = {}): Finding {
  const rule = record(id);
  return {
    typ: "unbestimmt",
    schwere: rule.schwere,
    quelle: "regel",
    regel_id: id,
    span: { start: 0, ende: 0 },
    zitat: null,
    vorschlag:
      rule.vorschlag ??
      (rule.vorschlag_baustein
        ? getBlock(rule.vorschlag_baustein).text
        : "Sachverhalt und Bausteinauswahl prüfen."),
    baustein_id: rule.vorschlag_baustein ?? null,
    begruendung: rule.meldung,
    referenz_ids: rule.referenz ?? [],
    beispiel_nicht_erfasst: null,
    sicherheit: "hoch",
    ...overrides,
  };
}

export function runDeterministicRules(
  profile: Profile,
  blockIds: string[],
  text: string,
): Finding[] {
  const findings: Finding[] = [];
  const hasSegment = (segment: string) => blockIds.some((id) => getBlock(id).segment === segment);
  const hasDomainScope = blockIds.includes("B-AB-02") || blockIds.includes("B-AB-04");

  // R-01: Keine Ordnungsmittelandrohung.
  if (!hasSegment("ordnungsmittelandrohung"))
    findings.push(finding("R-01", { typ: "fehlender_baustein", baustein_id: "B-OM-03" }));

  // R-02: Juristische Person ohne benannte Vollstreckungsperson.
  if (
    hasSegment("ordnungsmittelandrohung") &&
    blockIds.includes("B-OM-04") &&
    Boolean(profile.rechtsform)
  ) {
    findings.push(
      finding("R-02", {
        typ: "unbestimmt",
        baustein_id: "B-OM-03",
        zitat: getBlock("B-OM-04").text,
      }),
    );
  }

  // R-03: UKlaG-Klausel ohne Doppelausspruch.
  if (
    profile.fallgruppe === "agb_klausel" &&
    profile.rechtsgrundlage.some((norm) => /§\s*[12]\s*UKlaG/.test(norm)) &&
    !blockIds.includes("B-VH-43")
  ) {
    findings.push(
      finding("R-03", {
        typ: "zu_eng",
        baustein_id: "B-VH-43",
        beispiel_nicht_erfasst: "Berufen auf die Klausel in Altverträgen",
      }),
    );
  }

  // R-04: Klauselfall ohne Inhaltsgleichheitsformel.
  if (profile.fallgruppe === "agb_klausel" && !blockIds.includes("B-VH-42")) {
    findings.push(
      finding("R-04", {
        typ: "zu_eng",
        baustein_id: "B-VH-42",
        beispiel_nicht_erfasst: "Sprachlich umformulierte Klausel mit gleichem Regelungsgehalt",
      }),
    );
  }

  // R-05: Abstrakter Verbotsteil ohne konkrete Verletzungsform.
  if (hasSegment("verbotene_handlung") && !hasSegment("konkrete_verletzungsform")) {
    findings.push(finding("R-05", { typ: "unbestimmt", baustein_id: "B-KV-03" }));
  }

  // R-06: Domainbindung trotz mehrerer Kanäle.
  if (hasDomainScope && profile.kanal.length > 1) {
    findings.push(
      finding("R-06", {
        typ: "zu_eng",
        zitat: profile.url,
        beispiel_nicht_erfasst: "Verlagerung der Kündigungsstrecke in die Mobil-App",
      }),
    );
  }

  // R-07: Bekannte Umgehung plus Domainbindung.
  if (hasDomainScope && profile.bekannteUmgehungen.length > 0) {
    findings.push(
      finding("R-07", {
        typ: "zu_eng",
        beispiel_nicht_erfasst: profile.bekannteUmgehungen[0] ?? null,
        baustein_id: "B-AB-03",
      }),
    );
  }

  // R-08: Art. 25 DSA fälschlich als Anspruchsgrundlage.
  if (profile.rechtsgrundlage.some((norm) => /Art\.\s*25\s*DSA.*Anspruchsgrundlage/i.test(norm))) {
    findings.push(
      finding("R-08", {
        typ: "normbezug",
        zitat: "Art. 25 DSA als Anspruchsgrundlage",
        baustein_id: null,
      }),
    );
  }

  // R-09: Veraltete Bezeichnung TTDSG.
  if (profile.rechtsgrundlage.some((norm) => /§\s*25\s*TTDSG/i.test(norm))) {
    findings.push(
      finding("R-09", {
        typ: "normbezug",
        zitat: "§ 25 TTDSG",
        vorschlag: "§ 25 TDDDG",
        sicherheit: "hoch",
      }),
    );
  }

  // R-10: Dark Pattern nur über ein Gestaltungsmerkmal beschrieben.
  if (profile.fallgruppe === "dark_pattern_dsa" && profile.gestaltungsmerkmale.length <= 1) {
    findings.push(finding("R-10", { typ: "ueberdehnt", zitat: text || null, sicherheit: "hoch" }));
  }

  return findings;
}
