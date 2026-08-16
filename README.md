# DDRAG

DDRAG (Drag, Drop, Retrieve, Augment, Generate) is an independent portfolio project for building and evaluating local, document-grounded AI workflows.

## Current Status

Milestone 2, Database, is complete. The repository contains a small FastAPI application with typed environment-based configuration, structured request logging, request IDs, a health endpoint, and a migration-managed PostgreSQL + pgvector foundation.

The longer-term technology direction includes document retrieval, augmentation, generation, and evaluation. Those capabilities are planned but are not implemented yet.

## Development Setup

From Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

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
