-- SiteSync AI — Phase 2: Authentication + Authorization Foundation Schema & RLS
-- Minimal schema: profiles, projects, project_members

-- 1. Create custom project role enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_role') THEN
        CREATE TYPE project_role AS ENUM ('admin', 'planner', 'supervisor', 'viewer');
    END IF;
END $$;

-- 2. Profiles table (linked to Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Index on email
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);

-- 3. Projects table
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    description TEXT,
    created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Index on project code
CREATE INDEX IF NOT EXISTS idx_projects_code ON public.projects(code);

-- 4. Project Members table (User <-> Project relationship with explicit role)
CREATE TABLE IF NOT EXISTS public.project_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role project_role NOT NULL DEFAULT 'viewer'::project_role,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_project_members_project_user UNIQUE (project_id, user_id)
);

-- Indices for member lookups
CREATE INDEX IF NOT EXISTS idx_project_members_user_id ON public.project_members(user_id);
CREATE INDEX IF NOT EXISTS idx_project_members_project_id ON public.project_members(project_id);

-- 5. Trigger for automatic profile creation upon auth.users signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', '')
    )
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        full_name = EXCLUDED.full_name,
        updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger execution
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 6. Enable Row-Level Security (RLS) on all Phase 2 tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_members ENABLE ROW LEVEL SECURITY;

-- 7. Profiles RLS Policies
-- Users can view their own profile or profiles of members sharing a project
DROP POLICY IF EXISTS "Users can view own profile or teammates" ON public.profiles;
CREATE POLICY "Users can view own profile or teammates"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (
        auth.uid() = id
        OR EXISTS (
            SELECT 1 FROM public.project_members pm_me
            JOIN public.project_members pm_them ON pm_me.project_id = pm_them.project_id
            WHERE pm_me.user_id = auth.uid()
              AND pm_them.user_id = public.profiles.id
        )
    );

-- Users can update only their own profile
DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- 8. Projects RLS Policies
-- Users can only view projects of which they are explicit members
DROP POLICY IF EXISTS "Members can view authorized projects" ON public.projects;
CREATE POLICY "Members can view authorized projects"
    ON public.projects FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.projects.id
              AND pm.user_id = auth.uid()
        )
    );

-- Authenticated users can insert a new project if they are set as creator
DROP POLICY IF EXISTS "Authenticated users can create projects" ON public.projects;
CREATE POLICY "Authenticated users can create projects"
    ON public.projects FOR INSERT
    TO authenticated
    WITH CHECK (
        auth.uid() IS NOT NULL
        AND created_by = auth.uid()
    );

-- Only project admins can update project details
DROP POLICY IF EXISTS "Admins can update project" ON public.projects;
CREATE POLICY "Admins can update project"
    ON public.projects FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.projects.id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- Only project admins can delete a project
DROP POLICY IF EXISTS "Admins can delete project" ON public.projects;
CREATE POLICY "Admins can delete project"
    ON public.projects FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.projects.id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- 9. Project Members RLS Policies
-- Users can view membership records for projects they belong to
DROP POLICY IF EXISTS "Members can view project membership" ON public.project_members;
CREATE POLICY "Members can view project membership"
    ON public.project_members FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.project_members.project_id
              AND pm.user_id = auth.uid()
        )
    );

-- Only project admins can add new members to a project
DROP POLICY IF EXISTS "Admins can insert project members" ON public.project_members;
CREATE POLICY "Admins can insert project members"
    ON public.project_members FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.project_members.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- Only project admins can update member roles
DROP POLICY IF EXISTS "Admins can update project members" ON public.project_members;
CREATE POLICY "Admins can update project members"
    ON public.project_members FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.project_members.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );

-- Only project admins can remove project members
DROP POLICY IF EXISTS "Admins can remove project members" ON public.project_members;
CREATE POLICY "Admins can remove project members"
    ON public.project_members FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.project_members pm
            WHERE pm.project_id = public.project_members.project_id
              AND pm.user_id = auth.uid()
              AND pm.role = 'admin'::project_role
        )
    );
