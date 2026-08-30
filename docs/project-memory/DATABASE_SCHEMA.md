# DATABASE SCHEMA — SiteSync AI

> Database platform: **Supabase PostgreSQL** with **pgvector**
> Current active phase: **Phase 2 — Authentication + Authorization Foundation**

---

## Overview

SiteSync AI enforces multi-tenant project isolation using explicit PostgreSQL Row-Level Security (RLS) policies.
Phase 2 establishes the identity, project, and membership boundary.

---

## Enums

### `project_role`
Defines project-level authorization roles.

```sql
CREATE TYPE project_role AS ENUM ('admin', 'planner', 'supervisor', 'viewer');
```

Role Hierarchy:
1. `admin`: Full project administrative privileges (members, project settings, all project data).
2. `planner`: Schedule management, AI match review, variance analysis, plan-vs-actual approval.
3. `supervisor`: Field input review, site activity tracking, progress submission review.
4. `viewer`: Read-only access to authorized project data.

---

## Tables

### 1. `public.profiles`
User profile information linked directly to `auth.users`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE` | Supabase Auth User ID |
| `email` | `TEXT` | `NOT NULL` | User email address |
| `full_name` | `TEXT` | `NULL` | User display name |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last update timestamp |

**Indices:**
- `idx_profiles_email` ON `email`

**RLS Policies:**
- **SELECT**: Users can read their own profile or profiles of members sharing a mutual project.
- **UPDATE**: Users can update their own profile only (`auth.uid() = id`).
- **INSERT/DELETE**: Restricted; managed via automated trigger on `auth.users`.

---

### 2. `public.projects`
Project registry and metadata.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique project identifier |
| `name` | `TEXT` | `NOT NULL` | Human-readable project name |
| `code` | `TEXT` | `UNIQUE NOT NULL` | Unique project code / identifier |
| `description` | `TEXT` | `NULL` | Project description |
| `created_by` | `UUID` | `REFERENCES public.profiles(id) ON DELETE SET NULL` | Creator profile ID |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last update timestamp |

**Indices:**
- `idx_projects_code` ON `code`

**RLS Policies:**
- **SELECT**: Only users with an active record in `project_members` for this project.
- **INSERT**: Authenticated users can create a project (`created_by = auth.uid()`).
- **UPDATE**: Only project members with `role = 'admin'`.
- **DELETE**: Only project members with `role = 'admin'`.

---

### 3. `public.project_members`
Many-to-many relationship defining user membership and role within each project.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique membership ID |
| `project_id` | `UUID` | `NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE` | Associated project ID |
| `user_id` | `UUID` | `NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE` | Associated profile ID |
| `role` | `project_role` | `NOT NULL DEFAULT 'viewer'` | Member role within project |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Joined timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc', now())` | Last updated timestamp |

**Constraints:**
- `uq_project_members_project_user`: `UNIQUE(project_id, user_id)`

**Indices:**
- `idx_project_members_user_id` ON `user_id`
- `idx_project_members_project_id` ON `project_id`

**RLS Policies:**
- **SELECT**: Members can view member lists of projects they belong to.
- **INSERT**: Only project members with `role = 'admin'` for that project.
- **UPDATE**: Only project members with `role = 'admin'` for that project.
- **DELETE**: Only project members with `role = 'admin'` for that project.

---

## Security Invariants

1. No table in `public` schema may have RLS disabled.
2. Cross-project data access is strictly prohibited by RLS and API middleware.
3. Client-supplied role or user ID is never trusted by backend API operations.
