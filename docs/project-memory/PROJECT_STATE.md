# PROJECT STATE — SiteSync AI

> Updated: 2026-08-30
> Current Phase: **Phase 2 — Authentication + Authorization** ✅ COMPLETE

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
| `supabase/migrations/` | Phase 2 Supabase PostgreSQL schema and RLS policies migration |
| `frontend/` | React + Vite + TypeScript SPA with Supabase Auth |
| `frontend/src/features/auth/` | AuthContext, useAuth, auth types, and session management |
| `frontend/src/components/auth/ProtectedRoute.tsx` | Route guard component for protected views |
| `frontend/src/pages/LoginPage.tsx` | Phase 2 authentication login page |
| `frontend/src/pages/StatusPage.tsx` | Foundation status page with authenticated session state and sign out |
| `frontend/src/features/health/api.ts` | Health check query |
| `frontend/src/services/api.ts` | API service layer with automated Bearer JWT attachment |
| `frontend/src/test/` | Vitest test suite for auth, routing, and status page |
| `frontend/src/components/ui/` | shadcn/ui components (button) |
| `frontend/src/lib/` | Utilities (`utils.ts`) and Supabase client (`supabase.ts`) |
| `backend/` | FastAPI Python backend with JWT authorization and project RBAC |
| `backend/app/main.py` | FastAPI application factory with standard error envelopes |
| `backend/app/core/config.py` | Pydantic-settings configuration with Supabase settings |
| `backend/app/core/auth.py` | Supabase JWT token verification, identity resolution, project RBAC |
| `backend/app/api/v1/__init__.py` | v1 API router |
| `backend/app/api/v1/routers/health.py` | GET /api/v1/health endpoint |
| `backend/app/api/v1/routers/auth.py` | GET /api/v1/auth/me and protected project endpoints |
| `backend/app/schemas/auth.py` | Pydantic schemas for Auth, UserIdentity, Roles, Projects, Errors |
| `backend/app/schemas/health.py` | Health response Pydantic schema |
| `backend/tests/` | Pytest suite for auth, server-side RBAC, IDOR prevention, RLS policies, health |

---

## Verified Working

| Check | Result |
|---|---|
| Frontend TypeScript check (`npm run typecheck`) | ✅ Pass (0 errors) |
| Frontend build (`npm run build`) | ✅ Pass |
| Frontend lint (`npm run lint`) | ✅ Pass (0 errors) |
| Frontend tests (Vitest) | ✅ 15/15 pass |
| Backend import check | ✅ FastAPI app imports cleanly |
| Backend tests (pytest) | ✅ 18/18 pass |
| Unauthenticated access rejection | ✅ 401 Unauthorized with standard error envelope |
| Server-side project authorization (IDOR prevention) | ✅ 403 Forbidden on cross-project unauthorized access |
| Role hierarchy check (admin/planner/supervisor/viewer) | ✅ 403 Forbidden for non-admin on admin-restricted action |
| RLS policy verification | ✅ Syntax and policy rules verified |
| No secrets in source | ✅ Verified |

---

## What Does NOT Exist Yet

| Item | Phase |
|---|---|
| Schedule import | Phase 3 |
| Field input | Phase 4 |
| AI extraction pipeline | Phase 5 |
| Schedule matching | Phase 6 |
| Planner review UI | Phase 7 |
| Plan vs Actual | Phase 8 |
| Risk engine | Phase 9 |
| Audit viewer | Phase 10 |

---

## Active Decisions

See `DECISIONS.md` for all architectural decision records (ADR-001 through ADR-008).

Key decisions in effect:
- React + Vite + TypeScript + Tailwind + shadcn/ui + React Router + TanStack Query (frontend, ADR-008)
- FastAPI + Python + Pydantic v2 (backend, ADR-002)
- Supabase (PostgreSQL + Auth + Storage) (platform, ADR-003)
- Explicit project-scoped RLS policies (Phase 2, ADR-003)
- Server-side authorization on every endpoint (SECURITY_RULES.md)
- Light theme only (UI, ADR-006)
- AI recommends, humans decide (ADR-005)

---

## Known Issues / Risks

| Item | Type | Notes |
|---|---|---|
| Supabase live instance | Pending cloud provision | Auth and RLS architecture implemented and tested via mock/local fixtures; live Supabase credentials can be plugged in via environment variables without code changes |
| Gemini API access | Not configured | Required for Phase 5 |
| Schedule data format | Undefined | Input format to be decided in Phase 3 |

---

## Next Action

**Phase 3 — Schedule Import** is the next phase.

Do not begin Phase 3 without explicit human approval.
