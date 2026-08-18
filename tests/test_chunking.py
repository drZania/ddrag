"""Focused tests for the M6 chunking milestone."""

import io
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api import documents as documents_module
from app.chunking import chunk_text, persist_document_chunks
from app.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _register_and_login() -> str:
    email = f"chunking-{uuid4()}@example.com"
    password = "correct horse battery staple"

    register = client.post("/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def _configure_storage_and_chunking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    chunk_size_chars: int = 1000,
    chunk_overlap_chars: int = 200,
    chunking_version: str = "ddrag-chunking-v1",
) -> None:
    monkeypatch.setattr(
        documents_module,
        "settings",
        type(
            "Settings",
            (),
            {
                "document_storage_path": str(tmp_path),
                "max_upload_size_bytes": 10 * 1024 * 1024,
                "chunk_size_chars": chunk_size_chars,
                "chunk_overlap_chars": chunk_overlap_chars,
                "chunking_version": chunking_version,
            },
        )(),
    )


def _new_document(user_id: int, **overrides: object) -> Document:
    defaults: dict[str, object] = {
        "user_id": user_id,
        "original_filename": "notes.txt",
        "storage_path": f"{uuid4()}.txt",
        "content_type": "text/plain",
        "file_size_bytes": 12,
        "sha256_digest": uuid4().hex,
        "status": "ready",
        "extracted_text": "",
    }
    defaults.update(overrides)
    return Document(**defaults)


def test_chunk_text_empty_input_returns_empty_list() -> None:
    assert chunk_text("", chunk_size=5, overlap=2) == []


def test_chunk_text_shorter_than_chunk_size_stays_single_chunk() -> None:
    assert chunk_text("hello", chunk_size=20, overlap=5) == ["hello"]


def test_chunk_text_exact_boundary_size_stays_single_chunk() -> None:
    assert chunk_text("abcdefghij", chunk_size=10, overlap=0) == ["abcdefghij"]


def test_chunk_text_large_input_preserves_order_and_no_data_loss() -> None:
    text = "ABCDE" * 500
    chunk_size = 128
    overlap = 17

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    assert len(chunks) > 1
    reconstructed = chunks[0] + "".join(chunk[overlap:] for chunk in chunks[1:])
    assert reconstructed == text


def test_chunk_text_with_zero_overlap_uses_adjacent_windows() -> None:
    assert chunk_text("abcdefghijkl", chunk_size=5, overlap=0) == ["abcde", "fghij", "kl"]


def test_chunk_text_with_normal_overlap_is_predictable() -> None:
    text = "abcdefghijklmnop"

    assert chunk_text(text, chunk_size=5, overlap=2) == ["abcde", "defgh", "ghijk", "jklmn", "mnop"]


def test_chunk_text_with_overlap_close_to_chunk_size_is_stable() -> None:
    chunks = chunk_text("abcdefghij", chunk_size=5, overlap=4)

    assert chunks == ["abcde", "bcdef", "cdefg", "defgh", "efghi", "fghij"]


def test_chunk_text_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("abc", chunk_size=0, overlap=0)


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("abcdef", chunk_size=5, overlap=-1)

    with pytest.raises(ValueError, match="overlap"):
        chunk_text("abcdef", chunk_size=5, overlap=5)


def test_chunk_text_is_deterministic() -> None:
    text = "the quick brown fox jumps over the lazy dog"
    assert chunk_text(text, chunk_size=12, overlap=4) == chunk_text(text, chunk_size=12, overlap=4)


def test_settings_expose_chunking_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")

    settings = Settings()

    assert settings.chunk_size_chars == 1000
    assert settings.chunk_overlap_chars == 200
    assert settings.chunking_version == "ddrag-chunking-v1"


def test_settings_allow_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setenv("CHUNK_SIZE_CHARS", "64")
    monkeypatch.setenv("CHUNK_OVERLAP_CHARS", "8")
    monkeypatch.setenv("CHUNKING_VERSION", "ddrag-chunking-v1-test")

    settings = Settings()

    assert settings.chunk_size_chars == 64
    assert settings.chunk_overlap_chars == 8
    assert settings.chunking_version == "ddrag-chunking-v1-test"


def test_settings_reject_invalid_chunking_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-settings")
    monkeypatch.setenv("CHUNK_SIZE_CHARS", "10")
    monkeypatch.setenv("CHUNK_OVERLAP_CHARS", "10")

    with pytest.raises(ValidationError):
        Settings()


def test_persist_document_chunks_for_ready_document_stores_ordered_records() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-ready-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, extracted_text="abcdefghijklmnop")
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(
            session,
            document,
            chunk_size=5,
            overlap=2,
            chunking_version="ddrag-chunking-v1-test",
        )
        session.commit()

        stored = (
            session.query(Chunk)
            .filter_by(document_id=document.id)
            .order_by(Chunk.chunk_order.asc())
            .all()
        )
        assert [chunk.chunk_order for chunk in stored] == [0, 1, 2, 3, 4]
        assert [chunk.chunk_text for chunk in stored] == ["abcde", "defgh", "ghijk", "jklmn", "mnop"]
        assert all(chunk.chunk_size_chars == 5 for chunk in stored)
        assert all(chunk.chunk_overlap_chars == 2 for chunk in stored)
        assert all(chunk.chunking_version == "ddrag-chunking-v1-test" for chunk in stored)


def test_persist_document_chunks_with_empty_extracted_text_creates_no_rows() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-empty-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, extracted_text="")
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(session, document, chunk_size=5, overlap=2)
        session.commit()

        stored = session.query(Chunk).filter_by(document_id=document.id).all()
        assert stored == []


def test_persist_document_chunks_skips_failed_document() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-failed-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, status="failed", extracted_text=None)
        session.add(document)
        session.commit()
        session.refresh(document)

        persisted = persist_document_chunks(session, document, chunk_size=5, overlap=2)
        session.commit()

        assert persisted == []
        assert session.query(Chunk).filter_by(document_id=document.id).count() == 0


def test_persist_document_chunks_skips_ready_document_with_none_text() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-none-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, status="ready", extracted_text=None)
        session.add(document)
        session.commit()
        session.refresh(document)

        persisted = persist_document_chunks(session, document, chunk_size=5, overlap=2)
        session.commit()

        assert persisted == []
        assert session.query(Chunk).filter_by(document_id=document.id).count() == 0


def test_reprocessing_replaces_existing_chunks_for_document() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-reprocess-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, extracted_text="abcdefghij")
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(session, document, chunk_size=5, overlap=1)
        session.commit()

        document.extracted_text = "qrstuvwxyz"
        persist_document_chunks(session, document, chunk_size=4, overlap=0)
        session.commit()

        stored = (
            session.query(Chunk)
            .filter_by(document_id=document.id)
            .order_by(Chunk.chunk_order.asc())
            .all()
        )
        assert [chunk.chunk_text for chunk in stored] == ["qrst", "uvwx", "yz"]
        assert [chunk.chunk_order for chunk in stored] == [0, 1, 2]


def test_upload_ready_document_persists_chunks_from_configured_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_storage_and_chunking(
        monkeypatch,
        tmp_path,
        chunk_size_chars=5,
        chunk_overlap_chars=2,
        chunking_version="ddrag-chunking-v1-upload",
    )
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"abcdefghijklmnop"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    document_id = response.json()["id"]
    assert response.json()["status"] == "ready"

    with SessionLocal() as session:
        stored = (
            session.query(Chunk)
            .filter_by(document_id=document_id)
            .order_by(Chunk.chunk_order.asc())
            .all()
        )
        assert [chunk.chunk_text for chunk in stored] == ["abcde", "defgh", "ghijk", "jklmn", "mnop"]
        assert all(chunk.chunk_size_chars == 5 for chunk in stored)
        assert all(chunk.chunk_overlap_chars == 2 for chunk in stored)
        assert all(chunk.chunking_version == "ddrag-chunking-v1-upload" for chunk in stored)


def test_upload_failed_document_does_not_persist_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_storage_and_chunking(monkeypatch, tmp_path, chunk_size_chars=5, chunk_overlap_chars=2)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    document_id = response.json()["id"]
    assert response.json()["status"] == "failed"

    with SessionLocal() as session:
        assert session.query(Chunk).filter_by(document_id=document_id).count() == 0


def test_upload_chunk_persistence_failure_marks_document_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_storage_and_chunking(monkeypatch, tmp_path, chunk_size_chars=5, chunk_overlap_chars=2)
    monkeypatch.setattr(
        documents_module,
        "persist_document_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("controlled chunk failure")),
    )
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"abcdefghijklmnop"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    document_id = response.json()["id"]
    assert response.json()["status"] == "failed"

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == "failed"
        assert document.extraction_error == "Failed to persist document chunks: controlled chunk failure"
        assert session.query(Chunk).filter_by(document_id=document_id).count() == 0


def test_upload_final_commit_failure_marks_document_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_storage_and_chunking(monkeypatch, tmp_path, chunk_size_chars=5, chunk_overlap_chars=2)
    token = _register_and_login()
    original_commit = Session.commit
    request_commit_count = 0

    def fail_final_commit(session: Session) -> None:
        nonlocal request_commit_count
        request_commit_count += 1
        if request_commit_count == 2:
            raise RuntimeError("controlled final commit failure")
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_final_commit)

    response = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"abcdefghijklmnop"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    document_id = response.json()["id"]
    assert response.json()["status"] == "failed"

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == "failed"
        assert document.extraction_error == "Failed to finalize document chunks: controlled final commit failure"
        assert session.query(Chunk).filter_by(document_id=document_id).count() == 0


def test_failed_chunk_reprocessing_rolls_back_to_previous_chunks() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-rollback-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, extracted_text="abcdefghij")
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(session, document, chunk_size=5, overlap=1)
        session.commit()

        document.extracted_text = "qrstuvwxyz"
        persist_document_chunks(session, document, chunk_size=4, overlap=0)
        session.rollback()

        stored = (
            session.query(Chunk)
            .filter_by(document_id=document.id)
            .order_by(Chunk.chunk_order.asc())
            .all()
        )
        assert [chunk.chunk_text for chunk in stored] == ["abcde", "efghi", "ij"]


def test_deleting_document_cascades_to_chunks() -> None:
    with SessionLocal() as session:
        user = User(email=f"chunk-cascade-{uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        document = _new_document(user.id, extracted_text="abcdefghij")
        session.add(document)
        session.commit()
        session.refresh(document)

        persist_document_chunks(session, document, chunk_size=5, overlap=1)
        session.commit()
        assert session.query(Chunk).filter_by(document_id=document.id).count() > 0

        session.delete(document)
        session.commit()

        assert session.query(Chunk).filter_by(document_id=document.id).count() == 0


def test_chunks_remain_owner_scoped_through_document_relationship() -> None:
    with SessionLocal() as session:
        owner = User(email=f"chunk-owner-{uuid4()}@example.com")
        other = User(email=f"chunk-other-{uuid4()}@example.com")
        session.add_all([owner, other])
        session.commit()
        session.refresh(owner)
        session.refresh(other)

        owner_document = _new_document(owner.id, extracted_text="owner data")
        other_document = _new_document(other.id, extracted_text="other data")
        session.add_all([owner_document, other_document])
        session.commit()
        session.refresh(owner_document)
        session.refresh(other_document)

        persist_document_chunks(session, owner_document, chunk_size=5, overlap=1)
        persist_document_chunks(session, other_document, chunk_size=5, overlap=1)
        session.commit()

        owner_chunk = session.query(Chunk).filter_by(document_id=owner_document.id).first()
        assert owner_chunk is not None

        visible_to_owner = (
            session.query(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .filter(Chunk.id == owner_chunk.id, Document.user_id == owner.id)
            .one_or_none()
        )
        visible_to_other = (
            session.query(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .filter(Chunk.id == owner_chunk.id, Document.user_id == other.id)
            .one_or_none()
        )

        assert visible_to_owner is not None
        assert visible_to_other is None
