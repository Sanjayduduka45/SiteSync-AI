# ARCHITECTURE — SiteSync AI

## System Overview

SiteSync AI is a client-server application. The frontend is a Next.js web app. The backend is a FastAPI REST API. Data is stored in Supabase PostgreSQL with pgvector. Files are stored in Supabase Storage. Auth is managed by Supabase Auth.

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                       │
│                  Next.js + TypeScript + Tailwind            │
│                         shadcn/ui                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST (HTTPS)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                        │
│                    Python 3.11+ / Pydantic v2               │
│                                                             │
│   ┌─────────────┐  ┌────────────────┐  ┌────────────────┐  │
│   │  Auth Layer │  │  API Routers   │  │  AI Pipeline   │  │
│   │  (Supabase) │  │  (domain-based)│  │  (LangChain)   │  │
│   └─────────────┘  └────────────────┘  └────────────────┘  │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────┐                ┌──────────────────────┐
│  Supabase        │                │  Gemini API (LLM)    │
│  PostgreSQL      │                │  Whisper / STT       │
│  + pgvector      │                │  Embeddings API      │
│  Supabase Auth   │                └──────────────────────┘
│  Supabase Storage│
└──────────────────┘
```

---

## Frontend Architecture

### Framework
- **Next.js** — App Router (not Pages Router)
- **TypeScript** — strict mode enabled
- **Tailwind CSS** — utility-first, configuration-based design tokens
- **shadcn/ui** — component library (do not replace or override with another)

### Directory Structure (planned)

```
frontend/
  app/                   # Next.js App Router pages
  components/            # Shared UI components
    ui/                  # shadcn/ui components (auto-generated)
    domain/              # Domain-specific components
  lib/                   # Utilities, API clients, helpers
  types/                 # TypeScript type definitions
  hooks/                 # Custom React hooks
  public/                # Static assets
  next.config.ts
  tailwind.config.ts
  tsconfig.json
```

### API Communication
- Frontend communicates with the FastAPI backend via REST over HTTPS.
- No direct database access from the frontend.
- Supabase Auth JWT is passed as Bearer token in API requests.
- Frontend does **not** hold API keys or secrets.

---

## Backend Architecture

### Framework
- **FastAPI** — async, Python 3.11+
- **Pydantic v2** — request/response validation and serialization
- **Uvicorn** — ASGI server

### Directory Structure (planned)

```
backend/
  app/
    api/
      v1/
        routers/         # Domain-based API routers
    core/                # Config, security, database connection
    models/              # Pydantic models (request/response)
    services/            # Business logic layer
    ai/                  # AI pipeline components
    db/                  # Database access layer
  main.py
  requirements.txt
```

### Authorization
- Every API endpoint enforces server-side authorization.
- JWT from Supabase Auth is validated on every request.
- Row-level authorization is enforced at both API and database (RLS) layers.
- No endpoint trusts client-supplied user identifiers without JWT validation.

### AI Pipeline (within backend)
- LangChain orchestrates the extraction + matching pipeline.
- Gemini is the primary LLM for extraction.
- Embeddings are generated and stored in pgvector.
- AI pipeline results are returned to the API layer as structured Pydantic models.
- AI never writes to approved actual records directly. It only returns recommendations.

---

## Database Architecture

### Platform
- **Supabase PostgreSQL**
- **pgvector** extension enabled

### Core Tables (planned, Phase 1+)

| Table | Purpose |
|---|---|
| `projects` | Project registry |
| `users` | User profiles (linked to Supabase Auth) |
| `schedule_activities` | Imported schedule activities |
| `activity_embeddings` | pgvector embeddings for schedule matching |
| `field_inputs` | Raw field submissions |
| `ai_extractions` | AI extraction results |
| `ai_matches` | AI schedule match recommendations |
| `planner_decisions` | Planner approve/reject/modify records |
| `approved_actuals` | Official approved progress records |
| `audit_log` | Immutable audit trail |

### Row-Level Security
- RLS is enabled on all tables.
- Users can only access data within their authorized projects.
- Planner decisions are restricted to planner role.
- Audit log is append-only; no row deletions permitted.

---

## File Storage

- Supabase Storage for all uploaded files (photos, documents, voice).
- Files are referenced by ID in `field_inputs`.
- Files are not served directly from the database.
- Access to files is controlled by signed URLs generated by the backend.

---

## API Contract Principles

- All APIs are versioned under `/api/v1/`.
- All request and response bodies use Pydantic-validated JSON.
- API contracts are considered locked once a phase is complete.
- Changes to API contracts require change control (see DO_NOT_CHANGE.md).
- Error responses follow a consistent schema:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

---

## Environment Configuration

- All configuration via environment variables.
- `.env` files for local development only — never committed.
- `.env.example` files committed with placeholder values only.
- Production secrets managed via secure secrets management (not hardcoded).

---

## Deployment (Future)

Deployment architecture is not defined in Phase 0. It will be specified in Phase 1 scaffolding. The architecture must remain compatible with standard containerized deployment (Docker).
