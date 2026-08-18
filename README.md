# DDRAG

DDRAG (Drag, Drop, Retrieve, Augment, Generate) is an independent portfolio project for building and evaluating local, document-grounded AI workflows.

## Current Status

Milestones 1 through 5 are complete. The repository contains a small FastAPI application with typed environment-based configuration, structured request logging, request IDs, a health endpoint, a migration-managed PostgreSQL + pgvector foundation, Argon2id/JWT authentication, authenticated document ingestion management, and synchronous document text extraction.

M4 provides a document model with authenticated ownership, PostgreSQL migration support, local filesystem storage with UUID-based physical filenames, SHA-256 duplicate detection, a per-user database uniqueness constraint, a 10 MiB upload limit, an allowlist of PDF/plain-text/Markdown/DOCX MIME types, authenticated upload/list/get/delete endpoints, ownership isolation, and database/filesystem cleanup behavior. M5 adds a pure `app/extraction.py` module for the same PDF/plain-text/Markdown/DOCX formats, nullable `extracted_text`/`extraction_error` columns on `Document`, synchronous extraction during upload with `processing` -> `ready`/`failed` status transitions, and an owner-scoped `GET /documents/{document_id}/text` endpoint. Chunking, embeddings, retrieval, augmentation, generation, chat/history, React, application Docker infrastructure, and evaluation remain deferred. Milestone 6 (chunking) is next.

## Development Setup

From Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set a long, random `JWT_SECRET` in `.env` before using registration or login. Passwords must be at least 8 characters; email addresses are trimmed and lowercased.

Run the application:

```powershell
python -m uvicorn app.main:app --reload
```

The application is available at `http://127.0.0.1:8000`. Run the tests with:

```powershell
python -m pytest
```

Start the local database dependency with Docker Compose. Docker is used here only for isolated PostgreSQL + pgvector development; the FastAPI application is not containerized in M2.

```powershell
$env:POSTGRES_DB="ddrag"
$env:POSTGRES_USER="ddrag"
$env:POSTGRES_PASSWORD="ddrag_dev_password"
docker compose up -d
$env:DATABASE_URL="postgresql+psycopg://ddrag:ddrag_dev_password@127.0.0.1:55432/ddrag"
.\.venv\Scripts\alembic.exe upgrade head
```

See the [development guide](docs/DEVELOPMENT_GUIDE.md), [M1 record](docs/milestones/MILESTONE_01_FOUNDATION.md), and [M2 record](docs/milestones/MILESTONE_02_DATABASE.md) for more detail.
See the [M3 record](docs/milestones/MILESTONE_03_AUTHENTICATION.md) for the authentication flow and security decisions.
See the [M4 record](docs/milestones/MILESTONE_04_DOCUMENT_INGESTION.md) for document ownership, storage, API behavior, and verification.
See the [M5 record](docs/milestones/MILESTONE_05_TEXT_EXTRACTION.md) for the extraction module, synchronous lifecycle, persistence, and verification.
