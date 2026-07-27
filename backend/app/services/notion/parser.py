"""Rule-based parser: Notion blocks → grammar/vocab items (zero AI)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.models.schemas.common import ExampleSentence, PartOfSpeech
from app.models.schemas.grammar import GrammarItemInput, GrammarUsageBase
from app.models.schemas.ingestion import IngestionParseResult
from app.models.schemas.vocab import VocabularyDefinitionBase, VocabularyItemInput
from app.services.hash_service import grammar_source_hash
from app.services.notion.analyzer import SectionPreview, build_sections
from app.services.notion.client import FlatBlock

HEADING_TYPES = frozenset({"heading_1", "heading_2", "heading_3", "heading_4"})
TEXT_TYPES = frozenset(
    {
        "paragraph",
        "bulleted_list_item",
        "numbered_list_item",
        "to_do",
        "quote",
        "callout",
        "toggle",
        "code",
    }
)

SKIP_H1 = frozenset({"文法：", "文法:", "補充", "題目:", "題目："})

_META_PREFIXES = (
    "例：",
    "例:",
    "•",
    "◦",
    "結構：",
    "分析",
    "繁體字：",
    "接続：",
    "意思：",
    "變化方式",
    "【文法】",
    "【例句】",
    "💬",
    "💡",
    "1. 語法結構",
    "其他常見例句",
    "實用例句",
    "常見搭配詞",
)

_USAGE_HEADING = re.compile(
    r"^用法\s*[①②③④⑤⑥⑦⑧⑨⑩\u2460-\u2469A-Za-z0-9]*\s*[：:]"
)
_QUOTED_VARIANT = re.compile(r"^「[^」]{1,48}」[：:]")
_SECTION_LABEL = re.compile(r"^[一二三四五六七八九十百千万]+[、,.．]")
_GRAMMAR_PATTERN_H3 = re.compile(
    r"^[ぁ-んァ-ヶーA-Za-z0-9０-９].{0,45}(\+|＋|形|ても|のに|場合|辞書形)"
)

_GRAMMAR_BRACKET = re.compile(
    r"^(?:\d+\.\s*)?【([^】]+)】\s*(?:→|\$\\rightarrow\$)?\s*(.*)$"
)
_NUMBERED_BRACKET = re.compile(r"^\d+\.\s*【([^】]+)】")
_VOCAB_LINE = re.compile(
    r"^([ぁ-んァ-ヶーa-zA-Z0-9（）()・]+)\s+(\S+|ー)\s+(.+)$"
)


class _ParseMode(Enum):
    IDLE = "idle"
    TOPIC = "topic"
    CONTAINER = "container"
    GROUP = "group"


@dataclass
class _GrammarDraft:
    grammar_point: str
    notion_block_id: str | None = None
    notion_page_id: str | None = None
    image_urls: list[str] = field(default_factory=list)
    body_lines: list[str] = field(default_factory=list)
    block_ids: list[str] = field(default_factory=list)
    usages: list[GrammarUsageBase] = field(default_factory=list)
    _usage_lines: list[str] = field(default_factory=list)
    _usage_title: str | None = None

    def track_block(self, block_id: str | None) -> None:
        if block_id and block_id not in self.block_ids:
            self.block_ids.append(block_id)

    def add_image(self, url: str) -> None:
        if url and url not in self.image_urls:
            self.image_urls.append(url)

    def add_line(self, line: str) -> None:
        cleaned = line.strip()
        if not cleaned:
            return
        if self._usage_title is not None:
            self._usage_lines.append(cleaned)
        else:
            self.body_lines.append(cleaned)

    def start_usage(self, title: str) -> None:
        self._finish_usage()
        self._usage_title = title
        self._usage_lines = []

    def _finish_usage(self) -> None:
        if self._usage_title is None:
            return
        examples = _extract_examples(self._usage_lines)
        concept = self._usage_title
        self.usages.append(
            GrammarUsageBase(
                semantic_concept=concept,
                connection_rule=concept,
                meaning_zh="\n".join(self._usage_lines) if self._usage_lines else concept,
                example_sentences=examples,
            )
        )
        self._usage_title = None
        self._usage_lines = []

    def to_item(self) -> GrammarItemInput:
        self._finish_usage()
        if self.usages:
            usages = self.usages
        elif self.body_lines:
            usages = [
                GrammarUsageBase(
                    semantic_concept=self.grammar_point,
                    connection_rule="",
                    meaning_zh="\n".join(self.body_lines[:80]),
                    example_sentences=_extract_examples(self.body_lines),
                )
            ]
        else:
            usages = [
                GrammarUsageBase(
                    semantic_concept=self.grammar_point,
                    connection_rule=self.grammar_point,
                )
            ]
        source_hash = grammar_source_hash(
            grammar_point=self.grammar_point,
            image_urls=self.image_urls,
            usages=usages,
            block_ids=self.block_ids,
        )
        return GrammarItemInput(
            grammar_point=_normalize_grammar_title(self.grammar_point),
            image_urls=list(self.image_urls),
            usages=usages,
            notion_block_id=self.notion_block_id,
            notion_page_id=self.notion_page_id,
            source_content_hash=source_hash,
            block_ids=list(self.block_ids),
        )


@dataclass
class HeadingCandidate:
    """A top-level heading_1 + its immediate heading_2 child titles, worth
    asking an AI classifier whether it's a category label (children should
    each become an independent grammar point) or a grammar point itself
    (children are usage variants). See notion/heading_classifier.py.
    """

    block_id: str
    heading_text: str
    children: list[str]


def collect_heading_candidates(blocks: list[FlatBlock]) -> list[HeadingCandidate]:
    """Top-level headings (excluding known structural dividers) with 2+
    immediate heading_2 children — the ambiguous cases where the parser can't
    tell, from rules alone, whether the heading is a category or a topic.
    """
    candidates: list[HeadingCandidate] = []
    for idx, block in enumerate(blocks):
        if block.type != "heading_1" or block.depth != 0:
            continue
        text = block.text.strip()
        if not text or _is_skip_h1(text):
            continue

        children: list[str] = []
        for child in blocks[idx + 1 :]:
            if child.type == "heading_1" and child.depth == 0:
                break
            if child.type == "heading_2" and child.depth == 1:
                child_text = child.text.strip()
                if child_text:
                    children.append(child_text)

        if len(children) >= 2:
            candidates.append(
                HeadingCandidate(block_id=block.id, heading_text=text, children=children)
            )
    return candidates


def parse_blocks(
    blocks: list[FlatBlock],
    *,
    focus: str = "both",
    sections: list[SectionPreview] | None = None,
    notion_page_id: str | None = None,
    category_block_ids: set[str] | None = None,
) -> IngestionParseResult:
    grammars: list[GrammarItemInput] = []
    vocabularies: list[VocabularyItemInput] = []

    if focus in {"grammar", "both"}:
        grammars = _parse_grammar_blocks(
            blocks, notion_page_id=notion_page_id, category_block_ids=category_block_ids
        )
    if focus in {"vocabulary", "both"}:
        section_list = sections if sections is not None else build_sections(blocks)
        vocabularies = _parse_vocab_sections(
            section_list, blocks, notion_page_id=notion_page_id
        )

    return IngestionParseResult(vocabularies=vocabularies, grammars=grammars)


def parse_sections(
    sections: list[SectionPreview],
    *,
    focus: str = "both",
    blocks: list[FlatBlock] | None = None,
) -> IngestionParseResult:
    """Backward-compatible entry point — prefers block tree when blocks are supplied."""
    if blocks is not None and focus in {"grammar", "both"}:
        return parse_blocks(blocks, focus=focus, sections=sections)
    if blocks is not None:
        return parse_blocks(blocks, focus=focus, sections=sections)
    return IngestionParseResult(
        vocabularies=_parse_vocab_sections(sections, []) if focus != "grammar" else [],
        grammars=[],
    )


def _parse_grammar_blocks(
    blocks: list[FlatBlock],
    *,
    notion_page_id: str | None = None,
    category_block_ids: set[str] | None = None,
) -> list[GrammarItemInput]:
    grammars: list[GrammarItemInput] = []
    seen: set[str] = set()
    category_ids = category_block_ids or set()

    mode = _ParseMode.IDLE
    anchor_depth = 0
    current: _GrammarDraft | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        item = current.to_item()
        key = item.notion_block_id or item.grammar_point
        if item.grammar_point and key not in seen:
            seen.add(key)
            grammars.append(item)
        current = None

    def open_topic(title: str, block_id: str | None = None) -> None:
        nonlocal current
        flush()
        current = _GrammarDraft(
            grammar_point=title,
            notion_block_id=block_id,
            notion_page_id=notion_page_id,
        )
        current.track_block(block_id)

    def track_current(block: FlatBlock) -> None:
        if current is not None:
            current.track_block(block.id)

    for idx, block in enumerate(blocks):
        if block.type in HEADING_TYPES:
            level = int(block.type.split("_")[1])
            text = block.text.strip()

            if block.type == "heading_2" and block.depth == 0 and not _is_meta_heading(text):
                flush()
                mode = _ParseMode.TOPIC
                anchor_depth = 0
                open_topic(text, block.id)
                continue

            if level == 1:
                if _is_skip_h1(text):
                    flush()
                    mode = _ParseMode.IDLE
                    continue

                if block.id in category_ids:
                    flush()
                    mode = _ParseMode.CONTAINER
                    anchor_depth = block.depth
                    continue

                if _is_group_parent(blocks, idx):
                    flush()
                    mode = _ParseMode.GROUP
                    anchor_depth = block.depth
                    continue

                if mode == _ParseMode.GROUP and block.depth == anchor_depth + 1:
                    if not _is_meta_heading(text):
                        open_topic(text, block.id)
                    elif current is not None:
                        track_current(block)
                        current.add_line(text)
                    continue

                if block.depth != 0:
                    if current is not None and _should_start_usage(text, level):
                        track_current(block)
                        current.start_usage(text)
                    elif current is not None and text:
                        track_current(block)
                        current.add_line(text)
                    continue

                flush()
                mode = _ParseMode.TOPIC
                anchor_depth = block.depth
                open_topic(text, block.id)
                continue

            if mode == _ParseMode.CONTAINER and level == 2:
                if block.depth == anchor_depth + 1 and not _is_meta_heading(text):
                    open_topic(text, block.id)
                elif current is not None:
                    track_current(block)
                    _handle_in_grammar_heading(
                        current, text, level=level, depth=block.depth, anchor_depth=anchor_depth
                    )
                continue

            if mode == _ParseMode.GROUP and level in {1, 2}:
                if block.depth == anchor_depth + 1 and not _is_meta_heading(text):
                    open_topic(_normalize_grammar_title(text), block.id)
                elif current is not None:
                    track_current(block)
                    _handle_in_grammar_heading(
                        current, text, level=level, depth=block.depth, anchor_depth=anchor_depth
                    )
                continue

            if mode == _ParseMode.TOPIC and level == 2:
                if block.depth == anchor_depth + 1 and not _is_meta_heading(text):
                    track_current(block)
                    if current is None:
                        open_topic(text, block.id)
                    else:
                        current.start_usage(text)
                elif current is not None:
                    track_current(block)
                    _handle_in_grammar_heading(
                        current, text, level=level, depth=block.depth, anchor_depth=anchor_depth
                    )
                continue

            if current is not None and block.depth > anchor_depth:
                track_current(block)
                if _handle_in_grammar_heading(
                    current, text, level=level, depth=block.depth, anchor_depth=anchor_depth
                ):
                    continue

            if current is not None and text and not _is_empty_heading(text):
                track_current(block)
                current.add_line(text)
            continue

        if block.type == "image" and block.image_url:
            if current is not None:
                track_current(block)
                current.add_image(block.image_url)
            continue

        if block.type in TEXT_TYPES and block.text.strip():
            if current is not None:
                track_current(block)
                prefix = "• " if block.type == "bulleted_list_item" else ""
                current.add_line(prefix + block.text.strip())
            continue

        if block.type == "table_row" and block.table_rows and current is not None:
            track_current(block)
            for cell in block.table_rows:
                if cell.strip():
                    current.add_line(cell.strip())

    flush()
    return grammars


def _is_skip_h1(text: str) -> bool:
    return text.strip() in SKIP_H1


def _is_meta_heading(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True
    if _should_start_usage(cleaned, level=3):
        return False
    if cleaned in {"用法：", "用法:"}:
        return True
    if cleaned.startswith("• 用法：") or cleaned.startswith("• 用法:"):
        return True
    if cleaned.startswith(_META_PREFIXES):
        return True
    if _NUMBERED_BRACKET.match(cleaned) and "【" in cleaned:
        return False
    if cleaned.startswith("【") and "】" in cleaned:
        return False
    return False


def _should_start_usage(text: str, level: int) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    if _USAGE_HEADING.match(cleaned):
        return True
    if _QUOTED_VARIANT.match(cleaned):
        return True
    if _SECTION_LABEL.match(cleaned):
        return True
    if level >= 3 and _GRAMMAR_PATTERN_H3.match(cleaned):
        return True
    return False


def _handle_in_grammar_heading(
    current: _GrammarDraft,
    text: str,
    *,
    level: int,
    depth: int,
    anchor_depth: int,
) -> bool:
    if depth <= anchor_depth:
        return False
    if _should_start_usage(text, level):
        current.start_usage(text)
        return True
    if _is_meta_heading(text):
        current.add_line(text)
        return True
    if level >= 2:
        current.add_line(text)
        return True
    return False


def _is_empty_heading(text: str) -> bool:
    return not text.strip()


def _is_group_parent(blocks: list[FlatBlock], idx: int) -> bool:
    block = blocks[idx]
    if block.type != "heading_1":
        return False
    text = block.text.strip()
    if _is_skip_h1(text):
        return False

    parent_depth = block.depth
    for j in range(idx + 1, min(idx + 40, len(blocks))):
        child = blocks[j]
        if child.type not in HEADING_TYPES:
            continue
        if child.depth <= parent_depth:
            break
        if child.depth != parent_depth + 1:
            continue
        if child.type not in {"heading_1", "heading_2"}:
            continue
        child_text = child.text.strip()
        if child.type == "heading_1":
            return True
        if _NUMBERED_BRACKET.match(child_text):
            return True
    return False


def _normalize_grammar_title(text: str) -> str:
    cleaned = text.strip()
    bracket = _GRAMMAR_BRACKET.match(cleaned)
    if bracket:
        point, rule = bracket.groups()
        if rule.strip():
            return f"【{point.strip()}】{rule.strip()}"
        return point.strip()
    numbered = _NUMBERED_BRACKET.match(cleaned)
    if numbered:
        return numbered.group(1).strip()
    return cleaned


def _extract_examples(lines: list[str]) -> list[ExampleSentence]:
    examples: list[ExampleSentence] = []
    for line in lines:
        cleaned = line.lstrip("• ").lstrip("◦ ").lstrip("1. ").strip()
        if not cleaned:
            continue
        if cleaned.startswith("例：") or cleaned.startswith("例:"):
            cleaned = cleaned.split("：", 1)[-1].split(":", 1)[-1].strip()
        if cleaned.startswith(("結構", "用法", "接続", "繁體字", "意思")):
            continue
        if re.search(r"[ぁ-んァ-ヶ]", cleaned):
            examples.append(ExampleSentence(japanese=cleaned))
    return examples[:8]


def _parse_vocab_sections(
    sections: list[SectionPreview],
    blocks: list[FlatBlock],
    *,
    notion_page_id: str | None = None,
) -> list[VocabularyItemInput]:
    vocabularies: list[VocabularyItemInput] = []
    seen: set[tuple[str, str]] = set()

    def _add(vocab: VocabularyItemInput | None) -> None:
        if not vocab:
            return
        vocab.notion_page_id = notion_page_id
        key = (vocab.word, vocab.reading or "")
        if key not in seen:
            seen.add(key)
            vocabularies.append(vocab)

    for section in sections:
        for line in section.text_lines:
            _add(_line_to_vocab(line))

        for row in section.table_rows:
            _add(_row_to_vocab(row))

    if not vocabularies and blocks:
        for block in blocks:
            if block.type != "table_row":
                continue
            cells = block.table_rows
            if isinstance(cells, list) and cells and isinstance(cells[0], list):
                # Unexpected nested shape — flatten one level
                for nested in cells:
                    if isinstance(nested, list):
                        _add(_row_to_vocab(nested))
            elif isinstance(cells, list):
                _add(_row_to_vocab(cells))

    return vocabularies


_VOCAB_HEADER_MARKERS = frozenset({"發音", "発音", "單字", "単字", "汉字", "漢字", "中文", "例句", "補充", "补充"})


def _is_vocab_header_row(cells: list[str]) -> bool:
    joined = "".join(c.strip() for c in cells[:3] if c)
    return any(marker in joined for marker in _VOCAB_HEADER_MARKERS)


def _parse_example_cell(raw: str) -> list[ExampleSentence]:
    """Parse Notion 例句 cell: '日文 → 中文' (possibly multi-line)."""
    text = (raw or "").strip()
    if not text:
        return []

    examples: list[ExampleSentence] = []
    chunks = re.split(r"[\n\r]+", text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = re.split(r"\s*(?:→|⇒|➔|➜)\s*", chunk, maxsplit=1)
        japanese = parts[0].strip()
        chinese = parts[1].strip() if len(parts) > 1 else None
        if japanese:
            examples.append(ExampleSentence(japanese=japanese, chinese=chinese or None))
    return examples


def _row_to_vocab(row: list[str]) -> VocabularyItemInput | None:
    """Map Notion 5-col table: 發音 | 單字 | 中文 | 例句 | 補充."""
    cells = [ (c or "").strip() for c in row ]
    # Drop trailing empty cells but keep positional alignment for first 5
    while cells and not cells[-1]:
        cells.pop()
    if len(cells) < 3:
        # Fallback: join and try legacy line regex
        joined = " ".join(c for c in cells if c)
        return _line_to_vocab(joined) if joined else None
    if _is_vocab_header_row(cells):
        return None

    reading = cells[0]
    word_token = cells[1]
    meaning_zh = cells[2]
    if not reading or not meaning_zh:
        return None

    word = reading if word_token in {"ー", "-", "－", ""} else word_token
    examples = _parse_example_cell(cells[3]) if len(cells) > 3 else []
    notes_zh = cells[4].strip() if len(cells) > 4 and cells[4].strip() else None

    return VocabularyItemInput(
        word=word.strip(),
        reading=reading.strip(),
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.OTHER,
                meaning_zh=meaning_zh.strip(),
                example_sentences=examples,
                notes_zh=notes_zh,
            )
        ],
    )


def _line_to_vocab(line: str) -> VocabularyItemInput | None:
    match = _VOCAB_LINE.match(line.strip())
    if not match:
        return None
    reading, word_token, meaning_zh = match.groups()
    word = reading if word_token == "ー" else word_token
    return VocabularyItemInput(
        word=word.strip(),
        reading=reading.strip(),
        definitions=[
            VocabularyDefinitionBase(
                part_of_speech=PartOfSpeech.OTHER,
                meaning_zh=meaning_zh.strip(),
            )
        ],
    )
