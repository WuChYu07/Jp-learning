"""Page-aware grammar card extractor for Komorebi grammar PDF."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pypdf import PdfReader

_PAGE_FOOTER = re.compile(r"^⽇\s*⽂\s*筆\s*記$|^[0-9]+$")
_HAS_JP = re.compile(r"[ぁ-んァ-ヶ一-龯]")
_HAS_ZH = re.compile(r"[\u4e00-\u9fff]")
_EXAMPLE = re.compile(r"^(例[：:]|◦|・|•)")
_GRAMMAR_POINT = re.compile(
    r"^(【[^】]+】|〜|~|[ぁ-んァ-ヶ].{1,35})$"
)
_SKIP_LINE = re.compile(
    r"^(⽇|句型|中⽂|形容詞|✅|❌|🧠|🚨|👉|🔹|🔁|📌|🟢|💡|➡|題⽬|排序|Nniyote)"
)
_SECTION = re.compile(r"^【([^】]+)】\s*(.*)$")
_NUMBERED_BRACKET = re.compile(
    r"^(?:\d+\.\s*)?【([^】]+)】\s*(?:→|\$\\rightarrow\$)?\s*(.*)$"
)
_MEANING_HINT = re.compile(
    r"翻譯|表示|表⽰|用來|用於|表達|意思|必須|不要|請|用法|這個句型|這句型|用於|語意|功能|核⼼"
)
_JUNK_POINTS = frozenset(
    {
        "【文法】",
        "【例句】",
        "【方法】",
        "【解法】",
        "【解说】",
        "【解説】",
        "【違い】",
        "文法",
        "例句",
        "方法",
        "解説",
        "解法",
        "違い",
        "Nniyote",
        "た形",
        "て形",
        "受⾝形",
        "修飾名詞",
        "敬語（尊敬語、謙讓語）",
    }
)


@dataclass
class GrammarCard:
    grammar_point: str
    meaning_zh: str = ""
    connection_rule: str = ""
    usage_notes: str = ""
    examples_jp: list[str] = field(default_factory=list)
    examples_zh: list[str] = field(default_factory=list)
    source_page: int = 0
    parse_status: str = "complete"  # complete | partial | index_only
    raw_block: str = ""


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return text.replace("\x00", "").replace("\u2003", " ").strip()


def _is_footer(line: str) -> bool:
    return bool(_PAGE_FOOTER.match(line.strip()))


def _extract_jp_example(line: str) -> str | None:
    raw = line.strip()
    if not (_EXAMPLE.match(raw) or raw.startswith("例")):
        return None
    line = re.sub(r"^例[：:]\s*", "", raw)
    line = re.sub(r"^[◦・•]\s*", "", line)
    if _HAS_JP.search(line):
        jp = re.split(r"[（(]", line)[0].strip()
        if len(jp) >= 2:
            return jp
    return None


def _extract_zh_from_parens(line: str) -> str | None:
    m = re.search(r"[（(]([^）)]+)[）)]", line)
    if m and _HAS_ZH.search(m.group(1)):
        return m.group(1).strip()
    return None


def _looks_like_meaning(line: str) -> bool:
    line = line.strip()
    if not _HAS_ZH.search(line):
        return False
    if _MEANING_HINT.search(line):
        return True
    if not _HAS_JP.search(line) and 4 <= len(line) <= 120:
        return True
    return False


def _looks_like_grammar_point(line: str) -> bool:
    line = line.strip()
    if not line or line in _JUNK_POINTS or _SKIP_LINE.search(line) or _EXAMPLE.match(line):
        return False
    if _SECTION.match(line):
        return False
    if _looks_like_meaning(line) and not line.startswith("〜") and not line.startswith("~"):
        return False
    if line.startswith("〜") or line.startswith("~"):
        return len(line) <= 50
    if _HAS_JP.search(line) and len(line) <= 45:
        if any(x in line for x in ("ください", "ません", "ない", "ます", "たい", "ている", "てお", "てあ", "なければ", "なくて")):
            return True
        if re.match(r"^[ぁ-んァ-ヶー・／/（）()A-Za-z0-9\s~〜]+$", line):
            return True
    return False


def _is_index_page(lines: list[str]) -> bool:
    content = [line for line in lines if line and not _is_footer(line)]
    if len(content) < 4:
        return False
    wave = sum(1 for line in content if line.startswith("〜") or line.startswith("~"))
    rich = sum(
        1
        for line in content
        if "例：" in line
        or "例:" in line
        or (len(line) > 80 and _HAS_ZH.search(line))
        or "【文法】" in line
        or "【方法】" in line
    )
    return wave >= 4 and rich == 0


def _parse_index_page(lines: list[str], page_num: int) -> list[GrammarCard]:
    cards: list[GrammarCard] = []
    pending_point: str | None = None

    for line in lines:
        line = line.strip()
        if not line or _is_footer(line):
            continue

        if line.startswith("〜") or line.startswith("~"):
            for part in re.split(r"[\s\u3000]+", line):
                part = part.strip().rstrip("、，,")
                if part.startswith("〜") or part.startswith("~"):
                    cards.append(
                        GrammarCard(
                            grammar_point=part,
                            parse_status="index_only",
                            source_page=page_num,
                            raw_block=line,
                        )
                    )
            pending_point = None
            continue

        if pending_point and _looks_like_meaning(line):
            cards.append(
                GrammarCard(
                    grammar_point=pending_point,
                    meaning_zh=line,
                    parse_status="partial",
                    source_page=page_num,
                    raw_block=f"{pending_point} | {line}",
                )
            )
            pending_point = None
        elif _looks_like_grammar_point(line) and (line.startswith("〜") or line.startswith("~")):
            pending_point = line

    return cards


def _finalize_card(card: GrammarCard | None) -> GrammarCard | None:
    if card is None or not card.grammar_point:
        return None
    if card.grammar_point in _JUNK_POINTS:
        return None
    if card.parse_status == "index_only":
        return card

    has_meaning = bool(card.meaning_zh and card.meaning_zh != card.grammar_point)
    has_rule = bool(card.connection_rule and card.connection_rule != card.grammar_point)
    has_examples = bool(card.examples_jp)

    if has_meaning and (has_examples or has_rule):
        card.parse_status = "complete"
    elif has_meaning or has_examples or has_rule:
        card.parse_status = "partial"
    else:
        card.parse_status = "partial"
    return card


def _parse_grammar_block(lines: list[str], page_num: int, title: str = "") -> list[GrammarCard]:
    cards: list[GrammarCard] = []
    current: GrammarCard | None = None
    section = ""
    pending_point: str | None = None

    def start_card(point: str, meaning: str = "") -> None:
        nonlocal current, pending_point
        finalized = _finalize_card(current)
        if finalized:
            cards.append(finalized)
        point = point.strip()
        if point in _JUNK_POINTS:
            pending_point = None
            return
        current = GrammarCard(
            grammar_point=point,
            meaning_zh=meaning,
            source_page=page_num,
            raw_block=point if not meaning else f"{point} | {meaning}",
        )
        pending_point = None

    if title and title not in _JUNK_POINTS and (_looks_like_grammar_point(title) or title.startswith("〜")):
        start_card(title)

    for raw in lines:
        line = _clean(raw)
        if not line or _is_footer(line):
            continue

        sec = _SECTION.match(line)
        if sec:
            section = sec.group(1)
            rest = sec.group(2).strip()
            if section in ("文法", "解法") and rest:
                if _looks_like_grammar_point(rest):
                    start_card(rest)
                elif _looks_like_meaning(rest) and current:
                    current.meaning_zh = rest
                elif _looks_like_meaning(rest):
                    if title:
                        start_card(title, rest)
            elif section == "解説" and rest:
                if current:
                    current.meaning_zh = (current.meaning_zh + " " + rest).strip() if current.meaning_zh else rest
                elif title:
                    start_card(title, rest)
            elif section == "方法":
                if rest and current:
                    current.connection_rule = (current.connection_rule + " " + rest).strip()
            elif section == "例句":
                pass
            continue

        if section == "例句" or line.startswith("【例句】"):
            section = "例句"
            if "【例句】" in line:
                continue

        jp = _extract_jp_example(line)
        if jp:
            if current:
                current.examples_jp.append(jp)
                zh = _extract_zh_from_parens(line)
                if zh:
                    current.examples_zh.append(zh)
            elif pending_point:
                start_card(pending_point)
                current.examples_jp.append(jp)
            continue

        if _looks_like_grammar_point(line):
            if current and not current.meaning_zh and pending_point:
                start_card(pending_point)
            elif current and current.meaning_zh and current.examples_jp:
                finalized = _finalize_card(current)
                if finalized:
                    cards.append(finalized)
                current = None
            pending_point = line
            continue

        if pending_point and _looks_like_meaning(line):
            start_card(pending_point, line)
            continue

        if not current:
            if _looks_like_meaning(line) and title:
                start_card(title, line)
            continue

        if _looks_like_meaning(line):
            if not current.meaning_zh:
                current.meaning_zh = line
            else:
                current.usage_notes = (current.usage_notes + " " + line).strip()
        elif "用法" in line or "結構" in line or "變化" in line or "接續" in line:
            current.connection_rule = (current.connection_rule + " " + line).strip()
        elif section == "方法" or "→" in line or "＋" in line or " +" in line:
            current.connection_rule = (current.connection_rule + " " + line).strip()
        elif _HAS_ZH.search(line) and len(line) < 100:
            current.usage_notes = (current.usage_notes + " " + line).strip()
        elif _HAS_JP.search(line) and len(line) < 60:
            current.connection_rule = (current.connection_rule + " " + line).strip()

    if pending_point and not current:
        start_card(pending_point)
    elif pending_point and current and pending_point != current.grammar_point:
        start_card(pending_point)

    finalized = _finalize_card(current)
    if finalized:
        cards.append(finalized)
    return cards


def _parse_topic_page(lines: list[str], page_num: int, title: str) -> list[GrammarCard]:
    """Long-form explanatory pages (e.g. 場合は, V1てV2) — one card from title + body."""
    body_zh: list[str] = []
    body_rule: list[str] = []
    examples_jp: list[str] = []
    examples_zh: list[str] = []

    for raw in lines:
        line = _clean(raw)
        if not line or _is_footer(line) or line == title:
            continue
        if _SECTION.match(line):
            continue
        jp = _extract_jp_example(line)
        if jp:
            examples_jp.append(jp)
            zh = _extract_zh_from_parens(line)
            if zh:
                examples_zh.append(zh)
            continue
        if _HAS_ZH.search(line):
            if len(line) > 30:
                body_zh.append(line)
            else:
                body_rule.append(line)

    if not body_zh and not examples_jp:
        return []

    meaning = body_zh[0][:200] if body_zh else ""
    return [
        GrammarCard(
            grammar_point=title,
            meaning_zh=meaning,
            connection_rule=" ".join(body_rule[:3])[:300],
            usage_notes=" ".join(body_zh[1:3])[:400],
            examples_jp=examples_jp[:5],
            examples_zh=examples_zh[:5],
            source_page=page_num,
            parse_status="complete" if meaning and examples_jp else "partial",
            raw_block=title,
        )
    ]


def _parse_page(text: str, page_num: int) -> list[GrammarCard]:
    text = unicodedata.normalize("NFKC", text)
    lines = [_clean(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    if not lines or all(_is_footer(line) for line in lines):
        return []

    if _is_index_page(lines):
        return _parse_index_page(lines, page_num)

    title = ""
    for line in lines:
        if _is_footer(line):
            continue
        if line.startswith("【"):
            break
        if _HAS_JP.search(line) or line.startswith("〜") or line.startswith("~"):
            if len(line) <= 50 and line not in _JUNK_POINTS:
                title = line
                break

    if any(marker in text for marker in ("【文法】", "【解法】", "【方法】", "【解説】", "【例句】")):
        return _parse_grammar_block(lines, page_num, title=title)

    if title and len(text) > 400 and "例：" in text:
        return _parse_topic_page(lines, page_num, title)

    if title:
        return _parse_grammar_block(lines, page_num, title=title)

    return []


def _parse_early_numbered_section(text: str) -> list[GrammarCard]:
    """Pages 1-4: numbered 【のは】 style with rich bullets."""
    cards: list[GrammarCard] = []
    current: GrammarCard | None = None

    for raw in text.splitlines():
        line = _clean(raw)
        if not line or _is_footer(line):
            continue

        bracket = _NUMBERED_BRACKET.match(line)
        if bracket:
            if current:
                cards.append(current)
            point, rule = bracket.groups()
            current = GrammarCard(
                grammar_point=point.strip(),
                meaning_zh=rule.strip(),
                connection_rule=rule.strip(),
                parse_status="complete",
                source_page=1,
            )
            continue

        if not current:
            continue

        jp = _extract_jp_example(line)
        if jp:
            current.examples_jp.append(jp)
            zh = _extract_zh_from_parens(line)
            if zh:
                current.examples_zh.append(zh)
        elif line.startswith("•") or line.startswith("◦"):
            body = line.lstrip("•◦ ").strip()
            if "結構" in body or "用法" in body:
                current.connection_rule = (current.connection_rule + " " + body).strip()
            elif _HAS_ZH.search(body):
                current.usage_notes = (current.usage_notes + " " + body).strip()

    if current:
        cards.append(current)
    return cards


def _card_richness(card: GrammarCard) -> int:
    score = 0
    if card.meaning_zh and card.meaning_zh != card.grammar_point:
        score += 3
    if card.connection_rule and card.connection_rule != card.grammar_point:
        score += 2
    if card.examples_jp:
        score += 5 + len(card.examples_jp)
    if card.usage_notes:
        score += 1
    if card.parse_status == "complete":
        score += 2
    elif card.parse_status == "partial":
        score += 1
    return score


def _dedupe_cards(cards: list[GrammarCard]) -> list[GrammarCard]:
    best: dict[str, GrammarCard] = {}
    for card in cards:
        if len(card.grammar_point.strip()) < 2 or card.grammar_point.strip() in {"~", "〜"}:
            continue
        key = re.sub(r"\s+", "", card.grammar_point.lower())
        key = key.replace("~", "〜")
        if key not in best or _card_richness(card) > _card_richness(best[key]):
            best[key] = card
    return list(best.values())


def extract_grammar_cards(pdf_bytes: bytes) -> list[GrammarCard]:
    reader = PdfReader(__import__("io").BytesIO(pdf_bytes))
    all_cards: list[GrammarCard] = []

    early_text = "\n".join(
        (reader.pages[i].extract_text() or "") for i in range(min(4, len(reader.pages)))
    )
    all_cards.extend(_parse_early_numbered_section(early_text))

    for page_num, page in enumerate(reader.pages, start=1):
        if page_num <= 4:
            continue
        text = page.extract_text() or ""
        all_cards.extend(_parse_page(text, page_num))

    return _dedupe_cards(all_cards)
