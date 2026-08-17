"""Observable tests for the M1 application foundation."""

import uuid

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


client = TestClient(app)


def test_application_can_be_imported() -> None:
    assert app.title == "DDRAG"


def test_health_endpoint_returns_success() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_id_is_generated_and_returned() -> None:
    response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert str(uuid.UUID(request_id)) == request_id


def test_valid_request_id_is_preserved() -> None:
    request_id = str(uuid.uuid4())

    response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced() -> None:
    response = client.get("/health", headers={"X-Request-ID": "not-a-uuid"})

    replacement = response.headers["X-Request-ID"]
    assert str(uuid.UUID(replacement)) == replacement
    assert replacement != "not-a-uuid"


def test_configuration_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test DDRAG")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.app_name == "Test DDRAG"
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"


def test_configuration_exposes_default_upload_size(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    settings = Settings()

    assert settings.max_upload_size_bytes == 10 * 1024 * 1024
