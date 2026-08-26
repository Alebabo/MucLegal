const ARCHIVE_TITLE_LIMIT = 48;

export function compactArchiveCaseTitle(description: string, fallback: string) {
  const firstSentence = description
    .trim()
    .split(/(?<=[.!?])\s+/u)[0]
    ?.trim();
  let title = firstSentence || fallback.trim();
  title = title
    .replace(/^Klar gekennzeichneter\s+/iu, "")
    .replace(/^Historischer\s+/iu, "")
    .replace(/\s+nach dem\b.*$/iu, "")
    .replace(/\s+für die (?:lokale )?Vorführung\b.*$/iu, "")
    .trim();
  if (!title) title = fallback.trim();
  title = title.charAt(0).toUpperCase() + title.slice(1);
  if (title.length <= ARCHIVE_TITLE_LIMIT) return title;

  const shortened = title.slice(0, ARCHIVE_TITLE_LIMIT - 1);
  const lastSpace = shortened.lastIndexOf(" ");
  return `${(lastSpace > 24 ? shortened.slice(0, lastSpace) : shortened).trimEnd()}…`;
}
