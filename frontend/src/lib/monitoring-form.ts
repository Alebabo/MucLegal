export function splitLineValues(value: string) {
  return value
    .split(/[\r\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function splitAlternativeLabels(value: string) {
  return value
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}
