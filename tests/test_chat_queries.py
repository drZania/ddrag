"""Focused M10.3 tests for persistent chat query records."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ChatMessage, ChatQuery, ChatSession, User
from app.db.session import SessionLocal


def _session_with_messages() -> tuple[int, int, int, int]:
    with SessionLocal() as session:
        user = User(email=f"chat-query-{uuid4()}@example.com")
        session.add(user)
        session.flush()
        chat_session = ChatSession(user_id=user.id)
        user_message = ChatMessage(role="user", content="What is DDRAG?")
        assistant_message = ChatMessage(role="assistant", content="A document-grounded chat system.")
        chat_session.messages = [user_message, assistant_message]
        session.add(chat_session)
        session.commit()
        return user.id, chat_session.id, user_message.id, assistant_message.id


@pytest.mark.parametrize("status", ["pending", "completed", "failed"])
def test_query_persists_valid_status_and_message_links(status: str) -> None:
    user_id, session_id, user_message_id, assistant_message_id = _session_with_messages()
    with SessionLocal() as session:
        query = ChatQuery(
            session_id=session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id if status == "completed" else None,
            status=status,
        )
        session.add(query)
        session.commit()
        session.refresh(query)

        assert query.chat_session.user_id == user_id
        assert query.user_message.role == "user"
        assert query.user_message.content == "What is DDRAG?"
        assert query.assistant_message_id == (
            assistant_message_id if status == "completed" else None
        )
        assert query.status == status
        assert query.created_at is not None
        assert query.updated_at is not None
        assert "question" not in ChatQuery.__table__.columns


def test_failed_query_persists_without_assistant_message() -> None:
    _, session_id, user_message_id, _ = _session_with_messages()
    with SessionLocal() as session:
        query = ChatQuery(
            session_id=session_id,
            user_message_id=user_message_id,
            status="failed",
        )
        session.add(query)
        session.commit()
        session.refresh(query)

        assert query.assistant_message_id is None
        assert query.assistant_message is None


def test_invalid_query_status_is_rejected() -> None:
    _, session_id, user_message_id, _ = _session_with_messages()
    with SessionLocal() as session:
        session.add(ChatQuery(session_id=session_id, user_message_id=user_message_id, status="running"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_user_message_can_link_to_only_one_query() -> None:
    _, session_id, user_message_id, _ = _session_with_messages()
    with SessionLocal() as session:
        session.add(ChatQuery(session_id=session_id, user_message_id=user_message_id, status="pending"))
        session.commit()
        session.add(ChatQuery(session_id=session_id, user_message_id=user_message_id, status="failed"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_assistant_message_can_link_to_only_one_query() -> None:
    _, session_id, user_message_id, assistant_message_id = _session_with_messages()
    with SessionLocal() as session:
        second_user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content="What sources support that?",
        )
        session.add(second_user_message)
        session.flush()
        session.add(
            ChatQuery(
                session_id=session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                status="completed",
            )
        )
        session.commit()
        session.add(
            ChatQuery(
                session_id=session_id,
                user_message_id=second_user_message.id,
                assistant_message_id=assistant_message_id,
                status="completed",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()