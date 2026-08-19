"""Agent 1 — Extract PDF notes to raw CSV (no AI, no DB).

Usage (from backend/):
    python scripts/agents/agent1_extract_to_csv.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from curriculum.csv_io import write_csv
from curriculum.extractors import extract_grammar_rows_from_pdf, extract_vocabulary_rows
from app.services.hash_service import extract_pdf_text

DATA = PROJECT_ROOT / "data"
EXTRACTED = DATA / "extracted"


def main() -> None:
    vocab_pdf = DATA / "vocabulary.pdf"
    grammar_pdf = DATA / "grammar.pdf"

    print("[Agent 1] Extracting vocabulary.pdf → CSV ...")
    vocab_text = extract_pdf_text(vocab_pdf.read_bytes())
    vocab_rows = extract_vocabulary_rows(vocab_text)
    vocab_out = EXTRACTED / "vocabulary_raw.csv"
    write_csv(vocab_out, vocab_rows)
    print(f"  → {vocab_out} ({len(vocab_rows)} rows)")

    print("[Agent 1] Extracting grammar.pdf → CSV (page-card parser) ...")
    grammar_rows = extract_grammar_rows_from_pdf(grammar_pdf.read_bytes())
    grammar_out = EXTRACTED / "grammar_raw.csv"
    write_csv(grammar_out, grammar_rows)
    print(f"  → {grammar_out} ({len(grammar_rows)} rows)")

    partial_vocab = sum(1 for row in vocab_rows if row.parse_status != "complete")
    partial_grammar = sum(1 for row in grammar_rows if row.parse_status != "complete")
    print(f"[Agent 1] Done. Partial vocab={partial_vocab}, partial grammar={partial_grammar}")


if __name__ == "__main__":
    main()
