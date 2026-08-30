# AI SPECIFICATION — SiteSync AI

## Overview

The AI layer of SiteSync AI performs three primary functions:

1. **Extraction** — Parse unstructured field input into structured data.
2. **Matching** — Match extracted activity references to schedule activities.
3. **Scoring** — Assign confidence scores with supporting evidence.

AI outputs are **recommendations only**. All AI outputs require planner review and decision before affecting official records.

---

## AI Stack (Locked)

| Component | Technology |
|---|---|
| Orchestration | LangChain |
| Primary LLM | Gemini (Google) |
| Embeddings | Gemini Embeddings (or compatible) |
| Voice / STT | Whisper or suitable STT service |
| Vector Store | pgvector (Supabase PostgreSQL) |
| Matching | pgvector cosine similarity + contextual scoring |

> Do not replace these components without change control approval. See `DO_NOT_CHANGE.md`.

---

## Pipeline Architecture

```
Field Input (text / transcript / description)
         │
         ▼
  ┌──────────────────────────────────┐
  │       Input Preprocessor        │
  │  - Clean and sanitize input     │
  │  - Language detection           │
  │  - Voice transcript (Whisper)   │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │       AI Extraction (Gemini)    │
  │  - Structured output / JSON     │
  │  - Activity references          │
  │  - Progress / quantities        │
  │  - Constraints / blockers       │
  │  - Personnel / equipment refs   │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │         Normalization           │
  │  - Units standardization        │
  │  - Terminology mapping          │
  │  - Activity code formatting     │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │     Schedule Matching           │
  │  - Embed extraction             │
  │  - pgvector similarity search   │
  │  - Contextual re-ranking        │
  │  - Confidence scoring           │
  │  - Evidence token extraction    │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │       Recommendation Output     │
  │  - Validated Pydantic schema    │
  │  - Confidence score (0–1)       │
  │  - Top match + alternatives     │
  │  - Evidence tokens              │
  └──────────────────────────────────┘
                 │
                 ▼
         Planner Review API
         (human decision required)
```

---

## AI Output Schema (Planned)

All AI outputs are validated against Pydantic schemas before leaving the AI layer.

```python
class ExtractionResult(BaseModel):
    raw_input_id: str
    extracted_activities: list[ExtractedActivity]
    extraction_confidence: float  # 0.0 - 1.0
    model_version: str
    processing_timestamp: datetime

class ExtractedActivity(BaseModel):
    description: str
    progress_value: float | None
    progress_unit: str | None
    constraints: list[str]
    evidence_tokens: list[str]  # source text fragments

class MatchRecommendation(BaseModel):
    extraction_id: str
    recommended_activity_id: str
    confidence_score: float  # 0.0 - 1.0
    evidence_tokens: list[str]
    alternative_matches: list[AlternativeMatch]

class AlternativeMatch(BaseModel):
    activity_id: str
    confidence_score: float
```

---

## AI Security Rules

- AI pipeline runs entirely within the backend. No AI API calls from the frontend.
- AI pipeline does not have write access to approved actual records.
- AI pipeline does not have access to authentication tokens or user credentials.
- All LLM prompts are constructed server-side. User input is sanitized before inclusion.
- AI outputs are validated before any downstream processing.
- AI failures are surfaced to planners as review items — never silently auto-resolved.

---

## Confidence Score Policy

| Score Range | Display Label | Planner Action Required |
|---|---|---|
| 0.85 – 1.00 | High Confidence | Review recommended; one-click approve available |
| 0.60 – 0.84 | Medium Confidence | Planner review strongly encouraged |
| 0.00 – 0.59 | Low Confidence | Planner review required; highlight alternatives |

> These thresholds are configurable but must be validated per phase.

---

## Voice Transcription

- Voice inputs are transcribed using **Whisper** (or a compatible STT service).
- Transcription is treated as raw text input to the extraction pipeline.
- Transcription output is shown to the planner alongside the AI extraction so they can verify accuracy.
- If transcription confidence is low, this is surfaced to the planner.

---

## Embeddings and Vector Search

- Schedule activities are embedded at import time.
- Embeddings are stored in **pgvector** in Supabase PostgreSQL.
- Field input extractions are embedded at extraction time.
- Schedule matching uses cosine similarity search in pgvector.
- Contextual re-ranking refines raw similarity scores using project context.

---

## LangChain Usage

- LangChain orchestrates the multi-step extraction and matching pipeline.
- Chains are defined in the backend `app/ai/` module.
- All chains must be testable in isolation.
- Prompt templates are versioned and stored in code — not generated dynamically without review.

---

## AI Limitations (Documented)

- AI extraction is not 100% accurate. The planner review step exists precisely to catch errors.
- Confidence scores are model-relative, not absolute guarantees.
- Schedule matching quality depends on the quality of embedded schedule data.
- AI performance on construction-specific terminology requires prompt tuning during development.
