"""Integration tests for the dedicated DDRAG PostgreSQL database."""

from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.models import User
from app.db.session import SessionLocal, engine


def test_database_configuration_loads(monkeypatch) -> None:
    database_url = "postgresql+psycopg://ddrag:dev@127.0.0.1:55432/ddrag"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert Settings().database_url == database_url


@pytest.fixture(scope="session", autouse=True)
def database_is_available() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.fail(f"Dedicated DDRAG database is unavailable: {exc}")


def test_engine_connectivity_and_migrated_schema() -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        assert connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one() == 1

    assert "users" in inspect(engine).get_table_names()


def test_user_can_be_inserted_and_queried() -> None:
    email = f"database-test-{uuid4()}@example.com"

    with SessionLocal() as session:
        session.add(User(email=email))
        session.commit()

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email).one()
        assert user.email == email
        assert user.id is not None
        assert user.created_at is not None


def test_user_email_is_unique() -> None:
    email = f"unique-test-{uuid4()}@example.com"

    with SessionLocal() as session:
        session.add(User(email=email))
        session.commit()

    with SessionLocal() as session:
        session.add(User(email=email))
        with pytest.raises(IntegrityError):
            session.commit()