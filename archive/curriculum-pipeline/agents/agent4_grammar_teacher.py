"""Agent 4 — Professional Japanese teacher reviews grammar CSV.

Checks errors, corrects known mistakes, and enriches usage_when / usage_avoid
from teacher KB + PDF ✅❌ markers (no Gemini).

Usage (from backend/):
    python scripts/agents/agent4_grammar_teacher.py
    python scripts/agents/agent4_grammar_teacher.py --apply   # also overwrite grammar.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from curriculum.csv_io import read_csv, write_csv
from curriculum.enricher import GrammarCuratedRow
from curriculum.extractors import GrammarRawRow
from curriculum.grammar_teacher_agent import review_all_rows
from curriculum.pdf_usage_extractor import build_pdf_usage_index

DATA = PROJECT_ROOT / "data"
EXTRACTED = DATA / "extracted"
CURATED = DATA / "curated"
REPORTS = DATA / "reports"


def main() -> None:
    parser = argparse.ArgumentParser(description="Grammar teacher review agent")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Also write reviewed rows back to data/curated/grammar.csv",
    )
    args = parser.parse_args()

    grammar_curated_path = CURATED / "grammar.csv"
    grammar_raw_path = EXTRACTED / "grammar_raw.csv"
    grammar_pdf = DATA / "grammar.pdf"

    if not grammar_curated_path.exists():
        raise SystemExit("Run agent2 or agent3 first to create grammar.csv")

    print("[Agent 4] Loading grammar data ...")
    curated = read_csv(grammar_curated_path, GrammarCuratedRow)
    raw_rows = read_csv(grammar_raw_path, GrammarRawRow) if grammar_raw_path.exists() else []
    raw_by_id = {row.entry_id: row for row in raw_rows}

    print("[Agent 4] Indexing PDF usage guides (✅❌🚨) ...")
    pdf_index = build_pdf_usage_index(grammar_pdf.read_bytes())
    print(f"  → {len(pdf_index)} pages with OK/NG markers")

    print("[Agent 4] Teacher review in progress ...")
    reviewed, stats = review_all_rows(curated, raw_by_id, pdf_index)

    reviewed_path = CURATED / "grammar_reviewed.csv"
    write_csv(reviewed_path, reviewed)
    print(f"  → {reviewed_path} ({len(reviewed)} rows)")

    REPORTS.mkdir(parents=True, exist_ok=True)
    flagged = [
        {
            "entry_id": r.entry_id,
            "grammar_point": r.grammar_point,
            "review_status": r.review_status,
            "issues": r.review_issues,
        }
        for r in reviewed
        if r.review_status in {"flagged", "excluded"}
    ]
    report = {
        "summary": {
            "total": stats.total,
            "passed": stats.passed,
            "corrected": stats.corrected,
            "flagged": stats.flagged,
            "excluded": stats.excluded,
        },
        "flagged_entries": flagged[:80],
    }
    report_path = REPORTS / "grammar_teacher_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {report_path}")

    if args.apply:
        # Write teachable rows (non-excluded) to grammar.csv without review columns
        teachable = [
            GrammarCuratedRow(
                entry_id=r.entry_id,
                grammar_point=r.grammar_point,
                semantic_concept=r.semantic_concept,
                connection_rule=r.connection_rule,
                meaning_zh=r.meaning_zh,
                example_japanese=r.example_japanese,
                example_reading=r.example_reading,
                example_chinese=r.example_chinese,
                jlpt_level=r.jlpt_level,
                tags=r.tags,
                notes=_merge_notes(r),
                enriched_by=r.enriched_by,
                confidence=r.confidence,
            )
            for r in reviewed
            if r.review_status != "excluded"
        ]
        write_csv(grammar_curated_path, teachable)
        print(f"  → applied {len(teachable)} rows to {grammar_curated_path}")

    print(
        f"[Agent 4] Done. passed={stats.passed} corrected={stats.corrected} "
        f"flagged={stats.flagged} excluded={stats.excluded}"
    )
    print("Review: data/curated/grammar_reviewed.csv (含 usage_when / usage_avoid)")


def _merge_notes(row) -> str:
    parts = [row.notes] if row.notes else []
    if row.usage_when:
        parts.append(f"【可用】{row.usage_when}")
    if row.usage_avoid:
        parts.append(f"【避免】{row.usage_avoid}")
    if row.common_mistakes:
        parts.append(f"【易錯】{row.common_mistakes}")
    if row.review_issues:
        parts.append(f"【審核】{row.review_issues}")
    return " ".join(p for p in parts if p).strip()


if __name__ == "__main__":
    main()
