"""
SiteSync AI — SQL Migrations & RLS Security Policy Verification Tests.
Validates that:
  - All tables across Phase 2, Phase 3, Phase 4, and Phase 5 have Row-Level Security enabled.
  - No overly permissive policies (e.g. blanket TRUE for authenticated users) exist.
  - Project isolation and membership constraints are syntactically present.
  - Private Supabase Storage bucket and storage RLS policies are present for field-inputs.
  - Phase 4.1 submitter NOT NULL and voice/photo/doc content integrity constraints are enforced.
  - Phase 5.2 ai_extractions table, extraction_status enum, foreign keys, and RLS policies are enforced.
  - Phase 5.5 concurrency-safe idempotency unique constraint (project_id, field_input_id) is enforced.
"""

from __future__ import annotations

from pathlib import Path
import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
PHASE2_MIGRATION = MIGRATIONS_DIR / "20260830000000_phase2_auth_foundation.sql"
PHASE3_MIGRATION = MIGRATIONS_DIR / "20260830000001_phase3_reports_and_events.sql"
PHASE4_MIGRATION = MIGRATIONS_DIR / "20260830000002_phase4_field_inputs.sql"
PHASE5_MIGRATION = MIGRATIONS_DIR / "20260830000003_phase5_ai_extractions.sql"
PHASE5_IDEMPOTENCY_MIGRATION = MIGRATIONS_DIR / "20260830000004_phase5_ai_extractions_idempotency.sql"


def test_migration_files_exist():
    assert PHASE2_MIGRATION.exists(), f"Phase 2 migration missing at {PHASE2_MIGRATION}"
    assert PHASE3_MIGRATION.exists(), f"Phase 3 migration missing at {PHASE3_MIGRATION}"
    assert PHASE4_MIGRATION.exists(), f"Phase 4 migration missing at {PHASE4_MIGRATION}"
    assert PHASE5_MIGRATION.exists(), f"Phase 5 migration missing at {PHASE5_MIGRATION}"
    assert PHASE5_IDEMPOTENCY_MIGRATION.exists(), f"Phase 5 idempotency migration missing at {PHASE5_IDEMPOTENCY_MIGRATION}"


def test_rls_enabled_on_all_tables():
    # Phase 2 tables
    p2_sql = PHASE2_MIGRATION.read_text().lower()
    for table in ["profiles", "projects", "project_members"]:
        expected = f"alter table public.{table} enable row level security"
        assert expected in p2_sql, f"RLS not enabled on {table}"

    # Phase 3 tables
    p3_sql = PHASE3_MIGRATION.read_text().lower()
    for table in ["reports", "field_events"]:
        expected = f"alter table public.{table} enable row level security"
        assert expected in p3_sql, f"RLS not enabled on {table}"

    # Phase 4 tables
    p4_sql = PHASE4_MIGRATION.read_text().lower()
    assert "alter table public.field_inputs enable row level security" in p4_sql

    # Phase 5 tables
    p5_sql = PHASE5_MIGRATION.read_text().lower()
    assert "alter table public.ai_extractions enable row level security" in p5_sql


def test_no_blanket_authenticated_policies():
    all_sql = (
        PHASE2_MIGRATION.read_text()
        + "\n"
        + PHASE3_MIGRATION.read_text()
        + "\n"
        + PHASE4_MIGRATION.read_text()
        + "\n"
        + PHASE5_MIGRATION.read_text()
        + "\n"
        + PHASE5_IDEMPOTENCY_MIGRATION.read_text()
    )
    forbidden_patterns = [
        "to authenticated using (true)",
        "to authenticated using ( true )",
        "to anon using (true)",
        "with check (true)",
        "with check ( true )",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in all_sql.lower(), f"Found overly permissive pattern '{pattern}' in migrations"


def test_phase3_foreign_keys_and_enums():
    sql = PHASE3_MIGRATION.read_text()
    assert "report_status AS ENUM ('uploaded', 'processing', 'processed', 'failed')" in sql
    assert "field_event_status AS ENUM" in sql
    assert "REFERENCES public.projects(id) ON DELETE CASCADE" in sql


def test_phase4_foreign_keys_enums_and_storage_policies():
    sql = PHASE4_MIGRATION.read_text()
    assert "submitted_by UUID NOT NULL" in sql
    assert "REFERENCES public.projects(id) ON DELETE CASCADE" in sql
    assert "REFERENCES public.profiles(id) ON DELETE CASCADE" in sql
    assert "field_input_type AS ENUM ('text', 'voice', 'photo', 'document')" in sql
    assert "transcription_status AS ENUM ('none', 'pending', 'completed', 'failed')" in sql
    assert "chk_field_inputs_content_validity" in sql
    assert "(input_type = 'text' AND raw_text IS NOT NULL AND length(trim(raw_text)) > 0)" in sql
    assert "(input_type IN ('voice', 'photo', 'document') AND media_path IS NOT NULL AND length(trim(media_path)) > 0)" in sql
    assert "'field-inputs'" in sql
    assert "bucket_id = 'field-inputs'" in sql


def test_phase5_ai_extractions_schema_and_rls():
    sql = PHASE5_MIGRATION.read_text()
    assert "extraction_status AS ENUM ('pending', 'completed', 'failed')" in sql
    assert "REFERENCES public.projects(id) ON DELETE CASCADE" in sql
    assert "REFERENCES public.field_inputs(id) ON DELETE CASCADE" in sql
    assert "chk_ai_extractions_confidence" in sql
    assert "idx_ai_extractions_project_id" in sql
    assert "idx_ai_extractions_field_input_id" in sql
    assert "idx_ai_extractions_status" in sql
    assert "idx_ai_extractions_created_at" in sql
    assert "Members can view project ai extractions" in sql
    assert "Admins can delete ai extractions" in sql
    # Verify no open client INSERT/UPDATE
    assert "CREATE POLICY \"Supervisors and above can insert ai extractions\"" not in sql
    assert "CREATE POLICY \"Planners and admins can update ai extractions\"" not in sql


def test_phase5_ai_extractions_idempotency_unique_constraint():
    sql = PHASE5_IDEMPOTENCY_MIGRATION.read_text()
    assert "uq_ai_extractions_project_input" in sql
    assert "UNIQUE (project_id, field_input_id)" in sql
