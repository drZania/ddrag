"""Focused tests for the M5 owner-scoped document text retrieval endpoint."""

import io
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import documents as documents_module
from app.main import app


client = TestClient(app)


def _register_and_login() -> str:
    email = f"text-endpoint-{uuid4()}@example.com"
    password = "correct horse battery staple"

    register = client.post("/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200

    return login.json()["access_token"]


def _configure_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        documents_module,
        "settings",
        type(
            "Settings",
            (),
            {
                "document_storage_path": str(tmp_path),
                "max_upload_size_bytes": 10 * 1024 * 1024,
            },
        )(),
    )


def test_owner_can_retrieve_text_for_ready_document(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    upload = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"hello text endpoint"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    response = client.get(
        f"/documents/{document_id}/text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document_id
    assert body["status"] == "ready"
    assert body["extracted_text"] == "hello text endpoint"
    assert body["extraction_error"] is None


def test_owner_can_retrieve_text_for_failed_document(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    upload = client.post(
        "/documents",
        files={"file": ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    response = client.get(
        f"/documents/{document_id}/text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["extracted_text"] is None
    assert body["extraction_error"] is not None


def test_text_endpoint_requires_authentication() -> None:
    response = client.get("/documents/1/text")

    assert response.status_code == 401


def test_text_endpoint_returns_404_for_missing_document(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    response = client.get(
        "/documents/2147483647/text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_text_endpoint_returns_404_for_another_users_document(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    owner_token = _register_and_login()
    other_token = _register_and_login()

    upload = client.post(
        "/documents",
        files={"file": ("private.txt", io.BytesIO(b"private text"), "text/plain")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    response = client.get(
        f"/documents/{document_id}/text",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_document_metadata_response_does_not_include_extraction_fields(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    upload = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    body = upload.json()

    assert "extracted_text" not in body
    assert "extraction_error" not in body
