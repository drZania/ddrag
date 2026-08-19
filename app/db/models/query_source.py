"""Persistent retrieval-source metadata for chat queries."""

from sqlalchemy import Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuerySource(Base):
    """One M9 source attribution persisted for a chat query."""

    __tablename__ = "query_sources"
    __table_args__ = (
        UniqueConstraint("query_id", "citation_id", name="uq_query_sources_query_citation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(
        ForeignKey("chat_queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    citation_id: Mapped[int] = mapped_column(nullable=False)
    document_id: Mapped[int] = mapped_column(nullable=False)
    chunk_id: Mapped[int] = mapped_column(nullable=False)
    chunk_order: Mapped[int] = mapped_column(nullable=False)
    distance: Mapped[float] = mapped_column(Float(), nullable=False)

    query: Mapped["ChatQuery"] = relationship(back_populates="sources")