"""Deterministic chunking for normalized extracted document text."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document

DEFAULT_CHUNK_SIZE_CHARS = 1000
DEFAULT_CHUNK_OVERLAP_CHARS = 200
DEFAULT_CHUNKING_VERSION = "ddrag-chunking-v1"


def validate_chunking_config(chunk_size: int, overlap: int) -> None:
    """Validate chunking configuration values.

    A valid configuration must define a positive chunk size and an overlap
    smaller than the chunk size so the chunking step always advances.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split text into a deterministic sequence of overlapping chunks.

    The chunk size is measured in characters, and overlap is applied between
    sequential windows. A chunk may be returned as a single value when the text is
    shorter than or equal to the configured size.
    """
    validate_chunking_config(chunk_size, overlap)
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += step

    return chunks


def persist_document_chunks(
    session: Session,
    document: Document,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    chunking_version: str = DEFAULT_CHUNKING_VERSION,
) -> list[Chunk]:
    """Persist deterministic chunks for one eligible document.

    A document is eligible when it is `ready` and has extracted text. Existing
    chunks for the document are replaced so the function can be called safely
    for reprocessing with the same or different configuration.
    """

    validate_chunking_config(chunk_size, overlap)
    if not chunking_version.strip():
        raise ValueError("chunking_version must not be blank")

    if document.id is None:
        raise ValueError("document must be persisted before chunking")
    if document.status != "ready":
        return []
    if document.extracted_text is None:
        return []

    session.query(Chunk).filter_by(document_id=document.id).delete(synchronize_session=False)

    chunks = chunk_text(document.extracted_text, chunk_size=chunk_size, overlap=overlap)
    records = [
        Chunk(
            document_id=document.id,
            chunk_order=index,
            chunk_text=chunk,
            chunk_size_chars=chunk_size,
            chunk_overlap_chars=overlap,
            chunking_version=chunking_version,
        )
        for index, chunk in enumerate(chunks)
    ]

    session.add_all(records)
    # Flush so callers querying by document_id (e.g. embed_document_chunks) see these
    # rows immediately; the session is configured with autoflush disabled.
    session.flush()
    return records
