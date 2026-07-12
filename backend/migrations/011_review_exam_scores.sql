-- Review scores (per-vocab + wallet) and exam attempt history.
-- Run in Supabase SQL Editor after previous migrations.

-- -----------------------------------------------------------------------------
-- user_vocab_progress: familiarity score + view bonus tracking
-- -----------------------------------------------------------------------------

ALTER TABLE public.user_vocab_progress
    ADD COLUMN IF NOT EXISTS review_score REAL NOT NULL DEFAULT 0
        CHECK (review_score >= 0 AND review_score <= 100),
    ADD COLUMN IF NOT EXISTS times_reviewed INTEGER NOT NULL DEFAULT 0
        CHECK (times_reviewed >= 0),
    ADD COLUMN IF NOT EXISTS last_viewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_view_bonus_date DATE;

CREATE INDEX IF NOT EXISTS idx_user_vocab_progress_review_score
    ON public.user_vocab_progress (user_id, review_score);

-- -----------------------------------------------------------------------------
-- users: cumulative review wallet
-- -----------------------------------------------------------------------------

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS review_points INTEGER NOT NULL DEFAULT 0
        CHECK (review_points >= 0);

-- -----------------------------------------------------------------------------
-- exam_attempts: persisted quiz/exam sessions (vocab | grammar)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.exam_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    subject         TEXT NOT NULL CHECK (subject IN ('vocab', 'grammar')),
    mode            TEXT NOT NULL,
    correct_count   INTEGER NOT NULL DEFAULT 0 CHECK (correct_count >= 0),
    total_count     INTEGER NOT NULL DEFAULT 0 CHECK (total_count >= 0),
    score_percent   REAL NOT NULL DEFAULT 0 CHECK (score_percent >= 0 AND score_percent <= 100),
    detail          JSONB NOT NULL DEFAULT '{}'::jsonb,
    completed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exam_attempts_user_subject
    ON public.exam_attempts (user_id, subject, completed_at DESC);

ALTER TABLE public.exam_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "exam_attempts_all_own" ON public.exam_attempts;
CREATE POLICY "exam_attempts_all_own"
    ON public.exam_attempts FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

COMMENT ON TABLE public.exam_attempts IS
    'Quiz/exam session results. subject=vocab|grammar; does not mutate review scores.';
COMMENT ON COLUMN public.users.review_points IS
    'Cumulative review wallet points (flashcards + library views).';
COMMENT ON COLUMN public.user_vocab_progress.review_score IS
    'Per-word familiarity 0-100 used for low-score-first sampling.';
