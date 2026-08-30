"""
SiteSync AI — Phase 2 SQL Migration & RLS Security Policy Verification Tests.
Validates that:
  - All Phase 2 tables have Row-Level Security enabled.
  - No overly permissive policies (e.g. blanket TRUE for authenticated users) exist.
  - Project isolation and membership constraints are syntactically present.
"""

from __future__ import annotations

from pathlib import Path
import pytest

MIGRATION_PATH = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations" / "20260830000000_phase2_auth_foundation.sql"


def test_migration_file_exists():
    assert MIGRATION_PATH.exists(), f"Migration file missing at {MIGRATION_PATH}"


def test_rls_enabled_on_all_tables():
    sql = MIGRATION_PATH.read_text().lower()
    required_tables = ["profiles", "projects", "project_members"]
    for table in required_tables:
        expected_statement = f"alter table public.{table} enable row level security"
        assert expected_statement in sql, f"RLS not explicitly enabled on table '{table}'"


def test_no_blanket_authenticated_policies():
    """Ensure no policies allow blanket access to all rows without project/user checks."""
    sql = MIGRATION_PATH.read_text().lower()
    lines = sql.splitlines()

    for line in lines:
        stripped = line.strip()
        # Ensure we don't have naive 'using (true)' on public tables
        if stripped.startswith("using (true)") or stripped.startswith("using ( true )"):
            pytest.fail(f"Found unsafe blanket policy expression: '{stripped}'")


def test_project_membership_foreign_keys_and_unique_constraint():
    sql = MIGRATION_PATH.read_text()
    assert "REFERENCES public.projects(id) ON DELETE CASCADE" in sql
    assert "REFERENCES public.profiles(id) ON DELETE CASCADE" in sql
    assert "CONSTRAINT uq_project_members_project_user UNIQUE (project_id, user_id)" in sql
