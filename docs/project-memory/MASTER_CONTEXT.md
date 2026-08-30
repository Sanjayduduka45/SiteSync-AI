# MASTER CONTEXT — SiteSync AI

> **This is the primary reference for any AI agent or developer entering this repository.**
> Read this file before making any changes. Do not skip it.

---

## What Is SiteSync AI

SiteSync AI is a **construction project intelligence platform**.

It enables field teams to submit unstructured updates (text, voice, photos) which are processed by AI to extract structured progress data. That data is then matched to schedule activities and presented to planners for review and decision.

This is **not** a chatbot. This is **not** a generic AI dashboard. This is a professional construction domain tool.

---

## Core Principle

> **AI recommends. Humans decide.**

- AI extracts, normalizes, matches, and scores data.
- A human planner reviews every AI recommendation.
- Planners approve, reject, or modify before data affects the official schedule record.
- AI never writes directly to approved actual records without human sign-off.

---

## Core Workflow (Locked)

```
Field Input (text / voice / photo)
  → AI Extraction (structured data from unstructured input)
  → Normalization (units, terminology, schedule codes)
  → Schedule Matching (activity identification + confidence)
  → Confidence + Evidence (score + supporting evidence)
  → Planner Review (human reviews AI recommendation)
  → Planner Decision (approve / reject / modify)
  → Approved Actual (official record)
  → Plan vs Actual (comparison)
  → Variance (delta calculation)
  → Risk / Impact (downstream impact assessment)
  → Audit (immutable log)
```

---

## Locked Technology Stack

### Frontend
- **React** — UI library
- **TypeScript** — strict mode
- **Vite** — build tool and dev server
- **Tailwind CSS** — utility-first styling
- **shadcn/ui** — component library
- **React Router** — client-side routing
- **TanStack Query** — server state management

### Backend
- **FastAPI** — Python async REST API
- **Python 3.11+**
- **Pydantic v2** — data validation and schemas

### Platform
- **Supabase PostgreSQL** — primary database
- **Supabase Auth** — authentication
- **Supabase Storage** — file storage
- **pgvector** — vector similarity search

### AI
- **LangChain** — orchestration
- **Gemini** — primary LLM
- **Embeddings** — semantic matching
- **Whisper / suitable STT** — voice transcription
- **pgvector + contextual scoring** — schedule matching

> **Do not replace or silently change this stack.** See DECISIONS.md and DO_NOT_CHANGE.md.

---

## Key Documents

| Document | Purpose |
|---|---|
| `PRODUCT_REQUIREMENTS.md` | What the product does and for whom |
| `ARCHITECTURE.md` | System design and API contracts |
| `AI_SPEC.md` | AI pipeline architecture |
| `SECURITY_RULES.md` | Security rules and boundaries |
| `UI_UX_SYSTEM.md` | UI/UX principles and standards |
| `DEVELOPMENT_PHASES.md` | Phase roadmap and boundaries |
| `PROJECT_STATE.md` | Current state of the project |
| `DECISIONS.md` | Architectural decision records |
| `DO_NOT_CHANGE.md` | Locked items requiring explicit change control |
| `CHANGELOG.md` | Change log per phase |

---

## Current Phase

**Phase 1 — Scaffold**
Status: Complete

Frontend and backend scaffolds are operational. The next phase is Phase 2 — Authentication.

---

## Agent Rules (Mandatory)

1. Read `MASTER_CONTEXT.md` before any change.
2. Only implement work from the active approved phase.
3. Inspect existing code before modifying it.
4. Do not add unrequested features.
5. Do not replace locked architecture.
6. If a change touches a locked item, STOP and report before proceeding.
7. Never commit secrets or credentials.
8. See `DO_NOT_CHANGE.md` for the full lock list.
