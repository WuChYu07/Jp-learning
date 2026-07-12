"""Extract OK/NG usage hints (✅❌🚨) from grammar PDF text layers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pypdf import PdfReader

_OK_MARKERS = re.compile(r"✅|⭕|\(〇\)|\(○\)|OK\s*[?？]?|可以|適用")
_NG_MARKERS = re.compile(r"❌|🔴|\(X\)|\(×\)|不自然|不能用|錯誤|不要|禁止|不可")
_TIP_MARKERS = re.compile(r"🚨|⚠|👉|💡|重點|限制|注意")
_HAS_JP = re.compile(r"[ぁ-んァ-ヶ一-龯]")
_HAS_ZH = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class PageUsageNotes:
    page: int
    usage_ok: list[str] = field(default_factory=list)
    usage_ng: list[str] = field(default_factory=list)
    usage_tips: list[str] = field(default_factory=list)
    grammar_hints: list[str] = field(default_factory=list)


def _clean_line(line: str) -> str:
    line = unicodedata.normalize("NFKC", line).strip()
    line = re.sub(r"^[✅❌⭕🔴🚨⚠👉💡🔹\s]+", "", line)
    return line.strip()


def _grammar_hints_from_text(text: str) -> list[str]:
    hints: list[str] = []
    for line in text.splitlines():
        line = _clean_line(line)
        if not line or len(line) > 60:
            continue
        if line.startswith("〜") or line.startswith("~") or "【" in line:
            hints.append(line.split("【")[0].strip()[:40])
        elif _HAS_JP.search(line) and any(
            x in line for x in ("ます", "ない", "ください", "ている", "たい", "てお", "てあ")
        ):
            if len(line) <= 35:
                hints.append(line)
    return hints


def parse_page_usage(text: str, page_num: int) -> PageUsageNotes:
    notes = PageUsageNotes(page=page_num, grammar_hints=_grammar_hints_from_text(text))
    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line or len(line) < 3:
            continue
        if _OK_MARKERS.search(raw):
            notes.usage_ok.append(line)
        elif _NG_MARKERS.search(raw):
            notes.usage_ng.append(line)
        elif _TIP_MARKERS.search(raw):
            notes.usage_tips.append(line)
        elif "ONLY" in line.upper() or "只能" in line:
            notes.usage_ng.append(line)
    return notes


def build_pdf_usage_index(pdf_bytes: bytes) -> dict[int, PageUsageNotes]:
    reader = PdfReader(__import__("io").BytesIO(pdf_bytes))
    index: dict[int, PageUsageNotes] = {}
    for page_num, page in enumerate(reader.pages, start=1):
        text = unicodedata.normalize("NFKC", page.extract_text() or "")
        parsed = parse_page_usage(text, page_num)
        if parsed.usage_ok or parsed.usage_ng or parsed.usage_tips:
            index[page_num] = parsed
    return index


def usage_for_page(index: dict[int, PageUsageNotes], page: int, radius: int = 1) -> PageUsageNotes:
    merged = PageUsageNotes(page=page)
    for p in range(max(1, page - radius), page + radius + 1):
        if p not in index:
            continue
        src = index[p]
        merged.usage_ok.extend(src.usage_ok)
        merged.usage_ng.extend(src.usage_ng)
        merged.usage_tips.extend(src.usage_tips)
        merged.grammar_hints.extend(src.grammar_hints)
    return merged


def format_usage_sections(notes: PageUsageNotes, max_items: int = 5) -> tuple[str, str, str]:
    ok = " | ".join(notes.usage_ok[:max_items])
    ng = " | ".join(notes.usage_ng[:max_items])
    tips = " | ".join(notes.usage_tips[:max_items])
    return ok, ng, tips
