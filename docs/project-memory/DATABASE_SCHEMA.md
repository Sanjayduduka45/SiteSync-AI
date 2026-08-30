# DATABASE SCHEMA — SiteSync AI

> Database platform: **Supabase PostgreSQL** with **pgvector**
> Current active phase: **Phase 4 — Field Input Foundation**

---

## Overview

SiteSync AI enforces multi-tenant project isolation using explicit PostgreSQL Row-Level Security (RLS) policies.
Phase 2 established identity, projects, and membership. Phase 3 established reports and field events.
Phase 4 establishes raw unstructured field input ingestion (`public.field_inputs`) and private storage security (`field-inputs` bucket).

---

## Enums

### `project_role`
Defines project-level authorization roles.

```sql
CREATE TYPE project_role AS ENUM ('admin', 'planner', 'supervisor', 'viewer');
```

Role Hierarchy:
1. `admin` (40): Full project administrative privileges (members, reports deletion, event management, input deletion).
2. `planner` (30): Report viewing & upload, field event creation & editing, field input updates.
3. `supervisor` (20): Report viewing & upload, field event creation, field input creation.
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
2. Cross-project data access is strictly prohibited at both API and database levels.
3. Client-supplied role or user ID is never trusted by backend API operations.
4. Storage objects are strictly private; signed URLs generated server-side are used for access.
