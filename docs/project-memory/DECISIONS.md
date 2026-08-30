# DECISIONS — SiteSync AI

> This file records significant architectural and product decisions.
> Each decision is immutable once recorded. Revisions create a new entry referencing the original.

---

## Decision Record Format

Each ADR (Architectural Decision Record) contains:
- **ID**: Sequential identifier
- **Date**: When the decision was made
- **Status**: Decided | Superseded by ADR-XXX
- **Context**: Why a decision was needed
- **Decision**: What was decided
- **Consequences**: What this means going forward

---

## ADR-001 — Frontend Framework

**Date**: 2026-08-30
**Status**: Superseded by ADR-008

**Context**: A frontend framework is needed for the SiteSync AI web application.

**Decision**: ~~Next.js with the App Router~~ — superseded before any implementation. See ADR-008.

---

## ADR-002 — Backend Framework

**Date**: 2026-08-30
**Status**: Decided

**Context**: A backend API framework is needed. The system requires strong async support, Python ecosystem compatibility for AI/ML libraries, and clear schema validation.

**Decision**: **FastAPI** with **Pydantic v2** for request/response validation. Python 3.11+.

**Consequences**:
- All backend API contracts are defined as Pydantic v2 models.
- Pydantic v2 (not v1) is used. Migration from v1 is not planned.
- Async/await patterns are used throughout the backend.
- All API routes are in the `app/api/v1/` path.

---

## ADR-003 — Database Platform

**Date**: 2026-08-30
**Status**: Decided

**Context**: A managed database platform is needed. The system requires PostgreSQL for relational data, vector search for schedule matching, file storage, and managed authentication.

**Decision**: **Supabase** — providing PostgreSQL, pgvector, Auth, and Storage in a single managed platform.

**Consequences**:
- All persistent data is in Supabase PostgreSQL.
- pgvector is the vector store. No separate vector database (e.g., Pinecone, Weaviate) is used.
- Supabase Auth is the authentication system. No other auth system is used.
- Supabase Storage is used for file uploads. No other file storage is used.
- RLS must be configured and tested for all tables.

---

## ADR-004 — AI Orchestration

**Date**: 2026-08-30
**Status**: Decided

**Context**: An AI orchestration layer is needed to coordinate LLM calls, embeddings, and multi-step pipelines.

**Decision**: **LangChain** as the orchestration framework. **Gemini** as the primary LLM. **Whisper** (or suitable STT) for voice transcription.

**Consequences**:
- LangChain versions must be pinned and managed carefully (LangChain APIs change frequently).
- Gemini is the primary LLM. Other LLMs may be evaluated but require change control to adopt.
- All prompt templates are stored in code and versioned.
- All LLM outputs are validated against Pydantic schemas.

---

## ADR-005 — Core Product Principle

**Date**: 2026-08-30
**Status**: Decided

**Context**: A fundamental question exists in AI-assisted tools: should AI act autonomously or in support of human decision-making?

**Decision**: **AI recommends. Humans decide.**

No AI output becomes an approved actual without explicit planner sign-off. The AI pipeline produces recommendations only.

**Consequences**:
- The planner review step is mandatory in the workflow. It cannot be bypassed.
- Auto-approval features are not permitted without explicit change control and human approval.
- All AI outputs must display confidence scores and evidence.
- AI cannot write directly to approved actual records.

---

## ADR-006 — Theme and UI Identity

**Date**: 2026-08-30
**Status**: Decided

**Context**: SiteSync AI must feel like a professional construction project tool, not a generic AI product.

**Decision**: Light theme only. Professional, construction-specific UI. No AI avatar, no chatbot patterns, no excessive animations, no excessive glassmorphism.

**Consequences**:
- Dark mode is not implemented unless this decision is explicitly superseded.
- UI components are evaluated against the prohibited patterns in `UI_UX_SYSTEM.md`.
- Design reviews check against UI/UX principles before any new screen is accepted.

---

## ADR-007 — Phase Isolation

**Date**: 2026-08-30
**Status**: Decided

**Context**: To maintain codebase stability and prevent scope creep, development must be structured.

**Decision**: Strict phase isolation. Only the active approved phase is implemented. Completed phases are protected. Changes to completed-phase behavior require change control.

**Consequences**:
- Future agents and developers must read `DEVELOPMENT_PHASES.md` before any implementation work.
- Phase boundaries are enforced by human review, not automated tooling alone.
- Git tags mark stable phase checkpoints.

---

## ADR-008 — Frontend Framework (Correction, supersedes ADR-001)

**Date**: 2026-08-30
**Status**: Decided

**Context**: ADR-001 specified Next.js as the frontend framework. Before any implementation began, the product owner confirmed the final frontend stack. Next.js is not required; a Vite-based SPA is preferred for this product's architecture.

**Decision**: **React** with **Vite**, **TypeScript** in strict mode, **Tailwind CSS** for styling, **shadcn/ui** as the component library, **React Router** for client-side routing, and **TanStack Query** for server state management.

**Consequences**:
- All frontend code is in TypeScript. No plain JavaScript files in the frontend.
- Vite is the build tool and dev server. Next.js is not used.
- React Router is the routing library. No file-system-based routing.
- TanStack Query manages server state and API data fetching.
- shadcn/ui is the only UI component library. Additional component libraries are not added without change control.
- Tailwind CSS is the only styling mechanism. No CSS Modules, styled-components, or Emotion.
- The frontend is a client-side SPA. Server-side rendering (SSR) is not part of the current architecture.
- `NEXT_PUBLIC_` environment variable prefixes are not used. Vite uses `VITE_` prefix for client-exposed env vars.
