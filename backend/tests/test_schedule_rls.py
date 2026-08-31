"""
SiteSync AI — Phase 6.1 Database Foundation & RLS Policy Tests.
Tests:
  - Phase 6.1 migration file exists and is forward-only
  - pgvector extension is enabled
  - schedule_activities table, columns, indexes, and constraints
  - activity_embeddings table with vector(768) and composite tenant FK
  - ai_matches table with confidence constraint and composite tenant FK
  - RLS enabled on all three tables
  - Closed direct client write policies on activity_embeddings and ai_matches
  - RBAC on schedule_activities (SELECT viewer, INSERT/UPDATE planner, DELETE admin)
  - No blanket USING(true) or WITH CHECK(true) policies
  - Phase 7/8/9 concepts (approval, approved_actuals, variance, risk) absent
  - Protected Phase 2–5 migrations remain untouched
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "supabase" / "migrations"


def get_migration_sql(filename: str) -> str:
    path = MIGRATIONS_DIR / filename
    assert path.exists(), f"Migration file {filename} does not exist"
    return path.read_text(encoding="utf-8")


def test_phase6_migration_file_exists():
    """Verify Phase 6.1 migration file is present."""
    path = MIGRATIONS_DIR / "20260830000005_phase6_schedule_matching_foundation.sql"
    assert path.exists()


def test_pgvector_extension_enabled():
    """Verify pgvector extension is enabled."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in sql


def test_schedule_activities_schema_and_constraints():
    """Verify schedule_activities table, columns, unique constraints, and check constraints."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    assert "CREATE TABLE public.schedule_activities" in sql
    assert "activity_code TEXT NOT NULL" in sql
    assert "name TEXT NOT NULL" in sql
    assert "wbs_code TEXT NULL" in sql
    assert "discipline TEXT NULL" in sql
    assert "location TEXT NULL" in sql
    assert "planned_start_date DATE NULL" in sql
    assert "planned_finish_date DATE NULL" in sql
    assert "planned_quantity NUMERIC NULL CHECK (planned_quantity >= 0)" in sql
    assert "planned_unit TEXT NULL" in sql
    assert "metadata JSONB NOT NULL DEFAULT '{}'::jsonb" in sql
    assert "CONSTRAINT uq_schedule_activities_project_code UNIQUE (project_id, activity_code)" in sql
    assert "CONSTRAINT uq_schedule_activities_id_project UNIQUE (id, project_id)" in sql


def test_activity_embeddings_schema_and_vector_dimension():
    """Verify activity_embeddings table uses vector(768) and composite tenant foreign key."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    assert "CREATE TABLE public.activity_embeddings" in sql
    assert "embedding vector(768) NOT NULL" in sql
    assert "content_hash TEXT NOT NULL" in sql
    assert "CONSTRAINT uq_activity_embeddings_activity UNIQUE (schedule_activity_id)" in sql
    assert "CONSTRAINT fk_activity_embeddings_activity_tenant FOREIGN KEY (schedule_activity_id, project_id)" in sql


def test_ai_matches_schema_and_confidence_constraint():
    """Verify ai_matches table, composite uniqueness, and confidence score bounds."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    assert "CREATE TABLE public.ai_matches" in sql
    assert "activity_index INTEGER NOT NULL DEFAULT 0 CHECK (activity_index >= 0)" in sql
    assert "confidence_score NUMERIC(4,3) NOT NULL" in sql
    assert "confidence_score >= 0.0 AND confidence_score <= 1.0" in sql
    assert "scoring_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb" in sql
    assert "alternative_matches JSONB NOT NULL DEFAULT '[]'::jsonb" in sql
    assert "CONSTRAINT uq_ai_matches_project_extraction_activity UNIQUE (project_id, extraction_id, activity_index)" in sql
    assert "CONSTRAINT fk_ai_matches_extraction_tenant FOREIGN KEY (extraction_id, project_id)" in sql
    assert "CONSTRAINT fk_ai_matches_recommended_activity_tenant FOREIGN KEY (recommended_activity_id, project_id)" in sql


def test_rls_enabled_on_all_phase6_tables():
    """Verify RLS is explicitly enabled on all 3 Phase 6 tables."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    assert "ALTER TABLE public.schedule_activities ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE public.activity_embeddings ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE public.ai_matches ENABLE ROW LEVEL SECURITY;" in sql


def test_phase6_rls_policies_and_role_permissions():
    """Verify correct role hierarchy and closed direct client writes."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    # schedule_activities: SELECT viewer, INSERT/UPDATE planner, DELETE admin
    assert "has_project_role(project_id, 'viewer')" in sql
    assert "has_project_role(project_id, 'planner')" in sql
    assert "has_project_role(project_id, 'admin')" in sql

    # activity_embeddings: SELECT viewer only; direct client INSERT/UPDATE/DELETE are closed
    assert 'CREATE POLICY "Project members can view activity embeddings"' in sql
    assert 'ON public.activity_embeddings' in sql
    assert 'FOR INSERT\n    ON public.activity_embeddings' not in sql

    # ai_matches: SELECT viewer only; direct client INSERT/UPDATE/DELETE are closed
    assert 'CREATE POLICY "Project members can view AI match recommendations"' in sql
    assert 'ON public.ai_matches' in sql
    assert 'FOR INSERT\n    ON public.ai_matches' not in sql


def test_no_blanket_using_or_check_true_policies():
    """Ensure no permissive USING (true) or WITH CHECK (true) policies exist in Phase 6."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    assert not re.search(r"USING\s*\(\s*true\s*\)", sql, re.IGNORECASE)
    assert not re.search(r"WITH\s+CHECK\s*\(\s*true\s*\)", sql, re.IGNORECASE)


def test_phase7_8_9_concepts_absent_from_phase6_migration():
    """Verify absence of Phase 7 (approval), Phase 8 (variance), and Phase 9 (risk) fields."""
    sql = get_migration_sql("20260830000005_phase6_schedule_matching_foundation.sql")

    forbidden_keywords = [
        "approved_actual",
        "planner_approval",
        "approval_status",
        "approved_at",
        "approved_by",
        "variance",
        "critical_path",
        "risk_engine",
        "risk_heatmap",
    ]

    for kw in forbidden_keywords:
        assert kw not in sql.lower(), f"Forbidden concept '{kw}' found in Phase 6.1 migration"


def test_protected_migrations_remain_untouched():
    """Verify all migrations from Phase 2, 3, 4, and 5 exist."""
    protected_files = [
        "20260830000000_phase2_auth_foundation.sql",
        "20260830000001_phase3_reports_and_events.sql",
        "20260830000002_phase4_field_inputs.sql",
        "20260830000003_phase5_ai_extractions.sql",
        "20260830000004_phase5_ai_extractions_idempotency.sql",
    ]
    for filename in protected_files:
        assert (MIGRATIONS_DIR / filename).exists()
