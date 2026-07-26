-- Vocab orphan detection: track originating Notion page + soft-delete tombstone,
-- mirroring grammars.notion_page_id / sync_status.

ALTER TABLE public.vocabularies
    ADD COLUMN IF NOT EXISTS notion_page_id TEXT;

ALTER TABLE public.vocabularies
    ADD COLUMN IF NOT EXISTS sync_status TEXT NOT NULL DEFAULT 'synced';

COMMENT ON COLUMN public.vocabularies.notion_page_id IS
    'Notion page this word was last synced from; used to detect rows removed from Notion. NULL until first sync after this column existed.';
COMMENT ON COLUMN public.vocabularies.sync_status IS
    'synced | archived. Archived rows are hidden from lists/reviews and never resurrected by a Notion sync.';
