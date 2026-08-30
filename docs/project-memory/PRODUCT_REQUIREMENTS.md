# PRODUCT REQUIREMENTS — SiteSync AI

## Product Name

SiteSync AI — Field to Schedule Intelligence

---

## Problem Statement

Construction projects suffer from a systematic information gap between what happens in the field and what is recorded in the schedule. Field updates are unstructured (verbal, handwritten, ad-hoc), delayed, and inconsistently captured. Planners spend significant time manually extracting, interpreting, and entering field data into scheduling systems. This delay and inconsistency leads to inaccurate schedule status, poor variance detection, and reactive rather than proactive risk management.

---

## Product Vision

A professional construction intelligence platform that uses AI to bridge the field-to-schedule gap. SiteSync AI processes unstructured field inputs, extracts structured progress data using AI, matches it to schedule activities, and presents clear recommendations to planners — who make all final decisions.

**AI recommends. Humans decide.**

---

## Target Users

| Role | Description |
|---|---|
| Field Supervisor / Foreman | Submits progress updates from the field |
| Project Planner / Scheduler | Reviews AI recommendations, approves or rejects actuals |
| Project Manager | Reviews plan vs actual, variance, and risk reports |
| Site Administrator | Manages projects, users, and system configuration |

---

## Core Functional Requirements

### 1. Field Input
- Accept text input from field users.
- Accept voice input (transcribed via STT).
- Accept photo/document uploads.
- All input associated with a project and date.

### 2. AI Extraction
- Parse unstructured input to extract:
  - Activity references (explicit or implied)
  - Progress percentage or quantity
  - Work description
  - Constraints or blockers
  - Personnel and equipment references
- AI returns structured extraction with confidence score.

### 3. Normalization
- Standardize extracted data:
  - Units of measure
  - Construction terminology
  - Activity code formats
  - Date/time references

### 4. Schedule Matching
- Match extracted activity references to schedule activities.
- Use semantic similarity (embeddings + pgvector) and contextual scoring.
- Return top candidate matches with confidence scores and supporting evidence.

### 5. Confidence + Evidence
- Every AI recommendation must include:
  - Confidence score (0–1)
  - Evidence tokens (which field text drove the match)
  - Matched schedule activity
  - Alternative candidates if applicable

### 6. Planner Review
- Planners see AI extraction + match recommendation.
- Planners can:
  - View evidence for any recommendation.
  - Approve (accept AI recommendation as-is).
  - Modify (correct extraction or match before approving).
  - Reject (discard AI recommendation with reason).

### 7. Planner Decision
- Planner decision is final and creates the approved actual record.
- Rejected items are logged with reason.
- Modified items log both AI version and final human version.

### 8. Approved Actual
- Immutable record of approved progress.
- Tied to schedule activity, project, date, and approving planner.

### 9. Plan vs Actual
- Compare approved actuals to baseline schedule.
- Display at activity, WBS, and project level.

### 10. Variance
- Calculate schedule variance and progress variance.
- Flag activities with significant variance.

### 11. Risk / Impact
- Assess downstream impact of variance on dependent activities.
- Surface critical path risks.

### 12. Audit
- Immutable audit log of all field inputs, AI extractions, and planner decisions.
- Log every approval, rejection, and modification with timestamp and user.

---

## Non-Functional Requirements

- **Performance**: Planner review screen must load within 2 seconds for normal data volumes.
- **Reliability**: AI extraction failures must be gracefully handled and surfaced to the planner, never silently dropped.
- **Security**: See `SECURITY_RULES.md`.
- **Accessibility**: WCAG AA target for all planner-facing screens.
- **Responsiveness**: Must function on desktop and tablet.

---

## Out of Scope (for all phases)

- Direct integration with third-party scheduling software (e.g., Primavera P6, MS Project) — future consideration.
- Real-time collaboration features.
- Mobile native app.
- Financial cost tracking.
- Procurement management.

---

## Success Criteria

- Planner can receive a field update and produce an approved actual in under 3 minutes.
- AI extraction confidence is surfaced clearly on every recommendation.
- Every planner decision is auditable.
- No AI recommendation is written to approved actuals without planner sign-off.
