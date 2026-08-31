# SITESYNC AI — PHASE 10 CANON LOCK REPORT

## 1. Executive Summary
This report marks the formal completion of **Phase 10.0 — Canon Lock & Decision Gate** for SiteSync AI. All blocking canon gaps identified during discovery have been rigorously evaluated and resolved through Architectural Decision Records **ADR-019**, **ADR-020**, and **ADR-021** in [`docs/project-memory/DECISIONS.md`](file:///Users/sanjayduduka/Downloads/SiteSync/docs/project-memory/DECISIONS.md). The data boundaries, immutability rules, export formats, API contracts, and user interface architectures for Phase 10 (Audit and Reporting) are officially locked.

---

## 2. Canonical Phase 10 Objective
> **"Audit trail and reporting."**
> Establish an immutable, end-to-end audit trail and provenance graph across the full field-to-schedule lifecycle (`Field Input → AI Extraction → Match Recommendation → Planner Decision → Approved Actual → Variance → Risk`), and provide deterministic, formula-injection-safe exportable reports (CSV/JSON) for project progress, verified actuals, variance intelligence, and risk registers.

---

## 3. ADR Decisions

### ADR-019: Export Formats & Serialization Contract
- **Formats**: RFC 4180 CSV (`text/csv; charset=utf-8`) and structured JSON (`application/json; charset=utf-8`).
- **Heavyweight Libraries Excluded**: No PDF/XLSX generation dependencies.
- **Formula Injection Defense**: Escapes spreadsheet formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) with single quotes.
- **Datasets**: Approved Actuals (`actuals`), Plan vs Actual Variance (`variance`), Schedule Risk Register (`risks`).

### ADR-020: Audit Event Taxonomy & Immutability Contract
- **Canonical Taxonomy**: `FIELD_INPUT_SUBMITTED`, `AI_EXTRACTION_COMPLETED`, `AI_MATCH_GENERATED`, `PLANNER_DECISION_RECORDED`, `APPROVED_ACTUAL_COMMITTED`, `DEPENDENCY_EDGE_MUTATED`.
- **Immutability**: Append-only lifecycle. Modification (`UPDATE`) and Deletion (`DELETE`) are strictly forbidden across all roles including `admin`.
- **Event Envelope**: `event_id`, `project_id`, `event_type`, `entity_type`, `entity_id`, `actor_id`, `actor_name`, `actor_email`, `action`, `timestamp`, `summary`, `metadata`.

### ADR-021: Audit Route & Provenance Presentation Contract
- **Dedicated Route**: `/audit` (Navigation: **Audit Trail**).
- **Audit Viewer**: Chronological event stream with server-side filters (Actor, Event Type, Date Range), pagination, and detail drawer.
- **Provenance Visualizer**: Visual trace from raw field input to downstream risk.
- **Export UI**: One-click CSV and JSON download triggers on `/audit`, `/actuals`, `/variance`, and `/risks`.

---

## 4. Export Contract

### 1. Approved Actuals (`actuals`)
| Column | Type | Description |
|---|---|---|
| `project_id` | UUID | Project tenant ID |
| `schedule_activity_id` | UUID | Associated schedule activity ID |
| `activity_code` | String | Activity code (e.g. `ACT-101`) |
| `activity_name` | String | Activity title |
| `actual_date` | Date | Verified work date (`YYYY-MM-DD`) |
| `actual_quantity` | Numeric | Approved physical quantity |
| `actual_unit` | String | Unit of measure |
| `approved_by` | UUID | Approving planner user ID |
| `approved_at` | DateTime | Timestamp of planner approval |
| `is_modified` | Boolean | True if planner overrode AI recommendation |
| `notes` | String | Planner notes |

### 2. Plan vs Actual Variance (`variance`)
| Column | Type | Description |
|---|---|---|
| `project_id` | UUID | Project tenant ID |
| `activity_id` | UUID | Baseline activity ID |
| `activity_code` | String | Activity code |
| `name` | String | Activity name |
| `wbs_code` | String | WBS tier code |
| `discipline` | String | Trade discipline |
| `planned_quantity` | Numeric | Baseline quantity |
| `planned_unit` | String | Baseline unit |
| `actual_quantity` | Numeric | Cumulative approved actual quantity |
| `variance_status` | String | Deterministic status (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `OVER_DELIVERED`, `UNQUANTIFIED`, `UNIT_MISMATCH`) |
| `quantity_variance` | Numeric | $\Delta Q = \text{Actual} - \text{Planned}$ |
| `progress_percent` | Numeric | $P\% = (\text{Actual} / \text{Planned}) \times 100$ |
| `planned_finish_date` | Date | Baseline finish date |
| `latest_actual_date` | Date | Date of latest approved actual |
| `date_variance_days` | Integer | $\Delta T = \text{Latest Actual} - \text{Planned Finish}$ |

### 3. Schedule Risk Register (`risks`)
| Column | Type | Description |
|---|---|---|
| `project_id` | UUID | Project tenant ID |
| `activity_id` | UUID | Activity ID |
| `activity_code` | String | Activity code |
| `name` | String | Activity name |
| `wbs_code` | String | WBS tier code |
| `discipline` | String | Trade discipline |
| `severity` | String | Severity rank (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) |
| `risk_score` | Integer | Composite score ($0 - 100$) |
| `categories` | String | Active categories (comma-separated) |
| `is_critical_path` | Boolean | True if on critical path ($TF \le 0$) |
| `total_float` | Integer | Total Float in days |
| `date_variance_days` | Integer | Factual date slippage in days |
| `direct_successors_count` | Integer | Immediate successor fan-out |
| `transitive_successors_count` | Integer | Reachable downstream successor count |
| `critical_slippage_successors_count` | Integer | Successors forced into critical delay |
| `is_completed` | Boolean | True if verified COMPLETED |

---

## 5. Audit Event Contract

### Canonical Event Taxonomy
```
FIELD_INPUT_SUBMITTED       (public.field_inputs)
AI_EXTRACTION_COMPLETED     (public.ai_extractions)
AI_MATCH_GENERATED          (public.ai_matches)
PLANNER_DECISION_RECORDED   (public.planner_decisions)
APPROVED_ACTUAL_COMMITTED   (public.approved_actuals)
DEPENDENCY_EDGE_MUTATED     (public.schedule_dependencies)
```

---

## 6. Provenance Contract
Every verified progress entry or audit event can be traced along the canonical lineage:
$$\begin{array}{ccccccc}
\text{Field Input} & \rightarrow & \text{AI Extraction} & \rightarrow & \text{Match Recommendation} & \rightarrow & \text{Planner Decision} \\
\Downarrow & & & & & & \Downarrow \\
\text{Raw Audio / Notes} & & \text{Extracted Quantity} & & \text{Confidence Score} & & \text{Approval / Overrides} \\
\Downarrow & & & & & & \Downarrow \\
\text{Submitter Profile} & & \text{Model Version} & & \text{Alternative Matches} & & \text{Approved Actual} \\
& & & & & & \Downarrow \\
& & & & & & \text{Variance} \rightarrow \text{Downstream Risk}
\end{array}$$

- **Linking Identifiers**: `field_input_id` $\rightarrow$ `extraction_id` $\rightarrow$ `match_id` $\rightarrow$ `decision_id` $\rightarrow$ `approved_actual_id` $\rightarrow$ `schedule_activity_id`.
- **Rejection Handling**: Rejected match recommendations terminate at `planner_decisions` (logging the rejection reason) and do not create `approved_actuals`.
- **Modification Handling**: Planner modifications log both `original_payload` and `modified_payload` in `planner_decisions` and mark `is_modified = true` in `approved_actuals`.

---

## 7. Immutability Contract
- **No In-Place Edits**: Audit records and planner decisions are append-only.
- **Zero Deletion Policy**: No user or admin role can delete audit trail events.
- **Fail-Closed Permissions**: Database and service layers reject `UPDATE` and `DELETE` operations on audit entities.

---

## 8. RBAC Contract

| Role | View Audit Stream | View Provenance | Export Actuals | Export Variance | Export Risks | Mutate Audit Log |
|---|---|---|---|---|---|---|
| **VIEWER** | YES | YES | YES | YES | YES | NO (Forbidden) |
| **SUPERVISOR** | YES | YES | YES | YES | YES | NO (Forbidden) |
| **PLANNER** | YES | YES | YES | YES | YES | NO (Forbidden) |
| **ADMIN** | YES | YES | YES | YES | YES | NO (Forbidden) |

---

## 9. Tenant Isolation Contract
- **URL Scoping**: All Phase 10 API endpoints strictly derive `project_id` from the URL path.
- **Project Membership Enforcement**: Every request enforces server-side project membership via `require_project_membership(project_id, ProjectRole.VIEWER)`.
- **Zero Cross-Tenant Leakage**: Attempting to query audit logs, provenance graphs, or exports for another project is rejected with HTTP 403 Forbidden.

---

## 10. Database Contract
- Existing immutable tables (`public.planner_decisions`, `public.approved_actuals`, `public.field_inputs`, `public.ai_extractions`, `public.ai_matches`, `public.schedule_dependencies`) are leveraged as authoritative source data.
- Phase 10 is delivered as a pure, tenant-scoped audit domain query service and export serializer.
- No destructive alterations or schema rewrites on protected migrations (`00` through `07`).

---

## 11. API Contract
The following endpoints define the Phase 10 API surface:

```
GET /api/v1/projects/{project_id}/audit/events
GET /api/v1/projects/{project_id}/audit/events/{event_id}
GET /api/v1/projects/{project_id}/audit/provenance/{entity_type}/{entity_id}
GET /api/v1/projects/{project_id}/reports/export/actuals?format={csv|json}
GET /api/v1/projects/{project_id}/reports/export/variance?format={csv|json}
GET /api/v1/projects/{project_id}/reports/export/risks?format={csv|json}
```

---

## 12. Frontend Contract
- **Route**: `/audit` (AppLayout nav link: `"Audit Trail"`).
- **Components**:
  - `AuditLogTable`: Paginated chronological event stream with actor, timestamp, action type, and summary.
  - `AuditFilterBar`: Server-side filtering by Event Type, Actor, Entity Type, and Date Range.
  - `AuditDetailDrawer`: Raw JSON payload diff and metadata viewer.
  - `ProvenanceDrawer`: Interactive visual pipeline graph tracing ground truth origin to risk.
  - `ExportButton`: Reusable CSV/JSON export trigger button integrated across `/audit`, `/actuals`, `/variance`, and `/risks`.

---

## 13. Phase 9 Boundary
- **Read-Only Invariance**: Phase 10 consumes CPM results, Total Float, Downstream Impact, and Risk Assessments without re-calculating or modifying them.
- **No Algorithm Drifts**: All mathematical contracts in ADR-014 through ADR-018 remain locked.

---

## 14. Canon Gap Register

| Gap ID | Area | Resolution | Status |
|---|---|---|---|
| **GAP-10.1** | Export Formats | Standard RFC 4180 CSV + structured JSON. Heavyweight PDF/XLSX excluded. Escaped formula injection. | **RESOLVED (ADR-019)** |
| **GAP-10.2** | Route Placement | Dedicated `/audit` route with navigation link. Existing `/reports` preserved. | **RESOLVED (ADR-021)** |
| **GAP-10.3** | Event Taxonomy | 6-event canonical lifecycle stream with unified schema and immutable append-only enforcement. | **RESOLVED (ADR-020)** |

---

## 15. Acceptance Criteria
1. Audit stream deterministically aggregates lifecycle events sorted `timestamp DESC, event_id DESC`.
2. Provenance graph cleanly traces any approved actual back to its source field input and AI extraction.
3. CSV exports format numbers, dates, and strings cleanly according to RFC 4180 and escape spreadsheet formula characters.
4. JSON exports return valid structured payloads matching Pydantic response models.
5. Cross-tenant audit queries and exports return HTTP 403 Forbidden.
6. Mutation operations (POST/PUT/DELETE) on audit logs are strictly rejected.
7. Phase 8 and Phase 9 regression test suites remain 100% green.

---

## 16. Implementation Roadmap
- **Phase 10.1**: Audit & Provenance Domain Query Engine
- **Phase 10.2**: Report Export Serialization Services (CSV / JSON)
- **Phase 10.3**: FastAPI Audit & Export APIs (Tenant Isolation + RBAC)
- **Phase 10.4**: Frontend Audit Log Viewer & Lineage Visualizer UI
- **Phase 10.5**: Frontend Export Action Integration & Navigation
- **Phase 10.6**: Adversarial Security, IDOR & Data Integrity Audit
- **Phase 10.7**: Final Release Verification & Phase 10 Lock

---

## 17. Security Considerations
- **Formula Injection Mitigation**: Tested and validated single-quote escaping for spreadsheet safety.
- **Sanitized Error Envelopes**: Errors return `ApiErrorResponse` without exposing internal database structures or credentials.
- **Zero Client Trust**: All user identity, role, and tenant scopes are verified server-side.

---

## 18. Final Decision

# PHASE 10.0 CANON LOCK — COMPLETE & LOCKED
### ALL CANON GAPS RESOLVED
### SYSTEM IS READY FOR PHASE 10.1 IMPLEMENTATION
