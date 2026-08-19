"""Persistent user-owned chat sessions for M10."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatSession(Base):
    """A minimal chat session owned by one authenticated user."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="chat_session",
        cascade="all, delete-orphan",
    )
    queries: Mapped[list["ChatQuery"]] = relationship(
        back_populates="chat_session",
        cascade="all, delete-orphan",
    )