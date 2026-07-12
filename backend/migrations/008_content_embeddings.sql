-- =============================================================================
-- Semantic embeddings (pgvector) for auto same_meaning links across all JLPT
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.content_embeddings (
    entity_type   public.link_entity_type NOT NULL,
    entity_id     UUID NOT NULL,
    embedding     vector(768) NOT NULL,
    source_text   TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    model         TEXT NOT NULL DEFAULT 'gemini-embedding-001',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_type, entity_id)
);

COMMENT ON TABLE public.content_embeddings IS
    'Gemini embeddings for grammar/vocabulary; used for JLPT-agnostic semantic linking.';

CREATE INDEX IF NOT EXISTS idx_content_embeddings_hnsw
    ON public.content_embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_content_embeddings_hash
    ON public.content_embeddings (content_hash);

-- Cosine nearest neighbors within one entity type (NO jlpt filter).
CREATE OR REPLACE FUNCTION public.match_content_embeddings(
    query_embedding vector(768),
    match_entity_type public.link_entity_type,
    match_count int DEFAULT 10,
    exclude_id uuid DEFAULT NULL
)
RETURNS TABLE (
    entity_type public.link_entity_type,
    entity_id uuid,
    similarity float
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        e.entity_type,
        e.entity_id,
        (1 - (e.embedding <=> query_embedding))::float AS similarity
    FROM public.content_embeddings e
    WHERE e.entity_type = match_entity_type
      AND (exclude_id IS NULL OR e.entity_id <> exclude_id)
    ORDER BY e.embedding <=> query_embedding
    LIMIT greatest(match_count, 1);
$$;

COMMENT ON FUNCTION public.match_content_embeddings IS
    'Return top-K cosine-similar embeddings of the same entity_type (all JLPT levels).';

ALTER TABLE public.content_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "content_embeddings_select_authenticated"
    ON public.content_embeddings;
CREATE POLICY "content_embeddings_select_authenticated"
    ON public.content_embeddings FOR SELECT
    TO authenticated
    USING (true);

-- Inserts/updates go through FastAPI service role (bypasses RLS).
