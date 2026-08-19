"""Focused M10.5 tests for chat persistence ownership boundaries."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ChatMessage, ChatQuery, ChatSession, QuerySource, User
from app.db.session import SessionLocal


def _owned_session_with_messages() -> tuple[int, int, int, int]:
    with SessionLocal() as session:
        user = User(email=f"chat-owner-{uuid4()}@example.com")
        session.add(user)
        session.flush()
        chat_session = ChatSession(user_id=user.id)
        user_message = ChatMessage(role="user", content="What is DDRAG?")
        assistant_message = ChatMessage(role="assistant", content="A document-grounded chat system.")
        chat_session.messages = [user_message, assistant_message]
        session.add(chat_session)
        session.commit()
        return user.id, chat_session.id, user_message.id, assistant_message.id


@pytest.mark.parametrize("message_field", ["user_message_id", "assistant_message_id"])
def test_query_rejects_messages_from_another_users_session(message_field: str) -> None:
    _, owner_session_id, owner_user_message_id, owner_assistant_message_id = _owned_session_with_messages()
    _, foreign_session_id, foreign_user_message_id, foreign_assistant_message_id = _owned_session_with_messages()
    foreign_message_id = (
        foreign_user_message_id if message_field == "user_message_id" else foreign_assistant_message_id
    )
    message_ids = {
        "user_message_id": owner_user_message_id,
        "assistant_message_id": owner_assistant_message_id,
    }
    message_ids[message_field] = foreign_message_id

    with SessionLocal() as session:
        session.add(ChatQuery(session_id=owner_session_id, status="completed", **message_ids))
        with pytest.raises(IntegrityError):
            session.commit()

    assert owner_session_id != foreign_session_id


def test_query_source_ownership_resolves_through_its_owned_query_session() -> None:
    user_id, session_id, user_message_id, _ = _owned_session_with_messages()
    with SessionLocal() as session:
        query = ChatQuery(
            session_id=session_id,
            user_message_id=user_message_id,
            status="completed",
        )
        query.sources = [
            QuerySource(
                citation_id=1,
                document_id=7,
                chunk_id=11,
                chunk_order=0,
                distance=0.1,
            )
        ]
        session.add(query)
        session.commit()
        session.refresh(query)

        assert query.sources[0].query.chat_session.user_id == user_id