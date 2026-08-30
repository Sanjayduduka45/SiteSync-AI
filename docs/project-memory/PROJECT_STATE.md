# PROJECT STATE — SiteSync AI

> Updated: 2026-08-30
> Current Phase: **Phase 3 — Reports & Field Events Domain Foundation** ✅ COMPLETE

---

## Repository State

| Item | Status |
|---|---|
| Git repository | Active, remote: `Sanjayduduka45/SiteSync-AI` |
| Branch | `main` |
| Tags | `phase-0-complete` (commit `5882414`), `phase-1-complete` (commit `0ee7b64`) |

---

## What Exists

| Path | Description |
|---|---|
| `README.md` | Project README |
| `.gitignore` | Root gitignore |
| `.env.example` | Root environment variable template |
| `dev.sh` | Development startup script (starts both servers) |
| `docs/project-memory/` | All project memory documents including `DATABASE_SCHEMA.md` |
| `supabase/migrations/` | Phase 2 and Phase 3 Supabase PostgreSQL schema migrations with RLS policies |
| `frontend/` | React + Vite + TypeScript SPA with Supabase Auth, Project Context, Reports & Events UI |
| `frontend/src/features/auth/` | AuthContext, useAuth, auth types, and session management |
| `frontend/src/features/projects/` | ProjectContext, useProject, project switcher state |
| `frontend/src/features/reports/` | Reports types, API service layer |
| `frontend/src/features/events/` | Field Events types, API service layer |
| `frontend/src/components/layout/AppLayout.tsx` | Top navigation bar with brand, project switcher, role badge, nav links |
| `frontend/src/components/auth/ProtectedRoute.tsx` | Route guard component for protected views |
| `frontend/src/pages/LoginPage.tsx` | Authentication login page |
| `frontend/src/pages/StatusPage.tsx` | Foundation status page |
| `frontend/src/pages/ReportsPage.tsx` | Reports management, upload modal, detail drawer with linked events |
| `frontend/src/pages/EventsPage.tsx` | Field events table, create event modal, detail drawer with AI placeholders |
| `frontend/src/services/api.ts` | API service layer with automated Bearer JWT attachment (GET, POST, PATCH, DELETE) |
| `frontend/src/test/` | Vitest test suite for auth, routing, status page, project context, reports, events (25 tests) |
| `backend/` | FastAPI Python backend with JWT authorization, project RBAC, and domain services |
| `backend/app/main.py` | FastAPI application factory with standard error envelopes |
| `backend/app/core/config.py` | Pydantic-settings configuration with Supabase settings |
| `backend/app/core/auth.py` | Supabase JWT token verification, identity resolution, project RBAC |
| `backend/app/services/report_service.py` | Report domain service with project scoping and CRUD |
| `backend/app/services/event_service.py` | Field event domain service with validation and progress tracking |
| `backend/app/schemas/reports.py` | Pydantic schemas for Reports |
| `backend/app/schemas/events.py` | Pydantic schemas for Field Events |
| `backend/app/api/v1/routers/reports.py` | GET, POST, DELETE /api/v1/projects/{project_id}/reports |
| `backend/app/api/v1/routers/events.py` | GET, POST, PATCH /api/v1/projects/{project_id}/events |
| `backend/tests/` | Pytest suite for auth, reports, events, project isolation, RLS, health (37 tests) |

---

## Verified Working

| Check | Result |
|---|---|
| Frontend TypeScript check (`npm run typecheck`) | ✅ Pass (0 errors) |
| Frontend build (`npm run build`) | ✅ Pass |
| Frontend lint (`npm run lint`) | ✅ Pass (0 errors) |
| Frontend tests (Vitest) | ✅ 25/25 pass |
| Backend import check | ✅ FastAPI app imports cleanly |
| Backend tests (pytest) | ✅ 37/37 pass |
| Multi-tenant project isolation | ✅ Verified across reports & field events |
| Role-based access control (Admin, Planner, Supervisor, Viewer) | ✅ Enforced on backend and reflected in frontend UI |
| SQL Migration & RLS policies | ✅ Explicit project-scoped RLS policies verified |

---

## What Does NOT Exist Yet

| Item | Phase |
|---|---|
| Schedule import & parsing | Future Phase |
| AI extraction pipeline | Future Phase |
| Schedule matching & intelligence | Future Phase |
| Planner review & approval workflow | Future Phase |
| Plan vs Actual analytics | Future Phase |
| Risk detection engine | Future Phase |

---

## Active Decisions

See `DECISIONS.md` for all architectural decision records (ADR-001 through ADR-008).

Key decisions in effect:
- React + Vite + TypeScript + Tailwind + shadcn/ui + React Router + TanStack Query (frontend, ADR-008)
- FastAPI + Python + Pydantic v2 (backend, ADR-002)
- Supabase (PostgreSQL + Auth + Storage) (platform, ADR-003)
- Explicit project-scoped RLS policies for reports and field events (Phase 3)
- Server-side authorization on every endpoint (SECURITY_RULES.md)
- Light theme only (UI, ADR-006)
- AI recommends, humans decide (ADR-005)
