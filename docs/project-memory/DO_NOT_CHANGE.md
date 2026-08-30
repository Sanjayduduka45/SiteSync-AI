# DO NOT CHANGE — SiteSync AI

> This document lists items that are **locked**. They may not be changed without:
> 1. Stopping work.
> 2. Reporting: what must change, why, what is affected, and the minimal recommended change.
> 3. Explicit human approval.
> 4. Update to this document and `DECISIONS.md`.
>
> **If you are an AI agent and you need to change something on this list: STOP. Report. Do not proceed.**

---

## Locked Architecture

| Item | Locked Value | Reference |
|---|---|---|
| Frontend framework | React + Vite | ADR-008 |
| Frontend language | TypeScript (strict mode) | ADR-008 |
| Frontend styling | Tailwind CSS | ADR-008 |
| Frontend components | shadcn/ui | ADR-008 |
| Frontend routing | React Router | ADR-008 |
| Frontend server state | TanStack Query | ADR-008 |
| Backend framework | FastAPI | ADR-002 |
| Backend language | Python 3.11+ | ADR-002 |
| Backend validation | Pydantic v2 | ADR-002 |
| Database | Supabase PostgreSQL | ADR-003 |
| Vector store | pgvector (in Supabase) | ADR-003 |
| Authentication | Supabase Auth | ADR-003 |
| File storage | Supabase Storage | ADR-003 |
| AI orchestration | LangChain | ADR-004 |
| Primary LLM | Gemini | ADR-004 |
| Voice / STT | Whisper / suitable STT | ADR-004 |
| Core product principle | AI recommends. Humans decide. | ADR-005 |
| UI theme | Light theme only | ADR-006 |

---

## Locked Workflow

The following workflow steps are locked. The order and the human decision gate are non-negotiable.

```
Field Input → AI Extraction → Normalization → Schedule Matching
→ Confidence + Evidence → Planner Review → Planner Decision (REQUIRED)
→ Approved Actual → Plan vs Actual → Variance → Risk / Impact → Audit
```

**The Planner Decision step cannot be removed, bypassed, or made automatic without explicit change control.**

---

## Locked Security Rules

The following cannot be changed without change control:

- Secrets via environment variables only. Never committed.
- Server-side authorization on every endpoint.
- Supabase RLS on all tables.
- AI cannot write directly to approved actual records.
- AI cannot bypass authorization.
- Audit log is append-only.

See `SECURITY_RULES.md` for full details.

---

## Locked API Contract Principles

Once a phase is accepted:
- API endpoint paths are locked.
- Request/response schemas are locked.
- Database table names and columns are locked.

Changes to locked API contracts require change control.

---

## Completed Phase Protection

| Phase | Status | Protected |
|---|---|---|
| Phase 0 — Foundation | ✅ Complete | Yes |
| Phase 1 — Scaffold | ⏳ Not started | Not yet |
| Phase 2+ | ⏳ Not started | Not yet |

Once a phase is marked Complete, its behavior and outputs are added to this protection list.

---

## Change Control Procedure

If a change to a locked item is needed:

1. **STOP** — do not make the change.
2. **Report**:
   - What must change.
   - Why it must change.
   - What is affected by the change.
   - The minimal recommended change.
3. **Wait** for explicit human approval.
4. If approved:
   - Make only the approved change.
   - Update this document.
   - Create a new ADR in `DECISIONS.md`.
   - Update `CHANGELOG.md`.
