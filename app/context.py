"""Deterministic context assembly for grounded generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.retrieval import RetrievalResult


@dataclass(frozen=True)
class ContextSource:
    """A single retrieved chunk mapped to an ordinal citation ID."""

    citation_id: int
    document_id: int
    chunk_id: int
    chunk_order: int
    chunk_text: str
    distance: float


@dataclass(frozen=True)
class ContextBundle:
    """The context supplied to the LLM together with its citation map."""

    sources: list[ContextSource]
    citation_map: dict[int, ContextSource]
    context_text: str


def assemble_context(results: Sequence[RetrievalResult]) -> ContextBundle:
    """Assign deterministic ordinal citation IDs to retrieved chunks."""

    ordered_sources: list[ContextSource] = []
    blocks: list[str] = []

    for citation_id, result in enumerate(results, start=1):
        source = ContextSource(
            citation_id=citation_id,
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            chunk_order=result.chunk_order,
            chunk_text=result.chunk_text.strip(),
            distance=float(result.distance),
        )
        ordered_sources.append(source)
        blocks.append(
            "\n".join(
                [
                    f"[{citation_id}]",
                    f"Document ID: {source.document_id}",
                    f"Chunk ID: {source.chunk_id}",
                    f"Chunk Order: {source.chunk_order}",
                    f"Distance: {source.distance:.6f}",
                    "Text:",
                    source.chunk_text,
                ]
            )
        )

    citation_map = {source.citation_id: source for source in ordered_sources}
    return ContextBundle(
        sources=ordered_sources,
        citation_map=citation_map,
        context_text="\n\n".join(blocks),
    )


__all__ = ["ContextBundle", "ContextSource", "assemble_context"]
