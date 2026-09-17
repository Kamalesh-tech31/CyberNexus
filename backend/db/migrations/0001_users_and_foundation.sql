-- ============================================================================
-- CYBERNEXUS — PHASE 6F-1 MIGRATION: 0001_users_and_foundation.sql
-- Database Foundation: Users/profiles identity & minimal analysis foundation test table.
-- ============================================================================

-- 1. Users / Profiles Table (Identity Foundation)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Foundation Table for Future Analysis Ownership Verification
-- Note: This is a minimal foundation test table establishing foreign-key user ownership.
-- Full ML analysis result columns (prediction, confidence, feature contributions) belong to Phase 6F-2.
CREATE TABLE IF NOT EXISTS public.analysis_foundation_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'test_active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for user ownership lookups
CREATE INDEX IF NOT EXISTS idx_analysis_foundation_test_user_id 
    ON public.analysis_foundation_test(user_id);

-- 3. Insert Stable Placeholder Development User Identity
-- PLACEHOLDER / TEMPORARY — REPLACED BY REAL AUTH USER ID IN PHASE 6F-5.
INSERT INTO public.users (id, email, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'placeholder@cybernexus.local',
    'guest'
)
ON CONFLICT (id) DO UPDATE 
SET updated_at = NOW();
