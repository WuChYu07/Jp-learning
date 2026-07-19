-- Song lyrics learning (MARUMARU source + AI line enrichment).
-- Shared cache: one song processed once, reusable for all opens.
-- Solo owner: RLS permissive; backend uses service role.

CREATE TABLE IF NOT EXISTS public.songs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    artist          TEXT NOT NULL DEFAULT '',
    release_date    DATE,
    marumaru_id     TEXT,
    source_url      TEXT,
    category        TEXT,
    difficulty      INT CHECK (difficulty IS NULL OR (difficulty >= 1 AND difficulty <= 5)),
    youtube_url     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'lyrics_ready', 'enriching', 'enriched', 'failed')),
    lyrics_source   TEXT CHECK (lyrics_source IS NULL OR lyrics_source IN ('marumaru', 'paste', 'ai')),
    zh_source       TEXT CHECK (zh_source IS NULL OR zh_source IN ('marumaru', 'paste', 'ai')),
    error_message   TEXT,
    fetched_at      TIMESTAMPTZ,
    enriched_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT songs_source_url_unique UNIQUE (source_url),
    CONSTRAINT songs_marumaru_id_unique UNIQUE (marumaru_id)
);

CREATE INDEX IF NOT EXISTS idx_songs_status ON public.songs (status);
CREATE INDEX IF NOT EXISTS idx_songs_title ON public.songs (title);
CREATE INDEX IF NOT EXISTS idx_songs_updated ON public.songs (updated_at DESC);

DROP TRIGGER IF EXISTS trg_songs_updated_at ON public.songs;
CREATE TRIGGER trg_songs_updated_at
    BEFORE UPDATE ON public.songs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.songs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS songs_all ON public.songs;
CREATE POLICY songs_all ON public.songs
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.songs IS
    'Cached JP songs (MARUMARU / paste) with enrichment status.';

CREATE TABLE IF NOT EXISTS public.song_lines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    song_id         UUID NOT NULL REFERENCES public.songs(id) ON DELETE CASCADE,
    line_no         INT NOT NULL CHECK (line_no >= 1),
    text_ja         TEXT NOT NULL DEFAULT '',
    text_zh         TEXT,
    grammar_zh      TEXT,
    note_zh         TEXT,
    jlpt_hints      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT song_lines_song_line_unique UNIQUE (song_id, line_no)
);

CREATE INDEX IF NOT EXISTS idx_song_lines_song ON public.song_lines (song_id, line_no);

DROP TRIGGER IF EXISTS trg_song_lines_updated_at ON public.song_lines;
CREATE TRIGGER trg_song_lines_updated_at
    BEFORE UPDATE ON public.song_lines
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.song_lines ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS song_lines_all ON public.song_lines;
CREATE POLICY song_lines_all ON public.song_lines
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.song_lines IS
    'Per-line Japanese/Chinese lyrics with AI grammar and cultural notes.';

CREATE TABLE IF NOT EXISTS public.user_song_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    song_id         UUID NOT NULL REFERENCES public.songs(id) ON DELETE CASCADE,
    last_opened_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_song_history_unique UNIQUE (user_id, song_id)
);

CREATE INDEX IF NOT EXISTS idx_user_song_history_user
    ON public.user_song_history (user_id, last_opened_at DESC);

ALTER TABLE public.user_song_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_song_history_all ON public.user_song_history;
CREATE POLICY user_song_history_all ON public.user_song_history
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.user_song_history IS
    'Recently opened songs per user.';
