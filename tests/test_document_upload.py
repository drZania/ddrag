"""Focused tests for the M4 document upload endpoint."""

import io
import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import exc

from app.api import documents as documents_module
from app.main import app


client = TestClient(app)


def _register_and_login() -> tuple[str, str]:
    email = f"upload-user-{uuid4()}@example.com"
    password = "correct horse battery staple"

    register = client.post("/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200

    return login.json()["access_token"], email


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


def test_authenticated_upload_succeeds(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()
    payload = b"hello from the upload API"

    response = client.post(
        "/documents",
        files={"file": ("report.pdf", io.BytesIO(payload), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "report.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["file_size_bytes"] == len(payload)
    assert body["status"] == "uploaded"
    assert body["storage_path"] != "report.pdf"
    assert body["storage_path"].endswith(".pdf")
    assert (tmp_path / body["storage_path"]).exists()


def test_unauthenticated_upload_returns_401(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)

    response = client.post(
        "/documents",
        files={"file": ("report.pdf", io.BytesIO(b"hello"), "application/pdf")},
    )

    assert response.status_code == 401


def test_oversized_file_is_rejected(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("big.txt", io.BytesIO(b"x" * (10 * 1024 * 1024 + 1)), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 413


def test_unsupported_file_type_is_rejected(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("bad.bin", io.BytesIO(b"bad"), "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 415


def test_duplicate_upload_returns_409(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()
    payload = b"duplicate content"

    first = client.post(
        "/documents",
        files={"file": ("report.txt", io.BytesIO(payload), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    second = client.post(
        "/documents",
        files={"file": ("report.txt", io.BytesIO(payload), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_document_duplicate_constraint_is_detected() -> None:
    class Diagnostic:
        constraint_name = "uq_documents_user_sha256"

    class Original:
        diag = Diagnostic()

    error = exc.IntegrityError("statement", "params", Original())

    assert documents_module._is_document_duplicate_violation(error) is True


def test_unrelated_integrity_error_is_not_treated_as_duplicate() -> None:
    class Diagnostic:
        constraint_name = "users_email_key"

    class Original:
        diag = Diagnostic()

    error = exc.IntegrityError("statement", "params", Original())

    assert documents_module._is_document_duplicate_violation(error) is False


def test_duplicate_race_constraint_returns_409(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()

    class Diagnostic:
        constraint_name = "uq_documents_user_sha256"

    class Original:
        diag = Diagnostic()

    class FakeQuery:
        def filter_by(self, **kwargs):
            return self

        def one_or_none(self):
            return None

    class FakeSession:
        def get(self, model, key):
            if model.__name__ == "User":
                return type("User", (), {"id": 1})()
            return None

        def query(self, model):
            return FakeQuery()

        def add(self, document):
            return None

        def commit(self):
            raise exc.IntegrityError("statement", "params", Original())

        def rollback(self):
            return None

        def refresh(self, document):
            return None

    from app.main import app as fastapi_app

    original_dependency = fastapi_app.dependency_overrides.get(documents_module.get_db)
    fastapi_app.dependency_overrides[documents_module.get_db] = lambda: FakeSession()

    try:
        response = client.post(
            "/documents",
            files={"file": ("race.txt", io.BytesIO(b"racing payload"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        if original_dependency is None:
            fastapi_app.dependency_overrides.pop(documents_module.get_db, None)
        else:
            fastapi_app.dependency_overrides[documents_module.get_db] = original_dependency

    assert response.status_code == 409
    assert response.json()["detail"] == "A duplicate document was already uploaded by this user"


def test_storage_path_uses_generated_uuid_name(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("original-name.md", io.BytesIO(b"# title"), "text/markdown")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    storage_name = response.json()["storage_path"]
    assert storage_name != "original-name.md"
    assert "original-name" not in storage_name
    assert storage_name.endswith(".md")
    assert len(storage_name.split(".")) >= 2
    assert (tmp_path / storage_name).exists()


def test_list_documents_returns_only_current_users_files(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)

    first_email = f"owner-{uuid4()}@example.com"
    first_password = "correct horse battery staple"
    first_register = client.post("/auth/register", json={"email": first_email, "password": first_password})
    assert first_register.status_code == 201
    first_login = client.post("/auth/login", json={"email": first_email, "password": first_password})
    assert first_login.status_code == 200
    first_token = first_login.json()["access_token"]

    second_email = f"other-{uuid4()}@example.com"
    second_password = "correct horse battery staple"
    second_register = client.post("/auth/register", json={"email": second_email, "password": second_password})
    assert second_register.status_code == 201
    second_login = client.post("/auth/login", json={"email": second_email, "password": second_password})
    assert second_login.status_code == 200
    second_token = second_login.json()["access_token"]

    first_upload = client.post(
        "/documents",
        files={"file": ("alpha.txt", io.BytesIO(b"alpha"), "text/plain")},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_upload.status_code == 201

    second_upload = client.post(
        "/documents",
        files={"file": ("beta.txt", io.BytesIO(b"beta"), "text/plain")},
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_upload.status_code == 201

    first_list = client.get("/documents", headers={"Authorization": f"Bearer {first_token}"})
    assert first_list.status_code == 200
    first_docs = first_list.json()
    assert len(first_docs) == 1
    assert first_docs[0]["original_filename"] == "alpha.txt"

    second_list = client.get("/documents", headers={"Authorization": f"Bearer {second_token}"})
    assert second_list.status_code == 200
    second_docs = second_list.json()
    assert len(second_docs) == 1
    assert second_docs[0]["original_filename"] == "beta.txt"


def test_list_documents_requires_authentication() -> None:
    response = client.get("/documents")

    assert response.status_code == 401


def test_document_owner_can_retrieve_document(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()
    upload = client.post(
        "/documents",
        files={"file": ("retrieve.txt", io.BytesIO(b"retrieve me"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == document_id
    assert response.json()["original_filename"] == "retrieve.txt"


def test_document_retrieval_requires_authentication() -> None:
    response = client.get("/documents/1")

    assert response.status_code == 401


def test_nonexistent_document_returns_404(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()

    response = client.get("/documents/2147483647", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_another_users_document_returns_404(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    owner_token, _ = _register_and_login()
    other_token, _ = _register_and_login()
    upload = client.post(
        "/documents",
        files={"file": ("private.txt", io.BytesIO(b"private"), "text/plain")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert upload.status_code == 201

    response = client.get(
        f"/documents/{upload.json()['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_document_retrieval_query_scopes_by_id_and_owner() -> None:
    captured = {}

    class FakeQuery:
        def filter_by(self, **kwargs):
            captured.update(kwargs)
            return self

        def one_or_none(self):
            return object()

    class FakeSession:
        def query(self, model):
            assert model is documents_module.Document
            return FakeQuery()

    current_user = type("User", (), {"id": 7})()
    document = asyncio.run(documents_module.get_document(42, current_user, FakeSession()))

    assert document is not None
    assert captured == {"id": 42, "user_id": 7}


def test_document_owner_can_delete_document(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()
    upload = client.post(
        "/documents",
        files={"file": ("delete.txt", io.BytesIO(b"delete me"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document = upload.json()
    stored_file = tmp_path / document["storage_path"]
    assert stored_file.exists()

    response = client.delete(
        f"/documents/{document['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert not stored_file.exists()
    assert client.get(
        f"/documents/{document['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 404


def test_document_deletion_requires_authentication() -> None:
    response = client.delete("/documents/1")

    assert response.status_code == 401


def test_nonexistent_document_deletion_returns_404(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()

    response = client.delete(
        "/documents/2147483647",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_another_users_document_cannot_be_deleted(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    owner_token, _ = _register_and_login()
    other_token, _ = _register_and_login()
    upload = client.post(
        "/documents",
        files={"file": ("private-delete.txt", io.BytesIO(b"keep me"), "text/plain")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert upload.status_code == 201
    document = upload.json()
    stored_file = tmp_path / document["storage_path"]

    response = client.delete(
        f"/documents/{document['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
    assert stored_file.exists()
    assert client.get(
        f"/documents/{document['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).status_code == 200


def test_document_deletion_succeeds_when_physical_file_is_missing(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token, _ = _register_and_login()
    upload = client.post(
        "/documents",
        files={"file": ("already-missing.txt", io.BytesIO(b"missing"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document = upload.json()
    (tmp_path / document["storage_path"]).unlink()

    response = client.delete(
        f"/documents/{document['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert client.get(
        f"/documents/{document['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 404


def test_document_deletion_query_scopes_by_id_and_owner() -> None:
    captured = {}

    class FakeDocument:
        storage_path = "stored.txt"

    class FakeQuery:
        def filter_by(self, **kwargs):
            captured.update(kwargs)
            return self

        def one_or_none(self):
            return FakeDocument()

    class FakeSession:
        def query(self, model):
            assert model is documents_module.Document
            return FakeQuery()

        def delete(self, document):
            assert isinstance(document, FakeDocument)

        def commit(self):
            return None

    current_user = type("User", (), {"id": 7})()
    original_settings = documents_module.settings
    original_delete = documents_module.delete_document_file
    deleted = {}
    documents_module.settings = type("Settings", (), {"document_storage_path": "storage"})()
    documents_module.delete_document_file = lambda root, name: deleted.update(root=root, name=name)
    try:
        asyncio.run(documents_module.delete_document(42, current_user, FakeSession()))
    finally:
        documents_module.settings = original_settings
        documents_module.delete_document_file = original_delete

    assert captured == {"id": 42, "user_id": 7}
    assert deleted == {"root": "storage", "name": "stored.txt"}
