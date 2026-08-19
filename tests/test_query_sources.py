"""Focused M10.4 tests for persistent query retrieval sources."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ChatMessage, ChatQuery, ChatSession, QuerySource, User
from app.db.session import SessionLocal


def _query() -> tuple[int, int]:
    with SessionLocal() as session:
        user = User(email=f"query-source-{uuid4()}@example.com")
        session.add(user)
        session.flush()
        chat_session = ChatSession(user_id=user.id)
        user_message = ChatMessage(role="user", content="What is DDRAG?")
        chat_session.messages = [user_message]
        session.add(chat_session)
        session.flush()
        query = ChatQuery(
            session_id=chat_session.id,
            user_message_id=user_message.id,
            status="completed",
        )
        session.add(query)
        session.commit()
        return user.id, query.id


def test_sources_persist_m9_metadata_in_citation_order() -> None:
    user_id, query_id = _query()
    with SessionLocal() as session:
        second = QuerySource(
            query_id=query_id,
            citation_id=2,
            document_id=42,
            chunk_id=502,
            chunk_order=1,
            distance=0.25,
        )
        first = QuerySource(
            query_id=query_id,
            citation_id=1,
            document_id=42,
            chunk_id=501,
            chunk_order=0,
            distance=0.1,
        )
        session.add_all([second, first])
        session.commit()

        sources = (
            session.query(QuerySource)
            .filter_by(query_id=query_id)
            .order_by(QuerySource.citation_id.asc())
            .all()
        )
        assert [(source.citation_id, source.chunk_id) for source in sources] == [(1, 501), (2, 502)]
        assert sources[0].document_id == 42
        assert sources[0].chunk_order == 0
        assert sources[0].distance == pytest.approx(0.1)
        assert sources[0].query.chat_session.user_id == user_id
        assert "chunk_text" not in QuerySource.__table__.columns


def test_query_can_persist_without_sources() -> None:
    _, query_id = _query()
    with SessionLocal() as session:
        query = session.get(ChatQuery, query_id)

        assert query is not None
        assert query.sources == []


def test_query_citation_id_is_unique() -> None:
    _, query_id = _query()
    with SessionLocal() as session:
        session.add(
            QuerySource(
                query_id=query_id,
                citation_id=1,
                document_id=1,
                chunk_id=10,
                chunk_order=0,
                distance=0.1,
            )
        )
        session.commit()
        session.add(
            QuerySource(
                query_id=query_id,
                citation_id=1,
                document_id=2,
                chunk_id=20,
                chunk_order=0,
                distance=0.2,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()