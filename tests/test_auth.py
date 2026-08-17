"""Focused authentication tests for the M3 identity foundation."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token, decode_access_token
from app.config import get_settings
from app.db.models import User
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def credentials() -> tuple[str, str]:
    return f"auth-test-{uuid4()}@EXAMPLE.COM", "correct horse battery staple"


def test_registration_hashes_password_and_returns_safe_user() -> None:
    email, password = credentials()

    response = client.post("/auth/register", json={"email": email, "password": password})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email.lower()
    assert "password_hash" not in body
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        assert user.password_hash is not None
        assert user.password_hash != password


def test_duplicate_registration_is_rejected() -> None:
    email, password = credentials()
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201

    response = client.post("/auth/register", json={"email": email, "password": password})

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"


def test_login_returns_token_with_user_identity() -> None:
    email, password = credentials()
    registered = client.post("/auth/register", json={"email": email, "password": password}).json()

    response = client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"
    assert decode_access_token(token) == registered["id"]


def test_login_failures_are_generic() -> None:
    email, password = credentials()
    client.post("/auth/register", json={"email": email, "password": password})

    wrong_password = client.post("/auth/login", json={"email": email, "password": "wrong password"})
    unknown_user = client.post(
        "/auth/login", json={"email": "unknown@example.com", "password": password}
    )

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_expired_and_invalid_tokens_are_rejected() -> None:
    email, password = credentials()
    user = client.post("/auth/register", json={"email": email, "password": password}).json()
    settings = get_settings()
    expired = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    invalid_signature = create_access_token(user["id"]) + "tampered"

    expired_response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    invalid_response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {invalid_signature}"}
    )

    assert expired_response.status_code == invalid_response.status_code == 401
    assert expired_response.headers["WWW-Authenticate"] == "Bearer"
    assert invalid_response.headers["WWW-Authenticate"] == "Bearer"


def test_current_user_requires_existing_authenticated_user() -> None:
    missing = client.get("/auth/me")
    nonexistent = create_access_token(2_147_483_647)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {nonexistent}"})

    assert missing.status_code == 401
    assert response.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_current_user_rejects_malformed_authorization() -> None:
    response = client.get("/auth/me", headers={"Authorization": "Basic not-a-bearer-token"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_openapi_describes_bearer_jwt_authentication() -> None:
    openapi = app.openapi()
    security_scheme = openapi["components"]["securitySchemes"]["HTTPBearer"]

    assert security_scheme == {"type": "http", "scheme": "bearer"}
    assert not any(
        scheme["type"] == "oauth2"
        for scheme in openapi["components"]["securitySchemes"].values()
    )
    assert openapi["paths"]["/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert (
        "application/json"
        in openapi["paths"]["/auth/login"]["post"]["requestBody"]["content"]
    )


def test_current_user_returns_only_public_fields() -> None:
    email, password = credentials()
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert set(response.json()) == {"id", "email", "created_at"}