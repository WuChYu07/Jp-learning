-- Supplementary notes (補充) for vocabulary definitions, aligned with Notion 5-col table.
ALTER TABLE vocabulary_definitions
  ADD COLUMN IF NOT EXISTS notes_zh TEXT;
