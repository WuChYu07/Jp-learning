-- Cache for AI classification of ambiguous grammar headings: is a top-level
-- Notion heading a JLPT/category label (its heading_2 children are each an
-- independent grammar point, e.g. "N2文法") or a grammar point itself (its
-- children are usage variants of that one point, e.g. "て形")? Classified
-- once per notion_block_id and never re-asked, so re-syncing an unchanged
-- page never costs AI tokens.

CREATE TABLE IF NOT EXISTS public.notion_heading_classifications (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_block_id   TEXT NOT NULL UNIQUE,
    heading_text      TEXT NOT NULL,
    is_category       BOOLEAN NOT NULL,
    classified_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notion_heading_classifications_block_id
    ON public.notion_heading_classifications (notion_block_id);
