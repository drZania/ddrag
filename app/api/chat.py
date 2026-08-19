"""Authenticated persistent chat-session API for M10."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.answering import GroundedAnswer, answer_question
from app.auth.dependencies import get_current_user
from app.context import ContextSource
from app.db.models import ChatMessage, ChatQuery, ChatSession, QuerySource, User
from app.db.session import get_db
from app.embeddings import EmbeddingValidationError, OllamaEmbeddingError
from app.generation import OllamaGenerationError
from app.retrieval import RetrievalValidationError


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatSessionResponse(BaseModel):
    """Public representation of a user-owned chat session."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ChatMessageCreate(BaseModel):
    """The allowed fields for a message created in an owned chat session."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatMessageResponse(BaseModel):
    """Public representation of a persisted chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ChatQuestionRequest(BaseModel):
    """A validated question submitted to an owned chat session."""

    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class QuerySourceResponse(BaseModel):
    """Public source metadata preserved from M9 attribution."""

    citation_id: int
    document_id: int
    chunk_id: int
    chunk_order: int
    distance: float


class ChatQuestionResponse(BaseModel):
    """A persisted grounded answer and its M9 source attribution."""

    query_id: int
    assistant_message_id: int
    answer: str
    context_available: bool
    sources: list[QuerySourceResponse]
    citation_validation: dict[str, object]


def _owned_session(session: Session, current_user: User, session_id: int) -> ChatSession:
    """Load a chat session only when it belongs to the authenticated user."""

    chat_session = (
        session.query(ChatSession)
        .filter_by(id=session_id, user_id=current_user.id)
        .one_or_none()
    )
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    return chat_session


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ChatSession:
    """Create a chat session owned by the authenticated user."""

    chat_session = ChatSession(user_id=current_user.id)
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ChatSession]:
    """List only chat sessions owned by the authenticated user."""

    return (
        session.query(ChatSession)
        .filter_by(user_id=current_user.id)
        .order_by(ChatSession.id.desc())
        .all()
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ChatSession:
    """Return one chat session owned by the authenticated user."""

    return _owned_session(session, current_user, session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: int,
    request: ChatMessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ChatMessage:
    """Persist a message in a chat session owned by the authenticated user."""

    chat_session = _owned_session(session, current_user, session_id)
    message = ChatMessage(
        session_id=chat_session.id,
        role=request.role,
        content=request.content,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ChatMessage]:
    """List messages from one chat session owned by the authenticated user."""

    chat_session = _owned_session(session, current_user, session_id)
    return (
        session.query(ChatMessage)
        .filter_by(session_id=chat_session.id)
        .order_by(ChatMessage.id.asc())
        .all()
    )


def _mark_query_failed(session: Session, query: ChatQuery) -> None:
    """Persist a failed query after its user message and pending record are committed."""

    query.status = "failed"
    session.commit()


@router.post(
    "/sessions/{session_id}/questions",
    response_model=ChatQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_question(
    session_id: int,
    request: ChatQuestionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ChatQuestionResponse:
    """Persist and answer a question in a chat session owned by the current user."""

    chat_session = _owned_session(session, current_user, session_id)
    user_message = ChatMessage(
        session_id=chat_session.id,
        role="user",
        content=request.question,
    )
    query = ChatQuery(
        session_id=chat_session.id,
        user_message=user_message,
        status="pending",
    )
    session.add_all([user_message, query])
    session.commit()
    session.refresh(query)

    try:
        answer = answer_question(session, current_user, request.question)
    except RetrievalValidationError as exc:
        _mark_query_failed(session, query)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except (EmbeddingValidationError, OllamaEmbeddingError) as exc:
        _mark_query_failed(session, query)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Query embedding failed",
        ) from exc
    except OllamaGenerationError as exc:
        _mark_query_failed(session, query)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generation failed",
        ) from exc
    except Exception:
        _mark_query_failed(session, query)
        raise

    assistant_message = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content=answer.answer,
    )
    query.assistant_message = assistant_message
    query.status = "completed"
    sources = [
        QuerySource(
            citation_id=source.citation_id,
            document_id=source.document_id,
            chunk_id=source.chunk_id,
            chunk_order=source.chunk_order,
            distance=source.distance,
        )
        for source in answer.sources
    ]
    query.sources = sources
    session.add(assistant_message)
    session.commit()
    session.refresh(query)

    return ChatQuestionResponse(
        query_id=query.id,
        assistant_message_id=assistant_message.id,
        answer=answer.answer,
        context_available=answer.context_available,
        sources=[
            QuerySourceResponse(
                citation_id=source.citation_id,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                chunk_order=source.chunk_order,
                distance=source.distance,
            )
            for source in answer.sources
        ],
        citation_validation=answer.citation_validation,
    )


__all__ = [
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatQuestionRequest",
    "ChatQuestionResponse",
    "ChatSessionResponse",
    "QuerySourceResponse",
    "router",
]