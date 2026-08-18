"""Authenticated grounded-generation API for M9."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.answering import answer_question
from app.auth.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.embeddings import EmbeddingValidationError, OllamaEmbeddingError
from app.generation import OllamaGenerationError
from app.retrieval import RetrievalValidationError

router = APIRouter(prefix="/generation", tags=["generation"])


class GenerationRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)


class SourceResponse(BaseModel):
    citation_id: int
    document_id: int
    chunk_id: int
    chunk_order: int
    distance: float


class GenerationResponse(BaseModel):
    answer: str
    context_available: bool
    sources: list[SourceResponse]
    citation_validation: dict[str, object]


@router.post("", response_model=GenerationResponse)
def generate(
    request: GenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> GenerationResponse:
    """Generate an answer grounded in the authenticated user's retrieved chunks."""

    try:
        response = answer_question(session, current_user, request.question, top_k=request.top_k)
    except RetrievalValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (EmbeddingValidationError, OllamaEmbeddingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Query embedding failed",
        ) from exc
    except OllamaGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generation failed",
        ) from exc

    return GenerationResponse(
        answer=response.answer,
        context_available=response.context_available,
        sources=[
            SourceResponse(
                citation_id=source.citation_id,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                chunk_order=source.chunk_order,
                distance=source.distance,
            )
            for source in response.sources
        ],
        citation_validation=response.citation_validation,
    )


__all__ = ["GenerationRequest", "GenerationResponse", "SourceResponse", "router"]
