"""Focused tests for the M5 step 3 synchronous extraction upload lifecycle."""

import io
from pathlib import Path
from uuid import uuid4

import docx
from fastapi.testclient import TestClient

from app.api import documents as documents_module
from app.db.models import Document
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _register_and_login() -> str:
    email = f"extraction-lifecycle-{uuid4()}@example.com"
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
                "chunk_size_chars": 1000,
                "chunk_overlap_chars": 200,
                "chunking_version": "ddrag-chunking-v1",
            },
        )(),
    )


def _build_valid_pdf_bytes(text: str) -> bytes:
    content = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj_body in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{index} 0 obj\n".encode("latin-1") + obj_body + b"\nendobj\n"

    xref_offset = len(body)
    body += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    body += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        body += f"{offset:010} 00000 n \n".encode("latin-1")
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode("latin-1")

    return bytes(body)


def _build_valid_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _fetch_document(document_id: int) -> Document:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document is not None
        return document


def test_plain_text_upload_becomes_ready(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("notes.txt", io.BytesIO(b"hello plain text"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"

    stored = _fetch_document(body["id"])
    assert stored.extracted_text == "hello plain text"
    assert stored.extraction_error is None


def test_markdown_upload_becomes_ready(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("notes.md", io.BytesIO(b"# Title\n\nBody text."), "text/markdown")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"

    stored = _fetch_document(body["id"])
    assert stored.extracted_text == "# Title\n\nBody text."
    assert stored.extraction_error is None


def test_valid_pdf_upload_becomes_ready_with_extracted_text(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()
    pdf_bytes = _build_valid_pdf_bytes("Hello PDF")

    response = client.post(
        "/documents",
        files={"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"

    stored = _fetch_document(body["id"])
    assert stored.extraction_error is None
    assert "Hello PDF" in stored.extracted_text


def test_valid_docx_upload_becomes_ready_with_extracted_text(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()
    docx_bytes = _build_valid_docx_bytes(["First paragraph.", "Second paragraph."])

    response = client.post(
        "/documents",
        files={
            "file": (
                "report.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"

    stored = _fetch_document(body["id"])
    assert stored.extraction_error is None
    assert "First paragraph." in stored.extracted_text
    assert "Second paragraph." in stored.extracted_text


def test_malformed_pdf_upload_is_stored_as_failed(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"

    stored = _fetch_document(body["id"])
    assert stored.extracted_text is None
    assert stored.extraction_error is not None

    saved_file = tmp_path / stored.storage_path
    assert saved_file.exists()


def test_malformed_docx_upload_is_stored_as_failed(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={
            "file": (
                "broken.docx",
                io.BytesIO(b"not a real docx"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"

    stored = _fetch_document(body["id"])
    assert stored.extracted_text is None
    assert stored.extraction_error is not None

    saved_file = tmp_path / stored.storage_path
    assert saved_file.exists()


def test_failed_extraction_error_does_not_leak_traceback_or_paths(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    response = client.post(
        "/documents",
        files={"file": ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    stored = _fetch_document(response.json()["id"])

    error_text = stored.extraction_error
    assert error_text is not None
    assert "Traceback" not in error_text
    assert str(tmp_path) not in error_text
    assert "\\" not in error_text
    assert len(error_text) < 200


def test_delete_removes_ready_document_and_file(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    upload = client.post(
        "/documents",
        files={"file": ("ready-delete.txt", io.BytesIO(b"ready content"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    storage_path = upload.json()["storage_path"]
    assert upload.json()["status"] == "ready"

    delete_response = client.delete(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204
    assert not (tmp_path / storage_path).exists()

    get_response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404


def test_delete_removes_failed_document_and_file(monkeypatch, tmp_path: Path) -> None:
    _configure_storage(monkeypatch, tmp_path)
    token = _register_and_login()

    upload = client.post(
        "/documents",
        files={"file": ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    storage_path = upload.json()["storage_path"]
    assert upload.json()["status"] == "failed"

    delete_response = client.delete(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204
    assert not (tmp_path / storage_path).exists()

    get_response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404
