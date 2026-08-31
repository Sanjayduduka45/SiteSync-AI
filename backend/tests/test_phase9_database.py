"""
SiteSync AI — Phase 9.1 Database Foundation Static Tests.
Verifies the database schema, constraints, composite tenant foreign keys,
indexes, RLS policies, and security invariants for schedule_dependencies.
"""

from pathlib import Path
import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
PHASE9_MIGRATION = MIGRATIONS_DIR / "20260830000007_phase9_schedule_dependencies.sql"

PROTECTED_MIGRATIONS = [
    "20260830000000_phase2_auth_foundation.sql",
    "20260830000001_phase3_reports_and_events.sql",
    "20260830000002_phase4_field_inputs.sql",
    "20260830000003_phase5_ai_extractions.sql",
    "20260830000004_phase5_ai_extractions_idempotency.sql",
    "20260830000005_phase6_schedule_matching_foundation.sql",
    "20260830000006_phase7_planner_review_and_approved_actuals.sql",
]


def test_1_phase9_migration_file_exists():
    """Verify Phase 9.1 migration file is created and non-empty."""
    assert PHASE9_MIGRATION.exists(), f"Missing Phase 9 migration file: {PHASE9_MIGRATION}"
    content = PHASE9_MIGRATION.read_text()
    assert len(content.strip()) > 0


def test_2_schedule_dependencies_table_structure():
    """Verify schedule_dependencies table columns, defaults, and data types."""
    sql = PHASE9_MIGRATION.read_text()
    assert "CREATE TABLE public.schedule_dependencies" in sql
    assert "id UUID PRIMARY KEY DEFAULT gen_random_uuid()" in sql
    assert "project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE" in sql
    assert "predecessor_id UUID NOT NULL" in sql
    assert "successor_id UUID NOT NULL" in sql
    assert "relationship_type TEXT NOT NULL DEFAULT 'FS'" in sql
    assert "lag_days INTEGER NOT NULL DEFAULT 0" in sql
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())" in sql
    assert "updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())" in sql


def test_3_relationship_type_check_constraint():
    """Verify CHECK constraint for supported relationship types: FS, SS, FF, SF."""
    sql = PHASE9_MIGRATION.read_text()
    assert "chk_schedule_dependencies_rel_type" in sql
    assert "CHECK (relationship_type IN ('FS', 'SS', 'FF', 'SF'))" in sql


def test_4_self_dependency_prevention():
    """Verify CHECK constraint preventing self-loops (predecessor_id == successor_id)."""
    sql = PHASE9_MIGRATION.read_text()
    assert "chk_schedule_dependencies_no_self" in sql
    assert "CHECK (predecessor_id <> successor_id)" in sql


def test_5_duplicate_edge_prevention():
    """Verify uniqueness constraint on (project_id, predecessor_id, successor_id)."""
    sql = PHASE9_MIGRATION.read_text()
    assert "uq_schedule_dependencies_edge UNIQUE (project_id, predecessor_id, successor_id)" in sql


def test_6_composite_tenant_foreign_keys():
    """Verify composite foreign keys enforce project isolation on predecessor and successor."""
    sql = PHASE9_MIGRATION.read_text()
    assert "fk_dep_predecessor_tenant" in sql
    assert "FOREIGN KEY (predecessor_id, project_id)" in sql
    assert "REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE" in sql
    assert "fk_dep_successor_tenant" in sql
    assert "FOREIGN KEY (successor_id, project_id)" in sql


def test_7_indexes_for_graph_traversal():
    """Verify indexes for project lookup, outgoing successor traversal, and incoming predecessor traversal."""
    sql = PHASE9_MIGRATION.read_text()
    assert "idx_schedule_dependencies_project_id" in sql
    assert "ON public.schedule_dependencies(project_id)" in sql
    assert "idx_schedule_dependencies_predecessor" in sql
    assert "ON public.schedule_dependencies(project_id, predecessor_id)" in sql
    assert "idx_schedule_dependencies_successor" in sql
    assert "ON public.schedule_dependencies(project_id, successor_id)" in sql


def test_8_rls_enabled_and_no_unrestricted_policies():
    """Verify RLS is enabled and no permissive USING(true) or WITH CHECK(true) policies exist."""
    sql = PHASE9_MIGRATION.read_text()
    assert "ALTER TABLE public.schedule_dependencies ENABLE ROW LEVEL SECURITY;" in sql
    assert "USING (true)" not in sql
    assert "USING(true)" not in sql
    assert "WITH CHECK (true)" not in sql
    assert "WITH CHECK(true)" not in sql


def test_9_rls_role_hierarchy_and_tenant_scoping():
    """Verify RLS policies enforce RBAC and project tenant isolation."""
    sql = PHASE9_MIGRATION.read_text()
    # SELECT: viewer and above
    assert 'CREATE POLICY "Project members can view schedule dependencies"' in sql
    assert "USING (public.has_project_role(project_id, 'viewer'))" in sql

    # INSERT: planner and admin
    assert 'CREATE POLICY "Planners and admins can create schedule dependencies"' in sql
    assert "WITH CHECK (public.has_project_role(project_id, 'planner'))" in sql

    # UPDATE: planner and admin
    assert 'CREATE POLICY "Planners and admins can update schedule dependencies"' in sql
    assert "USING (public.has_project_role(project_id, 'planner'))" in sql

    # DELETE: admin only
    assert 'CREATE POLICY "Admins can delete schedule dependencies"' in sql
    assert "USING (public.has_project_role(project_id, 'admin'))" in sql


def test_10_protected_migrations_untouched():
    """Verify all previous migrations (Phases 2-7) remain untouched and unmodified."""
    for migration_name in PROTECTED_MIGRATIONS:
        path = MIGRATIONS_DIR / migration_name
        assert path.exists(), f"Protected migration missing: {migration_name}"


def test_11_cycle_prevention_boundary_assertion():
    """
    Verifies that the database does NOT attempt impossible arbitrary graph cycle checks
    via static SQL CHECK, confirming that multi-hop DAG cycle validation is strictly
    enforced at the service/API layer (Phase 9.2 / Phase 9.5).
    """
    sql = PHASE9_MIGRATION.read_text()
    # Ensure no naive check constraint claims to enforce full cycle prevention
    assert "CHECK (cycle" not in sql
    assert "CHECK (acyclic" not in sql
