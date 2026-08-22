from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import asdict, dataclass

from lxml import etree, html
from trafilatura import extract


NORMALIZER_VERSION = "2"
_SIMPLE_SELECTOR = re.compile(
    r"^(?P<tag>[A-Za-z][\w-]*)?(?:#(?P<id>[\w-]+))?(?:\.(?P<class>[\w-]+))?$"
)


class NormalizationError(ValueError):
    pass


@dataclass(frozen=True)
class VolatileRule:
    selector: str
    marker: str


@dataclass(frozen=True)
class NormalizationConfig:
    include_selector: str | None = None
    remove_selectors: tuple[str, ...] = ()
    volatile_rules: tuple[VolatileRule, ...] = ()

    @classmethod
    def from_dict(cls, value: dict) -> "NormalizationConfig":
        return cls(
            include_selector=value.get("include_selector"),
            remove_selectors=tuple(value.get("remove_selectors", ())),
            volatile_rules=tuple(VolatileRule(**rule) for rule in value.get("volatile_rules", ())),
        )

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NormalizedDocument:
    text: str
    sha256: str
    normalizer_version: str
    selector_config_hash: str


def normalize_html(raw_html: str | bytes, config: NormalizationConfig) -> NormalizedDocument:
    try:
        document = html.document_fromstring(raw_html)
    except (etree.ParserError, ValueError) as exc:
        raise NormalizationError(f"HTML konnte nicht geparst werden: {exc}") from exc

    root = document
    if config.include_selector:
        matches = _select(document, config.include_selector)
        if len(matches) != 1:
            raise NormalizationError(
                f"Include-Selektor {config.include_selector!r} muss genau einmal treffen; "
                f"gefunden: {len(matches)}."
            )
        root = deepcopy(matches[0])

    for selector in ("script", "style", "noscript", "template", *config.remove_selectors):
        for node in _select(root, selector):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

    for rule in config.volatile_rules:
        if not rule.marker.startswith("[") or not rule.marker.endswith("]"):
            raise NormalizationError(f"Typisierter Marker erwartet, erhalten: {rule.marker!r}")
        for node in _select(root, rule.selector):
            for child in list(node):
                node.remove(child)
            node.text = rule.marker

    prepared_html = html.tostring(root, encoding="unicode", method="html")
    extracted = extract(
        prepared_html,
        output_format="txt",
        favor_precision=True,
        include_comments=False,
        include_tables=True,
        include_links=False,
        include_images=False,
        with_metadata=False,
        deduplicate=False,
    )
    if not extracted or not extracted.strip():
        raise NormalizationError("Die konfigurierte Extraktion ergab keinen relevanten Text.")
    text = _canonicalize_text(extracted)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return NormalizedDocument(text, digest, NORMALIZER_VERSION, config.config_hash)


def _select(root: etree._Element, selector: str) -> list[etree._Element]:
    match = _SIMPLE_SELECTOR.fullmatch(selector.strip())
    if not match or not any(match.groupdict().values()):
        raise NormalizationError(
            f"Nicht unterstützter CSS-Selektor {selector!r}; erlaubt sind tag, #id, .klasse und tag.klasse."
        )
    tag = match.group("tag") or "*"
    predicates: list[str] = []
    if match.group("id"):
        predicates.append(f"@id={_xpath_literal(match.group('id'))}")
    if match.group("class"):
        class_name = _xpath_literal(f" {match.group('class')} ")
        predicates.append(f"contains(concat(' ', normalize-space(@class), ' '), {class_name})")
    suffix = f"[{' and '.join(predicates)}]" if predicates else ""
    return list(root.xpath(f"descendant-or-self::{tag}{suffix}"))


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    raise NormalizationError("Anführungszeichen sind in einfachen Selektoren nicht zulässig.")


def normalize_plain_text(value: str) -> str:
    """Canonicalize extracted text without removing substantive content."""
    value = unicodedata.normalize("NFKC", value.replace("\r\n", "\n").replace("\r", "\n"))
    value = value.translate(
        str.maketrans(
            {
                "\u00a0": " ",
                "\u00ad": None,
                "\u200b": None,
                "\u200c": None,
                "\u200d": None,
                "\ufeff": None,
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2212": "-",
            }
        )
    )
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in value.split("\n")]
    output: list[str] = []
    for line in lines:
        if line or (output and output[-1]):
            output.append(line)
    return "\n".join(output).strip() + "\n"


def _canonicalize_text(value: str) -> str:
    return normalize_plain_text(value)

