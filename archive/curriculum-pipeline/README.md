# Curriculum Pipeline (archived 2026-08-19)

Offline content-authoring pipeline used to bulk-extract, enrich, and gap-fill
grammar/vocab data from the source PDFs during initial content authoring.
Not called by the live API — moved out of `backend/app/services/` and
`backend/scripts/` once that authoring work was done, so it stops showing up
in "what does the running app actually use" audits.

## Layout

- `curriculum/` — was `backend/app/services/curriculum/`
- `agents/` — was `backend/scripts/agents/agent1_extract_to_csv.py` … `agent4_grammar_teacher.py`
- `run_data_pipeline.py` — was `backend/scripts/run_data_pipeline.py`, orchestrates agent1→4

Internal imports were rewritten from `app.services.curriculum.X` to
`curriculum.X` to match the new relative layout.

**Correction (same day)**: `grammar_kb.py` and `grammar_teacher_kb.py` were
initially moved here too, but `app/services/link_service.py` (a live,
actively-used service — grammar-pattern lookup for the knowledge graph)
depends on `grammar_kb.normalize_pattern` at runtime. Those two files were
moved back to `backend/app/services/` instead; they're a grammar-pattern
knowledge base with one live consumer, not curriculum-only tooling. This
archive's own files reference them back across that boundary
(`from app.services.grammar_kb import ...`), same as the `hash_service`
case below.

## If you ever need to run these again

1. Two imports cross back into the live backend:
   - `agents/agent1_extract_to_csv.py`: `from app.services.hash_service import extract_pdf_text`
   - `agents/agent3_fill_grammar_gaps.py`, `curriculum/enricher.py`, `curriculum/grammar_teacher_agent.py`: `from app.services.grammar_kb import ...` (and `grammar_teacher_kb`)

   Run from a context where `backend/` is also on `PYTHONPATH` before invoking these.
2. Run agent scripts with this folder (`archive/curriculum-pipeline/`) as the
   working directory / on `PYTHONPATH`, e.g.:
   ```bash
   cd archive/curriculum-pipeline
   python -m agents.agent1_extract_to_csv
   ```
3. These haven't been exercised since the move — expect to need a few fixes
   before a clean run (dependency versions, Supabase schema drift, etc.).
