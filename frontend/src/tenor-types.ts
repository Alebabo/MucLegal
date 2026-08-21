export type Width = "eng" | "kerngleich" | "weit";

export type Profile = {
  profilId: string;
  schuldner: string;
  rechtsform: string;
  kanal: string[];
  url: string;
  adressat: "verbraucher" | "unternehmer" | "gemischt";
  vertragstyp: string;
  fallgruppe: string;
  verstossModus: string;
  rechtsgrundlage: string[];
  beanstandeterWortlaut: string;
  wirkung: string;
  bekannteUmgehungen: string[];
  gestaltungsmerkmale: string[];
  anlage: string;
};

export type BuildingBlock = {
  id: string;
  text: string;
  segment: string;
  fallgruppe?: string;
  verstoss_modus?: string[];
  status?: string;
  belegt_in: string[];
  position?: string;
  slots?: Record<string, string>;
};

export type ReferenceTenor = {
  id: string;
  fallgruppe: string;
  gericht_az: string;
  zitat_geprueft: boolean | string;
  freigabe_jurist: boolean;
  nicht_umfasst: Array<{
    beschreibung: string;
    begruendung: string;
    sicherheit: string;
    belegt_durch?: string;
  }>;
  kerngleich_umfasst: Array<{ beschreibung: string; begruendung: string; sicherheit: string }>;
  pruefbare_merkmale: Array<{
    merkmal: string;
    pruefung: string;
    automatisierbar: boolean;
    hinweis?: string;
    herkunft?: string;
  }>;
};

export type Finding = {
  typ:
    "zu_eng" | "fehlender_baustein" | "unbestimmt" | "ueberdehnt" | "normbezug" | "technikgebunden";
  schwere: "hoch" | "mittel" | "niedrig";
  quelle: "regel" | "modell";
  regel_id: string | null;
  span: { start: number; ende: number };
  zitat: string | null;
  vorschlag: string;
  baustein_id: string | null;
  begruendung: string;
  referenz_ids: string[];
  beispiel_nicht_erfasst: string | null;
  sicherheit: "hoch" | "mittel" | "niedrig";
};

export type Draft = {
  width: Width;
  text: string;
  blockIds: string[];
  referenceIds: string[];
  unsupported: boolean;
};

export type ReviewFeature = {
  merkmal: string;
  pruefung: string;
  automatisierbar: boolean;
  referenzId: string;
};
