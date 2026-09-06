# DDRAG

### Drag, Drop, Retrieve, Augment, Generate

A full-stack, document-grounded RAG application that lets users upload their own documents and ask questions about them using locally hosted language models.

<p align="center">
  <img src="docs/images/desktop-chat.png" alt="DDRAG chat workspace" width="100%">
</p>

<p align="center">
  <strong>Upload documents. Ask questions. Get grounded answers with source attribution.</strong>
</p>

---

## ✨ Highlights

- 📄 Document upload and processing for PDF, TXT, Markdown, and DOCX
- 🔎 Semantic retrieval using PostgreSQL + pgvector
- 🤖 Local LLM and embedding inference through Ollama
- 💬 Persistent chat sessions and conversation history
- 📚 Source attribution for retrieved document content
- 🔐 JWT-based authentication and user-owned resources
- 🐳 Dockerized backend and database environment
- 📱 Responsive React interface for desktop and mobile
- 🧪 Automated backend test suite

---

## 🛠 Tech Stack

**Frontend**

React · TypeScript · Vite · Chakra UI

**Backend**

Python · FastAPI · SQLAlchemy · Alembic

**AI / RAG**

Ollama · Embeddings · Semantic Retrieval · Grounded Generation

**Data**

PostgreSQL · pgvector

**Infrastructure**

Docker · Docker Compose

**Testing**

pytest

---

## 📸 Interface

### Document Management

<p align="center">
  <img src="docs/images/desktop-documents.png" alt="DDRAG document management workspace" width="90%">
</p>

Upload documents, monitor processing status, and manage the document library from the workspace.

### Responsive Chat

<p align="center">
  <img src="docs/images/mobile-chat.png" alt="DDRAG mobile chat interface" width="35%">
</p>

The chat workspace adapts to smaller screens while preserving the core document-grounded question-answering experience.

---

## 🧠 How It Works

DDRAG follows a Retrieval-Augmented Generation pipeline:

```text
Document
   ↓
Text Extraction
   ↓
Chunking
   ↓
Embeddings
   ↓
PostgreSQL + pgvector
   ↓
Semantic Retrieval
   ↓
Context Construction
   ↓
Local LLM
   ↓
Grounded Answer + Sources
```

For the complete system design and implementation details:

**→ [Read the Architecture](docs/ARCHITECTURE.md)**

---

## 🚀 Running DDRAG

DDRAG can be run locally using Docker, PostgreSQL, Ollama, and the React frontend.

For prerequisites, environment configuration, setup instructions, database initialization, testing, and troubleshooting:

**→ [Read the Development Guide](docs/DEVELOPMENT.md)**

---

## 🔭 Future Work

A dedicated evaluation phase is planned to benchmark the RAG pipeline across areas such as retrieval quality, answer faithfulness, latency, embedding models, LLMs, and prompt strategies.

---

## 📌 About

DDRAG is a personal portfolio project focused on practical backend engineering, Retrieval-Augmented Generation, local LLM integration, and full-stack application development.

The project was built to explore how an LLM-powered application can be designed as a complete system—from document ingestion and vector retrieval to grounded generation, authentication, persistence, and a responsive user interface.

---

## 📄 License

MIT License. See [`LICENSE`](LICENSE).