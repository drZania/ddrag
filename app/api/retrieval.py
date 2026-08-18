"""Authenticated vector retrieval API for M8."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.embeddings import EmbeddingValidationError, OllamaEmbeddingError
from app.retrieval import (
    MAX_RETRIEVAL_TOP_K,
    RetrievalValidationError,
    retrieve_chunks,
)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=MAX_RETRIEVAL_TOP_K)


class RetrievalResultResponse(BaseModel):
    document_id: int
    chunk_id: int
    chunk_order: int
    chunk_text: str
    distance: float


class RetrievalDiagnosticsResponse(BaseModel):
    top_k_requested: int
    candidates_considered: int
    results_returned: int
    embedding_model: str
    embedding_dimension: int
    duration_ms: float


class RetrievalResponseModel(BaseModel):
    results: list[RetrievalResultResponse]
    diagnostics: RetrievalDiagnosticsResponse


@router.post("", response_model=RetrievalResponseModel)
def retrieve(
    request: RetrievalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RetrievalResponseModel:
    """Retrieve nearest chunks owned by the authenticated user."""

    try:
        response = retrieve_chunks(session, current_user, request.query, top_k=request.top_k)
    except RetrievalValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (EmbeddingValidationError, OllamaEmbeddingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Query embedding failed",
        ) from exc

    return RetrievalResponseModel(
        results=[
            RetrievalResultResponse(
                document_id=result.document_id,
                chunk_id=result.chunk_id,
                chunk_order=result.chunk_order,
                chunk_text=result.chunk_text,
                distance=result.distance,
            )
            for result in response.results
        ],
        diagnostics=RetrievalDiagnosticsResponse(
            top_k_requested=response.diagnostics.top_k_requested,
            candidates_considered=response.diagnostics.candidates_considered,
            results_returned=response.diagnostics.results_returned,
            embedding_model=response.diagnostics.embedding_model,
            embedding_dimension=response.diagnostics.embedding_dimension,
            duration_ms=response.diagnostics.duration_ms,
        ),
    )