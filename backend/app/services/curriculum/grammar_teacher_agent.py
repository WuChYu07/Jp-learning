"""Professional Japanese teacher agent — review, correct, and enrich grammar CSV."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.services.curriculum.enricher import GrammarCuratedRow
from app.services.curriculum.extractors import GrammarRawRow
from app.services.curriculum.grammar_kb import lookup_grammar
from app.services.curriculum.grammar_teacher_kb import TeacherGrammarEntry, lookup_teacher
from app.services.curriculum.pdf_usage_extractor import PageUsageNotes, format_usage_sections

_TEMPLATE_EXAMPLE = re.compile(r"(の例文です|を使います)。?$")
_HAS_JP = re.compile(r"[ぁ-んァ-ヶ一-龯]")
_SENTENCE_LIKE = re.compile(r"[。！？]$|ます$|です$|だ$|ない$")
_JUNK_POINT = re.compile(
    r"^(日\s*文\s*筆\s*記|例:|例：|否定\s|肯定\s|過去\s|未來|變化方式|口語|普通形|伴隨|二、|三、|四、|五、|①|②|③)"
)
_FOOTER = re.compile(r"日\s*文\s*筆\s*記")


@dataclass
class GrammarReviewedRow:
    entry_id: str
    grammar_point: str
    semantic_concept: str
    connection_rule: str
    meaning_zh: str
    example_japanese: str
    example_reading: str
    example_chinese: str
    jlpt_level: str
    tags: str
    notes: str
    usage_when: str
    usage_avoid: str
    common_mistakes: str
    review_issues: str
    review_status: str  # passed | corrected | flagged | excluded
    enriched_by: str
    confidence: float


@dataclass
class ReviewStats:
    total: int = 0
    passed: int = 0
    corrected: int = 0
    flagged: int = 0
    excluded: int = 0


def _is_template_example(example: str) -> bool:
    return bool(_TEMPLATE_EXAMPLE.search(example.strip()))


def _extract_jp_from_notes(notes: str) -> tuple[str, str] | None:
    if not notes:
        return None
    for fragment in re.split(r"[|◦•\n]", notes):
        fragment = fragment.strip()
        if not _HAS_JP.search(fragment):
            continue
        if "。" in fragment:
            jp = fragment.split("。")[0].strip() + "。"
            if len(jp) >= 4 and not _FOOTER.search(jp):
                return jp, jp
        elif len(fragment) >= 6 and _SENTENCE_LIKE.search(fragment):
            if not _FOOTER.search(fragment):
                return fragment[:100], fragment[:100]
    return None


def _is_junk_grammar_point(point: str) -> bool:
    point = point.strip()
    if len(point) < 2 or _JUNK_POINT.search(point):
        return True
    if _FOOTER.search(point):
        return True
    if point.startswith(("(〇)", "(X)", "①", "②", "③", "📘", "💬")):
        return True
    # Full example sentence mis-parsed as grammar point
    if len(point) > 28 and _SENTENCE_LIKE.search(point) and not point.startswith("〜"):
        return True
    if "→" in point and "ます" in point and not point.startswith("〜"):
        return True
    return False


def _validate_row(curated: GrammarCuratedRow, raw: GrammarRawRow | None) -> list[str]:
    issues: list[str] = []
    point = curated.grammar_point.strip()

    if _is_junk_grammar_point(point):
        issues.append("grammar_point 疑似誤拆（例句/說明文字）")
    if _is_template_example(curated.example_japanese):
        issues.append("例句為模板佔位，非真實例句")
    if curated.meaning_zh.strip() == point:
        issues.append("意思與句型名稱相同，缺少釋義")
    if len(point) > 55 and not point.startswith("〜"):
        issues.append("句型名稱過長，可能混入了說明文字")
    if curated.confidence < 0.6:
        issues.append(f"信心分偏低 ({curated.confidence})")
    if raw and raw.parse_status == "index_only" and "索引補齊" not in curated.tags:
        issues.append("來自索引頁，內容可能不完整")
    if "として" in curated.connection_rule and "は別として" in point:
        issues.append("接續規則錯誤：は別として 被誤配為 として")
    return issues


def _apply_teacher_entry(
    curated: GrammarCuratedRow,
    teacher: TeacherGrammarEntry,
) -> GrammarCuratedRow:
    return GrammarCuratedRow(
        entry_id=curated.entry_id,
        grammar_point=curated.grammar_point,
        semantic_concept=teacher.meaning_zh,
        connection_rule=teacher.connection_rule,
        meaning_zh=teacher.meaning_zh,
        example_japanese=teacher.example_jp,
        example_reading=teacher.example_jp,
        example_chinese=teacher.example_zh,
        jlpt_level=teacher.jlpt,
        tags=curated.tags,
        notes=curated.notes,
        enriched_by="grammar_teacher_agent",
        confidence=max(curated.confidence, 0.85),
    )


def _apply_kb_fallback(curated: GrammarCuratedRow) -> GrammarCuratedRow:
    kb = lookup_grammar(curated.grammar_point)
    if not kb:
        return curated
    meaning, rule, jp, zh, jlpt = kb
    return GrammarCuratedRow(
        entry_id=curated.entry_id,
        grammar_point=curated.grammar_point,
        semantic_concept=meaning,
        connection_rule=rule,
        meaning_zh=meaning,
        example_japanese=jp,
        example_reading=jp,
        example_chinese=zh,
        jlpt_level=jlpt,
        tags=curated.tags,
        enriched_by="grammar_teacher_agent",
        confidence=max(curated.confidence, 0.78),
    )


def _merge_pdf_usage(
    usage_when: str,
    usage_avoid: str,
    tips: str,
    page_notes: PageUsageNotes | None,
) -> tuple[str, str, str]:
    if not page_notes:
        return usage_when, usage_avoid, tips
    ok, ng, page_tips = format_usage_sections(page_notes)
    when = " | ".join(filter(None, [usage_when, ok]))
    avoid = " | ".join(filter(None, [usage_avoid, ng]))
    merged_tips = " | ".join(filter(None, [tips, page_tips]))
    return when.strip(), avoid.strip(), merged_tips.strip()


def review_grammar_row(
    curated: GrammarCuratedRow,
    raw: GrammarRawRow | None = None,
    page_usage: PageUsageNotes | None = None,
) -> GrammarReviewedRow:
    working = curated
    issues = _validate_row(working, raw)
    corrected = False

    teacher = lookup_teacher(working.grammar_point)
    if teacher:
        working = _apply_teacher_entry(working, teacher)
        corrected = True
        issues = [i for i in issues if "模板" not in i and "接續規則錯誤" not in i]
    elif _is_template_example(working.example_japanese):
        from_notes = _extract_jp_from_notes(working.notes or (raw.raw_notes if raw else ""))
        if from_notes:
            jp, rd = from_notes
            working = replace(
                working,
                example_japanese=jp,
                example_reading=rd,
                example_chinese=working.meaning_zh,
                enriched_by="grammar_teacher_agent",
                confidence=min(0.82, working.confidence + 0.15),
            )
            corrected = True
            issues = [i for i in issues if "模板" not in i]
        else:
            working = _apply_kb_fallback(working)
            if working.enriched_by == "grammar_teacher_agent":
                corrected = True
                issues = [i for i in issues if "模板" not in i]

    usage_when = teacher.usage_when if teacher else ""
    usage_avoid = teacher.usage_avoid if teacher else ""
    common_mistakes = teacher.common_mistakes if teacher else ""
    usage_when, usage_avoid, tip_extra = _merge_pdf_usage(
        usage_when, usage_avoid, common_mistakes, page_usage
    )
    if tip_extra and not common_mistakes:
        common_mistakes = tip_extra
    elif tip_extra:
        common_mistakes = f"{common_mistakes} | {tip_extra}"

    if _is_junk_grammar_point(working.grammar_point):
        status = "excluded"
    elif issues and not corrected:
        status = "flagged"
    elif corrected:
        status = "corrected"
    else:
        status = "passed"

    return GrammarReviewedRow(
        entry_id=working.entry_id,
        grammar_point=working.grammar_point,
        semantic_concept=working.semantic_concept,
        connection_rule=working.connection_rule,
        meaning_zh=working.meaning_zh,
        example_japanese=working.example_japanese,
        example_reading=working.example_reading,
        example_chinese=working.example_chinese,
        jlpt_level=working.jlpt_level,
        tags=working.tags,
        notes=working.notes,
        usage_when=usage_when,
        usage_avoid=usage_avoid,
        common_mistakes=common_mistakes,
        review_issues="; ".join(issues),
        review_status=status,
        enriched_by=working.enriched_by,
        confidence=working.confidence,
    )


def review_all_rows(
    curated_rows: list[GrammarCuratedRow],
    raw_by_id: dict[str, GrammarRawRow],
    pdf_usage_index: dict[int, PageUsageNotes],
) -> tuple[list[GrammarReviewedRow], ReviewStats]:
    stats = ReviewStats()
    reviewed: list[GrammarReviewedRow] = []

    for curated in curated_rows:
        raw = raw_by_id.get(curated.entry_id)
        page_usage = None
        if raw and raw.source_page.isdigit():
            page = int(raw.source_page)
            from app.services.curriculum.pdf_usage_extractor import usage_for_page

            page_usage = usage_for_page(pdf_usage_index, page, radius=0)

        row = review_grammar_row(curated, raw, page_usage)
        reviewed.append(row)
        stats.total += 1
        if row.review_status == "passed":
            stats.passed += 1
        elif row.review_status == "corrected":
            stats.corrected += 1
        elif row.review_status == "excluded":
            stats.excluded += 1
        else:
            stats.flagged += 1

    return reviewed, stats
