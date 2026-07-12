"""Run full curriculum data pipeline: extract → enrich.

Usage (from backend/):
    python scripts/run_data_pipeline.py [--clear-db]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Komorebi curriculum data pipeline")
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Truncate learning tables before processing (data only)",
    )
    args = parser.parse_args()

    if args.clear_db:
        print("=== Clearing database learning content ===")
        subprocess.run([sys.executable, str(BACKEND_ROOT / "scripts" / "db_cleanup.py")], check=True)

    print("=== Agent 1: PDF → raw CSV ===")
    subprocess.run([sys.executable, str(BACKEND_ROOT / "scripts" / "agents" / "agent1_extract_to_csv.py")], check=True)

    print("=== Agent 2: enrich CSV ===")
    subprocess.run([sys.executable, str(BACKEND_ROOT / "scripts" / "agents" / "agent2_enrich_curriculum.py")], check=True)

    print("=== Agent 3: fill grammar index gaps ===")
    subprocess.run([sys.executable, str(BACKEND_ROOT / "scripts" / "agents" / "agent3_fill_grammar_gaps.py")], check=True)

    print("=== Agent 4: grammar teacher review ===")
    subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "agents" / "agent4_grammar_teacher.py")],
        check=True,
    )

    print("=== Pipeline complete ===")
    print("Review: data/curated/vocabulary.csv & data/curated/grammar.csv")


if __name__ == "__main__":
    main()
