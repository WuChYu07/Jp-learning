-- Incremental Notion sync: stable block IDs, content hashes, image dedup

ALTER TABLE public.grammars
    ADD COLUMN IF NOT EXISTS notion_block_id TEXT,
    ADD COLUMN IF NOT EXISTS notion_page_id TEXT,
    ADD COLUMN IF NOT EXISTS source_content_hash TEXT,
    ADD COLUMN IF NOT EXISTS ai_content_hash TEXT,
    ADD COLUMN IF NOT EXISTS sync_status TEXT NOT NULL DEFAULT 'synced',
    ADD COLUMN IF NOT EXISTS block_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.grammars.notion_block_id IS
    'Notion heading block ID for this grammar unit (stable across edits).';
COMMENT ON COLUMN public.grammars.source_content_hash IS
    'Hash of parsed grammar content from Notion; used to detect updates.';
COMMENT ON COLUMN public.grammars.ai_content_hash IS
    'Hash of content when last sent to AI enrichment; skip AI if equals source_content_hash.';
COMMENT ON COLUMN public.grammars.sync_status IS
    'synced | needs_ai | archived';

CREATE UNIQUE INDEX IF NOT EXISTS idx_grammars_notion_block_id
    ON public.grammars (notion_block_id)
    WHERE notion_block_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_grammars_notion_page_id
    ON public.grammars (notion_page_id);

CREATE INDEX IF NOT EXISTS idx_grammars_source_content_hash
    ON public.grammars (source_content_hash);

CREATE TABLE IF NOT EXISTS public.notion_images (
    notion_block_id TEXT PRIMARY KEY,
    storage_url     TEXT NOT NULL,
    content_hash    TEXT,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.notion_images IS
    'Maps Notion image block IDs to permanent Supabase Storage URLs.';

ALTER TABLE public.notion_images ENABLE ROW LEVEL SECURITY;
