"""
SiteSync AI — SQL Migrations & RLS Security Policy Verification Tests.
Validates that:
  - All tables across Phase 2, Phase 3, and Phase 4 have Row-Level Security enabled.
  - No overly permissive policies (e.g. blanket TRUE for authenticated users) exist.
  - Project isolation and membership constraints are syntactically present.
  - Private Supabase Storage bucket and storage RLS policies are present for field-inputs.
  - Phase 4.1 submitter NOT NULL and voice/photo/doc content integrity constraints are enforced.
"""

from __future__ import annotations

from pathlib import Path
import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
PHASE2_MIGRATION = MIGRATIONS_DIR / "20260830000000_phase2_auth_foundation.sql"
PHASE3_MIGRATION = MIGRATIONS_DIR / "20260830000001_phase3_reports_and_events.sql"
PHASE4_MIGRATION = MIGRATIONS_DIR / "20260830000002_phase4_field_inputs.sql"


def test_migration_files_exist():
    assert PHASE2_MIGRATION.exists(), f"Phase 2 migration missing at {PHASE2_MIGRATION}"
    assert PHASE3_MIGRATION.exists(), f"Phase 3 migration missing at {PHASE3_MIGRATION}"
    assert PHASE4_MIGRATION.exists(), f"Phase 4 migration missing at {PHASE4_MIGRATION}"


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
    for table in ["field_inputs"]:
        expected = f"alter table public.{table} enable row level security"
        assert expected in p4_sql, f"RLS not enabled on {table}"


def test_no_blanket_authenticated_policies():
    """Ensure no policies allow blanket access to all rows without project/user checks."""
    for path in [PHASE2_MIGRATION, PHASE3_MIGRATION, PHASE4_MIGRATION]:
        sql = path.read_text().lower()
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.startswith("using (true)") or stripped.startswith("using ( true )"):
                pytest.fail(f"Found unsafe blanket policy in {path.name}: '{stripped}'")


def test_phase3_foreign_keys_and_enums():
    sql = PHASE3_MIGRATION.read_text()
    assert "REFERENCES public.projects(id) ON DELETE CASCADE" in sql
    assert "REFERENCES public.reports(id) ON DELETE SET NULL" in sql
    assert "CHECK (progress_percent >= 0 AND progress_percent <= 100)" in sql


def test_phase4_foreign_keys_enums_and_storage_policies():
    sql = PHASE4_MIGRATION.read_text()
    assert "REFERENCES public.projects(id) ON DELETE CASCADE" in sql
    assert "submitted_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE" in sql
    assert "field_input_type AS ENUM ('text', 'voice', 'photo', 'document')" in sql
    assert "transcription_status AS ENUM ('none', 'pending', 'completed', 'failed')" in sql
    assert "chk_field_inputs_content_validity" in sql
    assert "(input_type = 'text' AND raw_text IS NOT NULL AND length(trim(raw_text)) > 0)" in sql
    assert "(input_type IN ('voice', 'photo', 'document') AND media_path IS NOT NULL AND length(trim(media_path)) > 0)" in sql
    assert "'field-inputs'" in sql
    assert "bucket_id = 'field-inputs'" in sql
