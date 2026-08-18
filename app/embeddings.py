"""Ollama embedding integration for persisted chunks."""

from __future__ import annotations

import json
from collections.abc import Sequence
from math import isfinite
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk, Document


class EmbeddingValidationError(ValueError):
    """Raised when a candidate embedding is malformed or incompatible."""


class OllamaEmbeddingError(RuntimeError):
    """Raised when Ollama cannot generate an embedding."""


def validate_embedding_vector(
    vector: Sequence[float] | Sequence[int],
    *,
    expected_dimension: int | None = None,
) -> list[float]:
    """Validate and normalize a candidate embedding vector."""

    if vector is None:
        raise EmbeddingValidationError("embedding vector is required")
    if not isinstance(vector, (list, tuple)):
        raise EmbeddingValidationError("embedding vector must be a sequence of numbers")
    if not vector:
        raise EmbeddingValidationError("embedding vector must not be empty")

    normalized: list[float] = []
    for value in vector:
        if not isinstance(value, (int, float)):
            raise EmbeddingValidationError("embedding vector must contain only numeric values")
        numeric = float(value)
        if not isfinite(numeric):
            raise EmbeddingValidationError("embedding vector contains a non-finite value")
        normalized.append(numeric)

    if expected_dimension is not None:
        if len(normalized) != expected_dimension:
            raise EmbeddingValidationError(
                f"embedding dimension mismatch: expected {expected_dimension}, got {len(normalized)}"
            )

    return normalized


def generate_embedding(text: str, *, model: str | None = None, base_url: str | None = None) -> list[float]:
    """Generate a single embedding for text via the local Ollama API."""

    settings = get_settings()
    resolved_model = (model or settings.embedding_model).strip()
    resolved_base_url = (base_url or settings.ollama_base_url).rstrip("/")

    if not resolved_model:
        raise OllamaEmbeddingError("embedding model must not be blank")
    if not resolved_base_url:
        raise OllamaEmbeddingError("ollama base URL must not be blank")

    payload = {"model": resolved_model, "input": text}
    request = Request(
        f"{resolved_base_url}/api/embed",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except (HTTPError, URLError, OSError) as exc:
        raise OllamaEmbeddingError(f"Ollama embedding request failed: {exc}") from exc

    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise OllamaEmbeddingError("Ollama returned malformed JSON") from exc

    embeddings = decoded.get("embeddings")
    if not isinstance(embeddings, list) or not embeddings:
        raise OllamaEmbeddingError("Ollama response missing an embeddings array")

    first = embeddings[0]
    if not isinstance(first, list):
        raise EmbeddingValidationError("Ollama embedding payload is not a vector sequence")

    vector = validate_embedding_vector(first, expected_dimension=settings.embedding_dimension)
    return vector


def embed_document_chunks(
    session: Session,
    document: Document,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> list[Chunk]:
    """Generate and persist embeddings for a document's current chunk set."""

    if document.id is None:
        raise ValueError("document must be persisted before embedding")

    chunks = (
        session.query(Chunk)
        .filter_by(document_id=document.id)
        .order_by(Chunk.chunk_order.asc())
        .all()
    )
    if not chunks:
        return []

    for chunk in chunks:
        if not chunk.chunk_text:
            continue
        generated = generate_embedding(chunk.chunk_text, model=model, base_url=base_url)
        chunk.embedding = generated

    return chunks


__all__ = [
    "EmbeddingValidationError",
    "OllamaEmbeddingError",
    "embed_document_chunks",
    "generate_embedding",
    "validate_embedding_vector",
]
