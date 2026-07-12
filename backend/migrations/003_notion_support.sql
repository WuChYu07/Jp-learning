-- Notion sync support: source type, grammar images, sync log

ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'notion';

ALTER TABLE public.grammars
    ADD COLUMN IF NOT EXISTS image_urls JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.grammars.image_urls IS
    'Permanent image URLs associated with this grammar point (from Notion sync).';

CREATE TABLE IF NOT EXISTS public.notion_sync_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id         TEXT NOT NULL,
    page_title      TEXT,
    content_hash    TEXT NOT NULL,
    grammar_count   INTEGER NOT NULL DEFAULT 0,
    vocab_count     INTEGER NOT NULL DEFAULT 0,
    image_count     INTEGER NOT NULL DEFAULT 0,
    auto_approved   BOOLEAN NOT NULL DEFAULT FALSE,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notion_sync_log_page_id ON public.notion_sync_log (page_id);
CREATE INDEX IF NOT EXISTS idx_notion_sync_log_content_hash ON public.notion_sync_log (content_hash);

ALTER TABLE public.notion_sync_log
    ADD COLUMN IF NOT EXISTS focus TEXT;

ALTER TABLE public.notion_sync_log ENABLE ROW LEVEL SECURITY;
