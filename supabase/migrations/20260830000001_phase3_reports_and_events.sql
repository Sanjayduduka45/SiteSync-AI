-- SiteSync AI — Phase 3: Reports and Field Events Foundation Migration
-- Creates reports and field_events tables with explicit Row-Level Security (RLS)

-- 1. Create Enums for Reports and Field Events
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'report_status') THEN
        CREATE TYPE report_status AS ENUM ('uploaded', 'processing', 'processed', 'failed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'field_event_status') THEN
        CREATE TYPE field_event_status AS ENUM (
            'pending',
            'processed',
            'matched',
            'needs_review',
            'approved',
            'rejected'
        );
    END IF;
END $$;

-- 2. Reports Table
CREATE TABLE IF NOT EXISTS public.reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual_upload',
    status report_status NOT NULL DEFAULT 'uploaded'::report_status,
    uploaded_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Indices on reports
CREATE INDEX IF NOT EXISTS idx_reports_project_id ON public.reports(project_id);
CREATE INDEX IF NOT EXISTS idx_reports_uploaded_by ON public.reports(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_reports_status ON public.reports(status);

-- 3. Field Events Table
CREATE TABLE IF NOT EXISTS public.field_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    report_id UUID REFERENCES public.reports(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    discipline TEXT NOT NULL,
    location TEXT NOT NULL,
    event_date DATE NOT NULL,
    progress_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.00 CHECK (progress_percent >= 0 AND progress_percent <= 100),
    status field_event_status NOT NULL DEFAULT 'pending'::field_event_status,
    extracted_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Indices on field_events
CREATE INDEX IF NOT EXISTS idx_field_events_project_id ON public.field_events(project_id);
CREATE INDEX IF NOT EXISTS idx_field_events_report_id ON public.field_events(report_id);
CREATE INDEX IF NOT EXISTS idx_field_events_discipline ON public.field_events(discipline);
CREATE INDEX IF NOT EXISTS idx_field_events_event_date ON public.field_events(event_date);
CREATE INDEX IF NOT EXISTS idx_field_events_status ON public.field_events(status);

-- 4. Enable Row-Level Security (RLS) on Phase 3 Tables
ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.field_events ENABLE ROW LEVEL SECURITY;

-- 5. Reports RLS Policies
-- SELECT: Project members can view all reports belonging to their authorized projects
DROP POLICY IF EXISTS "Members can view project reports" ON public.reports;
CREATE POLICY "Members can view project reports"
    ON public.reports FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.reports.project_id
              AND pm.user_id = auth.uid()
        )
    );

-- INSERT: Project members with role 'admin', 'planner', or 'supervisor' can upload reports
DROP POLICY IF EXISTS "Supervisors and above can insert reports" ON public.reports;
CREATE POLICY "Supervisors and above can insert reports"
    ON public.reports FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.reports.project_id
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role, 'supervisor'::project_role)
        )
    );

-- UPDATE: Project members with role 'admin' or 'planner' can update reports
DROP POLICY IF EXISTS "Planners and admins can update reports" ON public.reports;
CREATE POLICY "Planners and admins can update reports"
    ON public.reports FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.reports.project_id
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role)
        )
    );

-- DELETE: Only project admins can delete reports
DROP POLICY IF EXISTS "Admins can delete reports" ON public.reports;
CREATE POLICY "Admins can delete reports"
    ON public.reports FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.reports.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- 6. Field Events RLS Policies
-- SELECT: Project members can view field events in their authorized projects
DROP POLICY IF EXISTS "Members can view project field events" ON public.field_events;
CREATE POLICY "Members can view project field events"
    ON public.field_events FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_events.project_id
              AND pm.user_id = auth.uid()
        )
    );

-- INSERT: Project members with role 'admin', 'planner', or 'supervisor' can create field events
DROP POLICY IF EXISTS "Supervisors and above can insert field events" ON public.field_events;
CREATE POLICY "Supervisors and above can insert field events"
    ON public.field_events FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_events.project_id
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role, 'supervisor'::project_role)
        )
    );

-- UPDATE: Project members with role 'admin' or 'planner' can update field events
DROP POLICY IF EXISTS "Planners and admins can update field events" ON public.field_events;
CREATE POLICY "Planners and admins can update field events"
    ON public.field_events FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_events.project_id
              AND pm.user_id = auth.uid()
              AND pm.role IN ('admin'::project_role, 'planner'::project_role)
        )
    );

-- DELETE: Only project admins can delete field events
DROP POLICY IF EXISTS "Admins can delete field events" ON public.field_events;
CREATE POLICY "Admins can delete field events"
    ON public.field_events FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.field_events.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );
