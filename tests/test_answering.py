"""Focused orchestration tests for M9 grounded answering behavior."""

import pytest

from app.answering import INSUFFICIENT_INFORMATION_MESSAGE, answer_question
from app.db.models import User
from app.db.session import SessionLocal
from app.retrieval import RetrievalResult


def _user() -> User:
    with SessionLocal() as session:
        user = User(email=f"answering-user-{__import__('uuid').uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def test_no_context_short_circuit_skips_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    called = {"value": False}

    monkeypatch.setattr("app.answering.retrieve_chunks", lambda *args, **kwargs: type("Resp", (), {"results": []})())

    def fake_generate(*args, **kwargs):
        called["value"] = True
        return "unexpected"

    monkeypatch.setattr("app.answering.generate_answer", fake_generate)

    response = answer_question(
        session=SessionLocal(),
        current_user=user,
        question="What is unknown?",
        top_k=3,
    )

    assert response.answer == INSUFFICIENT_INFORMATION_MESSAGE
    assert response.context_available is False
    assert response.sources == []
    assert response.citation_validation == {"cited_ids": [], "valid": True, "invalid_citations": []}
    assert called["value"] is False


def test_invalid_ordinal_citation_ids_are_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    retrieval_results = [
        RetrievalResult(
            document_id=1,
            chunk_id=10,
            chunk_order=0,
            chunk_text="Only one source exists.",
            distance=0.1,
        )
    ]

    monkeypatch.setattr("app.answering.retrieve_chunks", lambda *args, **kwargs: type("Resp", (), {"results": retrieval_results})())
    monkeypatch.setattr("app.answering.generate_answer", lambda *args, **kwargs: "Claim [2]")

    response = answer_question(
        session=SessionLocal(),
        current_user=user,
        question="What is the claim?",
        top_k=1,
    )

    assert response.citation_validation == {
        "cited_ids": [2],
        "valid": False,
        "invalid_citations": [2],
    }


def test_malformed_brackets_do_not_create_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    retrieval_results = [
        RetrievalResult(
            document_id=1,
            chunk_id=10,
            chunk_order=0,
            chunk_text="Reference text.",
            distance=0.1,
        )
    ]

    monkeypatch.setattr("app.answering.retrieve_chunks", lambda *args, **kwargs: type("Resp", (), {"results": retrieval_results})())
    monkeypatch.setattr("app.answering.generate_answer", lambda *args, **kwargs: "Answer [abc] [] [1a]")

    response = answer_question(
        session=SessionLocal(),
        current_user=user,
        question="What is the answer?",
        top_k=1,
    )

    assert response.citation_validation == {
        "cited_ids": [],
        "valid": True,
        "invalid_citations": [],
    }


def test_citation_mapping_is_deterministic_for_same_retrieval_results(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    retrieval_results = [
        RetrievalResult(document_id=2, chunk_id=20, chunk_order=0, chunk_text="A", distance=0.05),
        RetrievalResult(document_id=2, chunk_id=21, chunk_order=1, chunk_text="B", distance=0.08),
    ]

    monkeypatch.setattr("app.answering.retrieve_chunks", lambda *args, **kwargs: type("Resp", (), {"results": retrieval_results})())
    monkeypatch.setattr("app.answering.generate_answer", lambda *args, **kwargs: "Combined [1] [2]")

    first = answer_question(session=SessionLocal(), current_user=user, question="Q?", top_k=2)
    second = answer_question(session=SessionLocal(), current_user=user, question="Q?", top_k=2)

    assert [source.citation_id for source in first.sources] == [1, 2]
    assert [source.chunk_id for source in first.sources] == [20, 21]
    assert first.citation_validation == second.citation_validation
