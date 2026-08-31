-- SiteSync AI — Phase 5: AI Extractions Foundation Schema & Multi-Tenant RLS
-- Creates ai_extractions table, extraction_status enum, indices, and RLS policies.
-- Invariant: Extraction writes are server-generated; client RLS provides project-scoped SELECT and Admin-only DELETE.

-- 1. Create Enum for Extraction Status
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'extraction_status') THEN
        CREATE TYPE extraction_status AS ENUM ('pending', 'completed', 'failed');
    END IF;
END $$;

-- 2. AI Extractions Table (Structured entities extracted by AI from raw field_inputs)
CREATE TABLE IF NOT EXISTS public.ai_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    field_input_id UUID NOT NULL REFERENCES public.field_inputs(id) ON DELETE CASCADE,
    status extraction_status NOT NULL DEFAULT 'pending'::extraction_status,
    extracted_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_score NUMERIC(4, 3),
    model_version TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    -- Integrity Constraints
    CONSTRAINT chk_ai_extractions_confidence CHECK (
        (confidence_score IS NULL) OR ((confidence_score >= 0.0) AND (confidence_score <= 1.0))
    )
);

-- 3. Indices on ai_extractions
CREATE INDEX IF NOT EXISTS idx_ai_extractions_project_id ON public.ai_extractions(project_id);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_field_input_id ON public.ai_extractions(field_input_id);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_status ON public.ai_extractions(status);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_created_at ON public.ai_extractions(created_at DESC);

-- 4. Enable Row-Level Security on Table
ALTER TABLE public.ai_extractions ENABLE ROW LEVEL SECURITY;

-- 5. AI Extractions Table RLS Policies

-- SELECT: Authenticated project members can view AI extractions in their assigned projects
DROP POLICY IF EXISTS "Members can view project ai extractions" ON public.ai_extractions;
CREATE POLICY "Members can view project ai extractions"
    ON public.ai_extractions FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.ai_extractions.project_id
              AND pm.user_id = auth.uid()
        )
    );

-- DELETE: Only Project Admins can delete AI extraction records
DROP POLICY IF EXISTS "Admins can delete ai extractions" ON public.ai_extractions;
CREATE POLICY "Admins can delete ai extractions"
    ON public.ai_extractions FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.ai_extractions.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- NOTE ON INSERT / UPDATE:
-- Client-side direct INSERT and UPDATE are closed by default (fail closed).
-- AI extractions are generated exclusively through trusted server-side AI processing (FastAPI backend),
-- preventing client tampering or unauthorized forgery of structured extraction claims.
