-- Log of unattended Notion sync-preview checks (e.g. GitHub Actions cron).
-- These only ever call sync_preview — never confirm_sync — so no content is
-- written; this table just remembers "were there pending changes" for the
-- app to surface next time someone opens the Upload page.

CREATE TABLE IF NOT EXISTS public.notion_scheduled_checks (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checked_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    grammar_new_count       INT NOT NULL DEFAULT 0,
    grammar_updated_count   INT NOT NULL DEFAULT 0,
    vocab_new_count         INT NOT NULL DEFAULT 0,
    vocab_updated_count     INT NOT NULL DEFAULT 0,
    orphaned_grammar_count  INT NOT NULL DEFAULT 0,
    orphaned_vocab_count    INT NOT NULL DEFAULT 0,
    unclassified_count      INT NOT NULL DEFAULT 0,
    has_changes             BOOLEAN NOT NULL DEFAULT false,
    error                   TEXT
);

CREATE INDEX IF NOT EXISTS idx_notion_scheduled_checks_checked_at
    ON public.notion_scheduled_checks (checked_at DESC);

ALTER TABLE public.notion_scheduled_checks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notion_scheduled_checks_all ON public.notion_scheduled_checks;
CREATE POLICY notion_scheduled_checks_all ON public.notion_scheduled_checks
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.notion_scheduled_checks IS
    'History of unattended sync-preview checks; preview-only, never writes content.';
