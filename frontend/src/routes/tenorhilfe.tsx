import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  Check,
  FileUp,
  Keyboard,
  Loader2,
  Mic,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { composeDraft, getBlock, nextAutofillBlock, register } from "@/tenor-engine";
import type { Draft, Profile } from "@/tenor-types";
import { lottoDemoCases, type DemoCase } from "@/data/lottoDemoCases";

export const Route = createFileRoute("/tenorhilfe")({
  head: () => ({ meta: [{ title: "Tenorschreibhilfe – MucLegal" }] }),
  component: TenorHelpPage,
});

const baseProfile: Profile = {
  profilId: "V-2026-014",
  schuldner: "die Beklagte",
  rechtsform: "GmbH",
  kanal: ["website"],
  url: "https://www.beispiel.de",
  adressat: "verbraucher",
  vertragstyp: "dauerschuldverhaeltnis",
  fallgruppe: "kuendigungsbutton",
  verstossModus: "vorhanden_unzureichend",
  rechtsgrundlage: ["§ 2 Abs. 1 UKlaG", "§ 312k Abs. 2 BGB", "§ 890 ZPO"],
  beanstandeterWortlaut: "",
  wirkung: "",
  bekannteUmgehungen: [],
  gestaltungsmerkmale: ["Gestaltung", "Wirkung"],
  anlage: "K 1",
};

type SpeechResult = { readonly transcript: string };
type SpeechResultList = {
  readonly length: number;
  [index: number]: { [index: number]: SpeechResult };
};
type SpeechEvent = { readonly results: SpeechResultList };
type SpeechRecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;
type WritingMode = "sachverhalt" | "tenor" | "fälle";

const modeCommands: Array<{ id: WritingMode; command: string; title: string; hint: string }> = [
  {
    id: "sachverhalt",
    command: "/sachverhalt",
    title: "Sachverhalt",
    hint: "Einen neuen Verstoß beschreiben",
  },
  { id: "tenor", command: "/tenor", title: "Tenor", hint: "Einen bestehenden Tenor korrigieren" },
  { id: "fälle", command: "/fälle", title: "Fälle", hint: "Archiv und Hinweise durchsuchen" },
];

function isTenor(text: string) {
  return /(zu unterlassen|wird verurteilt|ordnungsgeld|zuwiderhandlung|der beklagten wird untersagt)/i.test(
    text,
  );
}

function assessCompleteness(text: string) {
  const checks = {
    action:
      /(kündig|button|schaltfläche|klausel|cookie|consent|tracking|werbung|rabatt|countdown|preis|vertrag|verlänger|versteckt|fehlt|irreführ)/i.test(
        text,
      ),
    channel:
      /(website|webseite|app|internet|online|domain|checkout|agb|vertrag|schreiben|e-mail|social media|filiale)/i.test(
        text,
      ),
    affected: /(verbraucher|kund|nutzer|abonnent|betroffen|privatperson|vertragspartner)/i.test(
      text,
    ),
    desired:
      /(unterlassen|künftig|soll|darf nicht|nicht mehr|muss|bereitstellen|entfernen|verbieten|untersagt)/i.test(
        text,
      ),
  };
  const question = !checks.action
    ? "Welche konkrete Handlung oder Gestaltung beanstandest du?"
    : !checks.channel
      ? "Wo genau tritt der Verstoß auf – zum Beispiel auf einer Website, in einer App oder in einem Vertrag?"
      : !checks.affected
        ? "Wer ist davon betroffen – Verbraucher, Kunden oder eine andere Gruppe?"
        : !checks.desired
          ? "Was genau soll das Unternehmen künftig unterlassen?"
          : null;
  return { complete: Object.values(checks).every(Boolean), question };
}

function caseContext(selectedCase: DemoCase) {
  return `${selectedCase.fall_id}: ${selectedCase.title}. ${selectedCase.secondary}. ${selectedCase.explanation} Fundstelle: ${selectedCase.evidence.fundstelle}.`;
}

function profileFromContext(context: string): Profile {
  const lower = context.toLowerCase();
  const fallgruppe = /klausel|agb|altvertrag/.test(lower)
    ? "agb_klausel"
    : /cookie|consent|tracking/.test(lower)
      ? "consent_gestaltung"
      : /dark pattern|checkout|versicherung/.test(lower)
        ? "dark_pattern_dsa"
        : /werbung|irreführ/.test(lower)
          ? "irrefuehrende_werbung"
          : "kuendigungsbutton";
  const verstossModus =
    fallgruppe === "agb_klausel"
      ? "klausel_verwendet"
      : fallgruppe === "kuendigungsbutton"
        ? "vorhanden_unzureichend"
        : "irrefuehrend_gestaltet";
  const url = context.match(/https?:\/\/[^\s,;)]+/i)?.[0] ?? baseProfile.url;
  return {
    ...baseProfile,
    fallgruppe,
    verstossModus,
    url,
    kanal: /\bapp\b/i.test(context) ? ["website", "app"] : ["website"],
    beanstandeterWortlaut: fallgruppe === "agb_klausel" ? context.slice(0, 500) : "",
    wirkung: context.slice(0, 500),
  };
}

function referenceSummary(draft: Draft) {
  const references = [...new Set(draft.blockIds.flatMap((id) => getBlock(id).belegt_in))];
  return `${draft.blockIds.join(" · ")}  —  ${references
    .map((id) => {
      const tenor = register.tenore.find((item) => item.id === id);
      return tenor?.zitat_geprueft === true ? id : `${id} ungeprüft`;
    })
    .join(" · ")}`;
}

function DraftChoice({
  title,
  draft,
  text,
  selected,
  onSelect,
  onText,
}: {
  title: string;
  draft: Draft;
  text: string;
  selected: boolean;
  onSelect: () => void;
  onText: (text: string) => void;
}) {
  return (
    <div className="min-w-0 px-1 py-4 md:px-8 md:py-2">
      <button type="button" onClick={onSelect} className="flex items-center gap-3 text-left">
        <span
          className={`grid size-5 place-items-center rounded-full border ${selected ? "border-slate-950 bg-slate-950" : "border-slate-300"}`}
        >
          {selected && <Check className="size-3 text-white" />}
        </span>
        <span className="text-sm font-semibold text-slate-900">{title}</span>
      </button>
      <textarea
        value={text}
        onFocus={onSelect}
        onChange={(event) => onText(event.target.value)}
        aria-label={`${title} bearbeiten`}
        className="mt-6 min-h-[360px] w-full resize-none bg-transparent font-serif text-[15px] leading-7 text-slate-700 outline-none"
      />
      <p className="mt-5 break-words font-mono text-[9px] leading-4 text-slate-300">
        {referenceSummary(draft)}
      </p>
    </div>
  );
}

function TenorHelpPage() {
  const [context, setContext] = useState("");
  const [mode, setMode] = useState<WritingMode | null>(null);
  const [selectedCase, setSelectedCase] = useState<DemoCase | null>(null);
  const [commandIndex, setCommandIndex] = useState(0);
  const [caseIndex, setCaseIndex] = useState(0);
  const [pdf, setPdf] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [dictating, setDictating] = useState(false);
  const [dictationNotice, setDictationNotice] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [selected, setSelected] = useState<"precise" | "neutral" | null>(null);
  const [preciseText, setPreciseText] = useState("");
  const [neutralText, setNeutralText] = useState("");
  const [acceptedIds, setAcceptedIds] = useState<string[]>([]);
  const [suggestion, setSuggestion] = useState<ReturnType<typeof nextAutofillBlock>>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const contextInput = useRef<HTMLTextAreaElement>(null);
  const speech = useRef<SpeechRecognitionInstance | null>(null);

  const profile = useMemo(() => profileFromContext(context), [context]);
  const preciseDraft = useMemo(() => composeDraft(profile, "eng"), [profile]);
  const neutralDraft = useMemo(() => composeDraft(profile, "kerngleich"), [profile]);
  const contextLength = context.trim().length;
  const completeness = useMemo(() => assessCompleteness(context), [context]);
  const correctionMode = mode === "tenor" || isTenor(context);
  const slashMatch = context.match(/(?:^|\s)\/([^\s]*)$/);
  const slashQuery = slashMatch?.[1]?.toLocaleLowerCase("de") ?? "";
  const showModeMenu = Boolean(slashMatch);
  const filteredCommands = modeCommands.filter((command) =>
    `${command.command} ${command.title}`.toLocaleLowerCase("de").includes(slashQuery),
  );
  const normalizedCaseQuery = context.trim().toLocaleLowerCase("de");
  const caseMatches =
    mode === "fälle" && !selectedCase
      ? lottoDemoCases
          .filter((item) =>
            `${item.title} ${item.fall_id} ${item.domain} ${item.secondary}`
              .toLocaleLowerCase("de")
              .includes(normalizedCaseQuery),
          )
          .slice(0, 5)
      : [];
  const needsMoreContext =
    mode !== "fälle" &&
    !pdf &&
    contextLength > 0 &&
    !correctionMode &&
    !completeness.complete &&
    !showModeMenu;
  const canGenerate =
    !showModeMenu &&
    (Boolean(pdf) ||
      Boolean(selectedCase) ||
      (correctionMode ? contextLength >= 20 : completeness.complete));
  const contextQuestion = completeness.question;

  useEffect(() => {
    if (!correctionMode || generated || context.trim().length < 4) {
      setSuggestion(null);
      return;
    }
    const timer = window.setTimeout(
      () => setSuggestion(nextAutofillBlock(profile, acceptedIds)),
      800,
    );
    return () => window.clearTimeout(timer);
  }, [acceptedIds, context, correctionMode, generated, profile]);

  useEffect(() => {
    setCommandIndex(0);
  }, [slashQuery]);

  useEffect(() => {
    setCaseIndex(0);
  }, [normalizedCaseQuery]);

  useEffect(() => {
    const input = contextInput.current;
    if (!input) return;
    input.style.height = "0px";
    input.style.height = `${Math.max(input.scrollHeight, 36)}px`;
  }, [context, pdf]);

  const acceptPdf = (file?: File) => {
    if (!file || (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")))
      return;
    setPdf(file);
    setGenerated(false);
  };

  const selectMode = (nextMode: WritingMode) => {
    const contextWithoutCommand = context.replace(/(?:^|\s)\/[^\s]*$/, "").trimEnd();
    setMode(nextMode);
    setSelectedCase(null);
    setContext(nextMode === "fälle" ? "" : contextWithoutCommand);
    setCommandIndex(0);
    setCaseIndex(0);
    setGenerated(false);
    setSuggestion(null);
    window.requestAnimationFrame(() => contextInput.current?.focus());
  };

  const chooseCase = (item: DemoCase) => {
    setMode("fälle");
    setSelectedCase(item);
    setCaseIndex(0);
    setContext(caseContext(item));
    setGenerated(false);
    setSuggestion(null);
    window.requestAnimationFrame(() => contextInput.current?.focus());
  };

  const toggleDictation = () => {
    if (dictating) {
      speech.current?.stop();
      setDictating(false);
      return;
    }
    const browserWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition = browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setDictationNotice("Diktat wird von diesem Browser nicht unterstützt.");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "de-DE";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1)
        transcript += `${event.results[index]?.[0]?.transcript ?? ""} `;
      setContext((current) => `${current}${current.trim() ? " " : ""}${transcript.trim()}`);
    };
    recognition.onend = () => setDictating(false);
    speech.current = recognition;
    setDictationNotice("");
    setDictating(true);
    recognition.start();
  };

  const acceptSuggestion = () => {
    if (!suggestion) return;
    setContext((current) => `${current.trim()} ${suggestion.text.replace(/\s+/g, " ").trim()}`);
    setAcceptedIds((current) => [...current, suggestion.id]);
    setSuggestion(null);
  };

  const generate = () => {
    if (!canGenerate) return;
    setGenerating(true);
    window.setTimeout(() => {
      setPreciseText(preciseDraft.text);
      setNeutralText(neutralDraft.text);
      setSelected(null);
      setGenerated(true);
      setGenerating(false);
    }, 550);
  };

  const reset = () => {
    setContext("");
    setMode(null);
    setSelectedCase(null);
    setCommandIndex(0);
    setCaseIndex(0);
    setPdf(null);
    setGenerated(false);
    setSelected(null);
    setAcceptedIds([]);
    setSuggestion(null);
  };

  const adoptSelected = () => {
    if (!selected) return;
    const draft = selected === "precise" ? preciseDraft : neutralDraft;
    setContext(selected === "precise" ? preciseText : neutralText);
    setAcceptedIds(draft.blockIds);
    setGenerated(false);
  };

  return (
    <div
      className={`min-h-screen bg-white transition-colors ${dragging ? "bg-blue-50/40" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        if (event.currentTarget === event.target) setDragging(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        acceptPdf(event.dataTransfer.files[0]);
      }}
    >
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" aria-label="Zurück" className="text-slate-300 transition hover:text-slate-700">
          <ArrowLeft className="size-4" />
        </Link>
        <span className="text-xs font-medium tracking-wide text-slate-300">Tenorschreibhilfe</span>
        {context || pdf || generated ? (
          <button
            type="button"
            onClick={reset}
            aria-label="Neu beginnen"
            className="text-slate-300 transition hover:text-slate-700"
          >
            <RotateCcw className="size-4" />
          </button>
        ) : (
          <span className="size-4" />
        )}
      </header>

      {!generated ? (
        <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-4xl flex-col px-6 pb-28 pt-[8vh]">
          {pdf && (
            <div className="mb-8 flex items-center gap-3 text-sm text-slate-500">
              <FileUp className="size-4" />
              <span className="truncate">{pdf.name}</span>
              <span className="text-[10px] text-slate-300">lokal · noch ohne Texterkennung</span>
              <button
                type="button"
                onClick={() => setPdf(null)}
                aria-label="PDF entfernen"
                className="ml-auto text-slate-300 hover:text-slate-700"
              >
                <X className="size-4" />
              </button>
            </div>
          )}
          <div
            className="min-h-[calc(100vh-17rem)] w-full flex-1 cursor-text"
            onClick={() => contextInput.current?.focus()}
          >
            <div className="flex items-start gap-2">
              {mode && (
                <strong className="max-w-[45%] shrink-0 truncate pt-[7px] text-sm leading-6 text-slate-900">
                  /{mode}
                  {selectedCase ? ` · ${selectedCase.title}` : ""}
                </strong>
              )}
              <textarea
                ref={contextInput}
                autoFocus
                value={context}
                onChange={(event) => {
                  setContext(event.target.value);
                  setGenerated(false);
                }}
                onKeyDown={(event) => {
                  const highlightedCase = caseMatches[caseIndex] ?? caseMatches[0];
                  if (showModeMenu && event.key === "ArrowDown" && filteredCommands.length > 0) {
                    event.preventDefault();
                    setCommandIndex((current) => (current + 1) % filteredCommands.length);
                    return;
                  }
                  if (showModeMenu && event.key === "ArrowUp" && filteredCommands.length > 0) {
                    event.preventDefault();
                    setCommandIndex(
                      (current) =>
                        (current - 1 + filteredCommands.length) % filteredCommands.length,
                    );
                    return;
                  }
                  if (
                    !showModeMenu &&
                    mode === "fälle" &&
                    !selectedCase &&
                    event.key === "ArrowDown" &&
                    caseMatches.length > 0
                  ) {
                    event.preventDefault();
                    setCaseIndex((current) => (current + 1) % caseMatches.length);
                    return;
                  }
                  if (
                    !showModeMenu &&
                    mode === "fälle" &&
                    !selectedCase &&
                    event.key === "ArrowUp" &&
                    caseMatches.length > 0
                  ) {
                    event.preventDefault();
                    setCaseIndex(
                      (current) => (current - 1 + caseMatches.length) % caseMatches.length,
                    );
                    return;
                  }
                  if (
                    event.key === "Backspace" &&
                    mode &&
                    event.currentTarget.selectionStart === 0 &&
                    event.currentTarget.selectionEnd === 0
                  ) {
                    event.preventDefault();
                    setMode(null);
                    setSelectedCase(null);
                    setSuggestion(null);
                    return;
                  }
                  if (event.key === "Enter" && showModeMenu && filteredCommands[commandIndex]) {
                    event.preventDefault();
                    selectMode(filteredCommands[commandIndex].id);
                    return;
                  }
                  if (
                    event.key === "Enter" &&
                    mode === "fälle" &&
                    !selectedCase &&
                    highlightedCase
                  ) {
                    event.preventDefault();
                    chooseCase(highlightedCase);
                    return;
                  }
                  if (event.key === "Tab" && suggestion) {
                    event.preventDefault();
                    acceptSuggestion();
                  }
                }}
                placeholder={
                  pdf
                    ? ""
                    : mode === "fälle"
                      ? "Tippe den Namen oder die Fall-ID …"
                      : mode === "tenor"
                        ? "Füge einen Tenor ein oder schreibe ihn weiter …"
                        : "Beschreibe den Sachverhalt oder droppe ein PDF oder diktiere den Sachverhalt …"
                }
                aria-label="Sachverhalt oder Tenor"
                rows={1}
                className="block min-h-9 min-w-0 flex-1 resize-none overflow-hidden bg-transparent font-serif text-lg leading-[1.8] text-slate-800 outline-none placeholder:text-slate-300 sm:text-xl"
              />
            </div>
            {showModeMenu && (
              <div
                className="mt-2 max-w-sm overflow-hidden rounded-lg border border-slate-200 bg-white py-0.5 shadow-md"
                onClick={(event) => event.stopPropagation()}
              >
                {filteredCommands.length > 0 ? (
                  filteredCommands.map((command, index) => (
                    <button
                      key={command.id}
                      type="button"
                      onMouseEnter={() => setCommandIndex(index)}
                      onClick={() => selectMode(command.id)}
                      className={`flex w-full items-center gap-3 px-3 py-2 text-left transition ${index === commandIndex ? "bg-slate-200" : "hover:bg-slate-100"}`}
                    >
                      <strong className="w-24 text-xs text-slate-900">{command.command}</strong>
                      <span className="truncate text-[11px] text-slate-400">{command.hint}</span>
                    </button>
                  ))
                ) : (
                  <p className="px-4 py-3 text-sm text-slate-400">Kein passender Modus</p>
                )}
              </div>
            )}
            {mode === "fälle" && !selectedCase && !showModeMenu && (
              <div
                className="ml-14 mt-1 max-w-sm overflow-hidden rounded-lg border border-slate-200 bg-white py-0.5 shadow-md"
                onClick={(event) => event.stopPropagation()}
              >
                {caseMatches.length > 0 ? (
                  caseMatches.map((item, index) => (
                    <button
                      key={item.case_id}
                      type="button"
                      aria-current={index === caseIndex ? "true" : undefined}
                      onMouseEnter={() => setCaseIndex(index)}
                      onClick={() => chooseCase(item)}
                      className={`flex w-full items-baseline gap-2 px-3 py-1.5 text-left transition ${index === caseIndex ? "bg-slate-200" : "hover:bg-slate-100"}`}
                    >
                      <span className="truncate text-xs font-semibold text-slate-900">
                        {item.title}
                      </span>
                      <span className="ml-auto shrink-0 font-mono text-[9px] text-slate-300">
                        {item.fall_id}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="px-3 py-2 text-xs text-slate-400">Kein Fall gefunden.</p>
                )}
              </div>
            )}
            {needsMoreContext && contextQuestion && (
              <p className="mt-2 text-sm leading-6 text-slate-300">{contextQuestion}</p>
            )}
            {suggestion && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  acceptSuggestion();
                }}
                className="mt-3 flex items-start gap-3 text-left text-sm leading-6 text-slate-300 transition hover:text-slate-500"
              >
                <span className="mt-1 flex shrink-0 items-center gap-1 font-mono text-[10px] text-slate-400">
                  <Keyboard className="size-3" />
                  Tab
                </span>
                <span>{suggestion.text.replace(/\s+/g, " ")}</span>
              </button>
            )}
          </div>

          <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-100 bg-white/95 backdrop-blur">
            <div className="mx-auto flex min-h-20 max-w-4xl items-center justify-between px-6">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  aria-label="PDF hochladen"
                  className="rounded-full p-3 text-slate-300 transition hover:bg-slate-50 hover:text-slate-700"
                >
                  <FileUp className="size-5" />
                </button>
                <button
                  type="button"
                  onClick={toggleDictation}
                  aria-label={dictating ? "Diktat beenden" : "Sachverhalt diktieren"}
                  className={`rounded-full p-3 transition ${dictating ? "bg-red-50 text-red-500" : "text-slate-300 hover:bg-slate-50 hover:text-slate-700"}`}
                >
                  <Mic className="size-5" />
                </button>
                <input
                  ref={fileInput}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(event) => acceptPdf(event.target.files?.[0])}
                />
                {correctionMode && (
                  <span className="ml-2 text-[10px] uppercase tracking-wider text-slate-300">
                    Tenor erkannt · Korrekturmodus
                  </span>
                )}
                {dictationNotice && (
                  <span className="ml-2 text-xs text-slate-400">{dictationNotice}</span>
                )}
              </div>
              {canGenerate && (
                <button
                  type="button"
                  onClick={generate}
                  disabled={generating}
                  className="flex items-center gap-2 rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
                >
                  {generating ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Sparkles className="size-4" />
                  )}
                  Generieren
                </button>
              )}
            </div>
          </div>
        </main>
      ) : (
        <main className="mx-auto max-w-6xl px-6 pb-16 pt-12">
          <h1 className="text-center font-sans text-sm font-medium text-slate-400">
            Wähle einen Entwurf
          </h1>
          <div className="mt-12 grid md:grid-cols-2 md:divide-x md:divide-slate-100">
            <DraftChoice
              title="Präzise"
              draft={preciseDraft}
              text={preciseText}
              selected={selected === "precise"}
              onSelect={() => setSelected("precise")}
              onText={setPreciseText}
            />
            <DraftChoice
              title="Technikneutral"
              draft={neutralDraft}
              text={neutralText}
              selected={selected === "neutral"}
              onSelect={() => setSelected("neutral")}
              onText={setNeutralText}
            />
          </div>
          {selected && (
            <div className="mt-10 flex justify-center">
              <button
                type="button"
                onClick={adoptSelected}
                className="rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white"
              >
                Entwurf übernehmen
              </button>
            </div>
          )}
        </main>
      )}
    </div>
  );
}
