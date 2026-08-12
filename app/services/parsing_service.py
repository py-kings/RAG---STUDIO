"""
Document parsing service - Phase 6.

Extracts raw text from PDF (PyMuPDF), DOCX (python-docx), and TXT
files, then chunks it (500 chars / 100 char overlap by default, per
project config) ready for embedding in Phase 7. Parsed chunks are
cached to disk as JSON so Phase 7 doesn't need to re-parse; MySQL
only stores the resulting page_count/chunk_count/status on Document.

PDF chunks retain their source page number (for citation, Phase 10).
DOCX/TXT have no native page concept, so page is left as None.
"""
import os
import json
import logging

import fitz  # PyMuPDF
import docx  # python-docx

from flask import current_app

from app import db
from app.models import Document

logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Raised when a document's text cannot be extracted."""


# --- Extraction ---------------------------------------------------

def _extract_pdf(path: str):
    """Returns (page_count, [(page_number, page_text), ...])."""
    pages = []
    with fitz.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            pages.append((i, page.get_text("text")))
        return len(pdf), pages


def _extract_docx(path: str):
    """Returns (page_count, [(None, full_text)]) - DOCX has no fixed pages."""
    d = docx.Document(path)
    text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    return None, [(None, text)]


def _extract_txt(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return None, [(None, text)]


def extract_text(document: Document, file_path: str):
    if document.file_type == "pdf":
        return _extract_pdf(file_path)
    if document.file_type == "docx":
        return _extract_docx(file_path)
    if document.file_type == "txt":
        return _extract_txt(file_path)
    raise ParsingError(f"Unsupported file type: {document.file_type}")


# --- Chunking -------------------------------------------------------

def chunk_text(text: str, chunk_size: int, chunk_overlap: int):
    """Sliding-window chunker. Returns a list of text chunks."""
    text = text.strip()
    if not text:
        return []

    step = max(chunk_size - chunk_overlap, 1)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += step
    return chunks


def _cache_path(document: Document) -> str:
    cache_dir = current_app.config["PARSED_CACHE_DIR"]
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{document.id}.json")


def load_cached_chunks(document: Document):
    """Read back a document's cached parsed chunks, or None if absent."""
    path = _cache_path(document)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Orchestration ----------------------------------------------------

def parse_document(document: Document, file_path: str) -> dict:
    """
    Extract + chunk a document and persist results. Updates the
    Document row (status, page_count, chunk_count) and writes a JSON
    chunk cache to disk. Raises ParsingError on failure (and marks
    the document status='failed' before re-raising).
    """
    chunk_size = current_app.config["CHUNK_SIZE"]
    chunk_overlap = current_app.config["CHUNK_OVERLAP"]

    try:
        page_count, pages = extract_text(document, file_path)
    except Exception as exc:  # noqa: BLE001 - convert any parser failure uniformly
        document.status = "failed"
        db.session.commit()
        logger.exception("Failed to parse document %s", document.id)
        raise ParsingError(str(exc)) from exc

    all_chunks = []
    for page_number, page_text in pages:
        for chunk in chunk_text(page_text, chunk_size, chunk_overlap):
            all_chunks.append({
                "chunk_index": len(all_chunks),
                "page": page_number,
                "text": chunk,
            })

    with open(_cache_path(document), "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    document.status = "parsed"
    document.page_count = page_count
    document.chunk_count = len(all_chunks)
    db.session.commit()

    return {"page_count": page_count, "chunk_count": len(all_chunks)}
