"""Persistent user and assistant messages for M10."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatMessage(Base):
    """A user or assistant message belonging to one chat session."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="chat_message_role_check"),
        UniqueConstraint("id", "session_id", name="uq_chat_messages_id_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chat_session: Mapped["ChatSession"] = relationship(back_populates="messages")
    submitted_query: Mapped["ChatQuery | None"] = relationship(
        foreign_keys="ChatQuery.user_message_id",
        back_populates="user_message",
    )
    response_query: Mapped["ChatQuery | None"] = relationship(
        foreign_keys="ChatQuery.assistant_message_id",
        back_populates="assistant_message",
    )