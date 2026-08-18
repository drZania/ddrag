"""Database/model tests for the M5 step 2 extraction persistence columns."""

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import Document, User
from app.db.session import SessionLocal, engine


def _create_user(session) -> User:
    user = User(email=f"extraction-persist-{uuid4()}@example.com")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _new_document(user_id: int, **overrides) -> Document:
    defaults = dict(
        user_id=user_id,
        original_filename="report.txt",
        storage_path=f"{uuid4()}.txt",
        content_type="text/plain",
        file_size_bytes=11,
        sha256_digest=uuid4().hex + uuid4().hex[:32],
        status="uploaded",
    )
    defaults.update(overrides)
    return Document(**defaults)


def test_documents_table_has_nullable_extraction_columns() -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("documents")}

    assert "extracted_text" in columns
    assert columns["extracted_text"]["nullable"] is True
    assert "extraction_error" in columns
    assert columns["extraction_error"]["nullable"] is True


def test_document_accepts_null_extraction_fields() -> None:
    with SessionLocal() as session:
        user = _create_user(session)
        document = _new_document(user.id)
        session.add(document)
        session.commit()
        session.refresh(document)

        assert document.extracted_text is None
        assert document.extraction_error is None


def test_extracted_text_can_be_persisted_and_retrieved() -> None:
    with SessionLocal() as session:
        user = _create_user(session)
        document = _new_document(user.id, extracted_text="hello extracted text")
        session.add(document)
        session.commit()
        document_id = document.id

    with SessionLocal() as session:
        stored = session.get(Document, document_id)
        assert stored is not None
        assert stored.extracted_text == "hello extracted text"
        assert stored.extraction_error is None


def test_extraction_error_can_be_persisted_and_retrieved() -> None:
    with SessionLocal() as session:
        user = _create_user(session)
        document = _new_document(
            user.id,
            content_type="application/pdf",
            extraction_error="Failed to read PDF document",
        )
        session.add(document)
        session.commit()
        document_id = document.id

    with SessionLocal() as session:
        stored = session.get(Document, document_id)
        assert stored is not None
        assert stored.extraction_error == "Failed to read PDF document"
        assert stored.extracted_text is None


def test_extracted_text_and_extraction_error_can_coexist() -> None:
    with SessionLocal() as session:
        user = _create_user(session)
        document = _new_document(
            user.id,
            extracted_text="partial text",
            extraction_error="Some pages failed to parse",
        )
        session.add(document)
        session.commit()
        document_id = document.id

    with SessionLocal() as session:
        stored = session.get(Document, document_id)
        assert stored is not None
        assert stored.extracted_text == "partial text"
        assert stored.extraction_error == "Some pages failed to parse"


def test_document_status_constraint_still_enforced() -> None:
    with SessionLocal() as session:
        user = _create_user(session)
        document = _new_document(user.id, status="not-a-real-status")
        session.add(document)
        with pytest.raises(IntegrityError):
            session.commit()


def test_document_user_sha256_uniqueness_still_enforced() -> None:
    with SessionLocal() as session:
        user = _create_user(session)
        digest = uuid4().hex + uuid4().hex[:32]
        session.add(_new_document(user.id, sha256_digest=digest))
        session.commit()

        session.add(_new_document(user.id, sha256_digest=digest, storage_path=f"{uuid4()}.txt"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_document_ownership_still_scoped_to_user() -> None:
    with SessionLocal() as session:
        owner = _create_user(session)
        other = _create_user(session)
        document = _new_document(owner.id, extracted_text="owner-only text")
        session.add(document)
        session.commit()
        document_id = document.id

    with SessionLocal() as session:
        found_for_owner = (
            session.query(Document).filter_by(id=document_id, user_id=owner.id).one_or_none()
        )
        found_for_other = (
            session.query(Document).filter_by(id=document_id, user_id=other.id).one_or_none()
        )

        assert found_for_owner is not None
        assert found_for_other is None
