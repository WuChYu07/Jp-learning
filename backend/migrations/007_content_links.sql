-- =============================================================================
-- Content knowledge graph: semantic concepts + typed links between entities
-- =============================================================================

CREATE TYPE public.link_entity_type AS ENUM ('grammar', 'vocabulary', 'concept');

CREATE TYPE public.link_relation_type AS ENUM (
    'same_meaning',    -- 同義/近義
    'contrast',        -- 對比差異
    'confusable',      -- 易混淆
    'prerequisite',    -- 先修
    'derived',         -- 延伸句型
    'example_vocab'    -- 例句中的關鍵單字
);

CREATE TABLE public.semantic_concepts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title_zh        TEXT NOT NULL,
    description_zh  TEXT,
    jlpt_level      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.semantic_concepts IS
    'Theme hubs (MOC) for grouping related grammar/vocab, e.g. 「看起來、似乎」.';

CREATE UNIQUE INDEX idx_semantic_concepts_title_zh
    ON public.semantic_concepts (title_zh);

CREATE TABLE public.content_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     public.link_entity_type NOT NULL,
    source_id       UUID NOT NULL,
    target_type     public.link_entity_type NOT NULL,
    target_id       UUID NOT NULL,
    relation_type   public.link_relation_type NOT NULL,
    label_zh        TEXT,
    note_zh         TEXT,
    confidence      REAL NOT NULL DEFAULT 1.0
                    CHECK (confidence >= 0 AND confidence <= 1),
    origin          TEXT NOT NULL DEFAULT 'manual',
    bidirectional   BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_type, source_id, target_type, target_id, relation_type)
);

COMMENT ON TABLE public.content_links IS
    'Typed edges between grammar, vocabulary, and semantic concept nodes.';
COMMENT ON COLUMN public.content_links.origin IS
    'manual | kb_seed | ai | parsed | cooccurrence';
COMMENT ON COLUMN public.content_links.bidirectional IS
    'When true, neighborhood queries match either endpoint.';

CREATE INDEX idx_content_links_source
    ON public.content_links (source_type, source_id);
CREATE INDEX idx_content_links_target
    ON public.content_links (target_type, target_id);
CREATE INDEX idx_content_links_relation
    ON public.content_links (relation_type);

CREATE TRIGGER trg_semantic_concepts_updated_at
    BEFORE UPDATE ON public.semantic_concepts
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.semantic_concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY "semantic_concepts_select_authenticated"
    ON public.semantic_concepts FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "content_links_select_authenticated"
    ON public.content_links FOR SELECT
    TO authenticated
    USING (true);

-- Inserts/updates go through FastAPI service role (bypasses RLS).
