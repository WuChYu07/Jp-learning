-- Allow multiple embedding vectors per entity — one per definition/usage
-- ("sense") — instead of averaging every meaning into a single diluted
-- vector. A word/grammar point with several distinct meanings previously
-- got one blended vector, which could hide a real match on one sense
-- because unrelated other senses pulled the vector away. Matching now finds
-- the best cross-sense similarity per target entity.

ALTER TABLE public.content_embeddings
    DROP CONSTRAINT content_embeddings_pkey;

ALTER TABLE public.content_embeddings
    ADD COLUMN IF NOT EXISTS sense_index SMALLINT NOT NULL DEFAULT 0;

ALTER TABLE public.content_embeddings
    ADD PRIMARY KEY (entity_type, entity_id, sense_index);

-- Cosine nearest neighbors, deduplicated to the single best-matching sense
-- per target entity (so a multi-sense entity's own rows don't crowd out
-- other distinct entities in the top-K).
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
    WITH best_per_entity AS (
        SELECT DISTINCT ON (e.entity_id)
            e.entity_type,
            e.entity_id,
            (1 - (e.embedding <=> query_embedding))::float AS similarity
        FROM public.content_embeddings e
        WHERE e.entity_type = match_entity_type
          AND (exclude_id IS NULL OR e.entity_id <> exclude_id)
        ORDER BY e.entity_id, e.embedding <=> query_embedding
    )
    SELECT entity_type, entity_id, similarity
    FROM best_per_entity
    ORDER BY similarity DESC
    LIMIT greatest(match_count, 1);
$$;

COMMENT ON FUNCTION public.match_content_embeddings IS
    'Return top-K cosine-similar entities (best sense per entity, all JLPT levels).';

COMMENT ON COLUMN public.content_embeddings.sense_index IS
    'Which definition/usage (0-based, in sort_order) this vector represents. Multiple rows per entity_id are expected.';
