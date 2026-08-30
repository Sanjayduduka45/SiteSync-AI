# DEVELOPMENT PHASES — SiteSync AI

## Phase Isolation Principles

- Only the **active approved phase** is implemented at any time.
- Completed phases are **protected**. Their behavior, APIs, and data contracts are locked.
- Changes to completed-phase behavior require change control (see DO_NOT_CHANGE.md).
- Every phase ends with a **stable Git checkpoint** (tagged commit).
- Regression testing is performed before any phase is accepted.

---

## Phase 0 — Foundation ✅ COMPLETE

**Objective**: Prepare the repository for structured development.

**Scope**:
- Repository initialization
- Project memory documentation
- Product vision and scope
- Architecture and technology decisions
- AI architecture documentation
- Security rules
- UI/UX principles
- Development and phase-isolation rules
- Definition of Done
- Environment/secrets handling baseline
- Current project state
- Architectural decision records

**Deliverables**:
- `docs/project-memory/` — all 11 required documents
- `README.md` — updated project README
- `.gitignore` — secrets and environment files excluded
- `.env.example` — placeholder environment variable template
- Git tag: `phase-0-complete`

**Does NOT include**:
- Any application code
- Authentication
- Dashboard
- AI extraction
- Schedule management
- File processing
- Database schema
- API routes

---

## Phase 1 — Scaffold (Next)

**Objective**: Establish working project skeleton with no application features.

**Planned Scope**:
- Frontend: React + Vite + TypeScript + Tailwind + shadcn/ui initialized
- Backend: FastAPI + Pydantic v2 project initialized
- Supabase project connection configured (env-based)
- Basic health-check API endpoint
- No authentication flows implemented
- No database schema
- No AI components
- Docker / dev environment setup

**Acceptance Criteria**:
- `npm run dev` starts the frontend without errors.
- `uvicorn app.main:app` starts the backend without errors.
- Health check endpoint returns 200.
- No secrets in code or Git.

---

## Phase 2 — Authentication (Planned)

**Objective**: Implement authentication using Supabase Auth.

**Planned Scope**:
- Sign in / sign out flow
- JWT validation on backend
- User profile basics
- Role assignment (field, planner, PM, admin)
- Protected routes on frontend
- RLS baseline on Supabase

**Does NOT include**:
- Application features
- Dashboard content
- Schedule data

---

## Phase 3 — Schedule Import (Planned)

**Objective**: Import construction schedule activities into the system.

**Planned Scope**:
- Schedule activity data model
- Schedule import API
- Activity embedding pipeline (pgvector)
- Basic schedule activity list view (read-only)

---

## Phase 4 — Field Input (Planned)

**Objective**: Allow field users to submit progress updates.

**Planned Scope**:
- Field input form (text)
- Voice input (Whisper transcription)
- Photo upload (Supabase Storage)
- Field input persistence
- No AI processing yet

---

## Phase 5 — AI Extraction (Planned)

**Objective**: Extract structured data from field inputs using AI.

**Planned Scope**:
- LangChain + Gemini extraction pipeline
- Extraction result validation (Pydantic)
- Extraction stored linked to field input
- Extraction output visible to planner (read-only)

---

## Phase 6 — Schedule Matching (Planned)

**Objective**: Match AI extractions to schedule activities.

**Planned Scope**:
- pgvector similarity search
- Contextual scoring and re-ranking
- Confidence score calculation
- Evidence token extraction
- Match recommendations stored

---

## Phase 7 — Planner Review (Planned)

**Objective**: Planner review and decision workflow.

**Planned Scope**:
- Planner review screen
- Approve / Reject / Modify actions
- Approved actual record creation
- Audit log entries

---

## Phase 8 — Plan vs Actual + Variance (Planned)

**Objective**: Compare approved actuals to schedule baseline.

**Planned Scope**:
- Plan vs actual calculation
- Variance display (activity, WBS, project levels)
- Variance flagging

---

## Phase 9 — Risk and Impact (Planned)

**Objective**: Surface risk from variance.

**Planned Scope**:
- Downstream impact assessment
- Critical path risk surfacing
- Risk display for PM role

---

## Phase 10 — Audit and Reporting (Planned)

**Objective**: Audit trail and reporting.

**Planned Scope**:
- Audit log viewer
- Basic exportable reports
- Full audit trail per field input → decision

---

## Definition of Done (per Phase)

A phase is **Done** when all of the following are true:

- [ ] All planned scope items are implemented.
- [ ] No scope items from future phases are implemented.
- [ ] All new APIs are tested (manual or automated).
- [ ] All security rules in `SECURITY_RULES.md` are upheld.
- [ ] No secrets are in Git.
- [ ] RLS policies are verified for any database changes.
- [ ] Regression: existing passing tests still pass.
- [ ] `PROJECT_STATE.md` is updated.
- [ ] `CHANGELOG.md` entry added.
- [ ] A stable Git tag is created: `phase-N-complete`.
- [ ] A human has reviewed and accepted the phase.
