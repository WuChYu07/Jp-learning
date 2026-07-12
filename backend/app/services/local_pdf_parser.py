"""Rule-based parser for structured Komorebi study PDFs (zero AI token cost)."""

from __future__ import annotations

import re

from app.models.schemas.common import PartOfSpeech
from app.models.schemas.grammar import GrammarItemInput, GrammarUsageBase
from app.models.schemas.ingestion import IngestionParseResult
from app.models.schemas.vocab import VocabularyDefinitionBase, VocabularyItemInput

_VOCAB_LINE = re.compile(
    r"^([ぁ-んァ-ヶーa-zA-Z0-9（）()・]+)\s+(\S+|ー)\s+(.+)$"
)
_VOCAB_SKIP = re.compile(
    r"^(⽇|平仮名|[0-9]+$|A\.|B\.|C\.|→|•|◦|《|例：|❌|✅|🧠|句型|結構|⽤法|分析|其他|實用|常⾒|搭配)"
)
_GRAMMAR_BRACKET = re.compile(
    r"^(?:\d+\.\s*)?【([^】]+)】\s*(?:→|\$\\rightarrow\$)?\s*(.*)$"
)
_GRAMMAR_WAVE = re.compile(r"^(〜.+?)\s{2,}(.+)$")
_GRAMMAR_PATTERN = re.compile(
    r"^(N[^。]{0,40}|V[^。]{0,40}|〜[^。]{0,40}|[ぁ-んァ-ヶ].{0,20}(?:です|ます|たい))\s*$"
)
_GRAMMAR_SKIP = re.compile(r"^(⽇|句型|中⽂|形容詞|[0-9]+$|•|◦|例：|《|❌|✅|🧠|注意)")


def _guess_pos(word: str, reading: str) -> PartOfSpeech:
    if word.endswith("する") or reading.endswith("する"):
        return PartOfSpeech.VERB
    if "（な）" in reading or "(な)" in reading:
        return PartOfSpeech.NA_ADJECTIVE
    if word.endswith("い") and re.search(r"[ぁ-ん]", word):
        return PartOfSpeech.I_ADJECTIVE
    if word.endswith("的"):
        return PartOfSpeech.NA_ADJECTIVE
    return PartOfSpeech.OTHER


def parse_vocabulary_pdf(text: str) -> IngestionParseResult:
    items: list[VocabularyItemInput] = []
    seen: set[tuple[str, str]] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _VOCAB_SKIP.search(line):
            continue

        match = _VOCAB_LINE.match(line)
        if not match:
            continue

        reading, word_token, meaning_zh = match.groups()
        reading = reading.strip()
        meaning_zh = meaning_zh.strip().replace("\x00", "")

        if word_token == "ー":
            word = re.sub(r"（な）|\(な\)", "", reading).strip()
        else:
            word = word_token.strip()

        if len(meaning_zh) < 1 or len(word) < 1:
            continue

        key = (word, reading)
        if key in seen:
            continue
        seen.add(key)

        items.append(
            VocabularyItemInput(
                word=word,
                reading=reading,
                definitions=[
                    VocabularyDefinitionBase(
                        part_of_speech=_guess_pos(word, reading),
                        meaning_zh=meaning_zh,
                    )
                ],
            )
        )

    return IngestionParseResult(vocabularies=items)


def parse_grammar_pdf(text: str) -> IngestionParseResult:
    items: list[GrammarItemInput] = []
    seen: set[str] = set()

    def add_grammar(point: str, rule: str, concept: str | None = None) -> None:
        point = point.strip()
        rule = rule.strip()
        if not point or point in seen:
            return
        seen.add(point)
        items.append(
            GrammarItemInput(
                grammar_point=point,
                usages=[
                    GrammarUsageBase(
                        semantic_concept=concept or rule or point,
                        connection_rule=rule or point,
                        meaning_zh=concept or rule,
                    )
                ],
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _GRAMMAR_SKIP.search(line):
            continue

        bracket = _GRAMMAR_BRACKET.match(line)
        if bracket:
            point, rule = bracket.groups()
            add_grammar(point, rule, rule or point)
            continue

        wave = _GRAMMAR_WAVE.match(line)
        if wave:
            point, concept = wave.groups()
            add_grammar(point, point, concept)
            continue

        if _GRAMMAR_PATTERN.match(line) and len(line) <= 40:
            add_grammar(line, line, line)

    return IngestionParseResult(grammars=items)
