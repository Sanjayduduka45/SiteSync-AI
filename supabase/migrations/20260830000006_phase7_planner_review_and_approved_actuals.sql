-- SiteSync AI — Phase 7.1 Database Foundation Migration
-- Description: Establishes planner_decision_type enum, planner_decisions (append-only audit log),
--              and approved_actuals with strict multi-tenant RLS, composite foreign keys, and idempotency.

-- 1. Create planner_decision_type enum
DO $$ BEGIN
    CREATE TYPE planner_decision_type AS ENUM ('approved', 'rejected', 'modified');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 2. Supporting composite uniqueness on ai_matches for tenant-safe foreign keys
ALTER TABLE public.ai_matches
    ADD CONSTRAINT uq_ai_matches_id_project UNIQUE (id, project_id);

-- ==============================================================================
-- 3. TABLE: public.planner_decisions
-- ==============================================================================
-- Append-only audit trail of human planner decisions on AI match recommendations.
CREATE TABLE public.planner_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    match_id UUID NOT NULL,
    extraction_id UUID NOT NULL,
    decision planner_decision_type NOT NULL,
    decided_by UUID NOT NULL REFERENCES public.profiles(id),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    rejection_reason TEXT NULL,
    original_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    modified_payload JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_planner_decisions_match_tenant FOREIGN KEY (match_id, project_id)
        REFERENCES public.ai_matches(id, project_id) ON DELETE CASCADE,
    CONSTRAINT fk_planner_decisions_extraction_tenant FOREIGN KEY (extraction_id, project_id)
        REFERENCES public.ai_extractions(id, project_id) ON DELETE CASCADE
);

-- Indexes for planner_decisions
CREATE INDEX idx_planner_decisions_project_id ON public.planner_decisions(project_id);
CREATE INDEX idx_planner_decisions_match_id ON public.planner_decisions(match_id);
CREATE INDEX idx_planner_decisions_extraction_id ON public.planner_decisions(extraction_id);
CREATE INDEX idx_planner_decisions_decided_by ON public.planner_decisions(decided_by);

-- Enable RLS on planner_decisions
ALTER TABLE public.planner_decisions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for planner_decisions (Append-only audit trail: no UPDATE or DELETE policies)
CREATE POLICY "Project members can view planner decisions"
    ON public.planner_decisions
    FOR SELECT
    USING (public.has_project_role(project_id, 'viewer'));

CREATE POLICY "Planners and admins can create planner decisions"
    ON public.planner_decisions
    FOR INSERT
    WITH CHECK (public.has_project_role(project_id, 'planner'));

-- ==============================================================================
-- 4. TABLE: public.approved_actuals
-- ==============================================================================
-- Official, immutable construction progress records approved by human planners.
CREATE TABLE public.approved_actuals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    schedule_activity_id UUID NOT NULL,
    extraction_id UUID NOT NULL,
    match_id UUID NOT NULL,
    activity_index INTEGER NOT NULL DEFAULT 0 CHECK (activity_index >= 0),
    actual_quantity NUMERIC NULL CHECK (actual_quantity >= 0),
    actual_unit TEXT NULL,
    actual_date DATE NOT NULL,
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_by UUID NOT NULL REFERENCES public.profiles(id),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    notes TEXT NULL,
    is_modified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_approved_actuals_project_extraction_activity UNIQUE (project_id, extraction_id, activity_index),
    CONSTRAINT fk_approved_actuals_project FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_approved_actuals_activity_tenant FOREIGN KEY (schedule_activity_id, project_id)
        REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE,
    CONSTRAINT fk_approved_actuals_extraction_tenant FOREIGN KEY (extraction_id, project_id)
        REFERENCES public.ai_extractions(id, project_id) ON DELETE CASCADE,
    CONSTRAINT fk_approved_actuals_match_tenant FOREIGN KEY (match_id, project_id)
        REFERENCES public.ai_matches(id, project_id) ON DELETE CASCADE
);

-- Indexes for approved_actuals
CREATE INDEX idx_approved_actuals_project_id ON public.approved_actuals(project_id);
CREATE INDEX idx_approved_actuals_schedule_activity_id ON public.approved_actuals(schedule_activity_id);
CREATE INDEX idx_approved_actuals_extraction_id ON public.approved_actuals(extraction_id);
CREATE INDEX idx_approved_actuals_match_id ON public.approved_actuals(match_id);
CREATE INDEX idx_approved_actuals_approved_by ON public.approved_actuals(approved_by);
CREATE INDEX idx_approved_actuals_actual_date ON public.approved_actuals(actual_date);

-- Enable RLS on approved_actuals
ALTER TABLE public.approved_actuals ENABLE ROW LEVEL SECURITY;

-- RLS Policies for approved_actuals
CREATE POLICY "Project members can view approved actuals"
    ON public.approved_actuals
    FOR SELECT
    USING (public.has_project_role(project_id, 'viewer'));

CREATE POLICY "Planners and admins can create approved actuals"
    ON public.approved_actuals
    FOR INSERT
    WITH CHECK (public.has_project_role(project_id, 'planner'));

CREATE POLICY "Planners and admins can update approved actuals"
    ON public.approved_actuals
    FOR UPDATE
    USING (public.has_project_role(project_id, 'planner'))
    WITH CHECK (public.has_project_role(project_id, 'planner'));

CREATE POLICY "Admins can delete approved actuals"
    ON public.approved_actuals
    FOR DELETE
    USING (public.has_project_role(project_id, 'admin'));
