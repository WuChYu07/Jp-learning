-- Remove example_vocab edges and enum value (cluttered relation graphs).

DELETE FROM public.content_links
WHERE relation_type = 'example_vocab';

-- Rebuild enum without example_vocab (Postgres cannot DROP ENUM value in-place).
CREATE TYPE public.link_relation_type_new AS ENUM (
    'same_meaning',
    'contrast',
    'confusable',
    'prerequisite',
    'derived'
);

ALTER TABLE public.content_links
    ALTER COLUMN relation_type TYPE public.link_relation_type_new
    USING relation_type::text::public.link_relation_type_new;

DROP TYPE public.link_relation_type;
ALTER TYPE public.link_relation_type_new RENAME TO link_relation_type;
