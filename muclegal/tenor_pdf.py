from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_TENOR_PDF_BYTES = 10 * 1024 * 1024
MAX_TENOR_PDF_PAGES = 100
MAX_TENOR_PDF_TEXT_CHARS = 40_000


class TenorPdfError(ValueError):
    pass


@dataclass(frozen=True)
class TenorPdfText:
    filename: str
    text: str
    page_count: int
    extracted_pages: int
    truncated: bool

    def to_dict(self) -> dict[str, str | int | bool]:
        return asdict(self)


def _clean_page_text(value: str) -> str:
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_tenor_pdf_text(data: bytes, *, filename: str) -> TenorPdfText:
    if not data:
        raise TenorPdfError("Die PDF-Datei ist leer.")
    if len(data) > MAX_TENOR_PDF_BYTES:
        raise TenorPdfError("Die PDF-Datei darf höchstens 10 MB groß sein.")
    if b"%PDF-" not in data[:1024]:
        raise TenorPdfError("Die hochgeladene Datei ist keine gültige PDF-Datei.")

    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise TenorPdfError(
                "Passwortgeschützte PDF-Dateien können nicht ausgewertet werden."
            )
        page_count = len(reader.pages)
        if page_count == 0:
            raise TenorPdfError("Die PDF-Datei enthält keine Seiten.")
        if page_count > MAX_TENOR_PDF_PAGES:
            raise TenorPdfError("Die PDF-Datei darf höchstens 100 Seiten enthalten.")

        page_blocks: list[str] = []
        extracted_pages = 0
        truncated = False
        current_length = 0
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = _clean_page_text(page.extract_text() or "")
            if not page_text:
                continue
            block = f"[Seite {page_number}]\n{page_text}"
            separator_length = 2 if page_blocks else 0
            remaining = MAX_TENOR_PDF_TEXT_CHARS - current_length - separator_length
            if remaining <= 0:
                truncated = True
                break
            if len(block) > remaining:
                block = block[:remaining].rstrip()
                truncated = True
            page_blocks.append(block)
            extracted_pages += 1
            current_length += separator_length + len(block)
            if truncated:
                break
    except TenorPdfError:
        raise
    except (PdfReadError, OSError, TypeError, ValueError) as exc:
        raise TenorPdfError("Die PDF-Datei konnte nicht gelesen werden.") from exc

    text = "\n\n".join(page_blocks).strip()
    if len(re.sub(r"\s+", "", text)) < 20:
        raise TenorPdfError(
            "Die PDF enthält keinen ausreichend maschinenlesbaren Text. "
            "Bei einem Scan ist zunächst eine OCR-Texterkennung erforderlich."
        )
    return TenorPdfText(
        filename=filename,
        text=text,
        page_count=page_count,
        extracted_pages=extracted_pages,
        truncated=truncated,
    )
