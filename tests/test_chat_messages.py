"""Focused M10.2 tests for persistent user-owned chat messages."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import ChatMessage, ChatSession
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _register_and_login() -> tuple[str, int]:
    email = f"chat-message-{uuid4()}@example.com"
    password = "correct horse battery staple"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    current_user = client.get("/auth/me", headers=_headers(token))
    assert current_user.status_code == 200
    return token, current_user.json()["id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(token: str) -> int:
    response = client.post("/chat/sessions", headers=_headers(token))
    assert response.status_code == 201
    return response.json()["id"]


def _create_message(token: str, session_id: int, role: str, content: str, **extra: object):
    return client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"role": role, "content": content, **extra},
        headers=_headers(token),
    )


def test_user_and_assistant_messages_persist_in_chronological_order() -> None:
    token, _ = _register_and_login()
    session_id = _create_session(token)

    user_message = _create_message(token, session_id, "user", "What is DDRAG?")
    assistant_message = _create_message(token, session_id, "assistant", "A document-grounded chat system.")
    listed = client.get(f"/chat/sessions/{session_id}/messages", headers=_headers(token))

    assert user_message.status_code == assistant_message.status_code == 201
    assert listed.status_code == 200
    assert [(message["role"], message["content"]) for message in listed.json()] == [
        ("user", "What is DDRAG?"),
        ("assistant", "A document-grounded chat system."),
    ]
    assert [message["id"] for message in listed.json()] == [
        user_message.json()["id"],
        assistant_message.json()["id"],
    ]
    with SessionLocal() as session:
        persisted = session.get(ChatMessage, assistant_message.json()["id"])
        assert persisted is not None
        assert persisted.session_id == session_id
        assert persisted.role == "assistant"


def test_message_role_is_validated() -> None:
    token, _ = _register_and_login()
    session_id = _create_session(token)

    response = _create_message(token, session_id, "system", "Not allowed")

    assert response.status_code == 422
    with SessionLocal() as session:
        assert session.query(ChatMessage).filter_by(session_id=session_id).count() == 0


def test_empty_message_content_is_rejected() -> None:
    token, _ = _register_and_login()
    session_id = _create_session(token)

    response = _create_message(token, session_id, "user", "")

    assert response.status_code == 422
    with SessionLocal() as session:
        assert session.query(ChatMessage).filter_by(session_id=session_id).count() == 0


def test_messages_cannot_use_client_controlled_ownership() -> None:
    owner_token, owner_id = _register_and_login()
    other_token, other_id = _register_and_login()
    session_id = _create_session(owner_token)

    response = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={
            "role": "user",
            "content": "Owned by the session owner.",
            "user_id": other_id,
            "session_id": 999999,
        },
        headers=_headers(owner_token),
    )

    assert response.status_code == 201
    with SessionLocal() as session:
        persisted = session.get(ChatMessage, response.json()["id"])
        assert persisted is not None
        assert persisted.session_id == session_id
        assert session.get(ChatSession, persisted.session_id).user_id == owner_id
        assert owner_id != other_id
        assert other_token


def test_message_routes_protect_owned_sessions() -> None:
    owner_token, _ = _register_and_login()
    other_token, _ = _register_and_login()
    session_id = _create_session(owner_token)
    _create_message(owner_token, session_id, "user", "Private message")

    foreign_list = client.get(f"/chat/sessions/{session_id}/messages", headers=_headers(other_token))
    foreign_create = _create_message(other_token, session_id, "assistant", "Unauthorized")
    missing_list = client.get("/chat/sessions/2147483647/messages", headers=_headers(owner_token))
    missing_create = _create_message(owner_token, 2147483647, "user", "Missing")

    assert foreign_list.status_code == foreign_create.status_code == 404
    assert missing_list.status_code == missing_create.status_code == 404
    assert foreign_list.json()["detail"] == foreign_create.json()["detail"] == "Chat session not found"
    assert missing_list.json()["detail"] == missing_create.json()["detail"] == "Chat session not found"


def test_message_routes_require_authentication() -> None:
    assert client.post("/chat/sessions/1/messages", json={"role": "user", "content": "Hello"}).status_code == 401
    assert client.get("/chat/sessions/1/messages").status_code == 401