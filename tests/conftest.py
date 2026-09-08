"""Test-only environment and database isolation."""

import os

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.engine import make_url


class _TestSettings(BaseSettings):
	"""Load the explicit database URL reserved for tests."""

	test_database_url: str

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		extra="ignore",
	)


def _validated_test_database_url() -> str:
	"""Reject missing, non-PostgreSQL, or suspiciously named test databases."""

	try:
		candidate = _TestSettings().test_database_url
	except Exception as exc:
		raise pytest.UsageError(
			"Tests require TEST_DATABASE_URL to point to a dedicated PostgreSQL test "
			"database (for example, a database named ddrag_test)."
		) from exc

	try:
		url = make_url(candidate)
	except Exception as exc:
		raise pytest.UsageError("TEST_DATABASE_URL is not a valid SQLAlchemy database URL.") from exc
	if not url.drivername.startswith("postgresql"):
		raise pytest.UsageError("TEST_DATABASE_URL must use PostgreSQL so pgvector behavior is tested.")
	if not url.database or "test" not in url.database.lower():
		raise pytest.UsageError(
			"Refusing to run tests: the TEST_DATABASE_URL database name must contain 'test'."
		)
	return candidate


TEST_DATABASE_URL = _validated_test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-32")

from app.api import documents as documents_module
from app.db.session import engine


APPLICATION_TABLES = (
	"query_sources",
	"chat_queries",
	"chat_messages",
	"chat_sessions",
	"chunks",
	"documents",
	"users",
)


def _clear_test_database() -> None:
	"""Remove all application records and reset generated identifiers."""

	quoted_tables = ", ".join(f'"{table}"' for table in APPLICATION_TABLES)
	with engine.begin() as connection:
		connection.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def clean_test_database() -> None:
	"""Guarantee that committed test records never survive a test boundary."""

	_clear_test_database()
	try:
		yield
	finally:
		_clear_test_database()


@pytest.fixture(autouse=True)
def mock_document_embedding_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Keep non-embedding tests independent of a local Ollama service."""

	monkeypatch.setattr(documents_module, "embed_document_chunks", lambda *args, **kwargs: [])
