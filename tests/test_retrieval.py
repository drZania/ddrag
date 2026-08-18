"""Focused tests for the M8 retrieval milestone."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import SessionLocal
from app.embeddings import OllamaEmbeddingError
from app.main import app
from app.retrieval import RetrievalValidationError, retrieve_chunks, validate_top_k

client = TestClient(app)
VECTOR_DIMENSION = 1024


def _vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second] + [0.0] * (VECTOR_DIMENSION - 2)


def _register_and_login_with_email() -> tuple[str, str]:
    email = f"retrieval-{uuid4()}@example.com"
    password = "correct horse battery staple"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"], email


def _register_and_login() -> str:
    token, _ = _register_and_login_with_email()
    return token


def _seed_chunks(user: User, values: list[tuple[str, list[float] | None]]) -> None:
    document = Document(
        user_id=user.id,
        original_filename="retrieval.txt",
        storage_path=f"{uuid4()}.txt",
        content_type="text/plain",
        file_size_bytes=10,
        sha256_digest=uuid4().hex,
        status="ready",
        extracted_text="seeded retrieval text",
    )
    document.chunks = [
        Chunk(
            chunk_order=index,
            chunk_text=text,
            chunk_size_chars=100,
            chunk_overlap_chars=0,
            embedding=embedding,
        )
        for index, (text, embedding) in enumerate(values)
    ]
    with SessionLocal() as session:
        session.add(document)
        session.commit()


def _user() -> User:
    with SessionLocal() as session:
        user = User(email=f"retrieval-user-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def test_retrieve_chunks_returns_relevant_owned_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    _seed_chunks(user, [("relevant", _vector(1.0)), ("less relevant", _vector(0.0, 1.0))])
    monkeypatch.setattr("app.retrieval.generate_embedding", lambda query: _vector(1.0))

    with SessionLocal() as session:
        response = retrieve_chunks(session, session.get(User, user.id), "where is the answer?", top_k=1)

    assert [result.chunk_text for result in response.results] == ["relevant"]
    assert response.results[0].document_id > 0
    assert response.results[0].chunk_order == 0
    assert response.results[0].distance == pytest.approx(0.0)
    assert response.diagnostics.candidates_considered == 2
    assert response.diagnostics.results_returned == 1


def test_retrieval_isolated_to_authenticated_user(monkeypatch: pytest.MonkeyPatch) -> None:
    owner_token, owner_email = _register_and_login_with_email()
    other_user = _user()
    with SessionLocal() as session:
        owner = session.query(User).filter_by(email=owner_email).one()
        assert owner is not None
        _seed_chunks(other_user, [("private other user content", _vector(1.0))])
        _seed_chunks(owner, [("owner content", _vector(1.0))])

    monkeypatch.setattr("app.retrieval.generate_embedding", lambda query: _vector(1.0))
    response = client.post(
        "/retrieval",
        json={"query": "find content", "top_k": 10},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    assert [item["chunk_text"] for item in response.json()["results"]] == ["owner content"]


def test_top_k_and_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    _seed_chunks(user, [(f"chunk-{index}", _vector(1.0)) for index in range(3)])
    monkeypatch.setattr("app.retrieval.generate_embedding", lambda query: _vector(1.0))

    with SessionLocal() as session:
        response = retrieve_chunks(session, session.get(User, user.id), "query", top_k=2)
        empty_user = _user()
        empty = retrieve_chunks(session, session.get(User, empty_user.id), "query", top_k=2)

    assert len(response.results) == 2
    assert response.diagnostics.top_k_requested == 2
    assert empty.results == []
    assert empty.diagnostics.candidates_considered == 0


@pytest.mark.parametrize("top_k", [0, -1, 51])
def test_validate_top_k_rejects_invalid_values(top_k: int) -> None:
    with pytest.raises(RetrievalValidationError):
        validate_top_k(top_k)


@pytest.mark.parametrize("default_top_k", [0, 51])
def test_settings_reject_invalid_default_top_k(monkeypatch: pytest.MonkeyPatch, default_top_k: int) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setenv("RETRIEVAL_DEFAULT_TOP_K", str(default_top_k))

    with pytest.raises(ValidationError, match="retrieval_default_top_k"):
        Settings()


def test_query_embedding_failure_returns_safe_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _register_and_login()
    monkeypatch.setattr(
        "app.retrieval.generate_embedding",
        lambda query: (_ for _ in ()).throw(OllamaEmbeddingError("service unavailable")),
    )

    response = client.post(
        "/retrieval",
        json={"query": "query"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Query embedding failed"


def test_retrieval_requires_authentication() -> None:
    response = client.post("/retrieval", json={"query": "query"})

    assert response.status_code == 401


def test_blank_query_is_rejected() -> None:
    token = _register_and_login()

    response = client.post(
        "/retrieval",
        json={"query": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422