"""Test-only environment defaults."""

import os

import pytest

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-32")

from app.api import documents as documents_module


@pytest.fixture(autouse=True)
def mock_document_embedding_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Keep non-embedding tests independent of a local Ollama service."""

	monkeypatch.setattr(documents_module, "embed_document_chunks", lambda *args, **kwargs: [])