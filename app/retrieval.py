"""Owner-scoped vector retrieval for persisted document chunks."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk, Document, User
from app.embeddings import generate_embedding

DEFAULT_RETRIEVAL_TOP_K = 5
MAX_RETRIEVAL_TOP_K = 50


class RetrievalValidationError(ValueError):
    """Raised when retrieval input is invalid."""


@dataclass(frozen=True)
class RetrievalResult:
    """A chunk and the distance produced by the vector search."""

    document_id: int
    chunk_id: int
    chunk_order: int
    chunk_text: str
    distance: float


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Development diagnostics for one retrieval operation."""

    top_k_requested: int
    candidates_considered: int
    results_returned: int
    embedding_model: str
    embedding_dimension: int
    duration_ms: float


@dataclass(frozen=True)
class RetrievalResponse:
    """Results and diagnostics returned by the retrieval service."""

    results: list[RetrievalResult]
    diagnostics: RetrievalDiagnostics


def validate_top_k(top_k: int) -> int:
    """Validate a bounded positive retrieval count."""

    if top_k < 1:
        raise RetrievalValidationError("top_k must be greater than zero")
    if top_k > MAX_RETRIEVAL_TOP_K:
        raise RetrievalValidationError(f"top_k must be at most {MAX_RETRIEVAL_TOP_K}")
    return top_k


def retrieve_chunks(
    session: Session,
    current_user: User,
    query: str,
    *,
    top_k: int | None = None,
) -> RetrievalResponse:
    """Embed a query and retrieve its nearest owned chunks."""

    normalized_query = query.strip()
    if not normalized_query:
        raise RetrievalValidationError("query must not be blank")

    settings = get_settings()
    requested_top_k = validate_top_k(top_k if top_k is not None else settings.retrieval_default_top_k)
    started = perf_counter()
    query_vector = generate_embedding(normalized_query)

    candidates_query = (
        session.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.user_id == current_user.id, Chunk.embedding.is_not(None))
    )
    candidates_considered = candidates_query.count()
    distance_expression = Chunk.embedding.cosine_distance(query_vector)
    rows = (
        candidates_query
        .add_columns(distance_expression.label("distance"))
        .order_by(distance_expression.asc(), Chunk.id.asc())
        .limit(requested_top_k)
        .all()
    )
    results = [
        RetrievalResult(
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            chunk_order=chunk.chunk_order,
            chunk_text=chunk.chunk_text,
            distance=float(distance),
        )
        for chunk, distance in rows
    ]
    duration_ms = round((perf_counter() - started) * 1000, 2)
    diagnostics = RetrievalDiagnostics(
        top_k_requested=requested_top_k,
        candidates_considered=candidates_considered,
        results_returned=len(results),
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        duration_ms=duration_ms,
    )
    return RetrievalResponse(results=results, diagnostics=diagnostics)


__all__ = [
    "DEFAULT_RETRIEVAL_TOP_K",
    "MAX_RETRIEVAL_TOP_K",
    "RetrievalDiagnostics",
    "RetrievalResponse",
    "RetrievalResult",
    "RetrievalValidationError",
    "retrieve_chunks",
    "validate_top_k",
]