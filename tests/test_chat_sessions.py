"""Focused M10.1 tests for persistent user-owned chat sessions."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import ChatSession
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


def _current_user_id(token: str) -> int:
    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 200
    return response.json()["id"]


def test_authenticated_session_creation_persists_owner() -> None:
    token = _register_and_login()
    current_user_id = _current_user_id(token)

    response = client.post("/chat/sessions", headers=_headers(token))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "created_at"}
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


def test_session_routes_require_authentication() -> None:
    assert client.post("/chat/sessions").status_code == 401
    assert client.get("/chat/sessions").status_code == 401
    assert client.get("/chat/sessions/1").status_code == 401