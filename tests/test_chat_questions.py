"""Focused M10.6 tests for persisted chat-question orchestration."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.answering import GroundedAnswer
from app.context import ContextSource
from app.db.models import ChatMessage, ChatQuery, QuerySource
from app.db.session import SessionLocal
from app.generation import OllamaGenerationError
from app.main import app


client = TestClient(app)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login() -> tuple[str, int]:
    email = f"chat-question-{uuid4()}@example.com"
    password = "correct horse battery staple"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    current_user = client.get("/auth/me", headers=_headers(token))
    assert current_user.status_code == 200
    return token, current_user.json()["id"]


def _create_session(token: str) -> int:
    response = client.post("/chat/sessions", headers=_headers(token))
    assert response.status_code == 201
    return response.json()["id"]


def _answer_with_source() -> GroundedAnswer:
    source = ContextSource(
        citation_id=1,
        document_id=7,
        chunk_id=11,
        chunk_order=0,
        chunk_text="DDRAG is a document-grounded chat system.",
        distance=0.1,
    )
    return GroundedAnswer(
        answer="DDRAG is a document-grounded chat system. [1]",
        context_available=True,
        sources=[source],
        citation_validation={"cited_ids": [1], "valid": True, "invalid_citations": []},
    )


def test_owned_question_persists_completed_query_answer_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    token, user_id = _register_and_login()
    session_id = _create_session(token)
    calls: list[tuple[object, object, str]] = []

    def fake_answer(session, current_user, question, **kwargs):
        calls.append((session, current_user, question))
        pending_query = (
            session.query(ChatQuery)
            .filter_by(session_id=session_id, status="pending")
            .one()
        )
        assert pending_query.user_message.content == "What is DDRAG?"
        return _answer_with_source()

    monkeypatch.setattr("app.api.chat.answer_question", fake_answer)
    response = client.post(
        f"/chat/sessions/{session_id}/questions",
        json={"question": " What is DDRAG? ", "user_id": user_id, "session_id": 999999},
        headers=_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer"] == "DDRAG is a document-grounded chat system. [1]"
    assert body["sources"] == [
        {"citation_id": 1, "document_id": 7, "chunk_id": 11, "chunk_order": 0, "distance": 0.1}
    ]
    assert len(calls) == 1
    assert calls[0][1].id == user_id
    assert calls[0][2] == "What is DDRAG?"
    with SessionLocal() as session:
        query = session.get(ChatQuery, body["query_id"])
        assert query is not None
        assert query.status == "completed"
        assert query.chat_session.user_id == user_id
        assert query.user_message.content == "What is DDRAG?"
        assert query.assistant_message_id == body["assistant_message_id"]
        assert query.assistant_message.content == body["answer"]
        assert [(source.citation_id, source.chunk_id) for source in query.sources] == [(1, 11)]
        assert session.get(QuerySource, query.sources[0].id).document_id == 7


def test_no_context_answer_is_successful_without_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    token, _ = _register_and_login()
    session_id = _create_session(token)
    monkeypatch.setattr(
        "app.api.chat.answer_question",
        lambda *args, **kwargs: GroundedAnswer(
            answer="I do not have enough information to answer that based on the retrieved document context.",
            context_available=False,
            sources=[],
            citation_validation={"cited_ids": [], "valid": True, "invalid_citations": []},
        ),
    )

    response = client.post(
        f"/chat/sessions/{session_id}/questions",
        json={"question": "What is unknown?"},
        headers=_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["context_available"] is False
    assert response.json()["sources"] == []
    with SessionLocal() as session:
        query = session.get(ChatQuery, response.json()["query_id"])
        assert query.status == "completed"
        assert query.assistant_message is not None
        assert query.sources == []


def test_answering_failure_persists_failed_query_without_answer_or_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    token, _ = _register_and_login()
    session_id = _create_session(token)
    monkeypatch.setattr(
        "app.api.chat.answer_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(OllamaGenerationError("model unavailable")),
    )

    response = client.post(
        f"/chat/sessions/{session_id}/questions",
        json={"question": "What happened?"},
        headers=_headers(token),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Generation failed"
    with SessionLocal() as session:
        query = (
            session.query(ChatQuery)
            .filter_by(session_id=session_id)
            .order_by(ChatQuery.id.desc())
            .first()
        )
        assert query is not None
        assert query.status == "failed"
        assert query.user_message.content == "What happened?"
        assert query.assistant_message is None
        assert query.sources == []
        assert session.query(ChatMessage).filter_by(session_id=session_id, role="assistant").count() == 0


def test_question_endpoint_requires_an_owned_session(monkeypatch: pytest.MonkeyPatch) -> None:
    owner_token, _ = _register_and_login()
    other_token, _ = _register_and_login()
    session_id = _create_session(owner_token)
    monkeypatch.setattr("app.api.chat.answer_question", lambda *args, **kwargs: _answer_with_source())

    unauthenticated = client.post(f"/chat/sessions/{session_id}/questions", json={"question": "Hello"})
    foreign = client.post(
        f"/chat/sessions/{session_id}/questions",
        json={"question": "Hello"},
        headers=_headers(other_token),
    )
    missing = client.post(
        "/chat/sessions/2147483647/questions",
        json={"question": "Hello"},
        headers=_headers(owner_token),
    )

    assert unauthenticated.status_code == 401
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["detail"] == missing.json()["detail"] == "Chat session not found"


def test_question_validation_rejects_blank_content() -> None:
    token, _ = _register_and_login()
    session_id = _create_session(token)

    response = client.post(
        f"/chat/sessions/{session_id}/questions",
        json={"question": "   "},
        headers=_headers(token),
    )

    assert response.status_code == 422