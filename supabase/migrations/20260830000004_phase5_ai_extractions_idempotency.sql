-- ==============================================================================
-- Migration: 20260830000004_phase5_ai_extractions_idempotency.sql
-- Description: Phase 5.5 Database Hardening — Concurrency-Safe Idempotency
-- Enforces a unique constraint on public.ai_extractions (project_id, field_input_id)
-- enabling atomic PostgreSQL ON CONFLICT / PostgREST upsert semantics.
-- ==============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_ai_extractions_project_input'
    ) THEN
        ALTER TABLE public.ai_extractions
        ADD CONSTRAINT uq_ai_extractions_project_input
        UNIQUE (project_id, field_input_id);
    END IF;
END $$;
