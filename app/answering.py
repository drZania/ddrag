"""Grounded answer orchestration for M9 generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.citations import validate_citations
from app.context import ContextSource, assemble_context
from app.generation import OllamaGenerationError, generate_answer
from app.prompting import build_system_prompt, build_user_prompt
from app.retrieval import RetrievalResult, retrieve_chunks

INSUFFICIENT_INFORMATION_MESSAGE = (
    "I do not have enough information to answer that based on the retrieved document context."
)


@dataclass(frozen=True)
class GroundedAnswer:
    """A grounded answer and the supporting retrieved source metadata."""

    answer: str
    context_available: bool
    sources: list[ContextSource]
    citation_validation: dict[str, Any]


def answer_question(
    session: Session,
    current_user: Any,
    question: str,
    *,
    top_k: int | None = None,
) -> GroundedAnswer:
    """Render a grounded answer using the authenticated user's retrieved chunks."""

    normalized_question = (question or "").strip()
    if not normalized_question:
        raise ValueError("question must not be blank")

    retrieval = retrieve_chunks(session, current_user, normalized_question, top_k=top_k)
    if not retrieval.results:
        return GroundedAnswer(
            answer=INSUFFICIENT_INFORMATION_MESSAGE,
            context_available=False,
            sources=[],
            citation_validation={
                "cited_ids": [],
                "valid": True,
                "invalid_citations": [],
            },
        )

    context = assemble_context(retrieval.results)
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(normalized_question, context.context_text)
    generated_answer = generate_answer(system_prompt, user_prompt)
    citation_validation = validate_citations(generated_answer, context.citation_map)

    return GroundedAnswer(
        answer=generated_answer,
        context_available=True,
        sources=context.sources,
        citation_validation=citation_validation,
    )


__all__ = ["GroundedAnswer", "INSUFFICIENT_INFORMATION_MESSAGE", "answer_question"]
