"""Curriculum data pipeline — PDF extraction with multi-line note capture."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.curriculum.grammar_extractor import GrammarCard, extract_grammar_cards

_VOCAB_LINE = re.compile(
    r"^([ぁ-んァ-ヶーa-zA-Z0-9（）()・]+)\s+(\S+|ー)\s+(.+)$"
)
_VOCAB_SKIP = re.compile(
    r"^(⽇|平仮名|[0-9]+$|A\.|B\.|C\.|→|•|◦|《|例：|❌|✅|🧠|句型|結構|⽤法|分析|其他|實用|常⾒|搭配|句型)"
)
_KANJI = re.compile(r"[\u4e00-\u9fff々〆ヵヶ]")
_KATAKANA = re.compile(r"^[\u30a0-\u30ffー・]+$")


@dataclass
class VocabRawRow:
    entry_id: str
    kanji: str
    kana: str
    meaning_zh: str
    part_of_speech_guess: str
    raw_notes: str
    source_line: str
    parse_status: str = "complete"


@dataclass
class GrammarRawRow:
    entry_id: str
    grammar_point: str
    semantic_concept: str
    connection_rule: str
    meaning_zh: str
    example_japanese: str
    example_chinese: str
    raw_notes: str
    source_page: str
    source_line: str
    parse_status: str = "complete"


def _normalize_kana(reading: str) -> str:
    return re.sub(r"（な）|\(な\)", "", reading).strip()


def _split_kanji_kana(reading: str, word_token: str) -> tuple[str, str]:
    if word_token == "ー":
        kana = _normalize_kana(reading)
        kanji = kana if _KANJI.search(kana) else ""
        if not kanji:
            return "", kana
        return kanji, kana

    kanji = word_token.strip()
    kana = _normalize_kana(reading)
    if not _KANJI.search(kanji):
        return "", kanji if _KATAKANA.search(kanji) else kana or kanji
    return kanji, kana


def _guess_pos(kanji: str, kana: str, reading: str) -> str:
    surface = kanji or kana
    if "（な）" in reading or "(な)" in reading:
        return "na_adjective"
    if surface.endswith("する") or kana.endswith("する"):
        return "verb"
    if surface.endswith("い") and re.search(r"[ぁ-ん]", surface):
        return "i_adjective"
    if surface.endswith("的"):
        return "na_adjective"
    if _KATAKANA.match(surface):
        return "noun"
    return "other"


def extract_vocabulary_rows(text: str) -> list[VocabRawRow]:
    lines = [line.strip().replace("\x00", "") for line in text.splitlines()]
    rows: list[VocabRawRow] = []
    seen: set[tuple[str, str]] = set()
    pending_notes: list[str] = []
    entry_counter = 0

    def flush_notes_to_last() -> None:
        nonlocal pending_notes
        if pending_notes and rows:
            extra = " ".join(pending_notes).strip()
            if extra:
                rows[-1].raw_notes = (rows[-1].raw_notes + " " + extra).strip()
        pending_notes = []

    for line in lines:
        if not line:
            continue

        match = _VOCAB_LINE.match(line) if not _VOCAB_SKIP.search(line) else None
        if match:
            flush_notes_to_last()
            reading, word_token, meaning_zh = match.groups()
            kanji, kana = _split_kanji_kana(reading.strip(), word_token)
            key = (kanji or kana, kana)
            if key in seen or not (kanji or kana) or not meaning_zh.strip():
                continue
            seen.add(key)
            entry_counter += 1
            rows.append(
                VocabRawRow(
                    entry_id=f"V{entry_counter:04d}",
                    kanji=kanji,
                    kana=kana,
                    meaning_zh=meaning_zh.strip(),
                    part_of_speech_guess=_guess_pos(kanji, kana, reading),
                    raw_notes="",
                    source_line=line,
                    parse_status="partial" if len(meaning_zh) < 2 else "complete",
                )
            )
        elif rows and not _VOCAB_SKIP.search(line):
            pending_notes.append(line)

    flush_notes_to_last()
    return rows


def extract_grammar_rows_from_pdf(pdf_bytes: bytes) -> list[GrammarRawRow]:
    cards = extract_grammar_cards(pdf_bytes)
    rows: list[GrammarRawRow] = []
    for index, card in enumerate(cards, start=1):
        examples_jp = " | ".join(card.examples_jp)
        examples_zh = " | ".join(card.examples_zh)
        rows.append(
            GrammarRawRow(
                entry_id=f"G{index:04d}",
                grammar_point=card.grammar_point,
                semantic_concept=card.meaning_zh or card.connection_rule or "",
                connection_rule=card.connection_rule or card.usage_notes,
                meaning_zh=card.meaning_zh,
                example_japanese=examples_jp,
                example_chinese=examples_zh,
                raw_notes=card.usage_notes,
                source_page=str(card.source_page),
                source_line=card.raw_block[:120],
                parse_status=card.parse_status,
            )
        )
    return rows

