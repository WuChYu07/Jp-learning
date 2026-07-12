-- Grammar enrichment: flexible JLPT labels, meaning blocks, supplementary sections

ALTER TABLE public.grammars
    ALTER COLUMN jlpt_level TYPE TEXT USING jlpt_level::text;

ALTER TABLE public.grammars
    ADD COLUMN IF NOT EXISTS supplementary_blocks JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.grammars.jlpt_level IS
    'JLPT label(s), e.g. N3, N3/N2, or unknown.';
COMMENT ON COLUMN public.grammars.supplementary_blocks IS
    'AI summaries from supplemental note images: [{title, summary_zh, example_sentences}]';

ALTER TABLE public.grammar_usages
    ADD COLUMN IF NOT EXISTS meaning_blocks JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.grammar_usages.meaning_blocks IS
    'Structured Chinese explanation blocks: [{text, variant}]';
