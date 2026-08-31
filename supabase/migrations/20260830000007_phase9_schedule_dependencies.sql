-- SiteSync AI — Phase 9.1 Database Foundation Migration
-- Description: Establishes public.schedule_dependencies for activity dependency network
--              with strict multi-tenant RLS, composite foreign-key tenant integrity,
--              self-dependency prevention, and duplicate edge rejection.

-- ==============================================================================
-- 1. TABLE: public.schedule_dependencies
-- ==============================================================================
CREATE TABLE public.schedule_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    predecessor_id UUID NOT NULL,
    successor_id UUID NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'FS',
    lag_days INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_schedule_dependencies_rel_type CHECK (relationship_type IN ('FS', 'SS', 'FF', 'SF')),
    CONSTRAINT chk_schedule_dependencies_no_self CHECK (predecessor_id <> successor_id),
    CONSTRAINT uq_schedule_dependencies_edge UNIQUE (project_id, predecessor_id, successor_id),
    CONSTRAINT fk_dep_predecessor_tenant FOREIGN KEY (predecessor_id, project_id) 
        REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE,
    CONSTRAINT fk_dep_successor_tenant FOREIGN KEY (successor_id, project_id) 
        REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE
);

-- ==============================================================================
-- 2. INDEXES
-- ==============================================================================
CREATE INDEX idx_schedule_dependencies_project_id 
    ON public.schedule_dependencies(project_id);

CREATE INDEX idx_schedule_dependencies_predecessor 
    ON public.schedule_dependencies(project_id, predecessor_id);

CREATE INDEX idx_schedule_dependencies_successor 
    ON public.schedule_dependencies(project_id, successor_id);

-- ==============================================================================
-- 3. ROW LEVEL SECURITY (RLS)
-- ==============================================================================
ALTER TABLE public.schedule_dependencies ENABLE ROW LEVEL SECURITY;

-- SELECT: Project members (viewer role and above) can view schedule dependencies
CREATE POLICY "Project members can view schedule dependencies"
    ON public.schedule_dependencies
    FOR SELECT
    USING (public.has_project_role(project_id, 'viewer'));

-- INSERT: Planners and admins can create schedule dependencies
CREATE POLICY "Planners and admins can create schedule dependencies"
    ON public.schedule_dependencies
    FOR INSERT
    WITH CHECK (public.has_project_role(project_id, 'planner'));

-- UPDATE: Planners and admins can update schedule dependencies
CREATE POLICY "Planners and admins can update schedule dependencies"
    ON public.schedule_dependencies
    FOR UPDATE
    USING (public.has_project_role(project_id, 'planner'))
    WITH CHECK (public.has_project_role(project_id, 'planner'));

-- DELETE: Admins only can delete schedule dependencies
CREATE POLICY "Admins can delete schedule dependencies"
    ON public.schedule_dependencies
    FOR DELETE
    USING (public.has_project_role(project_id, 'admin'));
