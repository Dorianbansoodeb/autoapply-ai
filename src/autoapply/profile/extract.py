"""Pull plain text out of a resume file. No LLM. No PyMuPDF."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}


class ExtractError(ValueError):
    """Resume could not be read as text."""


def extract_text(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise ExtractError(f"resume not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractError(
            f"unsupported resume type {suffix!r}; use .txt, .md, .pdf, or .docx"
        )
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        text = _pdf_text(path)
    else:
        text = _docx_text(path)
    cleaned = _normalize_text(text)
    if len(cleaned) < 20:
        raise ExtractError("resume text was empty or too short to import")
    return cleaned


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _docx_text(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    lines = [para.text for para in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\x00", "").splitlines()]
    return "\n".join(line for line in lines if line).strip()
