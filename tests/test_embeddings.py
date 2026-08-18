"""Focused tests for the M7 embedding milestone."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import documents as documents_module
from app.chunking import persist_document_chunks
from app.config import Settings, get_settings
from app.db.models import Chunk, Document, User
from app.db.session import SessionLocal
from app.embeddings import (
    EmbeddingValidationError,
    OllamaEmbeddingError,
    embed_document_chunks,
    generate_embedding,
    validate_embedding_vector,
)
from app.main import app


client = TestClient(app)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self.payload


def _embedding_response(vector: list[object]) -> FakeResponse:
    return FakeResponse(json.dumps({"embeddings": [vector]}).encode())


def _register_and_login() -> str:
    email = f"embedding-lifecycle-{uuid4()}@example.com"
    password = "correct horse battery staple"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def _configure_document_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        documents_module,
        "settings",
        type(
            "Settings",
            (),
            {
                "document_storage_path": str(tmp_path),
                "max_upload_size_bytes": 10 * 1024 * 1024,
                "chunk_size_chars": 5,
                "chunk_overlap_chars": 0,
                "chunking_version": "ddrag-chunking-v1",
            },
        )(),
    )


def test_settings_expose_embedding_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")

    settings = Settings()

    assert settings.embedding_model == "qwen3-embedding:0.6b"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.embedding_dimension == 1024


def test_settings_allow_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setenv("EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11435")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1024")

    settings = Settings()

    assert settings.embedding_model == "nomic-embed-text"
    assert settings.ollama_base_url == "http://localhost:11435"
    assert settings.embedding_dimension == 1024


def test_settings_reject_invalid_embedding_values(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setenv("EMBEDDING_MODEL", "")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("dimension", [0, -1, 768, 384, 1536])
def test_settings_reject_dimensions_other_than_1024(
    monkeypatch: pytest.MonkeyPatch,
    dimension: int,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setenv("EMBEDDING_DIMENSION", str(dimension))

    with pytest.raises(ValidationError, match="embedding_dimension must be 1024"):
        Settings()


def test_validate_embedding_vector_accepts_valid_vector() -> None:
    vector = [0.1, -0.2, 3.0, 7.5]

    assert validate_embedding_vector(vector, expected_dimension=4) == vector


def test_validate_embedding_vector_rejects_dimension_mismatch() -> None:
    with pytest.raises(EmbeddingValidationError, match="dimension"):
        validate_embedding_vector([0.1, 0.2], expected_dimension=4)


def test_generate_embedding_uses_mocked_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    expected_vector = [0.1] * 1024

    def fake_urlopen(request, timeout=None):
        assert request.full_url == "http://127.0.0.1:11434/api/embed"
        assert request.get_method() == "POST"
        assert json.loads(request.data.decode()) == {
            "model": "qwen3-embedding:0.6b",
            "input": "hello world",
        }
        return _embedding_response(expected_vector)

    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setattr("app.embeddings.urlopen", fake_urlopen)

    vector = generate_embedding("hello world")

    assert vector == expected_vector
    assert len(vector) == 1024
    assert all(isinstance(value, float) and value == 0.1 for value in vector)


def test_generate_embedding_rejects_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.embeddings.urlopen", lambda *args, **kwargs: FakeResponse(b"not json"))

    with pytest.raises(OllamaEmbeddingError, match="malformed JSON"):
        generate_embedding("hello")


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({}, OllamaEmbeddingError),
        ({"embeddings": []}, OllamaEmbeddingError),
        ({"embeddings": [1, 2, 3]}, EmbeddingValidationError),
    ],
)
def test_generate_embedding_rejects_invalid_embedding_structure(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    error: type[Exception],
) -> None:
    monkeypatch.setattr(
        "app.embeddings.urlopen",
        lambda *args, **kwargs: FakeResponse(json.dumps(payload).encode()),
    )

    with pytest.raises(error):
        generate_embedding("hello")


@pytest.mark.parametrize("invalid_value", ["bad", float("nan"), float("inf"), float("-inf")])
def test_generate_embedding_rejects_non_numeric_or_non_finite_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: object,
) -> None:
    vector: list[object] = [0.1] * 1024
    vector[512] = invalid_value
    monkeypatch.setattr("app.embeddings.urlopen", lambda *args, **kwargs: _embedding_response(vector))

    with pytest.raises(EmbeddingValidationError):
        generate_embedding("hello")


@pytest.mark.parametrize("dimension", [1023, 1025])
def test_generate_embedding_rejects_wrong_dimension(
    monkeypatch: pytest.MonkeyPatch,
    dimension: int,
) -> None:
    monkeypatch.setattr(
        "app.embeddings.urlopen",
        lambda *args, **kwargs: _embedding_response([0.1] * dimension),
    )

    with pytest.raises(EmbeddingValidationError, match="dimension mismatch"):
        generate_embedding("hello")


def test_generate_embedding_converts_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error = HTTPError("http://127.0.0.1:11434/api/embed", 500, "model error", None, None)
    monkeypatch.setattr("app.embeddings.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(OllamaEmbeddingError, match="Ollama embedding request failed"):
        generate_embedding("hello")


def test_generate_embedding_handles_unavailable_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()

    def fake_urlopen(*args, **kwargs):
        raise URLError("service unavailable")

    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setattr("app.embeddings.urlopen", fake_urlopen)

    with pytest.raises(OllamaEmbeddingError, match="Ollama"):
        generate_embedding("hello")


def test_embed_document_chunks_persists_vector_for_each_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")

    with SessionLocal() as session:
        user = User(email=f"embed-user-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = Document(
            user_id=user.id,
            original_filename="notes.txt",
            storage_path=f"{uuid4()}.txt",
            content_type="text/plain",
            file_size_bytes=16,
            sha256_digest=uuid4().hex,
            status="ready",
            extracted_text="abcdefghij klmnopqrst uvwxyz",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(session, document, chunk_size=5, overlap=0)
        session.commit()

        expected_vector = [0.1] * 1024

        def fake_urlopen(request, timeout=None):
            return _embedding_response(expected_vector)

        import app.embeddings as embeddings_module

        monkeypatch.setattr(embeddings_module, "urlopen", fake_urlopen)
        embed_document_chunks(session, document)
        session.commit()

        stored = session.query(Chunk).filter_by(document_id=document.id).order_by(Chunk.chunk_order.asc()).all()
        assert len(stored) > 0
        assert all(chunk.embedding is not None for chunk in stored)
        assert all(len(chunk.embedding) == 1024 for chunk in stored)


def test_embedding_failure_marks_document_failed_without_committing_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_document_settings(monkeypatch, tmp_path)

    def fail_embedding(*args, **kwargs):
        raise OllamaEmbeddingError("service unavailable")

    monkeypatch.setattr(documents_module, "embed_document_chunks", fail_embedding)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"abcdefghij"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    document_id = response.json()["id"]
    assert response.json()["status"] == "failed"

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == "failed"
        assert document.extracted_text is None
        assert document.extraction_error == "Failed to embed document chunks: service unavailable"
        assert session.query(Chunk).filter_by(document_id=document_id).count() == 0


def test_failed_reembedding_rolls_back_to_previous_chunks_and_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    old_embedding = [0.1] * 1024
    with SessionLocal() as session:
        user = User(email=f"embedding-reprocess-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = Document(
            user_id=user.id,
            original_filename="notes.txt",
            storage_path=f"{uuid4()}.txt",
            content_type="text/plain",
            file_size_bytes=10,
            sha256_digest=uuid4().hex,
            status="ready",
            extracted_text="abcdefghij",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(session, document, chunk_size=5, overlap=0)
        session.flush()
        for chunk in session.query(Chunk).filter_by(document_id=document.id):
            chunk.embedding = old_embedding
        session.commit()
        document_id = document.id

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        initial = session.query(Chunk).filter_by(document_id=document.id).order_by(Chunk.chunk_order.asc()).all()
        assert all(chunk.embedding is not None for chunk in initial)
        assert all(list(chunk.embedding) == old_embedding for chunk in initial)

        document.extracted_text = "qrstuvwxyz"
        persist_document_chunks(session, document, chunk_size=4, overlap=0)
        session.flush()
        monkeypatch.setattr(
            "app.embeddings.generate_embedding",
            lambda *args, **kwargs: (_ for _ in ()).throw(OllamaEmbeddingError("service unavailable")),
        )

        with pytest.raises(OllamaEmbeddingError):
            embed_document_chunks(session, document)
        session.rollback()

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        restored = session.query(Chunk).filter_by(document_id=document.id).order_by(Chunk.chunk_order.asc()).all()
        assert document.status == "ready"
        assert document.extracted_text == "abcdefghij"
        assert [chunk.chunk_text for chunk in restored] == ["abcde", "fghij"]
        assert all(list(chunk.embedding) == old_embedding for chunk in restored)
