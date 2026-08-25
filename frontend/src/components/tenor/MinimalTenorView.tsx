import { Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  Check,
  FileUp,
  Keyboard,
  Loader2,
  Mic,
  RotateCcw,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { nextAutofillBlock } from "@/tenor-engine";
import type { Profile } from "@/tenor-types";
import { lottoDemoCases, type DemoCase } from "@/data/lottoDemoCases";
import {
  composeRevisionContext,
  extractLegalBases,
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
import {
  createTenorProposals,
  createTenorQuestion,
  extractTenorPdf,
  listTenorArchiveEntries,
  saveTenorArchiveEntry,
  type TenorArchiveRecord,
  type TenorPdfExtraction,
  type TenorProposalResponse,
  type TenorQuestion,
} from "@/lib/tenor-api";
import {
  answeredQuestions,
  composeClarifiedContext,
  composePdfContext,
  formatSliderAnswer,
  type ClarificationTurn,
} from "@/lib/tenor-questions";
import { Slider } from "@/components/ui/slider";

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

function profileFromContext(context: string, uploadedContract = false): Profile {
  const lower = context.toLowerCase();
  const fallgruppe = inferFallgruppe(lower, uploadedContract);
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

function debtorFromContext(context: string) {
  const match = context.match(
    /\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&.,' -]{1,100}\s(?:GmbH|AG|UG|SE|KG|e\.\s?K\.))\b/,
  );
  return match?.[1]?.trim() ?? null;
}

function aiProvenance(response: TenorProposalResponse | null) {
  const proposal = response?.proposal;
  if (!response || !proposal) return null;
  return `OpenAI ${response.model} · ${response.reference_version} · ${proposal.source_ids.length} verifizierte Quellenanker · nicht juristisch freigegeben`;
}

function DraftChoice({
  title,
  text,
  onText,
  provenance,
}: {
  title: string;
  text: string;
  onText: (text: string) => void;
  provenance?: string | null;
}) {
  return (
    <div className="flex min-h-[64dvh] min-w-0 flex-1 flex-col px-0 py-2 md:min-h-0">
      <div className="flex min-h-11 items-center gap-3 text-left">
        <span className="grid size-5 place-items-center rounded-full border border-slate-950 bg-slate-950">
          <Check className="size-3 text-white" />
        </span>
        <span className="text-sm font-semibold text-slate-900">{title}</span>
      </div>
      <textarea
        value={text}
        onChange={(event) => onText(event.target.value)}
        aria-label={`${title} bearbeiten`}
        className="mt-4 min-h-[56dvh] w-full resize-y overflow-y-auto bg-transparent font-serif text-base leading-8 text-slate-700 outline-none md:min-h-0 md:flex-1"
      />
      <p className="mt-3 break-words font-mono text-[9px] leading-4 text-slate-300">
        {provenance ?? "Nicht juristisch freigegebener UE-Entwurf"}
      </p>
    </div>
  );
}

export function MinimalTenorView({ initialArchiveId }: { initialArchiveId?: string | undefined }) {
  const [context, setContext] = useState("");
  const [mode, setMode] = useState<WritingMode | null>(null);
  const [selectedCase, setSelectedCase] = useState<DemoCase | null>(null);
  const [commandIndex, setCommandIndex] = useState(0);
  const [caseIndex, setCaseIndex] = useState(0);
  const [pdf, setPdf] = useState<File | null>(null);
  const [pdfExtraction, setPdfExtraction] = useState<TenorPdfExtraction | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [dictating, setDictating] = useState(false);
  const [dictationNotice, setDictationNotice] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [proposalText, setProposalText] = useState("");
  const [proposalResponse, setProposalResponse] = useState<TenorProposalResponse | null>(null);
  const [violationBranch, setViolationBranch] = useState<"A" | "B" | "C" | null>(null);
  const [generationError, setGenerationError] = useState("");
  const [archiveError, setArchiveError] = useState("");
  const [savingArchive, setSavingArchive] = useState(false);
  const [activeArchive, setActiveArchive] = useState<TenorArchiveRecord | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveLoadError, setArchiveLoadError] = useState("");
  const [revisionInput, setRevisionInput] = useState("");
  const [revisionHistory, setRevisionHistory] = useState<string[]>([]);
  const [lastGenerationContext, setLastGenerationContext] = useState("");
  const [clarificationTurns, setClarificationTurns] = useState<ClarificationTurn[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<TenorQuestion | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);
  const [clarificationReady, setClarificationReady] = useState(false);
  const [questionError, setQuestionError] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [customChoiceOpen, setCustomChoiceOpen] = useState(false);
  const [sliderAnswer, setSliderAnswer] = useState(0);
  const [acceptedIds, setAcceptedIds] = useState<string[]>([]);
  const [suggestion, setSuggestion] = useState<ReturnType<typeof nextAutofillBlock>>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const contextInput = useRef<HTMLTextAreaElement>(null);
  const speech = useRef<SpeechRecognitionInstance | null>(null);
  const dictationBase = useRef("");
  const dictationSegments = useRef<DictationSegments>({});
  const dictationSession = useRef(0);
  const pdfSession = useRef(0);
  const questionSession = useRef(0);
  const sourceContext = useMemo(
    () => composePdfContext(context, pdfExtraction),
    [context, pdfExtraction],
  );
  const previousSourceContext = useRef(sourceContext);

  const factualContext = sourceContext;

  const clarifiedContext = useMemo(
    () => composeClarifiedContext(factualContext, clarificationTurns),
    [clarificationTurns, factualContext],
  );
  const profile = useMemo(
    () => profileFromContext(clarifiedContext, Boolean(pdfExtraction)),
    [clarifiedContext, pdfExtraction],
  );
  const contextLength = sourceContext.length;
  const correctionMode = mode === "tenor" || isTenor(sourceContext);
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
  const canRequestQuestions =
    !showModeMenu &&
    !correctionMode &&
    (mode !== "fälle" || Boolean(selectedCase)) &&
    contextLength >= 20 &&
    !pdfLoading &&
    !clarificationReady;
  const canGenerate =
    !showModeMenu &&
    !correctionMode &&
    !pdfLoading &&
    clarificationReady &&
    (Boolean(selectedCase) || clarifiedContext.length >= 20);

  useEffect(() => {
    if (!initialArchiveId) return;
    let cancelled = false;
    setArchiveLoading(true);
    setArchiveLoadError("");
    void listTenorArchiveEntries()
      .then(({ tenors }) => {
        if (cancelled) return;
        const archivedTenor = tenors.find((item) => item.tenor_id === initialArchiveId);
        if (!archivedTenor) {
          setArchiveLoadError("Der archivierte Tenor wurde nicht gefunden.");
          return;
        }
        setActiveArchive(archivedTenor);
        setMode("tenor");
        setContext(archivedTenor.text);
        setSelectedCase(null);
        setGenerated(false);
        setRevisionInput("");
        setRevisionHistory([]);
        setLastGenerationContext("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setArchiveLoadError(
          error instanceof Error ? error.message : "Das Tenorarchiv konnte nicht geladen werden.",
        );
      })
      .finally(() => {
        if (!cancelled) setArchiveLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialArchiveId]);

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

  useEffect(() => {
    if (previousSourceContext.current === sourceContext) return;
    previousSourceContext.current = sourceContext;
    questionSession.current += 1;
    setClarificationTurns([]);
    setCurrentQuestion(null);
    setQuestionLoading(false);
    setClarificationReady(false);
    setQuestionError("");
    setTextAnswer("");
    setCustomChoiceOpen(false);
    setViolationBranch(null);
  }, [sourceContext]);

  useEffect(
    () => () => {
      dictationSession.current += 1;
      pdfSession.current += 1;
      speech.current?.stop();
    },
    [],
  );

  const acceptPdf = async (file?: File) => {
    if (!file) return;
    const session = pdfSession.current + 1;
    pdfSession.current = session;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setPdf(null);
      setPdfExtraction(null);
      setPdfLoading(false);
      setPdfError("Bitte eine PDF-Datei auswählen.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setPdf(file);
      setPdfExtraction(null);
      setPdfLoading(false);
      setPdfError("Die PDF-Datei darf höchstens 10 MB groß sein.");
      return;
    }
    setPdf(file);
    setPdfExtraction(null);
    setPdfLoading(true);
    setPdfError("");
    setGenerated(false);
    setGenerationError("");
    try {
      const extraction = await extractTenorPdf(file);
      if (pdfSession.current !== session) return;
      setPdfExtraction(extraction);
    } catch (error) {
      if (pdfSession.current !== session) return;
      setPdfError(
        error instanceof Error ? error.message : "Der PDF-Text konnte nicht gelesen werden.",
      );
    } finally {
      if (pdfSession.current === session) setPdfLoading(false);
    }
  };

  const removePdf = () => {
    pdfSession.current += 1;
    setPdf(null);
    setPdfExtraction(null);
    setPdfLoading(false);
    setPdfError("");
  };

  const selectMode = (nextMode: WritingMode) => {
    const contextWithoutCommand = context.replace(/(?:^|\s)\/[^\s]*$/, "").trimEnd();
    setMode(nextMode);
    setSelectedCase(null);
    setActiveArchive(null);
    setRevisionInput("");
    setRevisionHistory([]);
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
    setActiveArchive(null);
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

  const requestClarificationQuestion = async (turns = clarificationTurns) => {
    if (sourceContext.length < 20 || questionLoading || pdfLoading) return;
    const session = questionSession.current + 1;
    questionSession.current = session;
    setQuestionLoading(true);
    setQuestionError("");
    setCurrentQuestion(null);
    try {
      const response = await createTenorQuestion({
        context: factualContext,
        fallgruppe: profile.fallgruppe,
        answered_questions: answeredQuestions(turns),
      });
      if (questionSession.current !== session) return;
      setViolationBranch(response.violation_branch);
      if (response.ready_to_generate) {
        setClarificationReady(true);
        return;
      }
      if (!response.question) throw new Error("Die KI hat keine Rückfrage geliefert.");
      setCurrentQuestion(response.question);
      setTextAnswer("");
      setCustomChoiceOpen(false);
      if (response.question.slider) {
        const { minimum, maximum, step } = response.question.slider;
        const steps = Math.floor((maximum - minimum) / step);
        setSliderAnswer(minimum + Math.floor(steps / 2) * step);
      }
    } catch (error) {
      if (questionSession.current !== session) return;
      setQuestionError(
        error instanceof Error ? error.message : "Die KI-Rückfrage konnte nicht erzeugt werden.",
      );
    } finally {
      if (questionSession.current === session) setQuestionLoading(false);
    }
  };

  const answerCurrentQuestion = (answer: string) => {
    const cleanedAnswer = answer.trim();
    if (!currentQuestion || !cleanedAnswer || questionLoading) return;
    const nextTurns = [...clarificationTurns, { question: currentQuestion, answer: cleanedAnswer }];
    setClarificationTurns(nextTurns);
    setCurrentQuestion(null);
    setTextAnswer("");
    setCustomChoiceOpen(false);
    void requestClarificationQuestion(nextTurns);
  };

  const generateProposals = async (generationContext: string) => {
    if (generating || generationContext.trim().length < 4) return;
    setGenerating(true);
    setGenerationError("");
    setSuggestion(null);
    setLastGenerationContext(generationContext);
    try {
      const legalBases = extractLegalBases(generationContext);
      const schuldner = activeArchive?.schuldner ?? debtorFromContext(generationContext);
      if (!schuldner) {
        throw new Error(
          "Für einen bestimmten UE-Entwurf fehlt die genaue Bezeichnung des Schuldners.",
        );
      }
      const response = await createTenorProposals({
        fall_id: activeArchive?.fall_id ?? selectedCase?.fall_id ?? "TENOR-ENTWURF",
        schuldner,
        fundstelle:
          selectedCase?.url ??
          generationContext.match(/https?:\/\/[^\s,;)]+/i)?.[0] ??
          (pdfExtraction ? `Hochgeladenes Vertragsdokument: ${pdfExtraction.filename}` : null),
        context: generationContext,
        fallgruppe: profile.fallgruppe,
        rechtsgrundlagen: legalBases,
        violation_branch: violationBranch,
      });
      setProposalResponse(response);
      setViolationBranch(response.violation_branch);
      if (response.status !== "ready" || !response.proposal) {
        const details = response.missing_information.join(", ");
        throw new Error(`Der UE-Entwurf ist noch nicht bestimmt genug. Es fehlen: ${details}`);
      }
      setProposalText(response.proposal.text);
      setGenerated(true);
    } catch (error) {
      setProposalResponse(null);
      setGenerationError(
        error instanceof Error ? error.message : "Der KI-Entwurf konnte nicht erzeugt werden.",
      );
    } finally {
      setGenerating(false);
    }
  };

  const generate = () => {
    if (!canGenerate) return;
    void generateProposals(clarifiedContext);
  };

  const submitRevision = () => {
    const instruction = revisionInput.trim();
    if (!instruction || generating || context.trim().length < 4) return;
    const revisionContext = composeRevisionContext(
      context,
      instruction,
      activeArchive?.context ?? "",
    );
    setRevisionHistory((current) => [...current, instruction]);
    setRevisionInput("");
    void generateProposals(revisionContext);
  };

  const reset = () => {
    setContext("");
    setMode(null);
    setSelectedCase(null);
    setCommandIndex(0);
    setCaseIndex(0);
    pdfSession.current += 1;
    setPdf(null);
    setPdfExtraction(null);
    setPdfLoading(false);
    setPdfError("");
    setGenerated(false);
    setProposalText("");
    setProposalResponse(null);
    setViolationBranch(null);
    setGenerationError("");
    setArchiveError("");
    setSavingArchive(false);
    setActiveArchive(null);
    setArchiveLoading(false);
    setArchiveLoadError("");
    setRevisionInput("");
    setRevisionHistory([]);
    setLastGenerationContext("");
    questionSession.current += 1;
    setClarificationTurns([]);
    setCurrentQuestion(null);
    setQuestionLoading(false);
    setClarificationReady(false);
    setQuestionError("");
    setTextAnswer("");
    setCustomChoiceOpen(false);
    setAcceptedIds([]);
    setSuggestion(null);
  };

  const adoptSelected = async () => {
    if (!proposalText.trim() || savingArchive) return;
    const proposal = proposalResponse?.proposal;
    const schuldner = activeArchive?.schuldner ?? debtorFromContext(lastGenerationContext);
    if (!schuldner) {
      setArchiveError("Der Schuldner ist nicht eindeutig bezeichnet.");
      return;
    }
    setArchiveError("");
    setSavingArchive(true);
    try {
      const archivedTenor = await saveTenorArchiveEntry({
        fall_id: activeArchive?.fall_id ?? selectedCase?.fall_id ?? "TENOR-ENTWURF",
        schuldner,
        title: activeArchive?.title ?? selectedCase?.title ?? schuldner,
        text: proposalText,
        context: lastGenerationContext.trim() || clarifiedContext.trim(),
        strategy: "complete",
        model: proposalResponse?.model ?? "Lokaler UE-Fallback",
        reference_version: proposalResponse?.reference_version ?? "ue-examples-2026-08-25-v1",
        source_ids: proposal?.source_ids ?? [],
      });
      setContext(proposalText);
      setActiveArchive(archivedTenor);
      setGenerated(false);
    } catch (error) {
      setArchiveError(
        error instanceof Error ? error.message : "Der Tenor konnte nicht archiviert werden.",
      );
    } finally {
      setSavingArchive(false);
    }
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
        void acceptPdf(event.dataTransfer.files[0]);
      }}
    >
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" aria-label="Zurück" className="text-slate-300 transition hover:text-slate-700">
          <ArrowLeft className="size-4" />
        </Link>
        <span className="text-xs font-medium tracking-wide text-slate-300">Tenorhilfe</span>
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
          {archiveLoading && (
            <p className="mb-6 flex items-center gap-2 text-sm text-slate-400" aria-live="polite">
              <Loader2 className="size-4 animate-spin" /> Archivierter Tenor wird geladen …
            </p>
          )}
          {archiveLoadError && (
            <p role="alert" className="mb-6 text-sm text-red-600">
              {archiveLoadError}
            </p>
          )}
          {pdf && (
            <div className="mb-8">
              <div className="flex items-center gap-3 text-sm text-slate-500">
                {pdfLoading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <FileUp className="size-4" />
                )}
                <span className="truncate">{pdf.name}</span>
                <span className="text-[10px] text-slate-300" aria-live="polite">
                  {pdfLoading
                    ? "Vertragstext wird lokal ausgelesen …"
                    : pdfExtraction
                      ? `${pdfExtraction.page_count} Seiten · im Tenor berücksichtigt${pdfExtraction.truncated ? " · gekürzt" : ""}`
                      : "nicht ausgelesen"}
                </span>
                <button
                  type="button"
                  onClick={removePdf}
                  aria-label="PDF entfernen"
                  className="ml-auto text-slate-300 hover:text-slate-700"
                >
                  <X className="size-4" />
                </button>
              </div>
              {pdfError && (
                <p role="alert" className="mt-2 text-xs text-red-600">
                  {pdfError}
                </p>
              )}
            </div>
          )}
          {!pdf && pdfError && (
            <p role="alert" className="mb-8 text-xs text-red-600">
              {pdfError}
            </p>
          )}
          <div
            className="min-h-[calc(100vh-17rem)] w-full flex-1 cursor-text"
            onClick={() => contextInput.current?.focus()}
          >
            <div className="flex items-start gap-2">
              {mode && (
                <strong className="max-w-[45%] shrink-0 truncate pt-[7px] text-sm leading-6 text-slate-900">
                  /{mode}
                  {selectedCase
                    ? ` · ${selectedCase.title}`
                    : activeArchive
                      ? ` · ${activeArchive.title}`
                      : ""}
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
            {correctionMode && context.trim().length >= 4 && !showModeMenu && (
              <section
                aria-label="Tenor überarbeiten"
                className="ml-4 mt-6 max-w-2xl border-l border-slate-200 pl-5 sm:ml-8 sm:pl-6"
                onClick={(event) => event.stopPropagation()}
              >
                {activeArchive && (
                  <p className="mb-4 text-[11px] leading-5 text-slate-400">
                    Archivfassung vom{" "}
                    {new Date(activeArchive.created_at).toLocaleDateString("de-DE")}. Das Original
                    bleibt erhalten; die Überarbeitung wird als neue Fassung archiviert.
                  </p>
                )}
                {revisionHistory.map((instruction, index) => (
                  <div key={`${instruction}-${index}`} className="mb-4 flex justify-end">
                    <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-slate-100 px-4 py-2.5 text-sm leading-6 text-slate-700">
                      {instruction}
                    </p>
                  </div>
                ))}
                <form
                  className="flex items-end gap-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    submitRevision();
                  }}
                >
                  <textarea
                    value={revisionInput}
                    maxLength={2_000}
                    rows={2}
                    aria-label="Änderungswunsch"
                    placeholder="Beschreibe, ob und wie der Tenor verändert werden soll …"
                    onChange={(event) => setRevisionInput(event.target.value)}
                    className="min-h-14 flex-1 resize-y rounded-2xl border border-slate-200 bg-white px-4 py-3 font-serif text-base leading-7 text-slate-700 outline-none placeholder:text-slate-300 focus:border-slate-400"
                  />
                  <button
                    type="submit"
                    disabled={!revisionInput.trim() || generating}
                    aria-label="Änderungswunsch senden"
                    className="grid size-11 shrink-0 place-items-center rounded-full bg-slate-950 text-white disabled:opacity-30"
                  >
                    {generating ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Send className="size-4" />
                    )}
                  </button>
                </form>
                {generationError && (
                  <p role="alert" className="mt-3 text-xs text-red-600">
                    {generationError}
                  </p>
                )}
              </section>
            )}
            {(clarificationTurns.length > 0 || currentQuestion || questionLoading) && (
              <div
                className="ml-4 mt-4 space-y-4 border-l border-slate-200 pl-5 sm:ml-8 sm:pl-6"
                onClick={(event) => event.stopPropagation()}
              >
                {clarificationTurns.map((turn, index) => (
                  <div key={`${turn.question.question_id}-${index}`}>
                    <p className="text-sm leading-6 text-slate-300">{turn.question.text}</p>
                    <p className="mt-1 font-serif text-base leading-7 text-slate-700">
                      {turn.answer}
                    </p>
                  </div>
                ))}

                {currentQuestion && (
                  <div>
                    <p className="text-sm leading-6 text-slate-300">{currentQuestion.text}</p>

                    {currentQuestion.answer_type === "yes_no" && (
                      <div className="mt-3 flex gap-2">
                        {(["Ja", "Nein"] as const).map((answer) => (
                          <button
                            key={answer}
                            type="button"
                            onClick={() => answerCurrentQuestion(answer)}
                            className="min-h-10 rounded-full border border-slate-200 px-5 text-sm text-slate-600 transition hover:border-slate-400 hover:text-slate-900"
                          >
                            {answer}
                          </button>
                        ))}
                      </div>
                    )}

                    {currentQuestion.answer_type === "single_choice" && (
                      <div className="mt-3 max-w-xl">
                        <div className="flex flex-wrap gap-2">
                          {currentQuestion.options.map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => answerCurrentQuestion(option.label)}
                              className="min-h-10 rounded-full border border-slate-200 px-4 text-left text-sm text-slate-600 transition hover:border-slate-400 hover:text-slate-900"
                            >
                              {option.label}
                            </button>
                          ))}
                          <button
                            type="button"
                            aria-expanded={customChoiceOpen}
                            onClick={() => {
                              setCustomChoiceOpen(true);
                              setTextAnswer("");
                            }}
                            className="min-h-10 rounded-full border border-dashed border-slate-300 px-4 text-sm text-slate-500 transition hover:border-slate-500 hover:text-slate-900"
                          >
                            Andere Angabe …
                          </button>
                        </div>
                        {customChoiceOpen && (
                          <form
                            className="mt-3 flex items-end gap-3"
                            onSubmit={(event) => {
                              event.preventDefault();
                              answerCurrentQuestion(textAnswer);
                            }}
                          >
                            <textarea
                              autoFocus
                              value={textAnswer}
                              maxLength={1_000}
                              rows={1}
                              placeholder={
                                currentQuestion.placeholder ?? "Andere Angabe ergänzen …"
                              }
                              onChange={(event) => setTextAnswer(event.target.value)}
                              className="min-h-10 flex-1 resize-y border-b border-slate-200 bg-transparent py-2 font-serif text-base leading-7 text-slate-700 outline-none placeholder:text-slate-300 focus:border-slate-500"
                            />
                            <button
                              type="submit"
                              disabled={!textAnswer.trim()}
                              className="min-h-10 rounded-full bg-slate-900 px-4 text-xs font-semibold text-white disabled:opacity-30"
                            >
                              Weiter
                            </button>
                          </form>
                        )}
                      </div>
                    )}

                    {currentQuestion.answer_type === "text" && (
                      <form
                        className="mt-2 flex items-end gap-3"
                        onSubmit={(event) => {
                          event.preventDefault();
                          answerCurrentQuestion(textAnswer);
                        }}
                      >
                        <textarea
                          autoFocus
                          value={textAnswer}
                          maxLength={1_000}
                          rows={1}
                          placeholder={currentQuestion.placeholder ?? "Antwort ergänzen …"}
                          onChange={(event) => setTextAnswer(event.target.value)}
                          className="min-h-10 flex-1 resize-y border-b border-slate-200 bg-transparent py-2 font-serif text-base leading-7 text-slate-700 outline-none placeholder:text-slate-300 focus:border-slate-500"
                        />
                        <button
                          type="submit"
                          disabled={!textAnswer.trim()}
                          className="min-h-10 rounded-full bg-slate-900 px-4 text-xs font-semibold text-white disabled:opacity-30"
                        >
                          Weiter
                        </button>
                      </form>
                    )}

                    {currentQuestion.answer_type === "slider" && currentQuestion.slider && (
                      <div className="mt-4 max-w-lg">
                        <div className="flex items-baseline justify-between gap-4">
                          <span className="text-[11px] text-slate-300">
                            {currentQuestion.slider.minimum_label}
                          </span>
                          <strong className="text-sm text-slate-700">
                            {formatSliderAnswer(currentQuestion, sliderAnswer)}
                          </strong>
                          <span className="text-right text-[11px] text-slate-300">
                            {currentQuestion.slider.maximum_label}
                          </span>
                        </div>
                        <Slider
                          aria-label={currentQuestion.text}
                          className="mt-3"
                          min={currentQuestion.slider.minimum}
                          max={currentQuestion.slider.maximum}
                          step={currentQuestion.slider.step}
                          value={[sliderAnswer]}
                          onValueChange={(values) =>
                            setSliderAnswer(values[0] ?? currentQuestion.slider!.minimum)
                          }
                        />
                        <button
                          type="button"
                          onClick={() =>
                            answerCurrentQuestion(formatSliderAnswer(currentQuestion, sliderAnswer))
                          }
                          className="mt-4 min-h-10 rounded-full bg-slate-900 px-4 text-xs font-semibold text-white"
                        >
                          Übernehmen
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {questionLoading && (
                  <p className="flex items-center gap-2 text-sm text-slate-300" aria-live="polite">
                    <Loader2 className="size-3.5 animate-spin" /> KI liest deine Ergänzung …
                  </p>
                )}
              </div>
            )}
            {clarificationReady && clarificationTurns.length > 0 && (
              <p className="ml-4 mt-4 text-xs text-slate-300 sm:ml-8">
                Die KI hat vorerst keine weitere tenorbezogene Sachverhaltsfrage.
              </p>
            )}
            {questionError && (
              <div
                role="alert"
                className="ml-4 mt-4 flex flex-wrap items-center gap-3 text-xs text-red-600 sm:ml-8"
                onClick={(event) => event.stopPropagation()}
              >
                <span>{questionError}</span>
                <button
                  type="button"
                  onClick={() => void requestClarificationQuestion()}
                  className="rounded-full border border-red-200 px-3 py-1.5 font-semibold"
                >
                  Erneut versuchen
                </button>
              </div>
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
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    event.currentTarget.value = "";
                    void acceptPdf(file);
                  }}
                />
                {correctionMode && (
                  <span className="ml-2 text-[10px] uppercase tracking-wider text-slate-300">
                    Tenor erkannt · Korrekturmodus
                  </span>
                )}
                {dictationNotice && (
                  <span className="ml-2 text-xs text-slate-400">{dictationNotice}</span>
                )}
                {generationError && !correctionMode && (
                  <span role="alert" className="ml-2 max-w-md text-xs text-red-600">
                    {generationError}
                  </span>
                )}
              </div>
              {canRequestQuestions &&
                !currentQuestion &&
                !questionLoading &&
                !questionError &&
                clarificationTurns.length === 0 && (
                  <button
                    type="button"
                    onClick={() => void requestClarificationQuestion()}
                    className="flex items-center gap-2 rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    <Sparkles className="size-4" />
                    KI-Rückfragen starten
                  </button>
                )}
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
                    {generating ? "KI erstellt den UE-Entwurf …" : "Generieren"}
                  </span>
                </button>
              )}
            </div>
          </div>
        </main>
      ) : (
        <main className="mx-auto flex max-w-6xl flex-col px-6 py-8 md:h-[calc(100dvh-2rem)] md:min-h-[38rem] md:py-6">
          <div className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2 text-sm text-slate-400">
              <Check className="size-4" /> Vollständiger UE-Entwurf
            </span>
            <span className="text-xs text-slate-300">Breite Lese- und Bearbeitungsansicht</span>
          </div>
          <div className="mx-auto mt-4 flex min-h-[64dvh] w-full max-w-5xl flex-1 flex-col md:min-h-0">
            <DraftChoice
              title="Unterlassungs- und Verpflichtungserklärung"
              text={proposalText}
              onText={setProposalText}
              provenance={aiProvenance(proposalResponse)}
            />
          </div>
          <div className="mt-4 flex min-h-11 items-center justify-center">
            <div className="text-center">
              {archiveError && (
                <p role="alert" className="mb-3 text-xs text-red-600">
                  {archiveError}
                </p>
              )}
              <button
                type="button"
                onClick={() => void adoptSelected()}
                disabled={savingArchive || !proposalText.trim()}
                aria-busy={savingArchive}
                className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {savingArchive && <Loader2 className="size-4 animate-spin" />}
                {savingArchive ? "Wird archiviert …" : "Entwurf übernehmen"}
              </button>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
