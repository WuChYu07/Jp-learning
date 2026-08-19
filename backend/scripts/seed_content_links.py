"""
Seed content_links from Teacher KB + curated synonym clusters.

Usage (from backend/):
  python -m scripts.seed_content_links
  python -m scripts.seed_content_links --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from uuid import UUID

# Allow running as script from repo root or backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.schemas.links import (  # noqa: E402
    ContentLinkCreate,
    LinkEntityType,
    LinkRelationType,
)
from app.services.grammar_kb import normalize_pattern  # noqa: E402
from app.services.grammar_teacher_kb import TEACHER_GRAMMAR  # noqa: E402
from app.services.link_service import link_service  # noqa: E402

# Patterns often referenced in teacher notes (longest first for matching)
_KNOWN_PATTERNS = sorted(
    {
        *TEACHER_GRAMMAR.keys(),
        "のを",
        "のが",
        "のは",
        "なくてもいい",
        "なければなりません",
        "ないでください",
        "てはいけません",
        "てから",
        "ておきます",
        "てあります",
        "ましょう",
        "として",
        "たら",
        "ば",
        "なら",
        "と",
        "かもしれない",
        "だろう",
        "わけがない",
        "向き",
        "向け",
        "そうだ",
        "ようだ",
        "らしい",
        "みたいだ",
        "ことができる",
    },
    key=len,
    reverse=True,
)

_EXTRACT_RE = re.compile(
    r"(?:應改用|→\s*用|用|與|不要與|那是|VS|vs|成對學習)\s*"
    r"([〜~]?[\u3040-\u30ff\u4e00-\u9fffぁ-んァ-ンーをがはでにとやも]+)"
)

# High-value synonym / contrast clusters (MOC hubs)
SYNONYM_CLUSTERS: list[dict] = [
    {
        "title_zh": "看起來、似乎",
        "description_zh": "外觀推測、傳聞、主觀印象等「看起來／似乎」相關文法",
        "jlpt_level": "N4/N3",
        "members": ["そうだ", "ようだ", "らしい", "みたいだ"],
        "contrasts": [
            ("そうだ", "らしい", "傳聞", "そうだ偏外觀推測；らしい偏傳聞資訊"),
            ("そうだ", "ようだ", "外觀推測", "そうだ多依直接外觀；ようだ可依綜合判斷"),
            ("ようだ", "みたいだ", "更口語", "みたいだ較口語，ようだ較中性"),
            ("らしい", "みたいだ", "資訊來源", "らしい偏傳聞；みたいだ偏主觀印象"),
        ],
    },
    {
        "title_zh": "條件句",
        "description_zh": "と／ば／たら／なら 條件表達對比",
        "jlpt_level": "N4",
        "members": ["と", "ば", "たら", "なら"],
        "contrasts": [
            ("と", "たら", "最嚴格", "と後半不可有意志・命令；たら較自由"),
            ("と", "ば", "限制", "と最嚴格；ば偏一般條件"),
            ("たら", "なら", "前提", "なら偏以對方說法為前提"),
            ("ば", "たら", "語感", "ば偏假設條件；たら偏「之後／如果」"),
        ],
    },
    {
        "title_zh": "のは／のが／のを",
        "description_zh": "形式名詞「の」＋助詞三角混淆",
        "jlpt_level": "N4",
        "members": ["のは", "のが", "のを"],
        "contrasts": [
            ("のは", "のが", "評價vs喜好", "のは接評價；のが接好き／上手等"),
            ("のは", "のを", "評價vs受詞", "のを把行為當受詞（看／聽／忘記）"),
            ("のが", "のを", "喜好vs受詞", "能力喜好用が；動作受詞用を"),
        ],
    },
    {
        "title_zh": "ておく／てある",
        "description_zh": "事先準備 vs 完成狀態殘留",
        "jlpt_level": "N4/N3",
        "members": ["ておきます", "てあります"],
        "contrasts": [
            (
                "ておきます",
                "てあります",
                "時間感",
                "ておく＝先做好準備；てある＝已完成且狀態還在",
            ),
        ],
    },
    {
        "title_zh": "必須／不必／禁止",
        "description_zh": "義務與禁止相關句型",
        "jlpt_level": "N4",
        "members": ["なければなりません", "なくてもいい", "てはいけません", "ないでください"],
        "contrasts": [
            ("なければなりません", "なくてもいい", "必須vs不必", "意思相反，常一起考"),
            ("ないでください", "てはいけません", "請求vs禁止", "ないでください較委婉"),
            ("なくてもいい", "てはいけません", "不必vs禁止", "語意完全不同"),
        ],
    },
]


def _extract_mentioned_patterns(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in _EXTRACT_RE.finditer(text or ""):
        raw = m.group(1).strip()
        for known in _KNOWN_PATTERNS:
            if known in raw or raw in known or normalize_pattern(raw) == normalize_pattern(known):
                key = normalize_pattern(known)
                if key not in seen:
                    seen.add(key)
                    found.append(known)
                break
    # Also scan for known patterns appearing anywhere in the text
    for known in _KNOWN_PATTERNS:
        if known in (text or ""):
            key = normalize_pattern(known)
            if key not in seen:
                seen.add(key)
                found.append(known)
    return found


def _resolve_or_report(pattern: str, unmatched: list[str]) -> dict | None:
    row = link_service.find_grammar_by_pattern(pattern)
    if not row:
        # Try with 〜 prefix
        row = link_service.find_grammar_by_pattern(f"〜{pattern}")
    if not row:
        unmatched.append(pattern)
        return None
    return row


def seed_synonym_clusters(dry_run: bool) -> dict:
    created_links = 0
    created_concepts = 0
    unmatched: list[str] = []

    for cluster in SYNONYM_CLUSTERS:
        if dry_run:
            print(f"[dry-run] concept: {cluster['title_zh']} members={cluster['members']}")
            created_concepts += 1
            concept_id = None
        else:
            concept = link_service.upsert_concept(
                title_zh=cluster["title_zh"],
                description_zh=cluster.get("description_zh"),
                jlpt_level=cluster.get("jlpt_level"),
            )
            concept_id = UUID(concept["id"])
            created_concepts += 1

        member_rows: list[dict] = []
        for pattern in cluster["members"]:
            row = _resolve_or_report(pattern, unmatched)
            if row:
                member_rows.append(row)
                if not dry_run and concept_id:
                    link_service.create_links_batch(
                        [
                            ContentLinkCreate(
                                source_type=LinkEntityType.GRAMMAR,
                                source_id=UUID(row["id"]),
                                target_type=LinkEntityType.CONCEPT,
                                target_id=concept_id,
                                relation_type=LinkRelationType.SAME_MEANING,
                                label_zh="同義群",
                                note_zh=cluster["title_zh"],
                                origin="kb_seed",
                                confidence=1.0,
                            )
                        ]
                    )
                    created_links += 1

        # same_meaning between consecutive members
        for i in range(len(member_rows)):
            for j in range(i + 1, len(member_rows)):
                a, b = member_rows[i], member_rows[j]
                if dry_run:
                    print(f"  same_meaning: {a['grammar_point']} ↔ {b['grammar_point']}")
                    created_links += 1
                    continue
                _, skipped = link_service.create_links_batch(
                    [
                        ContentLinkCreate(
                            source_type=LinkEntityType.GRAMMAR,
                            source_id=UUID(a["id"]),
                            target_type=LinkEntityType.GRAMMAR,
                            target_id=UUID(b["id"]),
                            relation_type=LinkRelationType.SAME_MEANING,
                            label_zh="近義",
                            note_zh=cluster["title_zh"],
                            origin="kb_seed",
                        )
                    ]
                )
                if not skipped:
                    created_links += 1

        for a_pat, b_pat, label, note in cluster.get("contrasts") or []:
            a = _resolve_or_report(a_pat, unmatched)
            b = _resolve_or_report(b_pat, unmatched)
            if not a or not b:
                continue
            if dry_run:
                print(f"  contrast: {a['grammar_point']} ↔ {b['grammar_point']} ({label})")
                created_links += 1
                continue
            _, skipped = link_service.create_links_batch(
                [
                    ContentLinkCreate(
                        source_type=LinkEntityType.GRAMMAR,
                        source_id=UUID(a["id"]),
                        target_type=LinkEntityType.GRAMMAR,
                        target_id=UUID(b["id"]),
                        relation_type=LinkRelationType.CONTRAST,
                        label_zh=label,
                        note_zh=note,
                        origin="kb_seed",
                    )
                ]
            )
            if not skipped:
                created_links += 1

    return {
        "concepts": created_concepts,
        "links": created_links,
        "unmatched": sorted(set(unmatched)),
    }


def seed_from_teacher_kb(dry_run: bool) -> dict:
    created = 0
    unmatched: list[str] = []

    for pattern, entry in TEACHER_GRAMMAR.items():
        source = _resolve_or_report(pattern, unmatched)
        if not source:
            continue

        texts = [entry.usage_avoid or "", entry.common_mistakes or ""]
        mentioned: list[str] = []
        for text in texts:
            for m in _extract_mentioned_patterns(text):
                if normalize_pattern(m) != normalize_pattern(pattern):
                    mentioned.append(m)

        # Dedupe
        seen: set[str] = set()
        unique_mentions: list[str] = []
        for m in mentioned:
            key = normalize_pattern(m)
            if key not in seen:
                seen.add(key)
                unique_mentions.append(m)

        for target_pat in unique_mentions:
            target = _resolve_or_report(target_pat, unmatched)
            if not target:
                continue
            note = (entry.common_mistakes or entry.usage_avoid or "")[:200]
            relation = (
                LinkRelationType.CONFUSABLE
                if "混淆" in note or "搞混" in note or "搞反" in note
                else LinkRelationType.CONTRAST
            )
            if dry_run:
                print(
                    f"[kb] {source['grammar_point']} -{relation.value}-> "
                    f"{target['grammar_point']}"
                )
                created += 1
                continue
            _, skipped = link_service.create_links_batch(
                [
                    ContentLinkCreate(
                        source_type=LinkEntityType.GRAMMAR,
                        source_id=UUID(source["id"]),
                        target_type=LinkEntityType.GRAMMAR,
                        target_id=UUID(target["id"]),
                        relation_type=relation,
                        label_zh="易混淆" if relation == LinkRelationType.CONFUSABLE else "對比",
                        note_zh=note or None,
                        origin="kb_seed",
                        confidence=0.9,
                    )
                ]
            )
            if not skipped:
                created += 1

    return {"links": created, "unmatched": sorted(set(unmatched))}


def seed_from_supplementary_blocks(dry_run: bool) -> dict:
    """Parse supplementary_blocks titles like「與〜ごとに的差別」."""
    from app.db.supabase import get_supabase_client

    db = get_supabase_client()
    rows = (
        db.table("grammars")
        .select("id, grammar_point, supplementary_blocks")
        .neq("sync_status", "archived")
        .execute()
    ).data or []

    title_re = re.compile(
        r"與\s*[〜~]?(.+?)的(?:差別|差異|不同|對比|混淆)|"
        r"和\s*[〜~]?(.+?)的(?:差別|差異)|"
        r"vs\.?\s*[〜~]?(.+)|"
        r"VS\.?\s*[〜~]?(.+)"
    )
    created = 0
    unmatched: list[str] = []

    for row in rows:
        blocks = row.get("supplementary_blocks") or []
        for block in blocks:
            title = block.get("title") or ""
            m = title_re.search(title)
            if not m:
                continue
            target_raw = next((g for g in m.groups() if g), None)
            if not target_raw:
                continue
            target_raw = target_raw.strip().rstrip("。．")
            target = _resolve_or_report(target_raw, unmatched)
            if not target:
                continue
            if dry_run:
                print(
                    f"[parsed] {row['grammar_point']} -contrast-> "
                    f"{target['grammar_point']} ({title})"
                )
                created += 1
                continue
            _, skipped = link_service.create_links_batch(
                [
                    ContentLinkCreate(
                        source_type=LinkEntityType.GRAMMAR,
                        source_id=UUID(row["id"]),
                        target_type=LinkEntityType.GRAMMAR,
                        target_id=UUID(target["id"]),
                        relation_type=LinkRelationType.CONTRAST,
                        label_zh="差別",
                        note_zh=(block.get("summary_zh") or title)[:300],
                        origin="parsed",
                        confidence=0.85,
                    )
                ]
            )
            if not skipped:
                created += 1

    return {"links": created, "unmatched": sorted(set(unmatched))}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed content_links knowledge graph")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Seeding synonym clusters ===")
    cluster_stats = seed_synonym_clusters(args.dry_run)
    print(
        f"concepts={cluster_stats['concepts']} links≈{cluster_stats['links']} "
        f"unmatched={cluster_stats['unmatched']}"
    )

    print("=== Seeding from Teacher KB ===")
    kb_stats = seed_from_teacher_kb(args.dry_run)
    print(f"links≈{kb_stats['links']} unmatched={kb_stats['unmatched']}")

    print("=== Seeding from supplementary_blocks ===")
    parsed_stats = seed_from_supplementary_blocks(args.dry_run)
    print(f"links≈{parsed_stats['links']} unmatched={parsed_stats['unmatched']}")

    print("Done.")


if __name__ == "__main__":
    main()
