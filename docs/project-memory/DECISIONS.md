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

---

## ADR-009 — Phase 8 Plan vs Actual Mathematical & Variance Contract

**Date**: 2026-08-31
**Status**: Decided

**Context**: Phase 8 introduces Plan vs Actual variance calculations. Clear, unambiguous sign conventions and formulas are required so that implementation does not invent conflicting mathematical interpretations.

**Decision**:
1. **Quantity Variance ($\Delta Q$)**:
   $$\text{quantity\_variance} = \text{actual\_quantity\_total} - \text{planned\_quantity}$$
   - **Sign Convention**:
     - Positive ($> 0$): Over plan (more physical quantity achieved than planned).
     - Zero ($= 0$): Exactly at planned quantity.
     - Negative ($< 0$): Under plan (less physical quantity achieved than planned).
   - **Examples**:
     - *Example 1*: Planned = $100\text{ LF}$, Actual = $80\text{ LF}$ $\rightarrow$ $\Delta Q = 80 - 100 = -20\text{ LF}$ ($20\text{ LF}$ under plan).
     - *Example 2*: Planned = $100\text{ LF}$, Actual = $120\text{ LF}$ $\rightarrow$ $\Delta Q = 120 - 100 = +20\text{ LF}$ ($20\text{ LF}$ over plan).
   - This sign convention is locked across all backend calculations, API responses, and frontend displays.

2. **Progress Percentage ($P\%$)**:
   $$\text{progress\_percent} = \left(\frac{\text{actual\_quantity\_total}}{\text{planned\_quantity}}\right) \times 100$$
   - **Rules**:
     - If `planned_quantity == NULL`, `progress_percent = NULL`.
     - If `actual_quantity_total == NULL`, `progress_percent = NULL`.
     - If `planned_quantity == 0`, `progress_percent = NULL` (division by zero prevented).
     - Actual quantity may exceed planned quantity; `progress_percent` **MUST NOT** be clamped to $100\%$.
   - **Examples**:
     - *Example 1*: Planned = $200\text{ m}^3$, Actual = $100\text{ m}^3$ $\rightarrow$ $P\% = (100 / 200) \times 100 = 50\%$.
     - *Example 2*: Planned = $100\text{ m}^3$, Actual = $125\text{ m}^3$ $\rightarrow$ $P\% = (125 / 100) \times 100 = 125\%$.

3. **Date / Schedule Variance ($\Delta T$)**:
   $$\text{date\_variance\_days} = \text{latest\_actual\_date} - \text{planned\_finish\_date}$$
   - **Sign Convention**:
     - Positive ($> 0$): Late (work recorded after planned finish date).
     - Zero ($= 0$): On time (work completed on planned finish date).
     - Negative ($< 0$): Early (work completed before planned finish date).
   - **Examples**:
     - *Example 1*: Planned Finish = `2026-08-10`, Latest Actual = `2026-08-13` $\rightarrow$ $\Delta T = +3\text{ days}$ ($3\text{ days late}$).
     - *Example 2*: Planned Finish = `2026-08-10`, Latest Actual = `2026-08-08` $\rightarrow$ $\Delta T = -2\text{ days}$ ($2\text{ days early}$).
   - If `planned_finish_date == NULL`, `date_variance_days = NULL`.
   - Positive date differences for incomplete activities indicate factual `PAST_DUE / INCOMPLETE` status, but must not trigger predictive delay forecasting (which is Phase 9).

4. **Progress Delta Terminology**:
   - The ambiguous term `progress_delta` is prohibited. Systems must explicitly use:
     - `quantity_variance` for physical quantity difference.
     - `progress_percent` for percentage completion.
     - `date_variance_days` for calendar day finish difference.

**Consequences**:
- All Phase 8 schemas, calculation services, and frontend displays must strictly follow these formulas.

---

## ADR-010 — Multiple Approved Actuals Cumulative Aggregation

**Date**: 2026-08-31
**Status**: Decided

**Context**: Multiple approved actuals can exist for a single schedule activity across different field reports and work dates. A deterministic aggregation rule is required.

**Decision**:
1. **Physical Quantity Aggregation**:
   $$\text{actual\_quantity\_total} = \sum \text{compatible approved\_actuals.actual\_quantity}$$
   - `NULL` actual quantities do not contribute to the sum.
   - If no approved actuals exist for an activity, $\text{actual\_quantity\_total} = 0$.
   - Independent field reports for the same schedule activity accumulate.
2. **Latest Work Date**:
   $$\text{latest\_actual\_date} = \max(\text{approved\_actuals.actual\_date})$$
   - If no approved actuals exist, `latest_actual_date = NULL`.
3. **Idempotency Clarification**:
   - The Phase 7 composite unique constraint `(project_id, extraction_id, activity_index)` prevents duplicate processing of the *same* extraction item.
   - It permits multiple distinct extraction items across different field reports to link to and accumulate against the same schedule activity.
   - *Example 1*: Day 1 = $20\text{ LF}$, Day 2 = $30\text{ LF}$, Day 3 = $25\text{ LF}$ $\rightarrow$ Cumulative actual = $75\text{ LF}$.
   - *Example 2*: Three independent approved extractions of $10$, $15$, and $20$ units $\rightarrow$ Cumulative actual = $45\text{ units}$.

**Consequences**:
- Aggregation services query all approved actuals scoped to `(project_id, schedule_activity_id)` and compute cumulative sums and maximum dates.

---

## ADR-011 — Unit Compatibility & Activity Status Lifecycle

**Date**: 2026-08-31
**Status**: Decided

**Context**: Baseline activities and field actuals may have differing units or unquantified scopes (e.g. milestones). Explicit compatibility and activity lifecycle rules are required.

**Decision**:
1. **Unit Compatibility**:
   - Direct quantity calculations ($\Delta Q$ and $P\%$) are valid **ONLY** when `actual_unit == planned_unit` (case-insensitive, trimmed).
   - Phase 8 **MUST NOT** perform automatic unit conversion.
   - If units mismatch (e.g., planned in `spools`, actual in `LF`), set `quantity_variance = NULL`, `progress_percent = NULL`, and assign `UNIT_MISMATCH` status.
   - *Example 1*: Planned = $100\text{ LF}$, Actual = $40\text{ LF}$ $\rightarrow$ Valid calculation ($40\%$, $-60\text{ LF}$).
   - *Example 2*: Planned = $100\text{ spools}$, Actual = $40\text{ LF}$ $\rightarrow$ Invalid direct calculation $\rightarrow$ `UNIT_MISMATCH`.
2. **Unquantified Activities**:
   - Activities with `planned_quantity == NULL` (e.g. milestones, inspections) remain visible.
   - Set `quantity_variance = NULL`, `progress_percent = NULL`, and assign `UNQUANTIFIED` status.
   - Date variance is still calculated if `planned_finish_date` and `latest_actual_date` exist.
3. **Deterministic Activity Status Rules**:
   - `NOT_STARTED`: No approved actuals exist, or valid $\text{actual\_quantity\_total} == 0$.
   - `IN_PROGRESS`: Valid quantity data and $0 < \text{actual\_quantity\_total} < \text{planned\_quantity}$.
   - `COMPLETED`: Valid quantity data and $\text{actual\_quantity\_total} == \text{planned\_quantity}$.
   - `OVER_DELIVERED`: Valid quantity data and $\text{actual\_quantity\_total} > \text{planned\_quantity}$.
   - `UNQUANTIFIED`: `planned_quantity == NULL`.
   - `UNIT_MISMATCH`: Quantities exist but units are incompatible.

**Consequences**:
- Status classification is fully deterministic and protects against division-by-zero or meaningless cross-unit additions.

---

## ADR-012 — WBS and Project-Level Rollup Contract

**Date**: 2026-08-31
**Status**: Decided

**Context**: Grouping variance across WBS tiers and whole projects requires mathematically honest aggregation without combining incompatible units or averaging percentages.

**Decision**:
1. **No Unweighted Averaging**:
   - WBS and Project progress **MUST NOT** be calculated as an unweighted average of activity percentages.
2. **Homogeneous Unit Rollups**:
   - For a WBS tier or Project with a compatible unit:
     $$\text{planned\_total} = \sum \text{planned\_quantity}$$
     $$\text{actual\_total} = \sum \text{actual\_quantity\_total}$$
     $$\text{progress\_percent} = \left(\frac{\text{actual\_total}}{\text{planned\_total}}\right) \times 100$$
     $$\text{quantity\_variance} = \text{actual\_total} - \text{planned\_total}$$
3. **Multi-Unit Grouping**:
   - If a WBS tier or Project contains multiple distinct units (e.g., $100\text{ LF}$ piping and $50\text{ tons}$ steel), the system provides **unit-specific rollups** rather than combining them into arbitrary "units".
   - *Example 1*: WBS 1.2 with Activity A ($100\text{ LF}$ plan, $50\text{ LF}$ act) and Activity B ($200\text{ LF}$ plan, $100\text{ LF}$ act) $\rightarrow$ Rollup = $300\text{ LF}$ planned, $150\text{ LF}$ actual, $50\%$ progress, $-150\text{ LF}$ variance.
   - *Example 2*: WBS 1.2 with Activity A ($100\text{ LF}$) and Activity B ($50\text{ tons}$) $\rightarrow$ Separate LF and tons rollups exposed.

**Consequences**:
- Multi-unit project rollups are mathematically sound and prevent distorted KPI representations.

---

## ADR-013 — Variance Flagging Policy & Strict Phase 8/9 Boundary

**Date**: 2026-08-31
**Status**: Decided

**Context**: Establishing the policy for variance flagging and preventing premature leakage of Phase 9 risk and critical path features into Phase 8.

**Decision**:
1. **Variance Flagging Policy**:
   - Arbitrary hardcoded thresholds (e.g. `progress < 80%` or `delay >= 5 days`) are **PROHIBITED** without formal product specification.
   - Phase 8.1 implements pure factual variance metrics first.
   - Default `is_flagged = false` (or explicit threshold-configured evaluation if specified by formal change control). The system must never label activities as "critically delayed" based on invented criteria.
2. **Strict Phase 8 vs Phase 9 Boundary**:
   - **Phase 8 Scope (ALLOWED)**:
     - Plan vs actual factual comparisons.
     - Physical quantity variance ($\Delta Q$).
     - Progress percentage ($P\%$).
     - Date / finish variance ($\Delta T$).
     - WBS and Project rollups.
     - Factual overdue/incomplete indicators.
   - **Phase 9 Scope (STRICTLY FORBIDDEN IN PHASE 8)**:
     - Critical path analysis, float, and slack.
     - Downstream activity delay propagation.
     - Predictive delay forecasting.
     - Predictive risk scoring (0–100 or High/Medium/Low risk levels).
     - Risk heatmaps and impact visualizations.
     - Cost tracking / Earned Value Management (EVM).

**Consequences**:
- Phase 8 remains strictly focused on factual historical and current plan-vs-actual variance intelligence.

---

## ADR-014 — Phase 9 Activity Dependency Data Foundation (`public.schedule_dependencies`)

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — NOT PREVIOUSLY CANONICAL

**Context**: Phase 9 requires an activity dependency network to compute Critical Path Method (CPM), Total Float, Free Float, and Downstream Impact. The existing schema (`public.schedule_activities`) contains zero predecessor/successor attributes or relationship edges.

**Decision**:
1. **Dedicated Edge Table**:
   - Introduce `public.schedule_dependencies` as a normalized many-to-many relationship table between schedule activities, rather than embedding JSON arrays in `schedule_activities`.
2. **Table Schema**:
   - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `project_id`: `UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE`
   - `predecessor_id`: `UUID NOT NULL`
   - `successor_id`: `UUID NOT NULL`
   - `relationship_type`: `TEXT NOT NULL DEFAULT 'FS' CHECK (relationship_type IN ('FS', 'SS', 'FF', 'SF'))`
   - `lag_days`: `INTEGER NOT NULL DEFAULT 0` (in calendar days; negative values represent lead time)
   - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())`
   - `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())`
3. **Relationship Types**:
   - `FS` (Finish-to-Start): Successor cannot start until predecessor finishes (Standard default).
   - `SS` (Start-to-Start): Successor cannot start until predecessor starts.
   - `FF` (Finish-to-Finish): Successor cannot finish until predecessor finishes.
   - `SF` (Start-to-Finish): Successor cannot finish until predecessor starts.
4. **Tenant Integrity & Constraints**:
   - `chk_no_self_dependency`: `CHECK (predecessor_id <> successor_id)` (prevents 1-hop self loops).
   - `uq_schedule_dependencies_edge`: `UNIQUE (project_id, predecessor_id, successor_id)` (exactly one relationship edge allowed between any directed pair $(u, v)$).
   - Composite Foreign Keys:
     - `FOREIGN KEY (predecessor_id, project_id) REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE`
     - `FOREIGN KEY (successor_id, project_id) REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE`
   - Cross-project edges are physically impossible at the database level.
5. **Cycle Detection & Acyclicity Enforcement**:
   - Relational database CHECK constraints cannot validate arbitrary graph acyclicity.
   - Acyclicity is validated at the application/service layer using Kahn's Algorithm / Tarjan's Topological Sort prior to committing dependency creations or updates.
   - Any dependency creation that would introduce a cycle is rejected with HTTP `400 BAD_REQUEST: Dependency cycle detected`.
6. **Row-Level Security (RLS)**:
   - `SELECT`: `viewer`, `supervisor`, `planner`, `admin` roles.
   - `INSERT` / `UPDATE`: `planner` and `admin` roles.
   - `DELETE`: `admin` role.

**Consequences**:
- Phase 9.1 will introduce migration `20260830000007_phase9_schedule_dependencies.sql`.
- Dependency management is exposed through authenticated, tenant-scoped endpoints with full cycle validation.

---

## ADR-015 — Phase 9 Critical Path Method (CPM) Mathematical & Float Contract

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — NOT PREVIOUSLY CANONICAL

**Context**: Calculating the Critical Path, Total Float, and Free Float requires deterministic mathematical formulas, calendar conventions, and duration derivations across all supported relationship types.

**Decision**:
1. **Calendar & Duration Semantics**:
   - Continuous calendar days (1 day = 1 calendar day). Working-day calendars and holiday exclusions are excluded from initial Phase 9 scope.
   - Activity Duration ($D_i$):
     $$D_i = (\text{planned\_finish\_date}_i - \text{planned\_start\_date}_i) + 1\text{ day}$$
     - If dates are missing (milestone), $D_i = 0$.
     - Durations are inclusive calendar-day intervals.
2. **Forward Pass (Early Dates)**:
   - For start nodes (in-degree 0): $ES_i = \text{Project Start Date}$, $EF_i = ES_i + D_i - 1$ (if $D_i > 0$ else $ES_i$).
   - For relationship from predecessor $i$ to successor $j$ with lag $L_{ij}$:
     - `FS`: $ES_j \ge EF_i + 1 + L_{ij}$
     - `SS`: $ES_j \ge ES_i + L_{ij}$
     - `FF`: $EF_j \ge EF_i + L_{ij} \implies ES_j \ge EF_i + L_{ij} - D_j + 1$
     - `SF`: $EF_j \ge ES_i + L_{ij} \implies ES_j \ge ES_i + L_{ij} - D_j + 1$
   - Node Early Start: $ES_j = \max_{(i, j) \in \text{Edges}} (\text{Constraint}(i, j))$.
   - Node Early Finish: $EF_j = ES_j + D_j - 1$ (if $D_j > 0$ else $ES_j$).
3. **Backward Pass (Late Dates)**:
   - Project Finish Anchor: $T_{\text{finish}} = \max_{k \in \text{Terminal}} (EF_k)$.
   - For terminal nodes (out-degree 0): $LF_k = T_{\text{finish}}$, $LS_k = LF_k - D_k + 1$ (if $D_k > 0$ else $LF_k$).
   - For relationship from successor $j$ to predecessor $i$ with lag $L_{ij}$:
     - `FS`: $LF_i \le LS_j - 1 - L_{ij}$
     - `SS`: $LS_i \le LS_j - L_{ij} \implies LF_i \le LS_j - L_{ij} + D_i - 1$
     - `FF`: $LF_i \le LF_j - L_{ij}$
     - `SF`: $LS_i \le LF_j - L_{ij} \implies LF_i \le LF_j - L_{ij} + D_i - 1$
   - Node Late Finish: $LF_i = \min_{(i, j) \in \text{Edges}} (\text{Constraint}(i, j))$.
   - Node Late Start: $LS_i = LF_i - D_i + 1$ (if $D_i > 0$ else $LF_i$).
4. **Float Calculations**:
   - **Total Float ($TF_i$)**:
     $$TF_i = LS_i - ES_i = LF_i - EF_i$$
   - **Free Float ($FF_i$)**:
     $$FF_i = \min_{j \in S(i)} (\text{Early Start Constraint}(i, j)) - EF_i$$
     - For terminal nodes, $FF_k = LF_k - EF_k = TF_k$.
5. **Criticality Definition**:
   - An activity is **Critical** $\iff TF_i \le 0$.
   - The **Critical Path** is the sequence of critical activities from project start to project finish.
6. **Worked Examples**:
   - **Example 1 (Linear FS Sequence)**:
     - Activity A (10 days, Day 1–10) $\xrightarrow{\text{FS}}$ Activity B (5 days, Day 11–15) $\xrightarrow{\text{FS}}$ Activity C (5 days, Day 16–20).
     - Forward Pass: $ES_A = 1, EF_A = 10 \rightarrow ES_B = 11, EF_B = 15 \rightarrow ES_C = 16, EF_C = 20$.
     - Backward Pass ($LF_C = 20$): $LS_C = 16 \rightarrow LF_B = 15, LS_B = 11 \rightarrow LF_A = 10, LS_A = 1$.
     - Floats: $TF_A = 0, TF_B = 0, TF_C = 0$. Critical Path: $A \rightarrow B \rightarrow C$.
   - **Example 2 (Branching Network with Mixed Relationship)**:
     - Activity A (10 days, Day 1–10).
     - Activity B (10 days, Day 11–20, $A \xrightarrow{\text{FS}} B$).
     - Activity C (4 days, Day 11–14, $A \xrightarrow{\text{SS, lag=2}} C$). Constraint: $ES_C \ge ES_A + 2 = 1 + 2 = 3$. If anchored to start Day 11, $ES_C = 11, EF_C = 14$.
     - Activity D (5 days, Day 21–25, $B \xrightarrow{\text{FS}} D$, $C \xrightarrow{\text{FF}} D$).
     - Forward Pass: $EF_B = 20 \rightarrow ES_D = \max(20 + 1, 14 + 1) = 21, EF_D = 25$.
     - Backward Pass ($LF_D = 25, LS_D = 21$):
       - $LF_B = 20, LS_B = 11 \rightarrow TF_B = 0$ (**Critical**).
       - $LF_C = 25 - 0 = 25, LS_C = 22 \rightarrow TF_C = 22 - 11 = \mathbf{11\text{ days Total Float}}$ (**Non-Critical**).
       - Free Float: $FF_C = 21 - 1 - 14 = \mathbf{6\text{ days Free Float}}$.

**Consequences**:
- The CPM engine is 100% deterministic, testable, and robust against multi-path merge/burst topologies.

---

## ADR-016 — Phase 9 Downstream Impact & Factual Delay Traversal Contract

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — NOT PREVIOUSLY CANONICAL

**Context**: Delays in upstream activities propagate downstream through the dependency network. A precise contract for traversal depth, cycle safety, and impact classification is required.

**Decision**:
1. **Transitive DAG Subgraph Traversal**:
   - Downstream impact evaluates the **entire transitive directed subgraph** of successors reachable from the source activity (not just 1-hop direct successors).
   - In multi-path DAG structures, each unique downstream activity is evaluated once with deduplicated traversal.
2. **Successor Impact Classification**:
   - When a source activity exhibits factual schedule slippage ($\Delta T > 0$):
     - **Buffer Absorbed**: Successor activity where Total Float $TF_j \ge \Delta T$ (downstream float buffer absorbs the slippage; project finish milestone unaffected).
     - **Critical Slippage Impact**: Successor activity where Total Float $TF_j < \Delta T$ (slippage exceeds float buffer; forces downstream activity start/finish dates into delay).
3. **Factual Delay vs Predictive Delay Boundary**:
   - **Factual Schedule Slippage**: Computed strictly from verified Phase 8 records:
     - Completed activity: $\Delta T = \text{latest\_actual\_date} - \text{planned\_finish\_date} > 0$.
     - Incomplete activity: $\text{Current Date} > \text{planned\_finish\_date}$.
   - **Predictive Delay Prohibition**: The system must surface factual float erosion and network vulnerability, not invent ungrounded future completion dates.
4. **Completed Activity Invariance**:
   - Successor activities already marked `COMPLETED` in Phase 8 are flagged as historical and excluded from active float erosion propagation.

**Consequences**:
- Downstream impact APIs return the complete, deduplicated impact tree with explicit absorbed vs critical classification.

---

## ADR-017 — Phase 9 Deterministic Risk Intelligence & Severity Taxonomy

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — NOT PREVIOUSLY CANONICAL

**Context**: Transforming schedule topology and verified variances into auditable, actionable risk visibility without black-box machine learning or arbitrary heuristic thresholds.

**Decision**:
1. **Canonical 6-Category Risk Taxonomy**:
   - `CRITICAL_PATH_DELAY`: Activity on critical path ($TF \le 0$) with factual progress lag or date slippage ($\Delta T > 0$).
   - `FLOAT_EROSION`: Near-critical activity ($0 < TF \le 3\text{ days}$) where delay or low progress threatens float buffer.
   - `DOWNSTREAM_BOTTLENECK`: Delayed activity with high successor fan-out ($\ge 3$ direct successors or $\ge 5$ transitive successors).
   - `PREDECESSOR_BLOCKER`: Activity unable to start or proceed because an upstream predecessor is incomplete past its planned finish.
   - `UNQUANTIFIED_MILESTONE_LAG`: Unquantified milestone past its planned due date.
   - `UNIT_MISMATCH_EXPOSURE`: Incompatible units preventing progress verification on a critical or near-critical activity.
2. **Discrete Severity Levels**:
   - **CRITICAL**: On Critical Path ($TF \le 0$) AND ($\Delta T > 0$ OR $\text{Current Date} > \text{Planned Finish}$).
   - **HIGH**: Near-Critical ($0 < TF \le 3\text{ days}$) AND $\Delta T > 0$; OR downstream bottleneck ($\ge 5$ transitive successors affected).
   - **MEDIUM**: Moderate Float ($3 < TF \le 7\text{ days}$) with progress lag ($P\% < 50\%$ past midpoint); OR non-critical predecessor blocked.
   - **LOW**: Safe Float ($TF > 7\text{ days}$) with minor or zero variance.
3. **Deterministic Composite Risk Score ($0 - 100$ Integer)**:
   $$\text{Risk Score} = \min\left(100, \text{round}\left(40 \cdot I_{\text{crit}} + 25 \cdot S_{\text{float}} + 20 \cdot S_{\text{fanout}} + 15 \cdot S_{\text{delay}}\right)\right)$$
   - $I_{\text{crit}} = 1.0$ if $TF \le 0$, else $0.0$.
   - $S_{\text{float}} = \max\left(0.0, 1.0 - \frac{TF}{10}\right)$ for $TF \ge 0$, and $1.0$ for $TF < 0$.
   - $S_{\text{fanout}} = \min\left(1.0, \frac{\text{transitive\_successors}}{5}\right)$.
   - $S_{\text{delay}} = \min\left(1.0, \frac{\max(0, \Delta T)}{5}\right)$.
4. **Worked Scoring Examples**:
   - **Example 1 (Critical Path Activity Delayed 3 Days, 4 Successors)**:
     - Inputs: $TF = 0$ ($I_{\text{crit}} = 1.0, S_{\text{float}} = 1.0$), $\Delta T = 3$ ($S_{\text{delay}} = 3/5 = 0.6$), $\text{Successors} = 4$ ($S_{\text{fanout}} = 4/5 = 0.8$).
     - Score: $\text{round}(40(1.0) + 25(1.0) + 20(0.8) + 15(0.6)) = \text{round}(40 + 25 + 16 + 9) = \mathbf{90}$ ($\mathbf{\text{CRITICAL}}$).
   - **Example 2 (Non-Critical Activity with 8 Days Float, 2 Days Delayed, 1 Successor)**:
     - Inputs: $TF = 8$ ($I_{\text{crit}} = 0.0, S_{\text{float}} = 1 - 8/10 = 0.2$), $\Delta T = 2$ ($S_{\text{delay}} = 2/5 = 0.4$), $\text{Successors} = 1$ ($S_{\text{fanout}} = 1/5 = 0.2$).
     - Score: $\text{round}(40(0) + 25(0.2) + 20(0.2) + 15(0.4)) = \text{round}(0 + 5 + 4 + 6) = \mathbf{15}$ ($\mathbf{\text{LOW}}$).

**Consequences**:
- Every risk score and severity assignment is 100% explainable, deterministic, and auditable.

---

## ADR-018 — Phase 9 Prediction, Heatmap & Presentation Boundary

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — NOT PREVIOUSLY CANONICAL

**Context**: Defining the visual and predictive boundaries for Phase 9 frontend dashboards and API responses.

**Decision**:
1. **Prediction Policy**:
   - Black-box probabilistic delay forecasting is **STRICTLY EXCLUDED**.
   - Phase 9 provides **Factual Schedule Float Exposure & Deterministic Downstream Impact Propagation**.
2. **2D Risk Heatmap Matrix**:
   - **X-Axis**: Float Severity (Critical: $TF \le 0$, Near-Critical: $1-5\text{ days}$, Safe: $> 5\text{ days}$).
   - **Y-Axis**: Work Breakdown Structure (WBS) Tier OR Trade Discipline.
   - **Cell Content**: Integer count of activities with interactive drill-down to filtered activity risk register.
3. **Presentation & UI Architecture**:
   - Route `/risks` (Navigation Label: **Risk & Critical Path**).
   - Executive KPI summary cards (Critical Path Activities, High Risk, Float Eroded).
   - Interactive Downstream Impact Drawer showing affected successor subgraphs.
   - Tabbed view: 1. Critical Path Network Schedule; 2. Activity Risk Register.

**Consequences**:
- Phase 9 provides a clean, professional project-controls risk dashboard without dashboard gimmicks or ungrounded AI predictions.

---

## ADR-019 — Phase 10 Export Formats & Serialization Contract

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — PHASE 10 CANON LOCK

**Context**: Phase 10 requires basic exportable reports for project progress, verified actuals, variance intelligence, and risk registers. Clear serialization standards, file formats, and safety boundaries are needed.

**Decision**:
1. **Supported Formats**:
   - **CSV**: Standard RFC 4180 format (`text/csv; charset=utf-8`) with header row and deterministic sorting.
   - **JSON**: Strongly-typed structured JSON (`application/json; charset=utf-8`) containing full metadata and items.
   - Heavyweight PDF and XLSX generation libraries are **EXCLUDED** from core scope (maintaining minimal dependencies and zero client/server bloat).
2. **Canonical Export Datasets**:
   - **Approved Actuals Dataset** (`actuals`):
     - Columns: `project_id`, `schedule_activity_id`, `activity_code`, `activity_name`, `actual_date`, `actual_quantity`, `actual_unit`, `approved_by`, `approved_at`, `is_modified`, `notes`.
   - **Plan vs Actual Variance Dataset** (`variance`):
     - Columns: `project_id`, `activity_id`, `activity_code`, `name`, `wbs_code`, `discipline`, `planned_quantity`, `planned_unit`, `actual_quantity`, `variance_status`, `quantity_variance`, `progress_percent`, `planned_finish_date`, `latest_actual_date`, `date_variance_days`.
   - **Schedule Risk Register Dataset** (`risks`):
     - Columns: `project_id`, `activity_id`, `activity_code`, `name`, `wbs_code`, `discipline`, `severity`, `risk_score`, `categories`, `is_critical_path`, `total_float`, `date_variance_days`, `direct_successors_count`, `transitive_successors_count`, `critical_slippage_successors_count`, `is_completed`.
3. **Formula Injection (CSV Injection) Mitigation**:
   - All text cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` MUST be escaped by prepending a single quote `'` during CSV serialization.
4. **Deterministic Ordering**:
   - Exports are sorted deterministically (e.g. by `activity_code ASC, actual_date DESC` or `severity_rank ASC, risk_score DESC`).
5. **Tenant Scoping & Delivery**:
   - All exports are generated synchronously over authenticated, project-scoped endpoints with `Content-Disposition: attachment; filename="..."` headers.

**Consequences**:
- Export endpoints provide clean, reliable, and secure data downloads without ungrounded dependencies.

---

## ADR-020 — Phase 10 Audit Event Taxonomy & Immutability Contract

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — PHASE 10 CANON LOCK

**Context**: Establishing a canonical audit event stream and defining the immutability boundary for all human decisions and lifecycle transitions.

**Decision**:
1. **Canonical Audit Event Taxonomy**:
   - `FIELD_INPUT_SUBMITTED`: Raw field note/voice/photo submission (`public.field_inputs`).
   - `AI_EXTRACTION_COMPLETED`: AI structured entity extraction (`public.ai_extractions`).
   - `AI_MATCH_GENERATED`: Schedule match recommendation generated (`public.ai_matches`).
   - `PLANNER_DECISION_RECORDED`: Human planner approval, rejection, or modification (`public.planner_decisions`).
   - `APPROVED_ACTUAL_COMMITTED`: Official approved actual progress record created (`public.approved_actuals`).
   - `DEPENDENCY_EDGE_MUTATED`: Schedule dependency relationship created or deleted (`public.schedule_dependencies`).
2. **Audit Event Schema**:
   - `event_id`: Unique identifier (`UUID`).
   - `project_id`: Project tenant identifier (`UUID`).
   - `event_type`: Canonical event type enum.
   - `entity_type`: Target entity name (`field_input`, `ai_extraction`, `ai_match`, `planner_decision`, `approved_actual`, `dependency`).
   - `entity_id`: Primary key of target entity (`UUID`).
   - `actor_id`: User ID of initiator (or `SYSTEM_AI` for autonomous pipeline stages).
   - `actor_name` / `actor_email`: Identity metadata of actor.
   - `action`: Specific action executed (`SUBMIT`, `EXTRACT`, `RECOMMEND`, `APPROVE`, `REJECT`, `MODIFY`, `CREATE_EDGE`, `DELETE_EDGE`).
   - `timestamp`: Event creation time in UTC.
   - `summary`: Human-readable description of event.
   - `metadata`: JSON payload snapshot containing before/after state or decision overrides.
3. **Immutability Contract**:
   - Audit events are strictly append-only.
   - Modification (UPDATE) and Deletion (DELETE) are **FORBIDDEN** across all roles (including `admin`).
   - RLS policies and backend endpoints enforce read-only retrieval for authenticated project members.

**Consequences**:
- Every action affecting schedule state or progress approval is completely transparent and tamper-resistant.

---

## ADR-021 — Phase 10 Audit Route & Provenance Presentation Contract

**Date**: 2026-08-31
**Status**: Decided
**Scope**: NEW DECISION — PHASE 10 CANON LOCK

**Context**: Defining the user interface routes, navigation placement, and end-to-end visual provenance chain for Phase 10.

**Decision**:
1. **Dedicated Route & Navigation**:
   - Route: `/audit` (Navigation Label: **Audit Trail**).
   - AppLayout navigation updated to include the dedicated `/audit` link.
   - Existing `/reports` route is preserved for uploaded field document management (`public.reports`).
2. **Audit Log Viewer Component Architecture**:
   - Chronological event timeline/table sorted `timestamp DESC, event_id DESC`.
   - Multi-factor filter controls: Event Type, Actor, Entity Type, Date Range.
   - Interactive event detail drawer displaying raw payload snapshots and modification diffs.
3. **Full Provenance Visualizer**:
   - Clickable "Trace Lineage" action on audit events, approved actuals, and variance items.
   - Visual step-by-step lineage modal/drawer:
     $$\text{Field Input} \rightarrow \text{AI Extraction} \rightarrow \text{Match Recommendation} \rightarrow \text{Planner Decision} \rightarrow \text{Approved Actual} \rightarrow \text{Variance / Risk}$$
   - Displays verbatim ground truth evidence tokens, confidence scores, and planner modification diffs.
4. **Export UI Integration**:
   - Direct CSV and JSON export action buttons placed on `/audit`, `/actuals`, `/variance`, and `/risks` pages.

**Consequences**:
- Provides an intuitive, enterprise-grade audit trail and provenance viewer adhering to all UI/UX principles.
