"""Turn a folder of company documents into searchable chunks."""

import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

SUPPORTED_TEXT = {".md", ".txt"}


@dataclass(frozen=True)
class Chunk:
    """A piece of a document plus where it came from, for citations."""

    text: str
    source: str
    page: int | None


def _read_text(path: Path) -> str:
    """UTF-8 (with or without BOM), falling back to Windows' cp1252 for older files."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _pdf_pages(path: Path) -> list[tuple[int, str]]:
    # pypdf logs noisy warnings on broken files; we report our own message instead.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(path)
    pages = [(number, page.extract_text() or "") for number, page in enumerate(reader.pages, 1)]
    if not any(text.strip() for _, text in pages):
        raise ValueError("el PDF no tiene texto (¿es un documento escaneado?)")
    return pages


def load_chunks(
    folder: Path, chunk_size: int = 800, overlap: int = 120
) -> tuple[list[Chunk], list[str]]:
    """Load .md, .txt and .pdf files under folder; return chunks and Spanish warnings."""
    if not folder.is_dir():
        return [], [f"La carpeta de documentos no existe: {folder}"]

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    chunks: list[Chunk] = []
    warnings: list[str] = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_TEXT and suffix != ".pdf":
            continue
        source = path.relative_to(folder).as_posix()
        try:
            if suffix == ".pdf":
                pages: list[tuple[int | None, str]] = list(_pdf_pages(path))
            else:
                pages = [(None, _read_text(path))]
        except Exception as exc:
            warnings.append(f"Se omitió {source}: {exc}")
            continue
        for page, text in pages:
            chunks.extend(Chunk(piece, source, page) for piece in splitter.split_text(text))
    return chunks, warnings
