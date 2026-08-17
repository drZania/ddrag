"""JWT access-token creation and validation."""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


class InvalidTokenError(Exception):
    """Raised when an access token cannot establish a user identity."""


def create_access_token(user_id: int) -> str:
    """Create a short-lived token whose subject is the user ID."""

    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """Validate a token and return its integer user subject."""

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError from exc