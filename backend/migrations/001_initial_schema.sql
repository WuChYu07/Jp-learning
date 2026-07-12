-- =============================================================================
-- Komorebi Japanese — Initial Schema Migration
-- Run in Supabase SQL Editor or via: supabase db push / migration apply
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Enums
-- -----------------------------------------------------------------------------

CREATE TYPE jlpt_level AS ENUM ('N5', 'N4', 'N3', 'N2', 'N1', 'unknown');

CREATE TYPE source_type AS ENUM ('image', 'pdf', 'manual', 'api');

CREATE TYPE part_of_speech AS ENUM (
    'noun',
    'verb',
    'i_adjective',
    'na_adjective',
    'adverb',
    'particle',
    'counter',
    'expression',
    'other'
);

-- -----------------------------------------------------------------------------
-- 0. Content Ingestion (Module 0 — upload-level dedup)
--    Stores SHA-256 of raw image bytes or extracted PDF text.
-- -----------------------------------------------------------------------------

CREATE TABLE public.content_ingestions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash    TEXT NOT NULL UNIQUE,
    source_type     source_type NOT NULL,
    mime_type       TEXT,
    file_name       TEXT,
    parsed_payload  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by      UUID REFERENCES auth.users (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.content_ingestions IS
    'Upload-level dedup cache. Same content_hash → skip Gemini, return parsed_payload.';

CREATE INDEX idx_content_ingestions_created_by ON public.content_ingestions (created_by);

-- -----------------------------------------------------------------------------
-- 1. Users (extends Supabase Auth)
-- -----------------------------------------------------------------------------

CREATE TABLE public.users (
    id                  UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    username            TEXT UNIQUE,
    display_name        TEXT,
    streak_days         INTEGER NOT NULL DEFAULT 0 CHECK (streak_days >= 0),
    tokens_balance      INTEGER NOT NULL DEFAULT 0 CHECK (tokens_balance >= 0),
    daily_ai_requests   INTEGER NOT NULL DEFAULT 0 CHECK (daily_ai_requests >= 0),
    last_request_date   DATE,
    last_active_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN public.users.daily_ai_requests IS
    'AI grading calls consumed today (Module 4). Reset when last_request_date < CURRENT_DATE.';
COMMENT ON COLUMN public.users.last_request_date IS
    'UTC date of last AI request; used to reset daily_ai_requests at day boundary.';

-- Auto-create profile row when a new auth user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (id, username, display_name)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data ->> 'username', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data ->> 'display_name', NEW.raw_user_meta_data ->> 'full_name')
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- -----------------------------------------------------------------------------
-- 2. Vocabularies (one-to-many with vocabulary_definitions)
-- -----------------------------------------------------------------------------

CREATE TABLE public.vocabularies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    word                TEXT NOT NULL,
    reading             TEXT,
    jlpt_level          jlpt_level NOT NULL DEFAULT 'unknown',
    content_hash        TEXT NOT NULL UNIQUE,
    source_type         source_type NOT NULL DEFAULT 'manual',
    ingestion_id        UUID REFERENCES public.content_ingestions (id) ON DELETE SET NULL,
    created_by          UUID REFERENCES public.users (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN public.vocabularies.content_hash IS
    'SHA-256 of normalized word+reading for per-entry dedup within ingestion.';

CREATE INDEX idx_vocabularies_jlpt_level ON public.vocabularies (jlpt_level);
CREATE INDEX idx_vocabularies_word ON public.vocabularies (word);
CREATE INDEX idx_vocabularies_created_by ON public.vocabularies (created_by);

CREATE TABLE public.vocabulary_definitions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vocabulary_id       UUID NOT NULL REFERENCES public.vocabularies (id) ON DELETE CASCADE,
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    part_of_speech      part_of_speech NOT NULL DEFAULT 'other',
    meaning_zh          TEXT NOT NULL,
    meaning_en          TEXT,
  -- [{ "japanese": "...", "reading": "...", "chinese": "...", "english": "..." }]
    example_sentences   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (vocabulary_id, sort_order)
);

CREATE INDEX idx_vocabulary_definitions_vocab_id ON public.vocabulary_definitions (vocabulary_id);

-- -----------------------------------------------------------------------------
-- 3. User Vocabulary Progress (SM-2 spaced repetition)
-- -----------------------------------------------------------------------------

CREATE TABLE public.user_vocab_progress (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    vocabulary_id       UUID NOT NULL REFERENCES public.vocabularies (id) ON DELETE CASCADE,
    easiness_factor     REAL NOT NULL DEFAULT 2.5 CHECK (easiness_factor >= 1.3),
    repetitions         INTEGER NOT NULL DEFAULT 0 CHECK (repetitions >= 0),
    interval_days       INTEGER NOT NULL DEFAULT 1 CHECK (interval_days >= 0),
    next_review_date    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_reviewed_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, vocabulary_id)
);

CREATE INDEX idx_user_vocab_progress_due
    ON public.user_vocab_progress (user_id, next_review_date);

-- -----------------------------------------------------------------------------
-- 4. Grammars (one-to-many with grammar_usages)
-- -----------------------------------------------------------------------------

CREATE TABLE public.grammars (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grammar_point       TEXT NOT NULL,
    jlpt_level          jlpt_level NOT NULL DEFAULT 'unknown',
    content_hash        TEXT NOT NULL UNIQUE,
    source_type         source_type NOT NULL DEFAULT 'manual',
    ingestion_id        UUID REFERENCES public.content_ingestions (id) ON DELETE SET NULL,
    created_by          UUID REFERENCES public.users (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_grammars_jlpt_level ON public.grammars (jlpt_level);
CREATE INDEX idx_grammars_grammar_point ON public.grammars (grammar_point);

CREATE TABLE public.grammar_usages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grammar_id          UUID NOT NULL REFERENCES public.grammars (id) ON DELETE CASCADE,
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    semantic_concept    TEXT NOT NULL,
    connection_rule     TEXT NOT NULL,
    meaning_zh          TEXT,
    meaning_en          TEXT,
  -- [{ "japanese": "...", "reading": "...", "chinese": "...", "english": "...",
  --    "acceptable_patterns": ["..."] }]
    example_sentences   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (grammar_id, sort_order)
);

CREATE INDEX idx_grammar_usages_grammar_id ON public.grammar_usages (grammar_id);

-- -----------------------------------------------------------------------------
-- 5. User Grammar Progress
-- -----------------------------------------------------------------------------

CREATE TABLE public.user_grammar_progress (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    grammar_id          UUID NOT NULL REFERENCES public.grammars (id) ON DELETE CASCADE,
    proficiency_score   REAL NOT NULL DEFAULT 0 CHECK (proficiency_score >= 0 AND proficiency_score <= 100),
    times_reviewed      INTEGER NOT NULL DEFAULT 0 CHECK (times_reviewed >= 0),
    last_reviewed_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, grammar_id)
);

CREATE INDEX idx_user_grammar_progress_user ON public.user_grammar_progress (user_id);

-- -----------------------------------------------------------------------------
-- updated_at trigger (shared)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_vocabularies_updated_at
    BEFORE UPDATE ON public.vocabularies
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_vocabulary_definitions_updated_at
    BEFORE UPDATE ON public.vocabulary_definitions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_user_vocab_progress_updated_at
    BEFORE UPDATE ON public.user_vocab_progress
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_grammars_updated_at
    BEFORE UPDATE ON public.grammars
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_grammar_usages_updated_at
    BEFORE UPDATE ON public.grammar_usages
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_user_grammar_progress_updated_at
    BEFORE UPDATE ON public.user_grammar_progress
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Row Level Security
-- -----------------------------------------------------------------------------

ALTER TABLE public.content_ingestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vocabularies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vocabulary_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_vocab_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grammars ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grammar_usages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_grammar_progress ENABLE ROW LEVEL SECURITY;

-- users: own profile only
CREATE POLICY "users_select_own"
    ON public.users FOR SELECT
    TO authenticated
    USING (auth.uid() = id);

CREATE POLICY "users_update_own"
    ON public.users FOR UPDATE
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Shared learning content: readable by all authenticated users
CREATE POLICY "vocabularies_select_authenticated"
    ON public.vocabularies FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "vocabulary_definitions_select_authenticated"
    ON public.vocabulary_definitions FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "grammars_select_authenticated"
    ON public.grammars FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "grammar_usages_select_authenticated"
    ON public.grammar_usages FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "content_ingestions_select_own"
    ON public.content_ingestions FOR SELECT
    TO authenticated
    USING (created_by = auth.uid());

-- Progress tables: user owns their rows
CREATE POLICY "user_vocab_progress_all_own"
    ON public.user_vocab_progress FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "user_grammar_progress_all_own"
    ON public.user_grammar_progress FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Inserts to shared content & ingestions go through FastAPI service role (bypasses RLS).
-- No INSERT/UPDATE policies for vocab/grammar on authenticated role by design.

-- -----------------------------------------------------------------------------
-- Helper: reset daily AI counter (called from backend before grading)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.reset_daily_ai_requests_if_needed(p_user_id UUID)
RETURNS public.users
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user public.users;
BEGIN
    SELECT * INTO v_user FROM public.users WHERE id = p_user_id FOR UPDATE;

    IF v_user.last_request_date IS NULL OR v_user.last_request_date < CURRENT_DATE THEN
        UPDATE public.users
        SET daily_ai_requests = 0,
            last_request_date = CURRENT_DATE
        WHERE id = p_user_id
        RETURNING * INTO v_user;
    END IF;

    RETURN v_user;
END;
$$;

COMMENT ON FUNCTION public.reset_daily_ai_requests_if_needed IS
    'Resets daily_ai_requests when the calendar day changes. Backend calls before AI grading.';
