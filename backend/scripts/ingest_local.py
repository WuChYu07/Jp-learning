"""Local CLI to ingest PDF study materials into Supabase.

Usage (from backend/):
    python scripts/ingest_local.py ../data/vocabulary.pdf --focus vocabulary
    python scripts/ingest_local.py ../data/grammar.pdf --focus grammar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.models.schemas.common import SourceType
from app.services.ingestion_service import ingestion_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest local PDF into Komorebi database")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    parser.add_argument(
        "--focus",
        choices=["vocabulary", "grammar", "both"],
        default="both",
        help="What to extract from the file",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path.resolve()
    if not pdf_path.exists():
        raise SystemExit(f"File not found: {pdf_path}")

    file_bytes = pdf_path.read_bytes()
    print(f"Ingesting {pdf_path.name} ({len(file_bytes):,} bytes), focus={args.focus} ...")

    result = ingestion_service.process_upload(
        file_bytes=file_bytes,
        mime_type="application/pdf",
        file_name=pdf_path.name,
        user_id=None,
        source_type=SourceType.PDF,
        focus=args.focus,
    )

    print(f"Done — cached={result.cached}, vocab={result.vocabulary_count}, grammar={result.grammar_count}")
    if result.vocabularies[:3]:
        print("Sample vocab:", [v.word for v in result.vocabularies[:3]])
    if result.grammars[:3]:
        print("Sample grammar:", [g.grammar_point for g in result.grammars[:3]])


if __name__ == "__main__":
    main()
