# SITESYNC AI — NEXT PHASE DISCOVERY REPORT

## 1. Executive Summary
This discovery report evaluates the canonical status of SiteSync AI following the successful verification and locking of **Phase 9 (Risk & Critical Path Method Intelligence)**. In accordance with the authoritative project-memory documentation (`DEVELOPMENT_PHASES.md`, `PRODUCT_REQUIREMENTS.md`, `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `DECISIONS.md`), this report formally defines the exact next phase: **Phase 10 — Audit and Reporting**.

---

## 2. Current Project Status
- **Phase 0 (Foundation)**: COMPLETE & LOCKED
- **Phase 1 (Scaffold)**: COMPLETE & LOCKED
- **Phase 2 (Authentication & Multi-Tenant Access)**: COMPLETE & LOCKED
- **Phase 3 (Reports & Field Events)**: COMPLETE & LOCKED
- **Phase 4 (Field Inputs & Media Ingestion)**: COMPLETE & LOCKED
- **Phase 5 (AI Extraction & Normalization)**: COMPLETE & LOCKED
- **Phase 6 (Schedule Ingestion & Matching)**: COMPLETE & LOCKED
- **Phase 7 (Planner Review & Approved Actuals)**: COMPLETE & LOCKED
- **Phase 8 (Plan vs Actual & Variance Intelligence)**: COMPLETE & LOCKED
- **Phase 9 (Risk & Critical Path Method Intelligence)**: COMPLETE & LOCKED
- **Test Baseline**: 497 backend tests passing, 157 frontend tests passing, 0 typecheck errors, 0 linter errors, clean production build.

---

## 3. Exact Next Canonical Phase
- **Phase Identifier**: `Phase 10`
- **Phase Title**: `Audit and Reporting`
- **Current Status**: `Planned (UNLOCKED)`
- **Canonical Definition Reference**: [`docs/project-memory/DEVELOPMENT_PHASES.md:L192-200`](file:///Users/sanjayduduka/Downloads/SiteSync/docs/project-memory/DEVELOPMENT_PHASES.md#L192-L200)

---

## 4. Canonical Objective
> **"Audit trail and reporting."**
> Surface an immutable, end-to-end audit log of all project updates and human decisions, and provide exportable progress and risk reporting across the full field-to-schedule lifecycle (`Field Input → Extraction → Match Recommendation → Planner Decision → Approved Actual → Variance → Risk`).

---

## 5. Requirements

### Canonical Requirements (from `PRODUCT_REQUIREMENTS.md` & `DEVELOPMENT_PHASES.md`)
1. **Audit Log Viewer**: Interactive viewer displaying chronological audit records of user and system actions.
2. **Full Provenance Chain**: End-to-end audit trail linking raw field inputs, AI extractions, confidence scores, AI matches, planner review decisions (approvals, rejections, modifications), and approved actuals.
3. **Decision Accountability**: Every approval, rejection (with reason), and modification (logging both AI version and human overrides) must display timestamp, user ID, and project context.
4. **Basic Exportable Reports**: Exportable summary reports for project progress, approved actuals, plan-vs-actual variance, and risk profiles.

### Scope Boundaries
- **In-Scope**: Audit log queries, provenance chain visualization, tabular export (CSV, JSON summary), project progress summary report.
- **Out of Scope (Locked)**: Direct bidirectional sync with third-party enterprise tools (Primavera P6, MS Project), real-time multi-user collaboration websockets, native mobile apps, financial cost accounting.

---

## 6. Existing Implementation Relevant to Next Phase

| Layer | Existing File | Current Status & Role for Phase 10 |
|---|---|---|
| **Database** | `public.planner_decisions` | Established in Phase 7. Append-only records of all decisions (`approved`, `rejected`, `modified`), payloads, and planner IDs. |
| **Database** | `public.approved_actuals` | Established in Phase 7. Official immutable progress records with `source_evidence`, `approved_by`, `notes`, `is_modified`. |
| **Database** | `public.field_inputs` | Established in Phase 4. Submitter profile, modality, STT transcription state, raw text, timestamp. |
| **Database** | `public.ai_extractions` | Established in Phase 5. Model version, confidence score, structured items. |
| **Database** | `public.ai_matches` | Established in Phase 6. Recommended activity, match confidence, scoring breakdown. |
| **Backend** | `backend/app/services/decision_service.py` | Query and create methods for planner decisions and approved actuals. |
| **Frontend** | `frontend/src/pages/ReportsPage.tsx` | Currently manages raw document uploads (`public.reports`). Does not yet support audit logs or analytical summary exports. |
| **Frontend** | `frontend/src/pages/ApprovedActualsPage.tsx` | Displays approved actuals, but lacks comprehensive provenance timeline drawer or export actions. |

---

## 7. Data Model Requirements

### Data Ownership & Boundary
- **Owned Data**: Unified audit trail views/aggregations, export report definitions and parameters.
- **Consumed Data (Read-Only)**:
  - `public.profiles` (user identity)
  - `public.field_inputs` (source submissions)
  - `public.ai_extractions` (AI extraction telemetry)
  - `public.ai_matches` (matching decisions)
  - `public.planner_decisions` (human decisions)
  - `public.approved_actuals` (approved ground truth)
  - `public.schedule_activities` (baseline activities)
  - `public.schedule_dependencies` (dependency graph)
- **Database Schema Changes**:
  - Existing tables in migrations `00` through `07` already capture all provenance entities with immutable constraints.
  - Phase 10 can be implemented primarily as domain query services and aggregation views without requiring destructive alterations to historical tables.

---

## 8. API Requirements

Expected Phase 10 REST API surface (to be formalized in Phase 10 Decision Gate):
1. `GET /api/v1/projects/{project_id}/audit/trail`: Paginated, filterable audit log stream (filterable by entity type, user, decision type, date range).
2. `GET /api/v1/projects/{project_id}/audit/provenance/{entity_type}/{entity_id}`: Full upstream and downstream lineage graph for a specific field input or approved actual.
3. `GET /api/v1/projects/{project_id}/reports/export/actuals`: Export approved actuals dataset (CSV / JSON format).
4. `GET /api/v1/projects/{project_id}/reports/export/variance`: Export Plan vs Actual variance summary (CSV / JSON format).
5. `GET /api/v1/projects/{project_id}/reports/export/risks`: Export risk and critical path register (CSV / JSON format).

---

## 9. Frontend Requirements

Expected Phase 10 User Interface components:
1. **Audit Log & History Dashboard** (`/audit` or integrated reporting tab):
   - Interactive audit event stream with actor, timestamp, action type, and diff viewer.
   - Filter bar: Actor, Action Type (`APPROVED`, `REJECTED`, `MODIFIED`, `SUBMITTED`), Date Range, WBS.
2. **Provenance Lineage Modal / Drawer**:
   - Visual step-by-step trace: `Field Input [Audio/Text] -> Extraction [Gemini] -> Match [Score] -> Decision [Planner] -> Approved Actual`.
3. **Export Controls**:
   - One-click CSV and JSON exports on Approved Actuals, Variance Dashboard, and Risk Register.

---

## 10. Security & Tenant Requirements
- **Authentication**: All audit and export endpoints must require authenticated Bearer JWT tokens.
- **Tenant Isolation**: Audit logs and exports are strictly scoped to the `project_id` in the URL path. Cross-tenant queries return HTTP 403 Forbidden.
- **RBAC Matrix**:
  - `viewer`, `supervisor`, `planner`, `admin`: Read-only access to audit logs and exports for assigned projects.
  - Audit trail is strictly read-only / append-only. Zero DELETE or UPDATE capabilities permitted.
- **PII & Data Sanitization**: Export files and audit streams must sanitize system credentials, service role keys, and internal database exception details.

---

## 11. Phase 9 → Next Phase Boundary

### Consumed from Phase 9 (Read-Only)
- Schedule dependency edges (`public.schedule_dependencies`)
- CPM calculation outputs (Early/Late dates, Total Float, Free Float, Critical Path)
- Transitive downstream delay propagation results
- Risk severity classifications and composite risk scores

### Phase 9 Protection Invariant
- Phase 10 **MUST NOT** recalculate CPM algorithms, alter dependency edges, or modify the 6-category risk taxonomy established in Phase 9.

---

## 12. Canon Gaps

| ID | Area | Missing Definition | Candidate Options | Recommended Option | Requires ADR? | Blocking? |
|---|---|---|---|---|---|---|
| **GAP-10.1** | Export Format Standard | `DEVELOPMENT_PHASES.md` specifies "Basic exportable reports" without defining file formats. | Option A: CSV only.<br>Option B: CSV and JSON.<br>Option C: PDF generation. | **Option B (CSV and structured JSON)**. Lightweight, deterministic, no heavyweight PDF rendering dependencies. | **YES (ADR-019)** | **YES** |
| **GAP-10.2** | UI Navigation & Route Structure | `DEVELOPMENT_PHASES.md` specifies "Audit log viewer" without specifying if it resides at `/audit` or expands `/reports`. | Option A: New dedicated `/audit` route + nav link.<br>Option B: Consolidate under `/reports` with sub-tabs. | **Option A (`/audit` route)**. Clear separation of operational field reports from regulatory/system audit trails. | **YES (ADR-020)** | **YES** |
| **GAP-10.3** | Audit Event Scope | Boundary of which system events are included in the audit log viewer. | Option A: Planner decisions only.<br>Option B: Complete lifecycle (inputs, extractions, decisions, dependency mutations). | **Option B (Complete lifecycle)**. Delivers full traceability demanded by `PRODUCT_REQUIREMENTS.md:L100`. | **YES (ADR-021)** | **YES** |

---

## 13. Required ADRs / Decision Gates
Before any code implementation begins for Phase 10, the following Architectural Decision Records must be authored, reviewed, and locked:
1. **ADR-019**: Phase 10 Export Formats & Serialization Contract (CSV/JSON schema specifications).
2. **ADR-020**: Phase 10 Audit Trail Data Model, Query Strategy & Route Architecture.
3. **ADR-021**: Phase 10 Lifecycle Event Taxonomy & Provenance Graph Contract.

---

## 14. Recommended Implementation Order

```
Phase 10.0: Canon Lock & Decision Gate (ADR-019 through ADR-021)
    ↓
Phase 10.1: Audit & Provenance Domain Query Engine
    ↓
Phase 10.2: Report Export Serialization Services (CSV / JSON)
    ↓
Phase 10.3: FastAPI Audit & Export Routers (Tenant Isolation + RBAC)
    ↓
Phase 10.4: Frontend Audit Log Viewer & Lineage Visualization UI
    ↓
Phase 10.5: Frontend Export Action Integration & Navigation
    ↓
Phase 10.6: Adversarial Security, IDOR & Data Integrity Audit
    ↓
Phase 10.7: Final Release Verification & Phase 10 Lock
```

---

## 15. Testing Strategy
- **Backend Tests**:
  - Audit trail query filters (actor, date range, action type, pagination).
  - Provenance lineage traversal integrity.
  - CSV/JSON export formatting and escaping tests (preventing CSV injection).
  - IDOR and cross-project audit data leakage rejection.
- **Frontend Tests**:
  - Audit Log table rendering, filtering, and empty states.
  - Provenance drawer step-by-step rendering.
  - Export download trigger tests.
- **Full Regression**: Complete backend suite (497+ tests), frontend suite (157+ tests), typecheck, linter, and build.

---

## 16. Protected File Verification
The following protected artifacts remain 100% untouched:
- `supabase/migrations/20260830000000_phase2_auth_foundation.sql`
- `supabase/migrations/20260830000001_phase3_reports_and_events.sql`
- `supabase/migrations/20260830000002_phase4_field_inputs.sql`
- `supabase/migrations/20260830000003_phase5_ai_extractions.sql`
- `supabase/migrations/20260830000004_phase5_ai_extractions_idempotency.sql`
- `supabase/migrations/20260830000005_phase6_schedule_matching_foundation.sql`
- `supabase/migrations/20260830000006_phase7_planner_review_and_approved_actuals.sql`
- `supabase/migrations/20260830000007_phase9_schedule_dependencies.sql`
- `docs/project-memory/DO_NOT_CHANGE.md`
- `docs/project-memory/SECURITY_RULES.md`

---

## 17. Risks / Unknowns
- **Large Dataset Exports**: Exporting complete project histories must support streaming or chunked memory consumption to avoid memory spikes on large projects.
- **CSV Formula Injection**: User inputs (e.g. planner notes, activity names) starting with `=`, `+`, `-`, or `@` must be safely escaped in CSV generation to prevent spreadsheet formula injection.

---

## 18. Final Readiness Assessment

# NEXT PHASE DISCOVERY — COMPLETE
### CANON GAPS IDENTIFIED
### IMPLEMENTATION BLOCKED UNTIL DECISION GATE (PHASE 10.0)
