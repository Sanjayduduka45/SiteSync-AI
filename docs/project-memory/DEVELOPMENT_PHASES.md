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

## Phase 1 — Scaffold ✅ COMPLETE

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

## Phase 8 — Plan vs Actual + Variance (COMPLETE — LOCKED)

**Objective**: Compare approved actuals to schedule baseline deterministically.

**Delivered Scope**:
- **Phase 8.1 Pure Domain Engine**: Mathematical models (`ΔQ = Actual - Planned`, `P% = (Actual / Planned) * 100` unclamped, `ΔT = Latest Actual Date - Planned Finish Date`), unit compatibility, null handling, multi-actual cumulative sum, and status lifecycle (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `OVER_DELIVERED`, `UNQUANTIFIED`, `UNIT_MISMATCH`). See ADR-009, ADR-010, ADR-011.
- **Phase 8.2 Read-Only FastAPI APIs**: `/api/v1/projects/{project_id}/variance/summary`, `/activities`, `/wbs` with project-level isolation, RBAC (all 4 roles read-only), server-side pagination, and error sanitization. See ADR-012, ADR-013.
- **Phase 8.3 Plan vs Actual Dashboard**: Frontend KPI cards, homogeneous unit scope rollups, itemized activity variance table, WBS rollups, and filter bar.
- **Phase 8.4 Security Audit & Lock**: 366 backend tests, 124 frontend tests, zero Phase 9 leaks, verified tenant isolation, 100% read-only enforcement.


---

## Phase 9 — Risk and Impact (COMPLETE — LOCKED)

**Objective**: Surface risk, critical path vulnerability, and downstream impact from schedule baseline and verified variances deterministically.

**Canon & ADRs**:
- **ADR-014**: Activity Dependency Data Foundation (`public.schedule_dependencies`, edge model, tenant integrity, cycle prevention).
- **ADR-015**: Critical Path Method (CPM) Mathematical & Float Contract (inclusive duration, forward/backward pass for `FS`, `SS`, `FF`, `SF`, Total/Free Float, $TF \le 0$ criticality).
- **ADR-016**: Downstream Impact & Factual Delay Traversal Contract (transitive DAG traversal, absorbed vs critical impact, factual slippage).
- **ADR-017**: Deterministic Risk Intelligence & Severity Taxonomy (6-category taxonomy, discrete severity, composite 0–100 integer score).
- **ADR-018**: Prediction, Heatmap & Presentation Boundary (exclusion of probabilistic AI forecasting, 2D Heatmap, PM dashboard).

**Delivered Scope**:
- **Phase 9.0**: Canon Lock & Decision Gate (COMPLETE)
- **Phase 9.1**: Database Foundation Migration (`public.schedule_dependencies` with RLS) (COMPLETE)
- **Phase 9.2**: Pure CPM & DAG Domain Engine (COMPLETE)
- **Phase 9.3**: Downstream Impact & Float Erosion Service (COMPLETE)
- **Phase 9.4**: Risk Intelligence & Severity Engine (COMPLETE)
- **Phase 9.5**: FastAPI Network & Risk APIs (RBAC + Tenant Isolation) (COMPLETE)
- **Phase 9.6**: Frontend Risk & Critical Path Intelligence UI (COMPLETE)
- **Phase 9.7**: Adversarial Security & Concurrency Audit (COMPLETE)
- **Phase 9.8**: Final Release Readiness & Lock (LOCKED)



---

## Phase 10 — Audit and Reporting (COMPLETE — LOCKED)

**Objective**: Surface an immutable, end-to-end audit log of all project updates and human decisions, and provide exportable progress, variance, and risk reporting across the full field-to-schedule lifecycle.

**Canon & ADRs**:
- **ADR-019**: Phase 10 Export Formats & Serialization Contract (RFC 4180 CSV with formula injection escaping, strongly-typed JSON, deterministic dataset columns).
- **ADR-020**: Phase 10 Audit Event Taxonomy & Immutability Contract (append-only unified audit event stream, strict update/delete prohibition, read-only RLS).
- **ADR-021**: Phase 10 Audit Route & Provenance Presentation Contract (dedicated `/audit` route, step-by-step visual provenance lineage, direct export actions).

**Delivered Scope**:
- **Phase 10.0**: Canon Lock & Decision Gate (COMPLETE)
- **Phase 10.1**: Audit & Provenance Domain Query Engine (COMPLETE)
- **Phase 10.2**: Report Export Serialization Services (CSV / JSON) (COMPLETE)
- **Phase 10.3**: FastAPI Audit & Export APIs (Tenant Isolation + RBAC) (COMPLETE)
- **Phase 10.4**: Frontend Audit Log Viewer & Lineage Visualizer UI (COMPLETE)
- **Phase 10.5**: Frontend Export Action Integration & Navigation (COMPLETE)
- **Phase 10.6**: Adversarial Security, IDOR & Data Integrity Audit (COMPLETE)
- **Phase 10.7**: Final Release Verification & Phase 10 Lock (COMPLETE — LOCKED)

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
