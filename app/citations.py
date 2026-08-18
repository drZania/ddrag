"""Basic citation extraction and validation for grounded generation."""

from __future__ import annotations

import re
from collections.abc import Mapping


def extract_citation_ids(answer_text: str) -> list[int]:
    """Extract ordinal citation IDs such as [1] and [3] from answer text."""

    if not answer_text:
        return []
    return [int(match) for match in re.findall(r"\[(\d+)\]", answer_text)]


def validate_citations(answer_text: str, citation_map: Mapping[int, object]) -> dict[str, object]:
    """Validate cited ordinal IDs against the citations actually supplied to the model."""

    cited_ids = extract_citation_ids(answer_text)
    normalized: list[int] = []
    seen: set[int] = set()
    for cited_id in cited_ids:
        if cited_id not in seen:
            seen.add(cited_id)
            normalized.append(cited_id)

    invalid_citations = [cited_id for cited_id in normalized if cited_id not in citation_map]
    return {
        "cited_ids": normalized,
        "valid": not invalid_citations,
        "invalid_citations": invalid_citations,
    }


__all__ = ["extract_citation_ids", "validate_citations"]
