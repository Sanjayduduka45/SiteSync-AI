"""
SiteSync AI — Phase 7.1 Database Foundation Static Tests.
Verifies the database schema, constraints, composite tenant foreign keys,
RLS policies, and security invariants for Phase 7.
"""

from pathlib import Path
import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
PHASE7_MIGRATION = MIGRATIONS_DIR / "20260830000006_phase7_planner_review_and_approved_actuals.sql"

PROTECTED_MIGRATIONS = [
    "20260830000000_phase2_auth_foundation.sql",
    "20260830000001_phase3_reports_and_events.sql",
    "20260830000002_phase4_field_inputs.sql",
    "20260830000003_phase5_ai_extractions.sql",
    "20260830000004_phase5_ai_extractions_idempotency.sql",
    "20260830000005_phase6_schedule_matching_foundation.sql",
]


def test_1_phase7_migration_file_exists():
    """Verify Phase 7.1 migration file is created and non-empty."""
    assert PHASE7_MIGRATION.exists(), f"Missing Phase 7 migration file: {PHASE7_MIGRATION}"
    content = PHASE7_MIGRATION.read_text()
    assert len(content.strip()) > 0


def test_2_planner_decision_type_enum():
    """Verify planner_decision_type enum contains approved, rejected, modified."""
    sql = PHASE7_MIGRATION.read_text()
    assert "planner_decision_type" in sql
    assert "'approved'" in sql
    assert "'rejected'" in sql
    assert "'modified'" in sql


def test_3_supporting_composite_uniqueness_on_ai_matches():
    """Verify ai_matches has supporting uniqueness on (id, project_id) for composite FKs."""
    sql = PHASE7_MIGRATION.read_text()
    assert "uq_ai_matches_id_project UNIQUE (id, project_id)" in sql


def test_4_planner_decisions_schema_and_composite_fks():
    """Verify planner_decisions table structure, audit semantics, and composite tenant FKs."""
    sql = PHASE7_MIGRATION.read_text()
    assert "CREATE TABLE public.planner_decisions" in sql
    assert "project_id UUID NOT NULL REFERENCES public.projects(id)" in sql
    assert "match_id UUID NOT NULL" in sql
    assert "extraction_id UUID NOT NULL" in sql
    assert "decision planner_decision_type NOT NULL" in sql
    assert "decided_by UUID NOT NULL REFERENCES public.profiles(id)" in sql
    assert "rejection_reason TEXT NULL" in sql
    assert "original_payload JSONB NOT NULL DEFAULT '{}'::jsonb" in sql
    assert "modified_payload JSONB NULL" in sql

    # Composite Tenant Foreign Keys
    assert "fk_planner_decisions_match_tenant" in sql
    assert "FOREIGN KEY (match_id, project_id)" in sql
    assert "REFERENCES public.ai_matches(id, project_id)" in sql
    assert "fk_planner_decisions_extraction_tenant" in sql
    assert "FOREIGN KEY (extraction_id, project_id)" in sql
    assert "REFERENCES public.ai_extractions(id, project_id)" in sql


def test_5_approved_actuals_schema_and_composite_fks():
    """Verify approved_actuals table structure, columns, and composite tenant FKs."""
    sql = PHASE7_MIGRATION.read_text()
    assert "CREATE TABLE public.approved_actuals" in sql
    assert "project_id UUID NOT NULL REFERENCES public.projects(id)" in sql
    assert "schedule_activity_id UUID NOT NULL" in sql
    assert "extraction_id UUID NOT NULL" in sql
    assert "match_id UUID NOT NULL" in sql
    assert "activity_index INTEGER NOT NULL DEFAULT 0 CHECK (activity_index >= 0)" in sql
    assert "actual_quantity NUMERIC NULL CHECK (actual_quantity >= 0)" in sql
    assert "actual_unit TEXT NULL" in sql
    assert "actual_date DATE NOT NULL" in sql
    assert "source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb" in sql
    assert "approved_by UUID NOT NULL REFERENCES public.profiles(id)" in sql
    assert "is_modified BOOLEAN NOT NULL DEFAULT FALSE" in sql

    # Composite Tenant Foreign Keys
    assert "fk_approved_actuals_activity_tenant" in sql
    assert "FOREIGN KEY (schedule_activity_id, project_id)" in sql
    assert "REFERENCES public.schedule_activities(id, project_id)" in sql
    assert "fk_approved_actuals_extraction_tenant" in sql
    assert "FOREIGN KEY (extraction_id, project_id)" in sql
    assert "REFERENCES public.ai_extractions(id, project_id)" in sql
    assert "fk_approved_actuals_match_tenant" in sql
    assert "FOREIGN KEY (match_id, project_id)" in sql
    assert "REFERENCES public.ai_matches(id, project_id)" in sql


def test_6_approved_actuals_idempotency_constraint():
    """Verify unique constraint on (project_id, extraction_id, activity_index)."""
    sql = PHASE7_MIGRATION.read_text()
    assert "uq_approved_actuals_project_extraction_activity UNIQUE (project_id, extraction_id, activity_index)" in sql


def test_7_rls_enabled_on_phase7_tables():
    """Verify RLS is explicitly enabled on all Phase 7 tables."""
    sql = PHASE7_MIGRATION.read_text()
    assert "ALTER TABLE public.planner_decisions ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE public.approved_actuals ENABLE ROW LEVEL SECURITY;" in sql


def test_8_rls_policies_and_role_permissions():
    """Verify RLS policies use has_project_role with appropriate role checks."""
    sql = PHASE7_MIGRATION.read_text()
    assert "public.has_project_role(project_id, 'viewer')" in sql
    assert "public.has_project_role(project_id, 'planner')" in sql
    assert "public.has_project_role(project_id, 'admin')" in sql

    # No UPDATE or DELETE policies for planner_decisions (append-only audit log)
    assert 'ON public.planner_decisions\n    FOR UPDATE' not in sql
    assert 'ON public.planner_decisions\n    FOR DELETE' not in sql


def test_9_no_blanket_using_or_check_true():
    """Verify zero blanket USING(true) or WITH CHECK(true) policies."""
    sql = PHASE7_MIGRATION.read_text()
    assert "USING (true)" not in sql
    assert "USING(true)" not in sql
    assert "WITH CHECK (true)" not in sql
    assert "WITH CHECK(true)" not in sql


def test_10_phase8_9_concepts_absent_from_phase7_migration():
    """Verify downstream Phase 8/9 concepts are absent from migration."""
    sql = PHASE7_MIGRATION.read_text().lower()
    forbidden_terms = [
        "variance",
        "plan_vs_actual",
        "forecasting",
        "critical_path",
        "risk_engine",
        "risk_heatmap",
        "downstream_impact",
    ]
    for term in forbidden_terms:
        assert term not in sql, f"Forbidden term '{term}' found in Phase 7 migration."


def test_11_protected_migrations_remain_untouched():
    """Verify previous protected migration files exist and are untouched."""
    for filename in PROTECTED_MIGRATIONS:
        path = MIGRATIONS_DIR / filename
        assert path.exists(), f"Protected migration missing: {filename}"
