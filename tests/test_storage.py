"""Focused tests for the M4 local document storage helper."""

from pathlib import Path

from app.storage import delete_document_file, generate_storage_filename, save_document_file, sha256_bytes


def test_generate_storage_filename_uses_uuid_not_original_name(tmp_path: Path) -> None:
    original_name = "notes.txt"

    generated = generate_storage_filename(original_name)

    assert generated.endswith(".txt")
    assert original_name not in generated
    assert len(generated) > len(original_name)


def test_storage_helper_saves_and_deletes_file(tmp_path: Path) -> None:
    original_name = "report.pdf"
    payload = b"hello from M4 storage"

    saved_name = save_document_file(tmp_path, original_name, payload)
    target = tmp_path / saved_name

    assert target.exists()
    assert target.read_bytes() == payload
    assert target.name != original_name
    assert target.name.endswith(".pdf")

    delete_document_file(tmp_path, saved_name)
    assert not target.exists()


def test_storage_helper_ignores_original_name_for_physical_path(tmp_path: Path) -> None:
    original_name = "../../evil.txt"

    saved_name = save_document_file(tmp_path, original_name, b"bad")
    target = tmp_path / saved_name

    assert target.exists()
    assert target.read_bytes() == b"bad"
    assert saved_name != original_name
    assert "evil.txt" not in saved_name
    assert target.name.endswith(".txt")


def test_storage_helper_rejects_traversal_on_delete(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_bytes(b"keep")

    try:
        delete_document_file(tmp_path, "../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected path traversal to be rejected")

    assert outside_file.read_bytes() == b"keep"


def test_storage_helper_rejects_sibling_prefix_on_delete(tmp_path: Path) -> None:
    sibling_root = tmp_path.parent / f"{tmp_path.name}-sibling"
    sibling_root.mkdir()
    outside_file = sibling_root / "outside.txt"
    outside_file.write_bytes(b"keep")

    try:
        delete_document_file(tmp_path, f"../{sibling_root.name}/outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected sibling-prefix path to be rejected")

    assert outside_file.read_bytes() == b"keep"


def test_storage_helper_rejects_storage_root_itself(tmp_path: Path) -> None:
    try:
        delete_document_file(tmp_path, ".")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected storage root deletion to be rejected")


def test_sha256_helper_returns_digest() -> None:
    digest = sha256_bytes(b"abc")

    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
