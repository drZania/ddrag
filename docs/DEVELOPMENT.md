# DDRAG Development Guide

This guide shows how to run DDRAG locally from a fresh clone.

If you only want to **try the application**, follow the **Quick Start** section. You do not need to understand the backend internals first.

If you want to **develop the backend**, see [Backend Development](#backend-development).

For the system architecture, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

# 1. What You Need

DDRAG runs as three main services:

```text
┌────────────────────┐
│   React + Vite     │
│     Frontend       │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│      FastAPI       │
│      Backend       │
└──────┬───────┬─────┘
       │       │
       ▼       ▼
 PostgreSQL   Ollama
 + pgvector   Embeddings
              + LLM
```

You need:

| Software       | Purpose                                |
| -------------- | -------------------------------------- |
| Git            | Clone the repository                   |
| Docker Desktop | Run PostgreSQL and the FastAPI backend |
| Ollama         | Run the local embedding model and LLM  |
| Node.js + npm  | Run the React frontend                 |

The backend itself uses **Python 3.13** when running outside Docker.

---

# 2. Quick Start

This is the recommended setup for someone cloning DDRAG for the first time.

## Step 1 — Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd ddrag
```

---

## Step 2 — Create the environment file

DDRAG provides an example configuration.

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### Linux/macOS

```bash
cp .env.example .env
```

For local development, the provided example already contains development defaults for PostgreSQL, JWT authentication, document storage, chunking, embeddings, retrieval, and Ollama.

> The `.env` file is for your local machine. Do not commit real secrets or credentials to Git.

---

# 3. Install and Start Ollama

DDRAG uses Ollama for both embeddings and LLM generation.

Install Ollama if it is not already installed, then make sure it is running.

Check that Ollama is available:

```bash
ollama list
```

DDRAG's default models are:

```text
Embedding:
qwen3-embedding:0.6b

Generation:
qwen2.5:1.5b
```

These defaults are defined in the project's environment configuration.

If the models are not installed:

```bash
ollama pull qwen3-embedding:0.6b
ollama pull qwen2.5:1.5b
```

Verify them:

```bash
ollama list
```

You should see both models available.

### Important for Docker users

The Dockerized backend connects to Ollama running on the host machine using:

```text
http://host.docker.internal:11434
```

This is already configured in `.env.example` and Docker Compose.

You therefore **do not need to run Ollama inside Docker**.

---

# 4. Start DDRAG Backend and Database

Make sure Docker Desktop is running.

From the repository root:

```bash
docker compose up -d
```

Docker Compose starts:

```text
PostgreSQL + pgvector
        +
FastAPI backend
```

The PostgreSQL service uses the `pgvector/pgvector:0.8.0-pg16` image.

Check the services:

```bash
docker compose ps
```

You should see the PostgreSQL and backend services running.

The backend waits for PostgreSQL to become healthy before starting.

---

# 5. Database Initialization

You do **not** need to manually create the database tables when using Docker Compose.

When the backend container starts, its startup command automatically runs:

```text
Alembic migrations
      ↓
FastAPI
```

The Dockerfile runs:

```bash
python -m alembic upgrade head
```

before starting Uvicorn.

This means a fresh development database is initialized automatically.

---

# 6. Check the Backend

Once Docker Compose has started, open:

```text
http://localhost:8000
```

The API health endpoint is:

```text
http://localhost:8000/health
```

FastAPI's interactive API documentation is available at:

```text
http://localhost:8000/docs
```

The backend is exposed from the container on port `8000`.

If `/health` responds successfully, the backend is running.

---

# 7. Start the Frontend

Open a **new terminal**.

Enter the frontend directory:

```bash
cd frontend
```

Install the frontend dependencies:

```bash
npm install
```

Create the frontend environment file:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### Linux/macOS

```bash
cp .env.example .env
```

Set:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Then start the development server:

```bash
npm run dev
```

Vite will display the local URL, normally:

```text
http://localhost:5173
```

Open that URL in your browser.

---

# 8. You Are Ready

At this point, the complete local environment should be running:

```text
Browser
   │
   ▼
React + Vite
   │
   │ HTTP
   ▼
FastAPI :8000
   │
   ├──────────────► PostgreSQL + pgvector
   │
   └──────────────► Ollama :11434
                         │
                         ├── qwen3-embedding:0.6b
                         └── qwen2.5:1.5b
```

---

# 9. First-Time User Walkthrough

Once the frontend is open:

### 1. Register

Create a new DDRAG account.

### 2. Log in

Sign in with the account you created.

### 3. Upload a document

Upload one of the supported document types:

* PDF
* DOCX
* TXT
* Markdown

### 4. Wait for processing

DDRAG processes the document through:

```text
Upload
  ↓
Text Extraction
  ↓
Chunking
  ↓
Embedding
  ↓
pgvector
```

### 5. Open a chat

Create or select a chat session.

### 6. Ask a question

Ask something related to the uploaded document.

DDRAG performs:

```text
Question
   ↓
Query Embedding
   ↓
Vector Search
   ↓
Relevant Chunks
   ↓
Context Construction
   ↓
Local LLM
   ↓
Grounded Answer
   ↓
Sources
```

The answer is generated using retrieved document context rather than relying solely on the model's general knowledge.

---

# 10. Stopping DDRAG

When you are finished, stop the Docker services:

```bash
docker compose down
```

This stops the PostgreSQL and FastAPI containers.

Your database and uploaded document data are stored in Docker-managed volumes, so stopping the containers does not normally remove that data. The Compose configuration defines persistent volumes for both PostgreSQL and document storage.
To start the application again:

```bash
docker compose up -d
```

---

# 11. Resetting the Development Database

If you intentionally want to start with a completely fresh database:

```bash
docker compose down -v
docker compose up -d
```

> **Warning:** `docker compose down -v` removes the Docker volumes, including the PostgreSQL data volume. This deletes your local development database.

Use this only when you want to reset the application state.

---

# 12. Backend Development

The Docker workflow is the easiest way to run the complete application.

If you want to modify and develop the Python backend directly on your machine, install **Python 3.13**.

The project explicitly requires Python `>=3.13,<3.14`.

From the repository root:

```bash
python -m venv .venv
```

Activate the environment.

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```cmd
.venv\Scripts\activate
```

### Linux/macOS

```bash
source .venv/bin/activate
```

Install the project and development dependencies:

```bash
pip install -e ".[dev]"
```

The development dependency group includes tools such as `pytest` and `httpx`.

---

# 13. Running the Backend Without Docker

If running FastAPI directly on your machine, make sure PostgreSQL and Ollama are available.

For local, non-containerized backend development, set:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

The provided environment example documents this distinction between Docker and local backend development.

The database URL for the Docker PostgreSQL instance is:

```text
postgresql+psycopg://ddrag:ddrag_dev_password@127.0.0.1:55432/ddrag
```

The PostgreSQL container maps its internal port `5432` to host port `55432`.

Apply migrations:

```bash
python -m alembic upgrade head
```

Start FastAPI:

```bash
python -m uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

---

# 14. Running Tests

With the development dependencies installed:

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

The project's pytest configuration automatically uses the `tests/` directory.

The test suite covers areas including:

* authentication
* database behavior
* document uploads
* document extraction
* chunking
* embeddings
* retrieval
* generation
* chat
* ownership
* source attribution
* storage

---

# 15. Database Migrations

DDRAG uses Alembic for schema management.

Show the current migration:

```bash
python -m alembic current
```

Show migration history:

```bash
python -m alembic history
```

Apply pending migrations:

```bash
python -m alembic upgrade head
```

When changing the database schema, create a migration rather than manually modifying the database.

Example:

```bash
python -m alembic revision --autogenerate -m "describe schema change"
```

Review the generated migration before applying it.

---

# 16. Useful Docker Commands

### Start

```bash
docker compose up -d
```

### Check services

```bash
docker compose ps
```

### View logs

```bash
docker compose logs -f
```

### View backend logs

```bash
docker compose logs -f backend
```

### View PostgreSQL logs

```bash
docker compose logs -f postgres
```

### Stop

```bash
docker compose down
```

### Rebuild after backend/Docker changes

```bash
docker compose up -d --build
```

### Reset all Docker-managed development data

```bash
docker compose down -v
```

---

# 17. Troubleshooting

## Backend does not start

Check:

```bash
docker compose ps
```

Then inspect the backend logs:

```bash
docker compose logs backend
```

Common causes include:

* PostgreSQL has not become healthy
* missing `.env` configuration
* invalid JWT configuration
* Ollama is unavailable
* required Ollama models are missing

---

## PostgreSQL does not start

Check:

```bash
docker compose logs postgres
```

Make sure Docker Desktop is running and that port `55432` is not already being used by another application.

---

## Ollama requests fail

Check:

```bash
ollama list
```

Make sure both configured models are installed.

For Docker-based backend development, make sure Ollama is running on the host machine because the backend connects through:

```text
http://host.docker.internal:11434
```

---

## Document processing fails

Check the backend logs:

```bash
docker compose logs -f backend
```

Possible causes include:

* unsupported file
* corrupted document
* missing Ollama embedding model
* Ollama unavailable
* database connection problem
* invalid embedding configuration

---

## Frontend cannot connect to the API

Check that FastAPI is running:

```text
http://localhost:8000/health
```

Then check:

```text
frontend/.env
```

The API base URL should point to:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Restart the Vite development server after changing environment variables.

---

# 18. Development Workflow

For normal application development:

```text
Start Docker
     ↓
Start Ollama
     ↓
Start Vite
     ↓
Use DDRAG
     ↓
Make changes
     ↓
Run tests
     ↓
Review changes
     ↓
Commit
```

For backend changes:

```text
Modify Python code
      ↓
Run relevant tests
      ↓
Run full test suite
      ↓
Check API behavior
      ↓
Commit
```

For database changes:

```text
Modify database model
      ↓
Create Alembic migration
      ↓
Review migration
      ↓
Apply migration
      ↓
Run tests
```

---

# 19. Repository Structure

The most important development directories are:

```text
ddrag/
├── app/                    # FastAPI backend and RAG pipeline
│   ├── api/                # REST API endpoints
│   ├── auth/               # Authentication
│   ├── db/                 # Database models and sessions
│   ├── answering.py        # End-to-end answering workflow
│   ├── chunking.py         # Text chunking
│   ├── citations.py        # Source attribution
│   ├── embeddings.py       # Embedding generation
│   ├── extraction.py       # Document extraction
│   ├── generation.py       # LLM generation
│   ├── retrieval.py        # Vector retrieval
│   └── storage.py          # Document storage
│
├── frontend/               # React + Vite frontend
│   └── src/
│
├── migrations/             # Alembic database migrations
│   └── versions/
│
├── tests/                  # Automated backend tests
│
├── storage/                # Local document storage
│
├── docker-compose.yml      # PostgreSQL + backend services
├── Dockerfile              # Backend container
├── pyproject.toml          # Python project configuration
├── .env.example            # Environment configuration template
└── README.md               # Project overview
```

---

# 20. Current Scope

The current implementation includes:

* user authentication
* document upload and management
* PDF, DOCX, TXT, and Markdown processing
* text extraction
* deterministic chunking
* local embeddings
* PostgreSQL + pgvector
* semantic retrieval
* grounded LLM generation
* source attribution
* persistent chat
* React frontend
* Dockerized backend and database
* automated backend testing

Systematic RAG evaluation and benchmarking are planned future work and are **not currently implemented**.

---

## Related Documentation

* [`README.md`](../README.md) — Project overview and portfolio introduction
* [`ARCHITECTURE.md`](./ARCHITECTURE.md) — System architecture and technical design
