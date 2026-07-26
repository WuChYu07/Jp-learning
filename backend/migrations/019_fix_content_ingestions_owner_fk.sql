-- content_ingestions.created_by still FKs to auth.users (missed by migration 012,
-- which moved the singleton owner into public.users and detached public.users
-- from auth.users). Every ingestion write with created_by = the singleton owner
-- id has been failing with a foreign-key violation because that id only exists
-- in public.users, never in auth.users. Align it with vocabularies/grammars,
-- which already reference public.users correctly.

ALTER TABLE public.content_ingestions
    DROP CONSTRAINT IF EXISTS content_ingestions_created_by_fkey;

ALTER TABLE public.content_ingestions
    ADD CONSTRAINT content_ingestions_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES public.users (id) ON DELETE SET NULL;
