-- SiteSync AI — Phase 6.1 Database Foundation Migration
-- Description: Establishes pgvector extension, schedule_activities, activity_embeddings, and ai_matches
--              with strict multi-tenant RLS, composite foreign-key tenant integrity, and idempotency constraints.

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Supporting composite uniqueness on ai_extractions for tenant-safe foreign keys
ALTER TABLE public.ai_extractions
    ADD CONSTRAINT uq_ai_extractions_id_project UNIQUE (id, project_id);

-- ==============================================================================
-- 3. TABLE: public.schedule_activities
-- ==============================================================================
CREATE TABLE public.schedule_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    activity_code TEXT NOT NULL,
    name TEXT NOT NULL,
    wbs_code TEXT NULL,
    discipline TEXT NULL,
    location TEXT NULL,
    planned_start_date DATE NULL,
    planned_finish_date DATE NULL,
    planned_quantity NUMERIC NULL CHECK (planned_quantity >= 0),
    planned_unit TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_schedule_activities_project_code UNIQUE (project_id, activity_code),
    CONSTRAINT uq_schedule_activities_id_project UNIQUE (id, project_id)
);

-- Indexes for schedule_activities
CREATE INDEX idx_schedule_activities_project_id ON public.schedule_activities(project_id);
CREATE INDEX idx_schedule_activities_discipline ON public.schedule_activities(discipline);
CREATE INDEX idx_schedule_activities_dates ON public.schedule_activities(planned_start_date, planned_finish_date);

-- Enable RLS on schedule_activities
ALTER TABLE public.schedule_activities ENABLE ROW LEVEL SECURITY;

-- RLS Policies for schedule_activities
CREATE POLICY "Project members can view schedule activities"
    ON public.schedule_activities
    FOR SELECT
    USING (public.has_project_role(project_id, 'viewer'));

CREATE POLICY "Planners and admins can create schedule activities"
    ON public.schedule_activities
    FOR INSERT
    WITH CHECK (public.has_project_role(project_id, 'planner'));

CREATE POLICY "Planners and admins can update schedule activities"
    ON public.schedule_activities
    FOR UPDATE
    USING (public.has_project_role(project_id, 'planner'))
    WITH CHECK (public.has_project_role(project_id, 'planner'));

CREATE POLICY "Admins can delete schedule activities"
    ON public.schedule_activities
    FOR DELETE
    USING (public.has_project_role(project_id, 'admin'));

-- ==============================================================================
-- 4. TABLE: public.activity_embeddings
-- ==============================================================================
-- Stores dense vector embeddings (Google text-embedding-004, 768 dimensions)
-- Composite foreign key ensures the embedding's project_id matches its schedule_activity's project_id.
CREATE TABLE public.activity_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    schedule_activity_id UUID NOT NULL,
    embedding vector(768) NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_activity_embeddings_activity UNIQUE (schedule_activity_id),
    CONSTRAINT fk_activity_embeddings_project FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_activity_embeddings_activity_tenant FOREIGN KEY (schedule_activity_id, project_id)
        REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE
);

-- Index for activity_embeddings
CREATE INDEX idx_activity_embeddings_project_id ON public.activity_embeddings(project_id);

-- Enable RLS on activity_embeddings
ALTER TABLE public.activity_embeddings ENABLE ROW LEVEL SECURITY;

-- RLS Policies for activity_embeddings (Direct client writes remain closed)
CREATE POLICY "Project members can view activity embeddings"
    ON public.activity_embeddings
    FOR SELECT
    USING (public.has_project_role(project_id, 'viewer'));

-- ==============================================================================
-- 5. TABLE: public.ai_matches
-- ==============================================================================
-- Stores AI candidate schedule match recommendations for planner review.
-- Composite foreign keys guarantee that the extraction, recommended activity,
-- and match record all share the exact same project_id.
CREATE TABLE public.ai_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    extraction_id UUID NOT NULL,
    activity_index INTEGER NOT NULL DEFAULT 0 CHECK (activity_index >= 0),
    recommended_activity_id UUID NOT NULL,
    confidence_score NUMERIC(4,3) NOT NULL CHECK (
        confidence_score >= 0.0 AND confidence_score <= 1.0
    ),
    scoring_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    alternative_matches JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_ai_matches_project_extraction_activity UNIQUE (project_id, extraction_id, activity_index),
    CONSTRAINT fk_ai_matches_project FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_matches_extraction_tenant FOREIGN KEY (extraction_id, project_id)
        REFERENCES public.ai_extractions(id, project_id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_matches_recommended_activity_tenant FOREIGN KEY (recommended_activity_id, project_id)
        REFERENCES public.schedule_activities(id, project_id) ON DELETE CASCADE
);

-- Indexes for ai_matches
CREATE INDEX idx_ai_matches_project_id ON public.ai_matches(project_id);
CREATE INDEX idx_ai_matches_extraction_id ON public.ai_matches(extraction_id);
CREATE INDEX idx_ai_matches_recommended_activity_id ON public.ai_matches(recommended_activity_id);

-- Enable RLS on ai_matches
ALTER TABLE public.ai_matches ENABLE ROW LEVEL SECURITY;

-- RLS Policies for ai_matches (Direct client writes remain closed)
CREATE POLICY "Project members can view AI match recommendations"
    ON public.ai_matches
    FOR SELECT
    USING (public.has_project_role(project_id, 'viewer'));
