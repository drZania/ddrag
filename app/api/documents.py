"""Document upload API for M4."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chunking import persist_document_chunks
from app.config import get_settings
from app.db.models import Document, User
from app.db.session import get_db
from app.embeddings import EmbeddingValidationError, OllamaEmbeddingError, embed_document_chunks
from app.extraction import ExtractionError, extract_text
from app.storage import delete_document_file, generate_storage_filename, save_document_file, sha256_bytes

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()
DOCUMENT_DUPLICATE_CONSTRAINT = "uq_documents_user_sha256"

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _is_document_duplicate_violation(error: sqlalchemy_exc.IntegrityError) -> bool:
    """Return whether the PostgreSQL violation is the document duplicate constraint."""

    original_error = getattr(error, "orig", None)
    diagnostics = getattr(original_error, "diag", None)
    return getattr(diagnostics, "constraint_name", None) == DOCUMENT_DUPLICATE_CONSTRAINT


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    original_filename: str
    storage_path: str
    content_type: str
    file_size_bytes: int
    sha256_digest: str
    status: str
    created_at: datetime


class DocumentTextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    extracted_text: str | None
    extraction_error: str | None


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[Document]:
    """List all documents belonging to the authenticated user."""

    return (
        session.query(Document)
        .filter_by(user_id=current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Document:
    """Return one document owned by the authenticated user."""

    document = (
        session.query(Document)
        .filter_by(id=document_id, user_id=current_user.id)
        .one_or_none()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
async def get_document_text(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Document:
    """Return extraction status and text for one document owned by the authenticated user."""

    document = (
        session.query(Document)
        .filter_by(id=document_id, user_id=current_user.id)
        .one_or_none()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete one document owned by the authenticated user and its stored file."""

    document = (
        session.query(Document)
        .filter_by(id=document_id, user_id=current_user.id)
        .one_or_none()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    storage_path = document.storage_path
    session.delete(document)
    session.commit()
    delete_document_file(settings.document_storage_path, storage_path)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Document:
    """Upload and persist a document for the authenticated user."""

    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required for upload",
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported document type",
        )

    uploaded_bytes = await file.read()
    if len(uploaded_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(uploaded_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds the 10 MB size limit",
        )

    digest = sha256_bytes(uploaded_bytes)
    existing = (
        session.query(Document)
        .filter_by(user_id=current_user.id, sha256_digest=digest)
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A duplicate document was already uploaded by this user",
        )

    storage_filename = generate_storage_filename(file.filename)
    storage_path = settings.document_storage_path

    try:
        saved_name = save_document_file(storage_path, file.filename, uploaded_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded document",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded document",
        ) from exc

    document = Document(
        user_id=current_user.id,
        original_filename=file.filename,
        storage_path=saved_name,
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(uploaded_bytes),
        sha256_digest=digest,
        status="processing",
    )

    try:
        session.add(document)
        session.commit()
        session.refresh(document)
    except sqlalchemy_exc.IntegrityError as error:
        session.rollback()
        try:
            delete_document_file(storage_path, saved_name)
        except ValueError:
            pass
        if _is_document_duplicate_violation(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A duplicate document was already uploaded by this user",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record uploaded document metadata",
        ) from None
    except Exception:
        session.rollback()
        try:
            delete_document_file(storage_path, saved_name)
        except ValueError:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record uploaded document metadata",
        ) from None

    try:
        document.extracted_text = extract_text(document.content_type, uploaded_bytes)
        document.extraction_error = None
        document.status = "ready"
    except ExtractionError as error:
        document.extracted_text = None
        document.extraction_error = str(error)
        document.status = "failed"
    else:
        try:
            persist_document_chunks(
                session,
                document,
                chunk_size=settings.chunk_size_chars,
                overlap=settings.chunk_overlap_chars,
                chunking_version=settings.chunking_version,
            )
            embed_document_chunks(session, document)
        except Exception as error:
            session.rollback()
            failed_document = session.get(Document, document.id)
            if failed_document is None:
                raise

            failed_document.status = "failed"
            if isinstance(error, (EmbeddingValidationError, OllamaEmbeddingError, ValueError, TypeError)):
                failed_document.extraction_error = f"Failed to embed document chunks: {error}"
            else:
                failed_document.extraction_error = f"Failed to persist document chunks: {error}"

    try:
        session.commit()
    except Exception as error:
        session.rollback()
        try:
            failed_document = session.get(Document, document.id)
        except Exception as recovery_error:
            raise error from recovery_error
        if failed_document is None:
            raise
        failed_document.status = "failed"
        failed_document.extraction_error = f"Failed to finalize document chunks: {error}"
        try:
            session.commit()
        except Exception as recovery_error:
            session.rollback()
            raise error from recovery_error

    session.refresh(document)

    return document
