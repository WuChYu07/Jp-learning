-- Track a Notion-only content snapshot for vocab, separate from DB's current
-- (possibly AI-enriched) content, so re-syncs diff against what Notion last
-- had instead of falsely flagging AI-added meaning/notes/examples as changes.

ALTER TABLE public.vocabularies
    ADD COLUMN IF NOT EXISTS notion_source_hash TEXT;

COMMENT ON COLUMN public.vocabularies.notion_source_hash IS
    'Hash of word+reading+definitions as last seen from Notion (see vocab_source_hash). NULL until first sync after this column existed.';
