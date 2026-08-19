from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from muclegal.normalize.core import normalize_plain_text


_LEGAL_HEADING = re.compile(
    r"^(?:(?P<section>§+\s*\d+[a-zA-Z]*)|"
    r"(?P<article>Artikel\s+\d+[a-zA-Z]*)|"
    r"(?P<number>\d+(?:\.\d+)*\.(?!\d))|"
    r"(?P<paragraph>\(\d+\))|"
    r"(?P<letter>(?:lit\.\s*)?[a-z]\)))\s*",
    re.IGNORECASE,
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9§(])")


@dataclass(frozen=True)
class Clause:
    ordinal: int
    heading_path: str | None
    text: str
    clause_hash: str
    is_tenor_relevant: bool = False


def split_clauses(text: str) -> tuple[Clause, ...]:
    """Split canonical text deterministically, preferring legal structure."""
    canonical = normalize_plain_text(text).rstrip("\n")
    if not canonical:
        return ()
    paragraphs = [line for line in canonical.split("\n") if line]
    if any(_LEGAL_HEADING.match(line) for line in paragraphs):
        chunks = _split_legal(paragraphs)
    else:
        chunks = [(None, part) for paragraph in paragraphs for part in _bounded_blocks(paragraph)]
    return tuple(
        Clause(
            ordinal=index,
            heading_path=heading,
            text=chunk,
            clause_hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
        )
        for index, (heading, chunk) in enumerate(chunks, start=1)
        if chunk
    )


def _split_legal(paragraphs: list[str]) -> list[tuple[str | None, str]]:
    chunks: list[tuple[str | None, str]] = []
    hierarchy: list[str] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        combined = "\n".join(buffer)
        chunks.extend((current_heading, part) for part in _bounded_blocks(combined))
        buffer.clear()

    for paragraph in paragraphs:
        match = _LEGAL_HEADING.match(paragraph)
        if match:
            flush()
            marker = match.group(0).strip()
            level = _heading_level(match)
            hierarchy[level:] = []
            if len(hierarchy) < level:
                hierarchy.extend([""] * (level - len(hierarchy)))
            hierarchy.append(marker)
            current_heading = " > ".join(item for item in hierarchy if item)
        buffer.append(paragraph)
    flush()
    return chunks


def _heading_level(match: re.Match[str]) -> int:
    if match.group("section") or match.group("article"):
        return 0
    if match.group("number"):
        return match.group("number").count(".") - 1
    if match.group("paragraph"):
        return 1
    return 2


def _bounded_blocks(value: str, minimum: int = 400, maximum: int = 800) -> list[str]:
    if len(value) <= maximum:
        return [value]
    sentences = _SENTENCE_BOUNDARY.split(value.replace("\n", " "))
    blocks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > maximum:
            if current:
                blocks.append(current)
                current = ""
            blocks.extend(sentence[index : index + maximum] for index in range(0, len(sentence), maximum))
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > maximum and len(current) >= minimum:
            blocks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        if blocks and len(current) < minimum and len(blocks[-1]) + 1 + len(current) <= maximum:
            blocks[-1] = f"{blocks[-1]} {current}"
        else:
            blocks.append(current)
    return blocks
