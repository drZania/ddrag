"""Focused M10.1 tests for persistent user-owned chat sessions."""

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.answering import GroundedAnswer
from app.db.models import ChatMessage, ChatQuery, ChatSession, QuerySource
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _register_and_login() -> str:
    email = f"chat-session-{uuid4()}@example.com"
    password = "correct horse battery staple"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(token: str) -> int:
    response = client.post("/chat/sessions", headers=_headers(token))
    assert response.status_code == 201
    return response.json()["id"]


def _current_user_id(token: str) -> int:
    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 200
    return response.json()["id"]


def _answer() -> GroundedAnswer:
    return GroundedAnswer(answer="Answer.", context_available=False, sources=[], citation_validation={})


def test_authenticated_session_creation_persists_owner() -> None:
    token = _register_and_login()
    current_user_id = _current_user_id(token)

    response = client.post("/chat/sessions", headers=_headers(token))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "title", "created_at"}
    assert body["title"] == "Untitled chat"
    with SessionLocal() as session:
        persisted = session.get(ChatSession, body["id"])
        assert persisted is not None
        assert persisted.user_id == current_user_id


def test_client_supplied_owner_is_ignored() -> None:
    owner_token = _register_and_login()
    other_user_token = _register_and_login()
    owner_id = _current_user_id(owner_token)
    other_user_id = _current_user_id(other_user_token)

    response = client.post(
        "/chat/sessions",
        json={"user_id": other_user_id},
        headers=_headers(owner_token),
    )

    assert response.status_code == 201
    with SessionLocal() as session:
        persisted = session.get(ChatSession, response.json()["id"])
        assert persisted is not None
        assert persisted.user_id == owner_id
        assert persisted.user_id != other_user_id


def test_session_listing_and_retrieval_are_owned_and_deterministic() -> None:
    owner_token = _register_and_login()
    other_token = _register_and_login()
    first = client.post("/chat/sessions", headers=_headers(owner_token)).json()
    second = client.post("/chat/sessions", headers=_headers(owner_token)).json()
    client.post("/chat/sessions", headers=_headers(other_token))

    listed = client.get("/chat/sessions", headers=_headers(owner_token))
    owned = client.get(f"/chat/sessions/{first['id']}", headers=_headers(owner_token))
    cross_user = client.get(f"/chat/sessions/{first['id']}", headers=_headers(other_token))

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [second["id"], first["id"]]
    assert owned.status_code == 200
    assert owned.json()["id"] == first["id"]
    assert cross_user.status_code == 404
    assert cross_user.json()["detail"] == "Chat session not found"


def test_unknown_session_returns_not_found() -> None:
    token = _register_and_login()

    response = client.get("/chat/sessions/2147483647", headers=_headers(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session not found"


def test_owner_can_delete_session_and_its_dependent_records() -> None:
    owner_token = _register_and_login()
    other_token = _register_and_login()
    session_id = _create_session(owner_token)
    other_session_id = _create_session(other_token)

    with SessionLocal() as session:
        owner_session = session.get(ChatSession, session_id)
        assert owner_session is not None
        user_message = ChatMessage(session_id=session_id, role="user", content="Delete this conversation.")
        assistant_message = ChatMessage(session_id=session_id, role="assistant", content="Deleting it now.")
        session.add_all([user_message, assistant_message])
        session.flush()
        query = ChatQuery(
            session_id=session_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            status="completed",
        )
        session.add(query)
        session.flush()
        source = QuerySource(
            query_id=query.id,
            citation_id=1,
            document_id=1,
            chunk_id=1,
            chunk_order=0,
            distance=0.1,
        )
        session.add(source)
        session.commit()
        owner_message_ids = [user_message.id, assistant_message.id]
        query_id = query.id
        source_id = source.id

    deleted = client.delete(f"/chat/sessions/{session_id}", headers=_headers(owner_token))
    retrieved = client.get(f"/chat/sessions/{session_id}", headers=_headers(owner_token))

    assert deleted.status_code == 204
    assert retrieved.status_code == 404
    with SessionLocal() as session:
        assert session.get(ChatSession, session_id) is None
        assert all(session.get(ChatMessage, message_id) is None for message_id in owner_message_ids)
        assert session.get(ChatQuery, query_id) is None
        assert session.get(QuerySource, source_id) is None
        assert session.get(ChatSession, other_session_id) is not None


def test_session_deletion_requires_ownership_and_authentication() -> None:
    owner_token = _register_and_login()
    other_token = _register_and_login()
    session_id = _create_session(owner_token)

    unauthenticated = client.delete(f"/chat/sessions/{session_id}")
    foreign = client.delete(f"/chat/sessions/{session_id}", headers=_headers(other_token))
    missing = client.delete("/chat/sessions/2147483647", headers=_headers(owner_token))

    assert unauthenticated.status_code == 401
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["detail"] == missing.json()["detail"] == "Chat session not found"
    assert client.get(f"/chat/sessions/{session_id}", headers=_headers(owner_token)).status_code == 200


def test_first_question_sets_bounded_normalized_title_and_manual_rename_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _register_and_login()
    session_id = _create_session(token)
    monkeypatch.setattr("app.api.chat.answer_question", lambda *args, **kwargs: _answer())
    question = "  What   does   this   session   demonstrate?  "

    response = client.post(f"/chat/sessions/{session_id}/questions", json={"question": question}, headers=_headers(token))
    assert response.status_code == 201
    listed = client.get("/chat/sessions", headers=_headers(token))
    assert listed.json()[0]["title"] == "What does this session demonstrate?"

    renamed = client.patch(f"/chat/sessions/{session_id}", json={"title": "  Manual research chat  "}, headers=_headers(token))
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Manual research chat"
    assert client.post(f"/chat/sessions/{session_id}/questions", json={"question": "A later question"}, headers=_headers(token)).status_code == 201
    assert client.get(f"/chat/sessions/{session_id}", headers=_headers(token)).json()["title"] == "Manual research chat"


def test_first_question_title_is_bounded_and_persists_after_session_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _register_and_login()
    session_id = _create_session(token)
    monkeypatch.setattr("app.api.chat.answer_question", lambda *args, **kwargs: _answer())
    question = "A" * 140

    assert client.post(f"/chat/sessions/{session_id}/questions", json={"question": question}, headers=_headers(token)).status_code == 201
    retrieved = client.get(f"/chat/sessions/{session_id}", headers=_headers(token))

    assert retrieved.status_code == 200
    assert retrieved.json()["title"] == "A" * 120


def test_session_title_rename_validates_and_protects_ownership() -> None:
    owner_token = _register_and_login()
    other_token = _register_and_login()
    session_id = _create_session(owner_token)

    assert client.patch(f"/chat/sessions/{session_id}", json={"title": ""}, headers=_headers(owner_token)).status_code == 422
    assert client.patch(f"/chat/sessions/{session_id}", json={"title": "   "}, headers=_headers(owner_token)).status_code == 422
    assert client.patch(f"/chat/sessions/{session_id}", json={"title": "x" * 121}, headers=_headers(owner_token)).status_code == 422
    assert client.patch(f"/chat/sessions/{session_id}", json={"title": "Foreign"}, headers=_headers(other_token)).status_code == 404
    assert client.patch("/chat/sessions/2147483647", json={"title": "Missing"}, headers=_headers(owner_token)).status_code == 404
    assert client.patch(f"/chat/sessions/{session_id}", json={"title": "No auth"}).status_code == 401


def test_session_routes_require_authentication() -> None:
    assert client.post("/chat/sessions").status_code == 401
    assert client.get("/chat/sessions").status_code == 401
    assert client.get("/chat/sessions/1").status_code == 401
    assert client.delete("/chat/sessions/1").status_code == 401