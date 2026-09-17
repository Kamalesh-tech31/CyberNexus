-- ============================================================================
-- CYBERNEXUS
-- PRODUCTION SUPABASE / POSTGRESQL SCHEMA
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. UPDATED_AT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


-- ============================================================================
-- 2. PUBLIC USERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS display_name TEXT;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();


-- ============================================================================
-- 3. REMOVE ONLY THE PHASE 6F-1 PLACEHOLDER USER
--
-- This is the known foundation placeholder, not a real authenticated user.
-- Do NOT delete arbitrary users here.
-- ============================================================================

DELETE FROM public.users
WHERE id = '00000000-0000-0000-0000-000000000001';


-- ============================================================================
-- 4. ENSURE USERS -> AUTH.USERS FOREIGN KEY
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_id_fkey'
          AND conrelid = 'public.users'::regclass
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_id_fkey
            FOREIGN KEY (id)
            REFERENCES auth.users(id)
            ON DELETE CASCADE;
    END IF;
END
$$;


-- ============================================================================
-- 5. USER ROLE VALIDATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_role_check'
          AND conrelid = 'public.users'::regclass
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_role_check
            CHECK (role IN ('user', 'admin', 'guest', 'researcher'));
    END IF;
END
$$;


-- ============================================================================
-- 6. USERS UPDATED_AT TRIGGER
-- ============================================================================

DROP TRIGGER IF EXISTS trg_users_updated_at
ON public.users;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- ============================================================================
-- 7. ANALYSIS SESSIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analysis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES public.users(id)
        ON DELETE CASCADE,

    title TEXT NOT NULL DEFAULT 'New Security Analysis',

    channel TEXT NOT NULL
        CHECK (channel IN ('sms', 'email', 'url', 'qr')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- 8. ANALYSIS SESSIONS UPDATED_AT
-- ============================================================================

DROP TRIGGER IF EXISTS trg_analysis_sessions_updated_at
ON public.analysis_sessions;

CREATE TRIGGER trg_analysis_sessions_updated_at
BEFORE UPDATE ON public.analysis_sessions
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- ============================================================================
-- 9. ANALYSIS MESSAGES
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analysis_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_id UUID NOT NULL
        REFERENCES public.analysis_sessions(id)
        ON DELETE CASCADE,

    role TEXT NOT NULL
        CHECK (role IN ('user', 'assistant')),

    input JSONB NOT NULL DEFAULT '{}'::jsonb,

    result JSONB NOT NULL DEFAULT '{}'::jsonb,

    explanation JSONB NOT NULL DEFAULT '{}'::jsonb,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- 10. INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user_id
ON public.analysis_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user_id_created_at
ON public.analysis_sessions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_messages_session_id
ON public.analysis_messages(session_id);

CREATE INDEX IF NOT EXISTS idx_analysis_messages_session_id_created_at
ON public.analysis_messages(session_id, created_at ASC);


-- ============================================================================
-- 11. ENABLE RLS
-- ============================================================================

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.analysis_sessions ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.analysis_messages ENABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 12. USERS RLS
-- ============================================================================

DROP POLICY IF EXISTS "users_select_own"
ON public.users;

CREATE POLICY "users_select_own"
ON public.users
FOR SELECT
TO authenticated
USING (auth.uid() = id);


DROP POLICY IF EXISTS "users_insert_own"
ON public.users;

CREATE POLICY "users_insert_own"
ON public.users
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = id);


DROP POLICY IF EXISTS "users_update_own"
ON public.users;

CREATE POLICY "users_update_own"
ON public.users
FOR UPDATE
TO authenticated
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);


-- ============================================================================
-- 13. ANALYSIS SESSIONS RLS
-- ============================================================================

DROP POLICY IF EXISTS "sessions_select_own"
ON public.analysis_sessions;

CREATE POLICY "sessions_select_own"
ON public.analysis_sessions
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);


DROP POLICY IF EXISTS "sessions_insert_own"
ON public.analysis_sessions;

CREATE POLICY "sessions_insert_own"
ON public.analysis_sessions
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);


DROP POLICY IF EXISTS "sessions_update_own"
ON public.analysis_sessions;

CREATE POLICY "sessions_update_own"
ON public.analysis_sessions
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);


DROP POLICY IF EXISTS "sessions_delete_own"
ON public.analysis_sessions;

CREATE POLICY "sessions_delete_own"
ON public.analysis_sessions
FOR DELETE
TO authenticated
USING (auth.uid() = user_id);


-- ============================================================================
-- 14. ANALYSIS MESSAGES RLS
-- ============================================================================

DROP POLICY IF EXISTS "messages_select_own"
ON public.analysis_messages;

CREATE POLICY "messages_select_own"
ON public.analysis_messages
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.analysis_sessions s
        WHERE s.id = analysis_messages.session_id
          AND s.user_id = auth.uid()
    )
);


DROP POLICY IF EXISTS "messages_insert_own"
ON public.analysis_messages;

CREATE POLICY "messages_insert_own"
ON public.analysis_messages
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.analysis_sessions s
        WHERE s.id = analysis_messages.session_id
          AND s.user_id = auth.uid()
    )
);


DROP POLICY IF EXISTS "messages_update_own"
ON public.analysis_messages;

CREATE POLICY "messages_update_own"
ON public.analysis_messages
FOR UPDATE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.analysis_sessions s
        WHERE s.id = analysis_messages.session_id
          AND s.user_id = auth.uid()
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.analysis_sessions s
        WHERE s.id = analysis_messages.session_id
          AND s.user_id = auth.uid()
    )
);


DROP POLICY IF EXISTS "messages_delete_own"
ON public.analysis_messages;

CREATE POLICY "messages_delete_own"
ON public.analysis_messages
FOR DELETE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.analysis_sessions s
        WHERE s.id = analysis_messages.session_id
          AND s.user_id = auth.uid()
    )
);


-- ============================================================================
-- 15. AUTOMATIC PROFILE CREATION AFTER SUPABASE SIGNUP
-- ============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (
        id,
        email,
        display_name,
        role
    )
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NEW.raw_user_meta_data->>'display_name',
            NEW.raw_user_meta_data->>'full_name',
            split_part(COALESCE(NEW.email, ''), '@', 1)
        ),
        'user'
    )
    ON CONFLICT (id)
    DO UPDATE SET
        email = EXCLUDED.email,
        updated_at = NOW();

    RETURN NEW;
END;
$$;


-- ============================================================================
-- 16. AUTH USER -> PUBLIC USER TRIGGER
-- ============================================================================

DROP TRIGGER IF EXISTS on_auth_user_created
ON auth.users;

CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_user();


-- ============================================================================
-- END OF CYBERNEXUS PHASE 6F-2A SCHEMA
-- ============================================================================