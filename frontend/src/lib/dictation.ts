export type DictationSegment = {
  transcript: string;
  isFinal: boolean;
};

export type DictationSegments = Record<number, DictationSegment>;

export type DictationUpdate = DictationSegment & {
  index: number;
};

export function mergeDictationSegments(
  current: Readonly<DictationSegments>,
  updates: readonly DictationUpdate[],
): DictationSegments {
  const merged = { ...current };
  for (const update of updates) {
    merged[update.index] = {
      transcript: update.transcript.trim(),
      isFinal: update.isFinal,
    };
  }
  return merged;
}

export function composeDictationText(baseText: string, segments: Readonly<DictationSegments>) {
  const transcript = Object.entries(segments)
    .sort(([left], [right]) => Number(left) - Number(right))
    .map(([, segment]) => segment.transcript.trim())
    .filter(Boolean)
    .join(" ");

  return [baseText.trimEnd(), transcript].filter(Boolean).join(" ");
}
