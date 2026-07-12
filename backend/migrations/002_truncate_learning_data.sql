-- =============================================================================
-- Komorebi Japanese — Truncate learning content (keep schema & users)
-- Run in Supabase SQL Editor or via scripts/db_cleanup.py
-- =============================================================================

TRUNCATE TABLE
    public.user_vocab_progress,
    public.user_grammar_progress,
    public.vocabulary_definitions,
    public.grammar_usages,
    public.vocabularies,
    public.grammars,
    public.content_ingestions
RESTART IDENTITY CASCADE;

-- Intentionally NOT truncated:
--   auth.users, public.users (login profiles & streak settings)
