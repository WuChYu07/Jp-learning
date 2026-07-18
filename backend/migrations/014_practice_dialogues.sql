-- AI practice dialogue log (speak / hint-translate modes).
-- Solo owner: RLS allows authenticated + anon read/write for personal deploy;
-- backend uses service role.

CREATE TABLE IF NOT EXISTS public.practice_dialogues (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    mode            TEXT NOT NULL CHECK (mode IN ('speak', 'hint_translate')),
    topic           TEXT,
    prompt_zh       TEXT,
    prompt_ja       TEXT,
    user_answer     TEXT NOT NULL DEFAULT '',
    score           INT CHECK (score IS NULL OR (score >= 1 AND score <= 5)),
    feedback_zh     TEXT,
    model_answer    TEXT,
    hints_json      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_practice_dialogues_user_created
    ON public.practice_dialogues (user_id, created_at DESC);

ALTER TABLE public.practice_dialogues ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS practice_dialogues_owner_all ON public.practice_dialogues;
CREATE POLICY practice_dialogues_owner_all ON public.practice_dialogues
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.practice_dialogues IS
    'AI practice Q&A / hint-translate sessions with scores and feedback.';
