-- SiteSync AI — Phase 4: Field Inputs Foundation Schema & Storage Security
-- Creates field_inputs table, enums, indices, and multi-tenant Row-Level Security (RLS)
-- Establishes private 'field-inputs' Supabase Storage bucket with project-scoped RLS policies.

-- 1. Create Enums for Field Inputs
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'field_input_type') THEN
        CREATE TYPE field_input_type AS ENUM ('text', 'voice', 'photo', 'document');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transcription_status') THEN
        CREATE TYPE transcription_status AS ENUM ('none', 'pending', 'completed', 'failed');
    END IF;
END $$;

-- 2. Field Inputs Table (Raw unstructured progress submissions)
CREATE TABLE IF NOT EXISTS public.field_inputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    submitted_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    input_type field_input_type NOT NULL,
    title TEXT,
    raw_text TEXT,
    media_path TEXT,
    media_filename TEXT,
    media_mime_type TEXT,
    media_size_bytes INTEGER NOT NULL DEFAULT 0,
    audio_duration_seconds NUMERIC(6, 2),
    transcription_status transcription_status NOT NULL DEFAULT 'none'::transcription_status,
    transcription_error TEXT,
    field_date DATE NOT NULL DEFAULT CURRENT_DATE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    -- Integrity Constraints
    CONSTRAINT chk_field_inputs_media_size CHECK (media_size_bytes >= 0),
    CONSTRAINT chk_field_inputs_audio_duration CHECK (audio_duration_seconds IS NULL OR audio_duration_seconds >= 0),
    CONSTRAINT chk_field_inputs_content_validity CHECK (
        (input_type = 'text' AND raw_text IS NOT NULL AND length(trim(raw_text)) > 0) OR
        (input_type IN ('voice', 'photo', 'document') AND media_path IS NOT NULL AND length(trim(media_path)) > 0)
    )
);

-- 3. Indices on field_inputs
CREATE INDEX IF NOT EXISTS idx_field_inputs_project_id ON public.field_inputs(project_id);
CREATE INDEX IF NOT EXISTS idx_field_inputs_submitted_by ON public.field_inputs(submitted_by);
CREATE INDEX IF NOT EXISTS idx_field_inputs_input_type ON public.field_inputs(input_type);
CREATE INDEX IF NOT EXISTS idx_field_inputs_field_date ON public.field_inputs(field_date);
CREATE INDEX IF NOT EXISTS idx_field_inputs_created_at ON public.field_inputs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_field_inputs_transcription ON public.field_inputs(transcription_status);

-- 4. Enable Row-Level Security on Table
ALTER TABLE public.field_inputs ENABLE ROW LEVEL SECURITY;

-- 5. Field Inputs Table RLS Policies
-- SELECT: Authenticated members can view field inputs in their authorized projects
DROP POLICY IF EXISTS "Members can view project field inputs" ON public.field_inputs;
CREATE POLICY "Members can view project field inputs"
    ON public.field_inputs FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_inputs.project_id
              AND pm.user_id = auth.uid()
        )
    );

-- INSERT: Supervisors, Planners, and Admins can submit field inputs
DROP POLICY IF EXISTS "Supervisors and above can insert field inputs" ON public.field_inputs;
CREATE POLICY "Supervisors and above can insert field inputs"
    ON public.field_inputs FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_inputs.project_id
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role, 'supervisor'::project_role)
        )
    );

-- UPDATE: Planners and Admins can update field input records (e.g. metadata/notes)
DROP POLICY IF EXISTS "Planners and admins can update field inputs" ON public.field_inputs;
CREATE POLICY "Planners and admins can update field inputs"
    ON public.field_inputs FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_inputs.project_id
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role)
        )
    );

-- DELETE: Only Project Admins can delete field inputs
DROP POLICY IF EXISTS "Admins can delete field inputs" ON public.field_inputs;
CREATE POLICY "Admins can delete field inputs"
    ON public.field_inputs FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_inputs.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- 6. Private Supabase Storage Bucket Setup
-- Bucket: 'field-inputs' (public: false)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'field-inputs',
    'field-inputs',
    false,
    26214400, -- 25 MB limit
    ARRAY[
        'image/jpeg', 'image/png', 'image/webp',
        'audio/webm', 'audio/mp4', 'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/x-m4a', 'audio/m4a',
        'application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv'
    ]::text[]
)
ON CONFLICT (id) DO UPDATE
SET public = false,
    file_size_limit = 26214400;

-- 7. Supabase Storage RLS Policies for 'field-inputs'
-- Storage Object Path Scheme: projects/{project_id}/inputs/{input_id}/{safe_filename}
-- Path extraction: (storage.foldername(name))[2] represents the project_id UUID

-- Storage SELECT: Project members can access storage objects in their project path
DROP POLICY IF EXISTS "Project members can read field input files" ON storage.objects;
CREATE POLICY "Project members can read field input files"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'field-inputs'
        AND EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id::text = (storage.foldername(name))[2]
              AND pm.user_id = auth.uid()
        )
    );

-- Storage INSERT: Supervisors, Planners, and Admins can upload storage objects in their project path
DROP POLICY IF EXISTS "Supervisors and above can upload field input files" ON storage.objects;
CREATE POLICY "Supervisors and above can upload field input files"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (
        bucket_id = 'field-inputs'
        AND EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id::text = (storage.foldername(name))[2]
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role, 'supervisor'::project_role)
        )
    );

-- Storage DELETE: Only Project Admins can delete storage objects in their project path
DROP POLICY IF EXISTS "Admins can delete field input files" ON storage.objects;
CREATE POLICY "Admins can delete field input files"
    ON storage.objects FOR DELETE
    TO authenticated
    USING (
        bucket_id = 'field-inputs'
        AND EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id::text = (storage.foldername(name))[2]
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );
