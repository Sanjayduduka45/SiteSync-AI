# DATABASE SCHEMA — SiteSync AI

> Database platform: **Supabase PostgreSQL** with **pgvector**
> Current active phase: **Phase 9 — Risk & Critical Path Intelligence**

---

## Overview

SiteSync AI enforces multi-tenant project isolation using explicit PostgreSQL Row-Level Security (RLS) policies.
- Phase 2 established identity, projects, and membership.
- Phase 3 established reports and field events.
- Phase 4 established raw unstructured field input ingestion (`public.field_inputs`) and private storage security (`field-inputs` bucket).
- Phase 5 established structured AI extractions persistence (`public.ai_extractions`) with project-scoped RLS and idempotency.
- Phase 6 established schedule activity storage (`public.schedule_activities`), dense vector embeddings (`public.activity_embeddings` with `vector(768)`), and AI match recommendation persistence (`public.ai_matches`).
- Phase 7 established human planner decision logging (`public.planner_decisions`) and official verified progress persistence (`public.approved_actuals`) with composite tenant integrity and RLS.
- Phase 8 established the deterministic Plan vs Actual variance calculation engine and rollups (pure domain logic over existing tables).
- Phase 9 establishes the activity dependency graph foundation (`public.schedule_dependencies`) with composite tenant foreign keys, self-dependency checks, and RLS.

---

## Enums

### `project_role`
Defines project-level authorization roles.

```sql
CREATE TYPE project_role AS ENUM ('admin', 'planner', 'supervisor', 'viewer');
```

Role Hierarchy:
1. `admin` (40): Full project administrative privileges (members, reports deletion, event management, input/extraction deletion, schedule deletion).
2. `planner` (30): Report viewing & upload, field event creation & editing, field input updates, schedule activity creation & editing, matching trigger.
3. `supervisor` (20): Report viewing & upload, field event creation, field input creation, extraction trigger.
4. `viewer` (10): Read-only access to authorized project data.

### `report_status`
Tracks file processing status for uploaded field documents.

```sql
CREATE TYPE report_status AS ENUM ('uploaded', 'processing', 'processed', 'failed');
```

### `field_event_status`
Tracks structured field progress event lifecycle.

```sql
CREATE TYPE field_event_status AS ENUM ('pending', 'processed', 'matched', 'needs_review', 'approved', 'rejected');
```

### `field_input_type` (Phase 4)
Defines the input modality for raw field submissions.

```sql
CREATE TYPE field_input_type AS ENUM ('text', 'voice', 'photo', 'document');
```

### `transcription_status` (Phase 4)
Tracks Speech-to-Text (STT) processing status for voice submissions.

```sql
CREATE TYPE transcription_status AS ENUM ('none', 'pending', 'completed', 'failed');
```

### `extraction_status` (Phase 5)
Tracks AI extraction processing state.

```sql
CREATE TYPE extraction_status AS ENUM ('pending', 'completed', 'failed');
```

### `planner_decision_type` (Phase 7)
Defines human planner review decision outcomes on AI match recommendations.

```sql
CREATE TYPE planner_decision_type AS ENUM ('approved', 'rejected', 'modified');
```

---

## Tables

### 1. `public.profiles`
User profile information linked directly to `auth.users`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE` | Supabase Auth User ID |
| `email` | `TEXT` | `NOT NULL` | User email address |
| `full_name` | `TEXT` | `NULL` | User display name |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last update timestamp |

---

### 2. `public.projects`
Project registry and metadata.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique project identifier |
| `name` | `TEXT` | `NOT NULL` | Human-readable project name |
| `code` | `TEXT` | `UNIQUE NOT NULL` | Unique project code / identifier |
| `description` | `TEXT` | `NULL` | Project description |
| `created_by` | `UUID` | `REFERENCES public.profiles(id) ON DELETE SET NULL` | Creator profile ID |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last update timestamp |

---

### 3. `public.project_members`
Many-to-many relationship defining user membership and role within each project.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique membership ID |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `user_id` | `UUID` | `NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE` | Associated profile ID |
| `role` | `project_role` | `NOT NULL DEFAULT 'viewer'` | Member role within project |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Joined timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last updated timestamp |

---

### 4. `public.reports` (Phase 3)
Field reports, site diaries, and progress documents submitted to a project.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique report identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `name` | `TEXT` | `NOT NULL` | User-assigned report title |
| `file_name` | `TEXT` | `NOT NULL` | Original filename |
| `file_type` | `TEXT` | `NOT NULL` | MIME / file extension (pdf, xlsx, csv, txt) |
| `file_size` | `INTEGER` | `NOT NULL DEFAULT 0` | Size in bytes |
| `source` | `TEXT` | `NOT NULL DEFAULT 'manual_upload'` | Ingestion source |
| `status` | `report_status` | `NOT NULL DEFAULT 'uploaded'` | Processing state |
| `uploaded_by` | `UUID` | `REFERENCES public.profiles(id) ON DELETE SET NULL` | Submitter profile ID |
| `uploaded_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Upload timestamp |
| `processed_at` | `TIMESTAMPTZ` | `NULL` | Processing completion timestamp |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record modification timestamp |

**Indices:**
- `idx_reports_project_id` ON `project_id`
- `idx_reports_uploaded_by` ON `uploaded_by`
- `idx_reports_status` ON `status`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view all project reports.
- **INSERT**: `supervisor`, `planner`, and `admin` roles can upload reports.
- **UPDATE**: `planner` and `admin` roles can update reports.
- **DELETE**: `admin` role only.

---

### 5. `public.field_events` (Phase 3)
Structured construction progress events extracted from reports or recorded from site.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique field event identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `report_id` | `UUID` | `REFERENCES public.reports(id) ON DELETE SET NULL` | Source report reference |
| `event_type` | `TEXT` | `NOT NULL` | Category (e.g. Spool Erection, Concrete Pour) |
| `description` | `TEXT` | `NOT NULL` | Description of physical work performed |
| `discipline` | `TEXT` | `NOT NULL` | Construction trade (Piping, Civil, Electrical, etc.) |
| `location` | `TEXT` | `NOT NULL` | Area / Grid / Unit location |
| `event_date` | `DATE` | `NOT NULL` | Date when event occurred on site |
| `progress_percent` | `NUMERIC(5,2)`| `NOT NULL DEFAULT 0.00 CHECK (0 <= progress_percent <= 100)` | Work percentage |
| `status` | `field_event_status` | `NOT NULL DEFAULT 'pending'` | Extraction / decision lifecycle status |
| `extracted_by` | `UUID` | `REFERENCES public.profiles(id) ON DELETE SET NULL` | Author / extractor ID |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record modification timestamp |

**Indices:**
- `idx_field_events_project_id` ON `project_id`
- `idx_field_events_report_id` ON `report_id`
- `idx_field_events_discipline` ON `discipline`
- `idx_field_events_event_date` ON `event_date`
- `idx_field_events_status` ON `status`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view project field events.
- **INSERT**: `supervisor`, `planner`, and `admin` roles can create field events.
- **UPDATE**: `planner` and `admin` roles can update field events.
- **DELETE**: `admin` role only.

---

### 6. `public.field_inputs` (Phase 4)
Raw, unstructured field updates submitted via text, voice recordings, site photos, or site documents.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique field input identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `submitted_by` | `UUID` | `NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE` | Submitter profile ID |
| `input_type` | `field_input_type` | `NOT NULL` | Submission modality (`text`, `voice`, `photo`, `document`) |
| `title` | `TEXT` | `NULL` | Optional summary title |
| `raw_text` | `TEXT` | `NULL` | Typed notes or STT transcription text |
| `media_path` | `TEXT` | `NULL` | Storage object key in `field-inputs` bucket |
| `media_filename` | `TEXT` | `NULL` | Original uploaded media filename |
| `media_mime_type` | `TEXT` | `NULL` | MIME type of uploaded media |
| `media_size_bytes`| `INTEGER` | `NOT NULL DEFAULT 0 CHECK (media_size_bytes >= 0)` | File size in bytes |
| `audio_duration_seconds` | `NUMERIC(6,2)` | `NULL CHECK (audio_duration_seconds >= 0)` | Audio length for voice notes |
| `transcription_status` | `transcription_status` | `NOT NULL DEFAULT 'none'` | STT lifecycle state |
| `transcription_error` | `TEXT` | `NULL` | Error details if transcription failed |
| `field_date` | `DATE` | `NOT NULL DEFAULT CURRENT_DATE` | Date work occurred |
| `metadata` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | Extensible payload attributes |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record submission timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record modification timestamp |

**Content Integrity Constraints:**
- `chk_field_inputs_content_validity`:
  - `text` inputs must have non-empty `raw_text`.
  - `voice`, `photo`, and `document` inputs must have a valid non-empty `media_path`.
  - For `voice` inputs, `raw_text` may be `NULL` (prior to/during transcription) or populated with transcript text, and `transcription_status` tracks STT lifecycle.

**Indices:**
- `idx_field_inputs_project_id` ON `project_id`
- `idx_field_inputs_submitted_by` ON `submitted_by`
- `idx_field_inputs_input_type` ON `input_type`
- `idx_field_inputs_field_date` ON `field_date`
- `idx_field_inputs_created_at` ON `created_at DESC`
- `idx_field_inputs_transcription` ON `transcription_status`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view all project field inputs.
- **INSERT**: `supervisor`, `planner`, and `admin` roles can submit field inputs.
- **UPDATE**: `planner` and `admin` roles can update field inputs.
- **DELETE**: `admin` role only.

---

### 7. `public.ai_extractions` (Phase 5)
Structured construction progress entities extracted from raw `field_inputs` using AI (Gemini + LangChain).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique extraction identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `field_input_id` | `UUID` | `NOT NULL REFERENCES public.field_inputs(id) ON DELETE CASCADE` | Source field input reference |
| `status` | `extraction_status` | `NOT NULL DEFAULT 'pending'` | Extraction lifecycle state (`pending`, `completed`, `failed`) |
| `extracted_data` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | Validated structured extraction payload |
| `confidence_score`| `NUMERIC(4,3)` | `NULL CHECK ((confidence_score IS NULL) OR ((confidence_score >= 0.0) AND (confidence_score <= 1.0)))` | Model extraction confidence |
| `model_version` | `TEXT` | `NOT NULL` | Identifier of the LLM/prompt version |
| `error_message` | `TEXT` | `NULL` | Processing failure details if extraction failed |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Record modification timestamp |

**Unique Constraints:**
- `uq_ai_extractions_project_input` UNIQUE (`project_id`, `field_input_id`) — Enforces concurrency-safe idempotent upsert semantics.
- `uq_ai_extractions_id_project` UNIQUE (`id`, `project_id`) — Supporting constraint for composite tenant foreign keys.

**Indices:**
- `idx_ai_extractions_project_id` ON `project_id`
- `idx_ai_extractions_field_input_id` ON `field_input_id`
- `idx_ai_extractions_status` ON `status`
- `idx_ai_extractions_created_at` ON `created_at DESC`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view all project AI extractions.
- **INSERT / UPDATE**: Closed to direct client writes (fail closed). Extractions are written exclusively through the trusted server-side AI processing pipeline.
- **DELETE**: `admin` role only.

---

### 8. `public.schedule_activities` (Phase 6)
Imported and managed baseline schedule activities for a project.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique schedule activity identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `activity_code` | `TEXT` | `NOT NULL` | Project-unique activity identifier/code (e.g. `ACT-1001`) |
| `name` | `TEXT` | `NOT NULL` | Activity title / description |
| `wbs_code` | `TEXT` | `NULL` | Work Breakdown Structure code (e.g. `1.2.4.1`) |
| `discipline` | `TEXT` | `NULL` | Trade discipline (e.g. `Piping`, `Civil`, `Electrical`) |
| `location` | `TEXT` | `NULL` | Area / Unit / Grid location reference |
| `planned_start_date` | `DATE` | `NULL` | Baseline planned start date |
| `planned_finish_date` | `DATE` | `NULL` | Baseline planned completion date |
| `planned_quantity` | `NUMERIC` | `NULL CHECK (planned_quantity >= 0)` | Baseline physical work quantity |
| `planned_unit` | `TEXT` | `NULL` | Unit of measure (e.g. `LF`, `m3`, `spools`) |
| `metadata` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | Extensible schedule attributes |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Modification timestamp |

**Unique Constraints:**
- `uq_schedule_activities_project_code` UNIQUE (`project_id`, `activity_code`) — Enforces unique activity codes per project.
- `uq_schedule_activities_id_project` UNIQUE (`id`, `project_id`) — Supporting constraint for composite tenant foreign keys.

**Indices:**
- `idx_schedule_activities_project_id` ON `project_id`
- `idx_schedule_activities_discipline` ON `discipline`
- `idx_schedule_activities_dates` ON (`planned_start_date`, `planned_finish_date`)

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view schedule activities.
- **INSERT**: `planner` and `admin` roles can create schedule activities.
- **UPDATE**: `planner` and `admin` roles can update schedule activities.
- **DELETE**: `admin` role only.

---

### 9. `public.activity_embeddings` (Phase 6)
Stores dense vector embeddings generated for schedule activities using Google `models/text-embedding-004` ($768$ dimensions).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique embedding identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `schedule_activity_id` | `UUID` | `NOT NULL` | Associated schedule activity ID |
| `embedding` | `vector(768)` | `NOT NULL` | 768-dimensional dense float vector |
| `content_hash` | `TEXT` | `NOT NULL` | SHA-256 hash of embedded text for cache invalidation |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Modification timestamp |

**Foreign Keys & Composite Tenant Constraints:**
- `fk_activity_embeddings_project` FOREIGN KEY (`project_id`) REFERENCES `public.projects(id)` ON DELETE CASCADE
- `fk_activity_embeddings_activity_tenant` FOREIGN KEY (`schedule_activity_id`, `project_id`) REFERENCES `public.schedule_activities(id`, `project_id)` ON DELETE CASCADE
- `uq_activity_embeddings_activity` UNIQUE (`schedule_activity_id`)

**Indices:**
- `idx_activity_embeddings_project_id` ON `project_id`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view activity embeddings.
- **INSERT / UPDATE / DELETE**: Closed to direct client writes (fail closed). Embeddings are managed exclusively through the trusted server-side AI pipeline.

---

### 10. `public.ai_matches` (Phase 6)
Stores AI candidate schedule match recommendations and contextual confidence scores for planner review.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique match recommendation record ID |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `extraction_id` | `UUID` | `NOT NULL` | Associated AI extraction reference |
| `activity_index` | `INTEGER` | `NOT NULL DEFAULT 0 CHECK (activity_index >= 0)` | Activity item index in extraction payload |
| `recommended_activity_id` | `UUID` | `NOT NULL` | Top recommended schedule activity |
| `confidence_score` | `NUMERIC(4,3)` | `NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)` | Match confidence score ($0.000 - 1.000$) |
| `scoring_breakdown` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | Contextual score components (semantic, trade, location, temporal) |
| `alternative_matches` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | List of alternative ranked candidate activities |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Modification timestamp |

**Foreign Keys & Composite Tenant Constraints:**
- `fk_ai_matches_project` FOREIGN KEY (`project_id`) REFERENCES `public.projects(id)` ON DELETE CASCADE
- `fk_ai_matches_extraction_tenant` FOREIGN KEY (`extraction_id`, `project_id`) REFERENCES `public.ai_extractions(id`, `project_id)` ON DELETE CASCADE
- `fk_ai_matches_recommended_activity_tenant` FOREIGN KEY (`recommended_activity_id`, `project_id`) REFERENCES `public.schedule_activities(id`, `project_id)` ON DELETE CASCADE
- `uq_ai_matches_project_extraction_activity` UNIQUE (`project_id`, `extraction_id`, `activity_index`)

**Indices:**
- `idx_ai_matches_project_id` ON `project_id`
- `idx_ai_matches_extraction_id` ON `extraction_id`
- `idx_ai_matches_recommended_activity_id` ON `recommended_activity_id`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view AI match recommendations.
- **INSERT / UPDATE / DELETE**: Closed to direct client writes (fail closed). Match recommendations are written exclusively through the trusted server-side AI processing pipeline.

---

### 11. `public.planner_decisions` (Phase 7)
Append-only audit trail of human planner decisions (Approve, Reject, Modify) executed on AI match recommendations.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique decision identifier |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `match_id` | `UUID` | `NOT NULL` | Associated AI match recommendation reference |
| `extraction_id` | `UUID` | `NOT NULL` | Associated source extraction reference |
| `decision` | `planner_decision_type` | `NOT NULL` | Decision outcome (`approved`, `rejected`, `modified`) |
| `decided_by` | `UUID` | `NOT NULL REFERENCES public.profiles(id)` | Planner user ID who executed decision |
| `decided_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Timestamp of decision |
| `rejection_reason` | `TEXT` | `NULL` | Explanation provided when decision is `rejected` |
| `original_payload` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | Snapshot of original AI match recommendation |
| `modified_payload` | `JSONB` | `NULL` | Snapshot of planner overrides when modified |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |

**Foreign Keys & Composite Tenant Constraints:**
- `fk_planner_decisions_match_tenant` FOREIGN KEY (`match_id`, `project_id`) REFERENCES `public.ai_matches(id`, `project_id)` ON DELETE CASCADE
- `fk_planner_decisions_extraction_tenant` FOREIGN KEY (`extraction_id`, `project_id`) REFERENCES `public.ai_extractions(id`, `project_id)` ON DELETE CASCADE

**Indices:**
- `idx_planner_decisions_project_id` ON `project_id`
- `idx_planner_decisions_match_id` ON `match_id`
- `idx_planner_decisions_extraction_id` ON `extraction_id`
- `idx_planner_decisions_decided_by` ON `decided_by`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view planner decisions.
- **INSERT**: `planner` and `admin` roles can record decisions.
- **UPDATE / DELETE**: Closed (fail closed) to maintain an append-only audit trail.

---

### 12. `public.approved_actuals` (Phase 7)
Official, immutable construction progress records approved by human planners, serving as the ground truth for Phase 8 plan-vs-actual variance and Phase 9 risk intelligence.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique approved actual ID |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `schedule_activity_id` | `UUID` | `NOT NULL` | Associated baseline schedule activity |
| `extraction_id` | `UUID` | `NOT NULL` | Source AI extraction reference |
| `match_id` | `UUID` | `NOT NULL` | Source AI match recommendation reference |
| `activity_index` | `INTEGER` | `NOT NULL DEFAULT 0 CHECK (activity_index >= 0)` | Activity item index in extraction payload |
| `actual_quantity` | `NUMERIC` | `NULL CHECK (actual_quantity >= 0)` | Verified physical progress quantity |
| `actual_unit` | `TEXT` | `NULL` | Unit of measure |
| `actual_date` | `DATE` | `NOT NULL` | Verified work date |
| `source_evidence` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | Verbatim grounding tokens |
| `approved_by` | `UUID` | `NOT NULL REFERENCES public.profiles(id)` | Approving planner user ID |
| `approved_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Timestamp of approval |
| `notes` | `TEXT` | `NULL` | Optional planner notes/clarifications |
| `is_modified` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Flag indicating human modification |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Modification timestamp |

**Foreign Keys & Composite Tenant Constraints:**
- `fk_approved_actuals_project` FOREIGN KEY (`project_id`) REFERENCES `public.projects(id)` ON DELETE CASCADE
- `fk_approved_actuals_activity_tenant` FOREIGN KEY (`schedule_activity_id`, `project_id`) REFERENCES `public.schedule_activities(id`, `project_id)` ON DELETE CASCADE
- `fk_approved_actuals_extraction_tenant` FOREIGN KEY (`extraction_id`, `project_id`) REFERENCES `public.ai_extractions(id`, `project_id)` ON DELETE CASCADE
- `fk_approved_actuals_match_tenant` FOREIGN KEY (`match_id`, `project_id`) REFERENCES `public.ai_matches(id`, `project_id)` ON DELETE CASCADE
- `uq_approved_actuals_project_extraction_activity` UNIQUE (`project_id`, `extraction_id`, `activity_index`)

**Indices:**
- `idx_approved_actuals_project_id` ON `project_id`
- `idx_approved_actuals_schedule_activity_id` ON `schedule_activity_id`
- `idx_approved_actuals_extraction_id` ON `extraction_id`
- `idx_approved_actuals_match_id` ON `match_id`
- `idx_approved_actuals_approved_by` ON `approved_by`
- `idx_approved_actuals_actual_date` ON `actual_date`

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view approved actuals.
- **INSERT**: `planner` and `admin` roles can create approved actuals.
- **UPDATE**: `planner` and `admin` roles can update approved actuals.
---

### 13. `public.schedule_dependencies` (Phase 9.1)
Stores directed activity dependency relationships (edges) for the project schedule network, enabling Critical Path Method (CPM) calculations, float determination, and downstream impact analysis.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique dependency edge ID |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `predecessor_id` | `UUID` | `NOT NULL` | Upstream predecessor activity reference |
| `successor_id` | `UUID` | `NOT NULL` | Downstream successor activity reference |
| `relationship_type` | `TEXT` | `NOT NULL DEFAULT 'FS' CHECK (relationship_type IN ('FS', 'SS', 'FF', 'SF'))` | Precedence relationship type |
| `lag_days` | `INTEGER` | `NOT NULL DEFAULT 0` | Calendar days lag (negative represents lead) |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last update timestamp |

**Integrity & Composite Tenant Constraints:**
- `chk_schedule_dependencies_rel_type`: `CHECK (relationship_type IN ('FS', 'SS', 'FF', 'SF'))`
- `chk_schedule_dependencies_no_self`: `CHECK (predecessor_id <> successor_id)` — Prevents 1-hop self-loops.
- `uq_schedule_dependencies_edge`: `UNIQUE (project_id, predecessor_id, successor_id)` — Ensures at most one edge exists between any ordered activity pair.
- `fk_dep_predecessor_tenant`: `FOREIGN KEY (predecessor_id, project_id) REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE`
- `fk_dep_successor_tenant`: `FOREIGN KEY (successor_id, project_id) REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE`

**Indices:**
- `idx_schedule_dependencies_project_id` ON `project_id`
- `idx_schedule_dependencies_predecessor` ON (`project_id`, `predecessor_id`) — Supports outgoing successor queries.
- `idx_schedule_dependencies_successor` ON (`project_id`, `successor_id`) — Supports incoming predecessor queries.

**RLS Policies:**
- **SELECT**: Project members (`viewer` and above) can view schedule dependencies.
- **INSERT**: `planner` and `admin` roles can create schedule dependencies.
- **UPDATE**: `planner` and `admin` roles can update schedule dependencies.
- **DELETE**: `admin` role only.

---

## Supabase Storage


### Bucket: `field-inputs`
Private bucket for construction media attachments and audio recordings.

- **Visibility**: `public: false` (signed URLs required).
- **Max File Size**: 25 MB (`26,214,400 bytes`).
- **Object Key Scheme**: `projects/{project_id}/inputs/{input_id}/{safe_filename}`.
- **Storage RLS**:
  - `SELECT`: Restricted to authenticated members of `project_id` matching `(storage.foldername(name))[2]`.
  - `INSERT`: Restricted to `supervisor`, `planner`, and `admin` roles of `project_id`.
  - `DELETE`: Restricted to `admin` role of `project_id`.

---

## Security Invariants

1. RLS is mandatory on all tables in `public` and all buckets in `storage`.
2. Cross-project data access is strictly prohibited at database, composite foreign key, and API levels.
3. Client-supplied role or user ID is never trusted by backend API operations.
4. Storage objects are strictly private; signed URLs generated server-side are used for access.
5. AI extraction, vector embedding, and match recommendation writes are strictly server-side operations; client-side write forging is prevented by closed client RLS.
