"""Agent 2 — Enrich & correct raw CSV (teacher agent, no Gemini).

Usage (from backend/):
    python scripts/agents/agent2_enrich_curriculum.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from curriculum.csv_io import read_csv_as_dicts, write_csv
from curriculum.enricher import (
    GrammarCuratedRow,
    GrammarRawRow,
    VocabCuratedRow,
    VocabRawRow,
    enrich_grammar_row,
    enrich_vocabulary_row,
)

DATA = PROJECT_ROOT / "data"
EXTRACTED = DATA / "extracted"
CURATED = DATA / "curated"


def _vocab_raw_from_dict(row: dict[str, str]) -> VocabRawRow:
    return VocabRawRow(**row)


def _grammar_raw_from_dict(row: dict[str, str]) -> GrammarRawRow:
    return GrammarRawRow(**row)


def main() -> None:
    vocab_in = EXTRACTED / "vocabulary_raw.csv"
    grammar_in = EXTRACTED / "grammar_raw.csv"

    if not vocab_in.exists() or not grammar_in.exists():
        raise SystemExit("Run agent1_extract_to_csv.py first.")

    print("[Agent 2] Enriching vocabulary ...")
    vocab_raw = [_vocab_raw_from_dict(row) for row in read_csv_as_dicts(vocab_in)]
    vocab_curated: list[VocabCuratedRow] = [enrich_vocabulary_row(row) for row in vocab_raw]
    vocab_out = CURATED / "vocabulary.csv"
    write_csv(vocab_out, vocab_curated)
    print(f"  → {vocab_out} ({len(vocab_curated)} rows)")

    print("[Agent 2] Enriching grammar ...")
    grammar_raw = [_grammar_raw_from_dict(row) for row in read_csv_as_dicts(grammar_in)]
    grammar_curated: list[GrammarCuratedRow] = [enrich_grammar_row(row) for row in grammar_raw]
    grammar_out = CURATED / "grammar.csv"
    write_csv(grammar_out, grammar_curated)
    print(f"  → {grammar_out} ({len(grammar_curated)} rows)")

    low_conf_vocab = sum(1 for row in vocab_curated if row.confidence < 0.6)
    low_conf_grammar = sum(1 for row in grammar_curated if row.confidence < 0.6)
    print(
        f"[Agent 2] Done. Low-confidence review: "
        f"vocab={low_conf_vocab}, grammar={low_conf_grammar}"
    )


if __name__ == "__main__":
    main()
