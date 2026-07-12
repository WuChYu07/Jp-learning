-- Single-tenant owner profile (no Auth signup / DEV_USER_ID required).
-- Run after 011_review_exam_scores.sql.
--
-- public.users originally FKs to auth.users. For solo use we detach that FK
-- so a fixed owner UUID can exist without creating a Supabase Auth account.

ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_id_fkey;

INSERT INTO public.users (id, username, display_name)
VALUES (
    'a0000000-0000-4000-8000-000000000001'::uuid,
    'owner',
    'Komorebi Owner'
)
ON CONFLICT (id) DO NOTHING;

COMMENT ON COLUMN public.users.id IS
    'Profile id. Fixed owner a0000000-0000-4000-8000-000000000001 is used when AUTH_ENABLED=false.';
