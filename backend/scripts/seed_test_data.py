"""Seed a small set of test vocabulary and grammar into Supabase.

Usage (from backend/):
    python scripts/seed_test_data.py
    python scripts/seed_test_data.py --clear   # truncate learning tables first
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.models.schemas.common import ExampleSentence, JlptLevel, PartOfSpeech, SourceType
from app.models.schemas.grammar import GrammarItemInput, GrammarUsageBase
from app.models.schemas.vocab import VocabularyDefinitionBase, VocabularyItemInput
from app.services.hash_service import compute_upload_hash
from app.services.ingestion_service import IngestionService

SEED_MARKER = b"komorebi-seed-v1"

TEST_VOCAB: list[VocabularyItemInput] = [
    VocabularyItemInput(
        word="食べる",
        reading="たべる",
        jlpt_level=JlptLevel.N5,
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.VERB,
                meaning_zh="吃",
                example_sentences=[
                    ExampleSentence(
                        japanese="毎朝パンを食べます。",
                        reading="まいあさパンをたべます。",
                        chinese="每天早上吃麵包。",
                    )
                ],
            )
        ],
    ),
    VocabularyItemInput(
        word="勉強",
        reading="べんきょう",
        jlpt_level=JlptLevel.N5,
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.NOUN,
                meaning_zh="讀書、學習",
                example_sentences=[
                    ExampleSentence(
                        japanese="毎日日本語を勉強しています。",
                        reading="まいにちにほんごをべんきょうしています。",
                        chinese="每天正在學日語。",
                    )
                ],
            )
        ],
    ),
    VocabularyItemInput(
        word="綺麗",
        reading="きれい",
        jlpt_level=JlptLevel.N4,
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.NA_ADJECTIVE,
                meaning_zh="漂亮、乾淨",
                example_sentences=[
                    ExampleSentence(
                        japanese="この部屋はとても綺麗です。",
                        reading="このへやはとてもきれいです。",
                        chinese="這個房間非常乾淨。",
                    )
                ],
            )
        ],
    ),
    VocabularyItemInput(
        word="約束",
        reading="やくそく",
        jlpt_level=JlptLevel.N4,
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.NOUN,
                meaning_zh="約定、承諾",
                example_sentences=[
                    ExampleSentence(
                        japanese="約束を守らなければなりません。",
                        reading="やくそくをまもらなければなりません。",
                        chinese="必須遵守約定。",
                    )
                ],
            )
        ],
    ),
    VocabularyItemInput(
        word="頑張る",
        reading="がんばる",
        jlpt_level=JlptLevel.N4,
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.VERB,
                meaning_zh="努力、加油",
                example_sentences=[
                    ExampleSentence(
                        japanese="試験のために頑張ります。",
                        reading="しけんのためにがんばります。",
                        chinese="為了考試而努力。",
                    )
                ],
            )
        ],
    ),
]

TEST_GRAMMAR: list[GrammarItemInput] = [
    GrammarItemInput(
        grammar_point="ないでください",
        jlpt_level=JlptLevel.N4,
        usages=[
            GrammarUsageBase(
                semantic_concept="請不要…（禮貌禁止）",
                connection_rule="Vない + でください",
                meaning_zh="要求對方不要做某事",
                example_sentences=[
                    ExampleSentence(
                        japanese="ここでタバコを吸わないでください。",
                        chinese="請不要在這裡吸煙。",
                    )
                ],
            )
        ],
    ),
    GrammarItemInput(
        grammar_point="なくてもいい",
        jlpt_level=JlptLevel.N4,
        usages=[
            GrammarUsageBase(
                semantic_concept="不必…；不…也可以",
                connection_rule="Vない + くてもいい",
                meaning_zh="表示沒有必要做某事",
                example_sentences=[
                    ExampleSentence(
                        japanese="靴を脱がなくてもいいです。",
                        chinese="不脱鞋也可以。",
                    )
                ],
            )
        ],
    ),
    GrammarItemInput(
        grammar_point="〜たり〜たり",
        jlpt_level=JlptLevel.N4,
        usages=[
            GrammarUsageBase(
                semantic_concept="又…又…；列舉動作",
                connection_rule="Vた + り、Vた + り + する",
                meaning_zh="從眾多事物中舉出代表性例子",
                example_sentences=[
                    ExampleSentence(
                        japanese="週末は買い物をしたり、映画を見たりします。",
                        chinese="週末又逛街又看電影。",
                    )
                ],
            )
        ],
    ),
    GrammarItemInput(
        grammar_point="のは",
        jlpt_level=JlptLevel.N4,
        usages=[
            GrammarUsageBase(
                semantic_concept="針對某行為發表評價、判斷或感想",
                connection_rule="[動詞辞書形]の + は + [評價/感想]",
                meaning_zh="後面接評價、判斷、感想",
                example_sentences=[
                    ExampleSentence(
                        japanese="早起きするのは、健康にいいです。",
                        reading="はやおきするのは、けんこうにいいです。",
                        chinese="早起這件事對健康很好。",
                    )
                ],
            )
        ],
    ),
]


def _ensure_seed_ingestion(svc: IngestionService) -> UUID:
    content_hash = compute_upload_hash(SEED_MARKER, "application/octet-stream")
    db = svc.db
    existing = (
        db.table("content_ingestions")
        .select("id")
        .eq("content_hash", content_hash)
        .maybe_single()
        .execute()
    )
    if existing is not None and existing.data:
        return UUID(existing.data["id"])

    result = (
        db.table("content_ingestions")
        .insert(
            {
                "content_hash": content_hash,
                "source_type": SourceType.MANUAL.value,
                "mime_type": "application/octet-stream",
                "file_name": "seed_test_data.py",
                "parsed_payload": {"seed": True, "version": 1},
            }
        )
        .execute()
    )
    return UUID(result.data[0]["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed test learning content")
    parser.add_argument("--clear", action="store_true", help="Clear learning tables first")
    args = parser.parse_args()

    if args.clear:
        import subprocess

        subprocess.run(
            [sys.executable, str(BACKEND_ROOT / "scripts" / "db_cleanup.py")],
            check=True,
        )

    svc = IngestionService()
    ingestion_id = _ensure_seed_ingestion(svc)

    vocab_count = svc._persist_vocabularies_bulk(  # noqa: SLF001
        TEST_VOCAB, ingestion_id, user_id=None, source_type=SourceType.MANUAL
    )
    grammar_count = svc._persist_grammars_bulk(  # noqa: SLF001
        TEST_GRAMMAR, ingestion_id, user_id=None, source_type=SourceType.MANUAL
    )

    db = svc.db
    total_vocab = db.table("vocabularies").select("id", count="exact").limit(1).execute().count
    total_grammar = db.table("grammars").select("id", count="exact").limit(1).execute().count

    print(f"[Seed] Vocab upserted: {vocab_count} | Grammar upserted: {grammar_count}")
    print(f"[Seed] DB totals — vocab: {total_vocab}, grammar: {total_grammar}")


if __name__ == "__main__":
    main()
