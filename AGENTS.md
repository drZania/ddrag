# DDRAG Agent Setup Guide

## Goal

Prepare a local DDRAG development environment safely and report what was verified. Preserve existing user configuration, databases, uploaded documents, and Docker volumes.

For detailed manual setup and troubleshooting, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Safety Rules

- Never delete existing Docker volumes or run `docker compose down -v` automatically.
- Never reset an existing PostgreSQL database.
- Never overwrite an existing `.env` or `frontend/.env`.
- Never expose JWT secrets or other credentials in command output unnecessarily.
- Never use the development database for tests.
- Never commit or push unless explicitly requested.
- If existing configuration is unexpected or conflicts with these instructions, stop and report it instead of replacing or destroying it.

## Prerequisites

Check for Git, Docker with Docker Compose, Ollama, and Node.js with npm. Docker runs the backend with its supported Python version; direct backend development requires Python `>=3.13,<3.14`. Report anything missing rather than claiming it is installed.

## Repository Setup

If the repository has not been cloned:

```bash
git clone https://github.com/drZania/ddrag.git
cd ddrag
```

If already inside the repository, use the existing checkout and do not clone another copy.

## Environment Setup

If `.env` is absent, copy `.env.example` to `.env` with the appropriate OS command (`Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` on Linux/macOS). If it exists, leave it untouched.

The checked-in `JWT_SECRET` is a development placeholder. Tell the developer to replace it with a unique local secret, but do not invent or print production credentials.

Apply the same preservation rule to the frontend: copy `frontend/.env.example` to `frontend/.env` only when `frontend/.env` is absent.

## Ollama

Check `ollama list` for these models:

- `qwen3-embedding:0.6b`
- `qwen2.5:1.5b`

Pull only missing models with `ollama pull`; do not re-download models already present. Ensure Ollama is running on the host.

## Backend and Database

DDRAG uses PostgreSQL with pgvector. Alembic migrations establish the schema when the backend container starts, and Docker named volumes preserve PostgreSQL and uploaded-document state.

Start services non-destructively from the repository root:

```bash
docker compose up -d
docker compose ps
```

Do not reset or remove existing volumes.

## Frontend

Because `frontend/package-lock.json` is present, install dependencies from `frontend/` with:

```bash
npm ci
npm run dev
```

The Vite development server normally runs at `http://localhost:5173` and proxies API requests to the backend.

## Verification

Where available, verify and report:

- Docker service state with `docker compose ps`
- backend health at `http://localhost:8000/health`
- frontend availability at the URL printed by Vite
- required Ollama models with `ollama list`

Do not claim a check passed unless it was executed successfully.

## Testing

Backend tests require `TEST_DATABASE_URL` to point to a dedicated PostgreSQL test database whose name contains `test`. Never point it at the development database. Do not create, clear, or destroy test infrastructure unless that action is explicitly appropriate and safe. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#14-running-tests) for setup details.

## Completion Report

Report:

- prerequisites found or missing
- environment files created or preserved
- Ollama models found or pulled
- Docker services started or preserved
- frontend dependency and server status
- health and availability checks actually performed
- any errors or manual action still required
