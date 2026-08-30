# SiteSync AI — Field to Schedule Intelligence

SiteSync AI is a construction project intelligence platform that bridges the gap between field observations and project schedules. It uses AI to extract structured data from unstructured field inputs and presents recommendations for planner review and decision.

## Core Workflow

```
Field Input → AI Extraction → Normalization → Schedule Matching
→ Confidence + Evidence → Planner Review → Planner Decision
→ Approved Actual → Plan vs Actual → Variance → Risk / Impact → Audit
```

**AI recommends. Humans decide.**

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python, Pydantic |
| Platform | Supabase (PostgreSQL, Auth, Storage), pgvector |
| AI | LangChain, Gemini, Embeddings, Whisper/STT |

## Documentation

All project memory and architecture decisions live in [`docs/project-memory/`](docs/project-memory/).

## Development Status

**Current Phase: Phase 0 — Foundation (Complete)**

See [`docs/project-memory/PROJECT_STATE.md`](docs/project-memory/PROJECT_STATE.md) for current state.
See [`docs/project-memory/DEVELOPMENT_PHASES.md`](docs/project-memory/DEVELOPMENT_PHASES.md) for phase roadmap.

## Getting Started

> Setup instructions will be added when Phase 1 scaffolding is complete.

## License

Proprietary. All rights reserved.
