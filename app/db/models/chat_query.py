"""Persistent query workflow records for M10."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatQuery(Base):
    """Trace one submitted user message through its answer workflow."""

    __tablename__ = "chat_queries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="chat_query_status_check",
        ),
        ForeignKeyConstraint(
            ["user_message_id", "session_id"],
            ["chat_messages.id", "chat_messages.session_id"],
            name="fk_chat_queries_user_message_session",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["assistant_message_id", "session_id"],
            ["chat_messages.id", "chat_messages.session_id"],
            name="fk_chat_queries_assistant_message_session",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    assistant_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chat_session: Mapped["ChatSession"] = relationship(back_populates="queries")
    user_message: Mapped["ChatMessage"] = relationship(
        foreign_keys=[user_message_id],
        back_populates="submitted_query",
    )
    assistant_message: Mapped["ChatMessage | None"] = relationship(
        foreign_keys=[assistant_message_id],
        back_populates="response_query",
    )
    sources: Mapped[list["QuerySource"]] = relationship(
        back_populates="query",
        cascade="all, delete-orphan",
    )