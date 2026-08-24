import { Link } from "@tanstack/react-router";
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
import {
  assessCompleteness,
  filterModeCommands,
  inferFallgruppe,
  isTenor,
  modeCommands,
  nextWrappedIndex,
  type WritingMode,
} from "@/lib/minimal-tenor-logic";
import {
  composeDictationText,
  mergeDictationSegments,
  type DictationSegments,
} from "@/lib/dictation";
import { createTenorProposals, type TenorProposalResponse } from "@/lib/tenor-api";

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
  [index: number]: { readonly isFinal: boolean; [index: number]: SpeechResult };
};
type SpeechEvent = { readonly resultIndex: number; readonly results: SpeechResultList };
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
function caseContext(selectedCase: DemoCase) {
  return `${selectedCase.fall_id}: ${selectedCase.title}. ${selectedCase.secondary}. ${selectedCase.explanation} Fundstelle: ${selectedCase.evidence.fundstelle}.`;
}

function profileFromContext(context: string): Profile {
  const lower = context.toLowerCase();
  const fallgruppe = inferFallgruppe(lower);
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

function legalBasesFor(fallgruppe: string) {
  if (fallgruppe === "agb_klausel") return ["§ 1 UKlaG"];
  if (fallgruppe === "irrefuehrende_werbung") return ["§ 5 UWG", "§ 8 Abs. 1 UWG"];
  if (fallgruppe === "consent_gestaltung") return ["§ 25 Abs. 1 TDDDG", "§ 2 Abs. 1 UKlaG"];
  if (fallgruppe === "dark_pattern_dsa") return ["Art. 25 DSA", "§ 2 Abs. 1 UKlaG"];
  return ["§ 312k Abs. 2 BGB", "§ 2 Abs. 1 UKlaG"];
}

function debtorFromContext(context: string) {
  const match = context.match(
    /\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&.,' -]{1,100}\s(?:GmbH|AG|UG|SE|KG|e\.\s?K\.))\b/,
  );
  return match?.[1]?.trim() ?? "die Antragsgegnerin";
}

function aiProvenance(response: TenorProposalResponse | null, strategy: "precise" | "neutral") {
  const proposal = response?.proposals.find((item) => item.strategy === strategy);
  if (!response || !proposal) return null;
  const knowledgeLabel = response.reference_version.includes("2026-08-24")
    ? "Wissensbasis 24.08.2026"
    : response.reference_version;
  return `OpenAI ${response.model} · ${knowledgeLabel} · ${proposal.source_ids.length} Quellenanker · nicht juristisch freigegeben`;
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
  provenance,
  expanded = false,
}: {
  title: string;
  draft: Draft;
  text: string;
  selected: boolean;
  onSelect: () => void;
  onText: (text: string) => void;
  provenance?: string | null;
  expanded?: boolean;
}) {
  return (
    <div
      className={`flex min-w-0 flex-col ${
        expanded
          ? "min-h-[64dvh] flex-1 px-0 py-2 md:min-h-0"
          : "px-1 py-4 md:min-h-0 md:px-6 md:py-1"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className={`flex items-center gap-3 text-left ${expanded ? "min-h-11" : ""}`}
      >
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
        className={`w-full overflow-y-auto bg-transparent font-serif text-slate-700 outline-none ${
          expanded
            ? "mt-4 min-h-[56dvh] resize-y text-base leading-8 md:min-h-0 md:flex-1"
            : "mt-3 min-h-48 resize-none text-sm leading-6 md:min-h-0 md:flex-1"
        }`}
      />
      <p className="mt-3 break-words font-mono text-[9px] leading-4 text-slate-300">
        {provenance ?? referenceSummary(draft)}
      </p>
    </div>
  );
}

export function MinimalTenorView() {
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
  const [proposalResponse, setProposalResponse] = useState<TenorProposalResponse | null>(null);
  const [generationError, setGenerationError] = useState("");
  const [acceptedIds, setAcceptedIds] = useState<string[]>([]);
  const [suggestion, setSuggestion] = useState<ReturnType<typeof nextAutofillBlock>>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const contextInput = useRef<HTMLTextAreaElement>(null);
  const speech = useRef<SpeechRecognitionInstance | null>(null);
  const dictationBase = useRef("");
  const dictationSegments = useRef<DictationSegments>({});
  const dictationSession = useRef(0);

  const profile = useMemo(() => profileFromContext(context), [context]);
  const preciseDraft = useMemo(() => composeDraft(profile, "eng"), [profile]);
  const neutralDraft = useMemo(() => composeDraft(profile, "kerngleich"), [profile]);
  const contextLength = context.trim().length;
  const completeness = useMemo(() => assessCompleteness(context), [context]);
  const correctionMode = mode === "tenor" || isTenor(context);
  const slashMatch = context.match(/(?:^|\s)\/([^\s]*)$/);
  const slashQuery = slashMatch?.[1]?.toLocaleLowerCase("de") ?? "";
  const showModeMenu = Boolean(slashMatch);
  const filteredCommands = filterModeCommands(slashQuery);
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
    contextLength > 0 &&
    !correctionMode &&
    !completeness.complete &&
    !showModeMenu;
  const canGenerate =
    !showModeMenu &&
    (Boolean(selectedCase) || (correctionMode ? contextLength >= 20 : completeness.complete));
  const contextQuestion = completeness.nextQuestion;

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

  useEffect(
    () => () => {
      dictationSession.current += 1;
      speech.current?.stop();
    },
    [],
  );

  const acceptPdf = (file?: File) => {
    if (!file || (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")))
      return;
    setPdf(file);
    setGenerated(false);
    setGenerationError("");
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
    setGenerationError("");
    window.requestAnimationFrame(() => contextInput.current?.focus());
  };

  const chooseCase = (item: DemoCase) => {
    setMode("fälle");
    setSelectedCase(item);
    setCaseIndex(0);
    setContext(caseContext(item));
    setGenerated(false);
    setSuggestion(null);
    setGenerationError("");
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
    const session = dictationSession.current + 1;
    dictationSession.current = session;
    dictationBase.current = context;
    dictationSegments.current = {};
    recognition.lang = "de-DE";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      if (dictationSession.current !== session) return;
      const updates = [];
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        updates.push({
          index,
          transcript: result?.[0]?.transcript ?? "",
          isFinal: result?.isFinal ?? false,
        });
      }
      dictationSegments.current = mergeDictationSegments(dictationSegments.current, updates);
      setContext(composeDictationText(dictationBase.current, dictationSegments.current));
    };
    recognition.onend = () => {
      if (dictationSession.current !== session) return;
      speech.current = null;
      setDictating(false);
    };
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

  const generate = async () => {
    if (!canGenerate || generating) return;
    setGenerating(true);
    setGenerationError("");
    setSuggestion(null);
    try {
      const response = await createTenorProposals({
        fall_id: selectedCase?.fall_id ?? "TENOR-ENTWURF",
        schuldner: debtorFromContext(context),
        fundstelle:
          selectedCase?.url ??
          context.match(/https?:\/\/[^\s,;)]+/i)?.[0] ??
          "Vom Nutzer beschriebene Fundstelle",
        context,
        fallgruppe: profile.fallgruppe,
        rechtsgrundlagen: legalBasesFor(profile.fallgruppe),
      });
      const precise = response.proposals.find((item) => item.strategy === "precise");
      const neutral = response.proposals.find((item) => item.strategy === "neutral");
      if (!precise || !neutral) throw new Error("Die KI hat nicht beide Entwürfe geliefert.");
      setProposalResponse(response);
      setPreciseText(precise.text);
      setNeutralText(neutral.text);
      setSelected(null);
      setGenerated(true);
    } catch (error) {
      setProposalResponse(null);
      setGenerationError(
        error instanceof Error ? error.message : "Die KI-Entwürfe konnten nicht erzeugt werden.",
      );
    } finally {
      setGenerating(false);
    }
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
    setProposalResponse(null);
    setGenerationError("");
    setAcceptedIds([]);
    setSuggestion(null);
  };

  const adoptSelected = () => {
    if (!selected) return;
    const draft = selected === "precise" ? preciseDraft : neutralDraft;
    setContext(selected === "precise" ? preciseText : neutralText);
    setAcceptedIds(draft.blockIds);
    setGenerated(false);
    setSelected(null);
  };

  return (
    <div
      className={`min-h-[calc(100dvh-4rem)] bg-white transition-colors ${dragging ? "bg-blue-50/40" : ""}`}
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
                  if (dictating) {
                    dictationSession.current += 1;
                    speech.current?.stop();
                    speech.current = null;
                    setDictating(false);
                  }
                  setContext(event.target.value);
                  setGenerated(false);
                  setGenerationError("");
                }}
                onKeyDown={(event) => {
                  if (event.nativeEvent.isComposing) return;
                  const highlightedCase = caseMatches[caseIndex] ?? caseMatches[0];
                  if (showModeMenu && event.key === "ArrowDown" && filteredCommands.length > 0) {
                    event.preventDefault();
                    setCommandIndex((current) =>
                      nextWrappedIndex(current, filteredCommands.length, 1),
                    );
                    return;
                  }
                  if (showModeMenu && event.key === "ArrowUp" && filteredCommands.length > 0) {
                    event.preventDefault();
                    setCommandIndex((current) =>
                      nextWrappedIndex(current, filteredCommands.length, -1),
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
                    setCaseIndex((current) => nextWrappedIndex(current, caseMatches.length, 1));
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
                    setCaseIndex((current) => nextWrappedIndex(current, caseMatches.length, -1));
                    return;
                  }
                  if (event.key === "Escape" && showModeMenu) {
                    event.preventDefault();
                    setContext((current) => current.replace(/(?:^|\s)\/[^\s]*$/, "").trimEnd());
                    return;
                  }
                  if (event.key === "Escape" && mode === "fälle" && !selectedCase) {
                    event.preventDefault();
                    setMode(null);
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
                role="listbox"
                aria-label="Schreibmodus wählen"
                className="mt-2 max-w-sm overflow-hidden rounded-lg border border-slate-200 bg-white py-0.5 shadow-md"
                onClick={(event) => event.stopPropagation()}
              >
                {filteredCommands.length > 0 ? (
                  filteredCommands.map((command, index) => (
                    <button
                      key={command.id}
                      type="button"
                      role="option"
                      aria-selected={index === commandIndex}
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
                role="listbox"
                aria-label="Fall auswählen"
                className="ml-14 mt-1 max-w-sm overflow-hidden rounded-lg border border-slate-200 bg-white py-0.5 shadow-md"
                onClick={(event) => event.stopPropagation()}
              >
                {caseMatches.length > 0 ? (
                  caseMatches.map((item, index) => (
                    <button
                      key={item.case_id}
                      type="button"
                      role="option"
                      aria-selected={index === caseIndex}
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
                {generationError && (
                  <span role="alert" className="ml-2 max-w-md text-xs text-red-600">
                    {generationError}
                  </span>
                )}
              </div>
              {canGenerate && (
                <button
                  type="button"
                  onClick={generate}
                  disabled={generating}
                  aria-busy={generating}
                  className="flex items-center gap-2 rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
                >
                  {generating ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Sparkles className="size-4" />
                  )}
                  <span aria-live="polite">
                    {generating ? "KI erstellt zwei Entwürfe …" : "Generieren"}
                  </span>
                </button>
              )}
            </div>
          </div>
        </main>
      ) : (
        <main
          className={`mx-auto flex max-w-6xl flex-col px-6 py-8 md:py-6 ${
            selected
              ? "md:h-[calc(100dvh-2rem)] md:min-h-[38rem]"
              : "md:h-[calc(100dvh-8rem)] md:min-h-[30rem]"
          }`}
        >
          {selected ? (
            <>
              <div className="flex items-center justify-between gap-4">
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="flex items-center gap-2 text-sm text-slate-400 transition hover:text-slate-800"
                >
                  <ArrowLeft className="size-4" /> Beide Entwürfe
                </button>
                <span className="text-xs text-slate-300">Breite Lese- und Bearbeitungsansicht</span>
              </div>
              <div className="mx-auto mt-4 flex min-h-[64dvh] w-full max-w-5xl flex-1 flex-col md:min-h-0">
                <DraftChoice
                  title={selected === "precise" ? "Präzise" : "Technikneutral"}
                  draft={selected === "precise" ? preciseDraft : neutralDraft}
                  text={selected === "precise" ? preciseText : neutralText}
                  selected
                  onSelect={() => undefined}
                  onText={selected === "precise" ? setPreciseText : setNeutralText}
                  provenance={aiProvenance(proposalResponse, selected)}
                  expanded
                />
              </div>
              <div className="mt-4 flex min-h-11 items-center justify-center">
                <button
                  type="button"
                  onClick={adoptSelected}
                  className="rounded-full bg-slate-950 px-6 py-2.5 text-sm font-semibold text-white"
                >
                  Entwurf übernehmen
                </button>
              </div>
            </>
          ) : (
            <>
              <h1 className="text-center font-sans text-sm font-medium text-slate-400">
                Wähle einen Entwurf
              </h1>
              <div className="mt-5 grid md:min-h-0 md:flex-1 md:grid-cols-2 md:divide-x md:divide-slate-100">
                <DraftChoice
                  title="Präzise"
                  draft={preciseDraft}
                  text={preciseText}
                  selected={false}
                  onSelect={() => setSelected("precise")}
                  onText={setPreciseText}
                  provenance={aiProvenance(proposalResponse, "precise")}
                />
                <DraftChoice
                  title="Technikneutral"
                  draft={neutralDraft}
                  text={neutralText}
                  selected={false}
                  onSelect={() => setSelected("neutral")}
                  onText={setNeutralText}
                  provenance={aiProvenance(proposalResponse, "neutral")}
                />
              </div>
              <div className="mt-4 min-h-11" />
            </>
          )}
        </main>
      )}
    </div>
  );
}
