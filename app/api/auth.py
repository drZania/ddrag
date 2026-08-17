"""Registration, login, and current-user routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.db.models import User
from app.db.session import get_db


PASSWORD_MIN_LENGTH = 8
EMAIL_UNIQUE_CONSTRAINT = "users_email_key"
router = APIRouter(prefix="/auth", tags=["auth"])


def _is_email_unique_violation(error: IntegrityError) -> bool:
    """Return whether PostgreSQL identified the users email constraint."""

    original_error = getattr(error, "orig", None)
    diagnostics = getattr(original_error, "diag", None)
    return getattr(diagnostics, "constraint_name", None) == EMAIL_UNIQUE_CONSTRAINT


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=PASSWORD_MIN_LENGTH)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("Enter a valid email address")
        return normalized


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@router.post("/register", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials, session: Annotated[Session, Depends(get_db)]) -> User:
    """Create a user with a normalized email and Argon2id password hash."""

    user = User(email=credentials.email, password_hash=hash_password(credentials.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if not _is_email_unique_violation(error):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(credentials: Credentials, session: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Verify credentials and return a bearer access token."""

    user = session.query(User).filter_by(email=credentials.email).one_or_none()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id), token_type="bearer")


@router.get("/me", response_model=PublicUser)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return safe public information for the authenticated user."""

    return user