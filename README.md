# DDRAG

DDRAG (Drag, Drop, Retrieve, Augment, Generate) is an independent portfolio project for building and evaluating local, document-grounded AI workflows.

## Current Status

Milestone 1, Foundation, is complete. The repository currently contains a small FastAPI application with typed environment-based configuration, structured request logging, request IDs, and a health endpoint.

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

See the [development guide](docs/DEVELOPMENT_GUIDE.md) and [M1 record](docs/milestones/MILESTONE_01_FOUNDATION.md) for more detail.
