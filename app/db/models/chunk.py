"""Chunk records for the M6 chunking milestone."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Chunk(Base):
    """Persisted chunk metadata for a document's normalized text."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_order", name="uq_chunks_document_order"),
        CheckConstraint("chunk_size_chars > 0", name="chunk_size_positive"),
        CheckConstraint("chunk_overlap_chars >= 0", name="chunk_overlap_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_order: Mapped[int] = mapped_column(nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text(), nullable=False)
    chunk_size_chars: Mapped[int] = mapped_column(nullable=False)
    chunk_overlap_chars: Mapped[int] = mapped_column(nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False, default="ddrag-chunking-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")
