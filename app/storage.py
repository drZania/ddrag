"""Minimal local filesystem storage helper for M4 document uploads."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4


def ensure_storage_root(directory: str | Path) -> Path:
    """Create the configured storage directory if it does not exist and return it."""

    storage_root = Path(directory).expanduser().resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    return storage_root


def generate_storage_filename(original_name: str) -> str:
    """Return a UUID-based filename that preserves only a safe extension."""

    suffix = Path(original_name).suffix.lower()
    return f"{uuid4()}{suffix}"


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 digest for the provided bytes."""

    return hashlib.sha256(data).hexdigest()


def save_document_file(storage_root: str | Path, original_name: str, data: bytes) -> str:
    """Write the document bytes to disk and return the generated storage filename."""

    root = ensure_storage_root(storage_root)
    filename = generate_storage_filename(original_name)
    target = (root / filename).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Storage path escapes the configured storage root")

    target.write_bytes(data)
    return filename


def delete_document_file(storage_root: str | Path, storage_filename: str) -> None:
    """Delete a stored document file if it exists."""

    root = ensure_storage_root(storage_root)
    target = (root / storage_filename).resolve()

    try:
        relative_target = target.relative_to(root)
    except ValueError:
        raise ValueError("Storage path escapes the configured storage root")
    if relative_target == Path():
        raise ValueError("Storage path must identify a file inside the configured storage root")

    if target.exists():
        target.unlink()
