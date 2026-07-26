-- Track each Notion page's last_edited_time as of its last confirmed sync, so
-- the next preview can skip re-fetching every block (Notion API is rate
-- limited; a page with thousands of blocks can take minutes to fetch) when
-- the page provably has not changed since then.

ALTER TABLE public.notion_sync_log
    ADD COLUMN IF NOT EXISTS last_edited_time TEXT;

COMMENT ON COLUMN public.notion_sync_log.last_edited_time IS
    'Notion page last_edited_time as of this sync. Compared against the live page on the next preview to skip a full block re-fetch when unchanged.';
