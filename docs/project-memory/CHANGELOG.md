# CHANGELOG — SiteSync AI

All significant changes are recorded here, organized by phase.

---

## Phase 0 — Foundation

**Date**: 2026-08-30
**Status**: Complete
**Git Tag**: `phase-0-complete`

### Added

- `README.md` — Project overview, tech stack, and documentation index.
- `docs/project-memory/MASTER_CONTEXT.md` — Primary reference document for agents and developers.
- `docs/project-memory/PRODUCT_REQUIREMENTS.md` — Product vision, users, and functional requirements.
- `docs/project-memory/ARCHITECTURE.md` — System architecture, directory structure, and API contract principles.
- `docs/project-memory/SECURITY_RULES.md` — Non-negotiable security rules and boundaries.
- `docs/project-memory/UI_UX_SYSTEM.md` — UI/UX principles, prohibited patterns, and required patterns.
- `docs/project-memory/AI_SPEC.md` — AI pipeline architecture, output schemas, and security rules.
- `docs/project-memory/DEVELOPMENT_PHASES.md` — Phase roadmap, scope boundaries, and Definition of Done.
- `docs/project-memory/PROJECT_STATE.md` — Current project state snapshot.
- `docs/project-memory/DECISIONS.md` — Architectural Decision Records (ADR-001 through ADR-007).
- `docs/project-memory/DO_NOT_CHANGE.md` — Locked items list and change control procedure.
- `docs/project-memory/CHANGELOG.md` — This file.
- `.gitignore` — Excludes secrets, environment files, and build artifacts.
- `.env.example` — Placeholder environment variable template.

### Changed

- `README.md` — Replaced placeholder empty file with full project README.

### Not Implemented (by design)

- No application code.
- No authentication.
- No frontend or backend scaffold.
- No database schema.
- No AI components.

---

## Phase 1 — Scaffold

**Date**: 2026-08-30
**Status**: Complete
**Git Tag**: `phase-1-complete`

### Added

**Frontend**
- `frontend/` — React + Vite + TypeScript SPA initialized
- `frontend/vite.config.ts` — Tailwind CSS (`@tailwindcss/vite`), path alias (`@/`), dev proxy to backend, Vitest configuration
- `frontend/src/index.css` — Tailwind v4 import and shadcn theme variables
- `frontend/src/main.tsx` — Application entry point (StrictMode)
- `frontend/src/App.tsx` — QueryClientProvider + BrowserRouter + Routes
- `frontend/src/pages/StatusPage.tsx` — Phase 1 foundation status screen
- `frontend/src/features/health/api.ts` — Health check query (TanStack Query)
- `frontend/src/services/api.ts` — API service layer (all backend calls go here)
- `frontend/src/test/setup.ts` — Vitest setup (jest-dom)
- `frontend/src/test/StatusPage.test.tsx` — StatusPage unit tests (4 tests)
- `frontend/.env.example` — Frontend environment variable template (`VITE_*`)

**Backend**
- `backend/` — FastAPI + Python 3.13 + Pydantic v2 backend
- `backend/app/main.py` — FastAPI application factory (CORS, conditional docs)
- `backend/app/core/config.py` — Pydantic-settings configuration (env-based)
- `backend/app/api/v1/__init__.py` — v1 API router
- `backend/app/api/v1/routers/health.py` — `GET /api/v1/health` endpoint
- `backend/app/schemas/health.py` — HealthResponse Pydantic schema
- `backend/tests/test_health.py` — Health endpoint tests (5 tests)
- `backend/requirements.txt` — Pinned Python dependencies
- `backend/.env.example` — Backend environment variable template
- `backend/.venv/` — Python virtual environment (gitignored)

**Root**
- `dev.sh` — Development startup script (starts both servers)

---

## Phase 2 — Authentication & Authorization

**Date**: 2026-08-30
**Status**: Complete

### Added

**Database & RLS**
- `supabase/migrations/20260830000000_phase2_auth_foundation.sql` — PostgreSQL migration creating `profiles`, `projects`, `project_members`, `project_role` enum, automatic profile trigger, and explicit multi-tenant Row-Level Security (RLS) policies.
- `docs/project-memory/DATABASE_SCHEMA.md` — Full database schema specification with column types, relationships, indices, RLS policies, and role hierarchy.

**Backend**
- `backend/app/core/auth.py` — Supabase JWT verification, server-side identity extraction, project membership resolution, and role hierarchy authorization.
- `backend/app/schemas/auth.py` — Pydantic schemas for `UserIdentity`, `ProjectRole`, `ProjectMembershipSummary`, `AuthMeResponse`, `ProjectDetailResponse`, and `ApiErrorResponse`.
- `backend/app/api/v1/routers/auth.py` — `GET /api/v1/auth/me`, `GET /api/v1/projects/{project_id}`, `POST /api/v1/projects/{project_id}/admin-check`.
- `backend/tests/test_auth.py` — 9 tests covering token validation, 401 unauthenticated, 403 cross-project access/IDOR prevention, and role hierarchy.
- `backend/tests/test_rls_policies.py` — 4 tests validating SQL migration RLS constraints and anti-permissive policy checks.

**Frontend**
- `frontend/src/lib/supabase.ts` — Client-safe Supabase instance initialization with graceful fallback.
- `frontend/src/features/auth/` — `types.ts`, `context.ts`, `AuthContext.tsx`, `useAuth.ts` for session persistence and auth state management.
- `frontend/src/components/auth/ProtectedRoute.tsx` — Client-side route guard with session loading spinner and redirect to `/login`.
- `frontend/src/pages/LoginPage.tsx` — Light-theme sign in form using existing design system tokens and shadcn Button.
- `frontend/src/pages/StatusPage.tsx` — Updated to display authenticated user profile and sign-out action while preserving Phase 1 connectivity indicators.
- `frontend/src/services/api.ts` — Automatically attaches Bearer JWT token to API requests.
- `frontend/src/test/LoginPage.test.tsx` (5 tests)
- `frontend/src/test/ProtectedRoute.test.tsx` (3 tests)
- `frontend/src/test/AuthContext.test.tsx` (3 tests)

### Test Results

| Suite | Tests | Result |
|---|---|---|
| Frontend (Vitest) | 15 | ✅ All pass |
| Backend (pytest) | 18 | ✅ All pass |
| TypeScript check (`npm run typecheck`) | — | ✅ Pass (0 errors) |
| Frontend build (`npm run build`) | — | ✅ Pass |
| Frontend lint (`oxlint`) | — | ✅ Pass (0 errors) |

### Not Implemented (by design)

- No dashboard
- No project management UI
- No schedule import
- No file upload
- No AI pipeline
- No social logins / MFA
