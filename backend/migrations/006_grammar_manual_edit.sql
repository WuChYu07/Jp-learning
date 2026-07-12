-- Manual grammar create/edit protection + soft-delete tombstone support

ALTER TABLE public.grammars
    ADD COLUMN IF NOT EXISTS manual_edited_at TIMESTAMPTZ;

COMMENT ON COLUMN public.grammars.manual_edited_at IS
    'Set when user manually creates/edits this grammar; Notion sync must not overwrite content.';

COMMENT ON COLUMN public.grammars.sync_status IS
    'synced | needs_ai | archived. archived = soft-deleted tombstone; Notion sync must not resurrect.';
