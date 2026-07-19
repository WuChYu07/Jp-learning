-- Song-level AI overview (background / common interpretations, Traditional Chinese).

ALTER TABLE public.songs
    ADD COLUMN IF NOT EXISTS overview_zh TEXT;

COMMENT ON COLUMN public.songs.overview_zh IS
    'AI-generated song background and common interpretations (Traditional Chinese).';
