# DDRAG Architecture

This document describes the architecture of DDRAG (Document Retrieval-Augmented Generation), a full-stack application for uploading documents and interacting with their contents through a grounded, locally hosted LLM.

The system is designed around a clear separation between document processing, vector retrieval, grounded generation, persistent chat, and the user interface.

---

## 1. System Overview

DDRAG follows a Retrieval-Augmented Generation (RAG) architecture:

```text
                         ┌──────────────────────┐
                         │      React UI        │
                         │   Vite + TypeScript  │
                         └──────────┬───────────┘
                                    │
                              HTTP / REST
                                    │
                         ┌──────────▼───────────┐
                         │       FastAPI        │
                         │       Backend        │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       Authentication        Document Pipeline        Chat System
              │                     │                     │
              │                     ▼                     │
              │              Text Extraction             │
              │                     │                     │
              │                     ▼                     │
              │                 Chunking                  │
              │                     │                     │
              │                     ▼                     │
              │                Embeddings                 │
              │                     │                     │
              │                     ▼                     │
              │             PostgreSQL + pgvector         │
              │                     │                     │
              │                     ▼                     │
              │                 Retrieval                 │
              │                     │                     │
              │                     ▼                     │
              │            Grounded Generation            │
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                                    ▼
                              Ollama / LLM
```

The backend remains the authority for authentication, ownership, document processing, retrieval, generation, and chat persistence. The React frontend acts as a client of the existing API rather than duplicating backend business logic.

---

## 2. Core Technology Stack

| Layer               | Technology                | Responsibility                                  |
| ------------------- | ------------------------- | ----------------------------------------------- |
| Frontend            | React + TypeScript + Vite | User interface and API interaction              |
| UI                  | Chakra UI                 | Components, layout, responsive styling, theming |
| Backend             | Python + FastAPI          | REST API and application orchestration          |
| Database            | PostgreSQL                | Relational persistence                          |
| Vector Search       | pgvector                  | Embedding storage and similarity search         |
| ORM                 | SQLAlchemy                | Database access and model mapping               |
| Migrations          | Alembic                   | Database schema lifecycle                       |
| Document Processing | pypdf, python-docx        | PDF and DOCX text extraction                    |
| Embeddings          | Ollama                    | Local embedding generation                      |
| LLM                 | Ollama                    | Local language-model inference                  |
| Authentication      | JWT + Argon2id            | User authentication and password protection     |
| Runtime             | Docker Compose            | Reproducible backend/database environment       |

---

# 3. Application Layers

DDRAG is divided into several logical layers.

```text
┌───────────────────────────────────────────────┐
│                  React Frontend               │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                 FastAPI Routes                │
│      Authentication · Documents · Chat       │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                Application Logic              │
│ Extraction · Chunking · Retrieval · Answering│
└───────────────────────┬───────────────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
┌─────────────────────┐  ┌─────────────────────┐
│     PostgreSQL      │  │       Ollama        │
│   + pgvector        │  │ Embeddings + LLM    │
└─────────────────────┘  └─────────────────────┘
```

The application separates external API concerns from the core processing components. This keeps individual responsibilities explicit and makes the RAG pipeline easier to test and maintain.

---

# 4. Authentication and User Ownership

Authentication establishes the ownership boundary used throughout the application.

### Authentication flow

```text
Register
   ↓
Password hashing (Argon2id)
   ↓
User stored in PostgreSQL
   ↓
Login
   ↓
JWT access token
   ↓
Authenticated API requests
   ↓
Current user resolved by backend
```

DDRAG uses bearer JWTs for authenticated API access.

Passwords are never stored in plaintext. Password hashes are generated using Argon2id, while JWT configuration is provided through environment-backed settings.

The authenticated user is the authoritative ownership source. Client requests do not provide a user ID to determine ownership.

### Ownership model

```text
User
 ├── Documents
 │    └── Chunks
 │
 └── Chat Sessions
      ├── Messages
      └── Queries
           └── Query Sources
```

This ownership model is enforced at the API and database levels.

For example:

* document queries are filtered by the authenticated user
* retrieval only considers chunks belonging to the authenticated user
* chat sessions are user-scoped
* messages are accessed through owned sessions
* query sources belong to queries within owned sessions

This prevents users from using resource identifiers to access another user's data.

---

# 5. Document Ingestion Pipeline

The document pipeline transforms an uploaded file into searchable vector representations.

```text
Upload
  ↓
File Validation
  ↓
SHA-256 Duplicate Check
  ↓
Secure Local Storage
  ↓
Text Extraction
  ↓
Text Normalization
  ↓
Chunking
  ↓
Embedding Generation
  ↓
PostgreSQL + pgvector
```

DDRAG currently accepts:

* PDF
* Plain text
* Markdown
* DOCX

Uploaded files are subject to size and MIME-type validation.

Physical storage filenames are generated by the application rather than trusting client-provided filenames. Original filenames are retained as metadata.

A SHA-256 digest is calculated from uploaded content and used for duplicate detection within the user's document scope.

---

# 6. Text Extraction

Text extraction is performed synchronously as part of document processing.

The extraction layer dispatches according to the uploaded MIME type:

```text
PDF
 └── pypdf

DOCX
 └── python-docx

TXT / Markdown
 └── UTF-8 decoding
```

Extracted text is normalized and stored with the document record.

The document processing lifecycle uses explicit states:

```text
uploaded
    ↓
processing
    ↓
ready
```

or, when processing fails:

```text
processing
    ↓
failed
```

Extraction errors are represented using controlled, safe error messages rather than exposing parser tracebacks or filesystem information.

---

# 7. Chunking

Ready documents are divided into deterministic text chunks before embedding.

The current chunking strategy uses fixed character windows:

```text
Document Text
      │
      ▼
┌───────────────┐
│    Chunk 0    │
└───────────────┘
       overlap
     ┌───────────────┐
     │    Chunk 1    │
     └───────────────┘
            overlap
          ┌───────────────┐
          │    Chunk 2    │
          └───────────────┘
```

Default configuration:

| Setting          |               Value |
| ---------------- | ------------------: |
| Chunk size       |     1000 characters |
| Chunk overlap    |      200 characters |
| Chunking version | `ddrag-chunking-v1` |

Each chunk stores:

* source document ID
* chunk order
* chunk text
* chunking configuration
* chunking version
* creation timestamp

The `(document_id, chunk_order)` relationship is unique, providing deterministic chunk ordering.

Chunks inherit ownership through their parent document:

```text
User → Document → Chunk
```

There is no separate user ownership field on the chunk itself.

---

# 8. Embedding Generation

Each persisted chunk is converted into a vector embedding using a locally hosted Ollama embedding model.

```text
Chunk Text
    ↓
Ollama Embedding API
    ↓
Embedding Vector
    ↓
PostgreSQL pgvector
```

DDRAG uses a fixed 1024-dimensional embedding representation.

Embedding configuration is environment-based so the model and Ollama endpoint can be changed without modifying application code.

The embedding layer validates generated vectors before persistence, including:

* vector structure
* numeric values
* expected dimensionality
* finite values

Embedding failures cause document processing to fail safely rather than silently storing incomplete vector data.

---

# 9. Vector Storage

Embeddings are stored directly in PostgreSQL using the `pgvector` extension.

The relevant relationship is:

```text
Document
   │
   └── Chunk
        ├── chunk_text
        └── embedding VECTOR(1024)
```

PostgreSQL therefore acts as both the relational database and vector store.

This avoids introducing a separate vector database for the current system and keeps document metadata, ownership information, chunks, and embeddings within the same persistence layer.

---

# 10. Retrieval

DDRAG performs semantic retrieval using PostgreSQL pgvector cosine distance.

The retrieval flow is:

```text
User Question
      ↓
Query Embedding
      ↓
1024-dimensional Vector
      ↓
pgvector Cosine Similarity Search
      ↓
Owner-scoped Chunks
      ↓
Top-K Results
```

The default retrieval count is:

```text
top_k = 5
```

The API allows a bounded request-level `top_k` value.

Retrieval is always scoped to the authenticated user:

```sql
WHERE document.user_id = authenticated_user_id
```

Chunks without embeddings are excluded from vector search.

Results are ordered by cosine distance, with chunk ID used as a deterministic tie-breaker.

Each retrieved result contains metadata such as:

* document ID
* chunk ID
* chunk order
* chunk text
* cosine distance

This metadata is later used to construct traceable source attribution.

---

# 11. Grounded Generation

Retrieval results are passed into the generation pipeline rather than allowing the LLM to answer from unrestricted outside knowledge.

```text
Question
   ↓
Vector Retrieval
   ↓
Relevant Chunks
   ↓
Citation Assignment
   ↓
Context Assembly
   ↓
Grounding Prompt
   ↓
Ollama LLM
   ↓
Citation Validation
   ↓
Grounded Answer + Sources
```

The generation layer is intentionally separated from retrieval.

### Context assembly

Retrieved chunks are assigned deterministic ordinal citation identifiers:

```text
[1] → Retrieved chunk 1
[2] → Retrieved chunk 2
[3] → Retrieved chunk 3
...
```

The system maintains a mapping between the citation ID and its underlying document/chunk metadata.

### Grounding rules

The generation prompt instructs the model to:

* answer using the supplied context
* avoid unsupported claims
* avoid relying on outside knowledge
* treat retrieved content as reference material rather than executable instructions
* indicate when the supplied context does not contain enough information
* use the provided citation format

If retrieval returns no usable context, DDRAG returns an insufficient-information response without calling the LLM.

---

# 12. Citation and Source Attribution

Source attribution is generated from retrieval results rather than invented by the frontend.

The generation response can associate an answer with metadata including:

```text
citation_id
document_id
chunk_id
chunk_order
retrieval_distance
```

Citation validation checks whether cited ordinal identifiers correspond to sources actually supplied to the model.

The frontend displays only source metadata returned by the backend. It does not invent document names, page numbers, source text, or citations.

This keeps source attribution under backend control.

---

# 13. Chat Architecture

The chat layer builds persistent conversations on top of the existing retrieval and generation pipeline.

```text
User
 ↓
Chat Session
 ├── User Message
 ├── Query
 │    └── Query Sources
 └── Assistant Message
```

A question submitted through chat follows this flow:

```text
Question
   ↓
Persist User Message
   ↓
Create Pending Query
   ↓
RAG Answering Pipeline
   ├── Retrieval
   ├── Context Assembly
   ├── Generation
   └── Citation Validation
   ↓
Persist Assistant Message
   ↓
Persist Source Metadata
   ↓
Mark Query Completed
```

If generation fails:

```text
User Message
   ↓
Pending Query
   ↓
Generation Failure
   ↓
Query marked failed
```

The user message remains persisted, while an invalid or fabricated assistant response is not created.

---

# 14. Database Model

The main persistence relationships can be summarized as:

```text
User
 │
 ├──< Document
 │       │
 │       └──< Chunk
 │
 └──< ChatSession
         │
         ├──< ChatMessage
         │
         └──< ChatQuery
                 │
                 └──< QuerySource
```

### Core entities

**User**

Stores authenticated user identity and account metadata.

**Document**

Stores document ownership, metadata, storage information, processing status, extracted text, and processing errors.

**Chunk**

Stores deterministic document segments and their embeddings.

**ChatSession**

Represents an authenticated user's conversation.

**ChatMessage**

Stores user and assistant messages within a session.

**ChatQuery**

Tracks an individual question-answer workflow and its processing status.

**QuerySource**

Stores source attribution metadata produced by the RAG pipeline.

Database migrations are managed through Alembic rather than modifying the schema automatically at application startup.

---

# 15. Frontend Architecture

The React frontend intentionally remains thin:

```text
React Components
      ↓
Typed API Client
      ↓
FastAPI REST API
```

The frontend is responsible for:

* authentication screens
* document upload and status display
* document listing
* chat session selection
* message rendering
* source metadata display
* loading and error states
* responsive layout
* light/dark theme support

The backend remains responsible for:

* identity
* authorization
* ownership
* document processing
* chunking
* embeddings
* retrieval
* generation
* citation validation
* persistence

This prevents business logic from being duplicated between the frontend and backend.

---

# 16. API Boundaries

The major API areas are:

```text
/auth
    ├── register
    ├── login
    └── me

/documents
    ├── upload
    ├── list
    ├── get
    ├── get extracted text
    └── delete

/retrieval
    └── semantic retrieval

/generation
    └── grounded answer generation

/chat/sessions
    ├── create
    ├── list
    ├── get
    ├── messages
    └── questions
```

Each protected resource uses the authenticated current-user dependency before performing ownership-sensitive operations.

---

# 17. Local LLM Architecture

DDRAG uses Ollama as the local model runtime.

Ollama provides two distinct capabilities:

```text
                  Ollama
                 /      \
                /        \
               ▼          ▼
        Embedding Model   Generation Model
               │          │
               ▼          ▼
          pgvector       Answer
```

Embedding and generation models are configured independently.

This separation allows the retrieval representation and language-generation model to be changed independently.

The backend communicates with Ollama through its HTTP API.

---

# 18. Docker Runtime

Docker Compose provides the reproducible backend/database runtime.

The Compose stack contains:

```text
┌─────────────────────────────────────────┐
│              Docker Compose             │
│                                         │
│  ┌──────────────┐   ┌────────────────┐ │
│  │   Backend    │──▶│   PostgreSQL   │ │
│  │   FastAPI    │   │   + pgvector   │ │
│  └──────┬───────┘   └────────────────┘ │
│         │                               │
└─────────┼───────────────────────────────┘
          │
          ▼
     Host Ollama

Host React/Vite
       │
       ▼
Backend container
```

The current Docker architecture intentionally keeps:

* Ollama outside the Compose stack
* the Vite frontend outside the Compose stack

On Docker Desktop, the backend can reach a host Ollama instance through the configured host gateway.

PostgreSQL data and uploaded document storage use Docker-managed named volumes.

---

# 19. Configuration

Runtime configuration is environment-based.

Important configuration areas include:

```text
Database
Authentication
Document storage
Upload limits
Chunking
Embeddings
Retrieval
Generation
Ollama connectivity
```

Sensitive values such as JWT secrets are supplied through environment variables and are not committed to source control.

`.env.example` documents the expected configuration without containing production secrets.

---

# 20. Security Principles

DDRAG follows several security-oriented design principles throughout the application:

### Authentication

Protected endpoints require a valid bearer token.

### Ownership

The authenticated user's identity is used for resource ownership rather than accepting ownership information from clients.

### Password protection

Passwords are hashed using Argon2id.

### File safety

Client-provided filenames are not used directly as filesystem paths.

### Path containment

Document storage operations are constrained to the application's designated storage area.

### Safe errors

Internal exception details, parser tracebacks, secrets, and full tokens are not exposed through API responses or application logs.

### Database constraints

Important invariants are reinforced through PostgreSQL constraints, foreign keys, uniqueness rules, and cascading relationships.

---

# 21. Key Design Decisions

## PostgreSQL + pgvector

DDRAG uses PostgreSQL as both the relational database and vector store. This keeps document metadata, ownership, chunks, and embeddings within one persistence system while avoiding an additional vector database for the current scope.

## Synchronous document processing

Document extraction, chunking, and embedding currently occur during the upload workflow. This keeps the architecture simple and explicit, which is appropriate for the project's current scope.

## Separate retrieval and generation layers

Retrieval and generation are implemented as separate responsibilities. This makes it possible to reason about retrieval independently from LLM behavior and provides a clear boundary for future evaluation.

## Backend-controlled source attribution

Source metadata originates from the retrieval/generation pipeline and is passed to the frontend. The frontend does not construct or infer citations.

## Thin frontend

The React application consumes backend APIs instead of duplicating RAG or ownership logic. This keeps business rules centralized.

## Local model inference

Ollama provides local embedding and generation services, allowing the application to operate without requiring a hosted LLM API for its core workflow.

---

# 22. Current System Boundary

The implemented DDRAG system covers:

```text
Authentication
      ↓
Document Management
      ↓
Text Extraction
      ↓
Deterministic Chunking
      ↓
Local Embeddings
      ↓
pgvector Retrieval
      ↓
Grounded LLM Generation
      ↓
Citation / Source Attribution
      ↓
Persistent Chat
      ↓
React Frontend
      ↓
Dockerized Backend + Database
```

The architecture intentionally favors explicit boundaries, straightforward data ownership, and a small number of infrastructure components.

Future improvements may include more advanced retrieval strategies, asynchronous processing, streaming generation, and systematic evaluation. These are outside the current architecture and should not be treated as implemented functionality.
