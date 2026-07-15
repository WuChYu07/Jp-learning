-- Grammar SRS fields aligned with user_vocab_progress.
-- Run in Supabase SQL Editor after 012_singleton_owner.sql.

ALTER TABLE public.user_grammar_progress
    ADD COLUMN IF NOT EXISTS easiness_factor REAL NOT NULL DEFAULT 2.5
        CHECK (easiness_factor >= 1.3),
    ADD COLUMN IF NOT EXISTS repetitions INTEGER NOT NULL DEFAULT 0
        CHECK (repetitions >= 0),
    ADD COLUMN IF NOT EXISTS interval_days INTEGER NOT NULL DEFAULT 1
        CHECK (interval_days >= 0),
    ADD COLUMN IF NOT EXISTS next_review_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS review_score REAL NOT NULL DEFAULT 0
        CHECK (review_score >= 0 AND review_score <= 100);

-- Keep proficiency_score in sync conceptually with review_score for legacy reads.
UPDATE public.user_grammar_progress
SET review_score = LEAST(100, GREATEST(0, COALESCE(proficiency_score, 0)))
WHERE review_score = 0 AND proficiency_score IS NOT NULL AND proficiency_score > 0;

CREATE INDEX IF NOT EXISTS idx_user_grammar_progress_due
    ON public.user_grammar_progress (user_id, next_review_date);

CREATE INDEX IF NOT EXISTS idx_user_grammar_progress_review_score
    ON public.user_grammar_progress (user_id, review_score);

COMMENT ON COLUMN public.user_grammar_progress.review_score IS
    'Per-grammar familiarity 0-100; mirrored to proficiency_score on review.';
COMMENT ON COLUMN public.user_grammar_progress.next_review_date IS
    'SM-2 next due date for flashcard review.';
