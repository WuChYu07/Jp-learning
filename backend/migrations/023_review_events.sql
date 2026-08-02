-- Append-only review event log, for trend charts.
-- user_vocab_progress / user_grammar_progress only hold *current* SM-2 state
-- (one row per item), so they can't answer "how many reviews per day over
-- the last two weeks" — this table exists purely for that.

CREATE TABLE IF NOT EXISTS public.review_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('vocab', 'grammar')),
    entity_id       UUID NOT NULL,
    rating          TEXT NOT NULL CHECK (rating IN ('again', 'hard', 'good', 'easy')),
    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_events_user_date
    ON public.review_events (user_id, reviewed_at DESC);

ALTER TABLE public.review_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS review_events_owner_all ON public.review_events;
CREATE POLICY review_events_owner_all ON public.review_events
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.review_events IS
    'Append-only log of every flashcard review submission, for trend charts.';
