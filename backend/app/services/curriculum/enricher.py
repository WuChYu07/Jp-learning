"""Japanese teacher agent — enrich curriculum rows without external AI APIs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.curriculum.extractors import GrammarRawRow, VocabRawRow
from app.services.curriculum.grammar_kb import lookup_grammar

# Common N5 surface forms seen in beginner materials
_N5_HINTS = {
    "つまらない", "せなか", "なみだ", "えがお", "やちん", "のんびり",
    "たべる", "のむ", "いく", "くる", "みる", "きく", "はなす",
}
_N4_HINTS = {
    "にぎやか", "素敵", "ステキ", "納得", "友情", "仲間", "知り合い",
    "患者", "救急", "商品", "製品", "用心",
}
_N3_HINTS = {
    "汚れ", "書類", "包帯", "覆蓋物", "非常に", "必ずしも",
}
_N2_HINTS = {
    "迷惑", "行為", "優秀", "被害", "役割",
}

_PARTICLE_GRAMMAR = {"は", "が", "を", "に", "で", "の", "と", "へ", "も"}


@dataclass
class VocabCuratedRow:
    entry_id: str
    kanji: str
    kana: str
    meaning: str
    part_of_speech: str
    jlpt_level: str
    example_sentence: str
    example_reading: str
    example_chinese: str
    tags: str
    notes: str
    enriched_by: str
    confidence: float


@dataclass
class GrammarCuratedRow:
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
    enriched_by: str
    confidence: float


def _surface(kanji: str, kana: str) -> str:
    return kanji or kana


def _estimate_jlpt(kanji: str, kana: str, pos: str) -> tuple[str, float]:
    surface = _surface(kanji, kana)
    compact = surface.replace("（な）", "")

    if compact in _N5_HINTS or (len(compact) <= 3 and not kanji):
        return "N5", 0.75
    if compact in _N4_HINTS or "（な）" in kana:
        return "N4", 0.7
    if compact in _N3_HINTS:
        return "N3", 0.65
    if compact in _N2_HINTS:
        return "N2", 0.6
    if kanji and len(kanji) >= 4:
        return "N2", 0.5
    if _surface("", kana) and re.match(r"^[\u30a0-\u30ffー]+$", kana):
        return "N3", 0.55
    return "N4", 0.45


def _refine_pos(guess: str, kanji: str, kana: str) -> str:
    surface = _surface(kanji, kana)
    if guess != "other":
        return guess
    if surface.endswith("する"):
        return "verb"
    if re.search(r"[ぁ-ん]る$", kana):
        return "verb"
    if re.search(r"[\u4e00-\u9fff]", surface):
        return "noun"
    return guess


def _build_vocab_example(
    kanji: str, kana: str, meaning: str, pos: str
) -> tuple[str, str, str]:
    surface = kanji or kana
    reading_surface = kana or kanji

    if pos == "na_adjective":
        jp = f"この辺りは{surface}です。"
        rd = f"このへんりは{reading_surface}です。"
        zh = f"這一帶很{meaning.split('、')[0].split('，')[0]}。"
    elif pos == "i_adjective":
        jp = f"今日は{surface}。"
        rd = f"きょうは{reading_surface}。"
        zh = f"今天很{meaning.split('、')[0]}。"
    elif pos == "verb":
        jp = f"私は毎日{surface}。"
        rd = f"わたしはまいにち{reading_surface}。"
        zh = f"我每天{meaning.split('、')[0]}。"
    elif pos == "adverb":
        jp = f"{surface}勉強します。"
        rd = f"{reading_surface}べんきょうします。"
        zh = f"{meaning.split('、')[0]}學習。"
    else:
        jp = f"{surface}について勉強しています。"
        rd = f"{reading_surface}についてべんきょうしています。"
        zh = f"我正在學習關於{meaning.split('、')[0]}的內容。"

    return jp, rd, zh


def _build_tags(kanji: str, kana: str, pos: str, jlpt: str) -> str:
    tags = [jlpt, pos]
    if kana and re.match(r"^[\u30a0-\u30ffー]+$", kana) and not kanji:
        tags.append("外来語")
    if "（な）" in kana or "(な)" in kana:
        tags.append("な形容詞")
    return "|".join(tags)


def enrich_vocabulary_row(raw: VocabRawRow) -> VocabCuratedRow:
    pos = _refine_pos(raw.part_of_speech_guess, raw.kanji, raw.kana)
    jlpt, jlpt_conf = _estimate_jlpt(raw.kanji, raw.kana, pos)
    jp, rd, zh = _build_vocab_example(raw.kanji, raw.kana, raw.meaning_zh, pos)

    # Use example from notes if PDF already contains one (→ line)
    notes = raw.raw_notes
    if "→" in notes or "。" in notes:
        for fragment in re.split(r"[→◦•]", notes):
            fragment = fragment.strip()
            if re.search(r"[ぁ-んァ-ヶ]", fragment) and "。" in fragment:
                jp = fragment.split("。")[0] + "。"
                rd = jp  # keep as-is when reading unknown
                zh = raw.meaning_zh
                jlpt_conf = min(1.0, jlpt_conf + 0.15)
                break

    confidence = round(min(0.95, 0.55 + jlpt_conf * 0.3 + (0.1 if raw.parse_status == "complete" else 0)), 2)

    return VocabCuratedRow(
        entry_id=raw.entry_id,
        kanji=raw.kanji,
        kana=raw.kana,
        meaning=raw.meaning_zh,
        part_of_speech=pos,
        jlpt_level=jlpt,
        example_sentence=jp,
        example_reading=rd,
        example_chinese=zh,
        tags=_build_tags(raw.kanji, raw.kana, pos, jlpt),
        notes=notes,
        enriched_by="teacher_agent",
        confidence=confidence,
    )


def _estimate_grammar_jlpt(point: str) -> tuple[str, float]:
    if point in {"は", "が", "を", "です", "ます"} or "があります" in point:
        return "N5", 0.8
    if point in {"のは", "のが", "のを"} or point.startswith("〜"):
        return "N4", 0.75
    if "たい" in point or "ている" in point:
        return "N4", 0.7
    if len(point) > 20:
        return "N3", 0.55
    return "N3", 0.5


def _grammar_example(point: str, concept: str) -> tuple[str, str, str]:
    if point == "のは":
        jp = "早起きするのは、健康にいいです。"
        rd = "はやおきするのは、けんこうにいいです。"
        zh = "早起這件事對健康很好。"
    elif point == "のが":
        jp = "私は音楽を聴くのが好きです。"
        rd = "わたしはおんがくをきくのがすきです。"
        zh = "我喜歡聽音樂這件事。"
    elif point == "のを":
        jp = "鍵を閉めるのを忘れました。"
        rd = "かぎをしめるのをわすれました。"
        zh = "我忘記鎖門這件事了。"
    elif "があります" in point:
        jp = "私は車があります。"
        rd = "わたしはくるまがあります。"
        zh = "我有車。"
    elif "が好き" in point:
        jp = "私は野菜が好きです。"
        rd = "わたしはやさいがすきです。"
        zh = "我喜歡蔬菜。"
    elif point.startswith("〜") or "N" in point[:2]:
        jp = f"{point} の例文です。"
        rd = jp
        zh = concept or "文法例句。"
    else:
        jp = f"{point}を使います。"
        rd = jp
        zh = concept or "使用此句型。"

    return jp, rd, zh


def enrich_grammar_row(raw: GrammarRawRow) -> GrammarCuratedRow:
    meaning = raw.meaning_zh or raw.semantic_concept or ""
    rule = raw.connection_rule or ""
    notes = raw.raw_notes or ""

    if raw.example_japanese:
        jp = raw.example_japanese.split(" | ")[0]
        zh = (raw.example_chinese.split(" | ")[0] if raw.example_chinese else meaning)
        rd = jp
        enriched_by = "pdf_extract"
        jlpt, jlpt_conf = _estimate_grammar_jlpt(raw.grammar_point)
        confidence = 0.88 if raw.parse_status == "complete" else 0.75
    else:
        jp, rd, zh = "", "", ""
        enriched_by = "teacher_agent"
        jlpt, jlpt_conf = _estimate_grammar_jlpt(raw.grammar_point)
        confidence = 0.5

    if raw.parse_status == "index_only" or not meaning or not jp:
        kb = lookup_grammar(raw.grammar_point)
        if kb:
            kb_meaning, kb_rule, kb_jp, kb_zh, kb_jlpt = kb
            meaning = meaning or kb_meaning
            rule = rule or kb_rule
            if not jp:
                jp, rd, zh = kb_jp, kb_jp, kb_zh
            jlpt = kb_jlpt
            jlpt_conf = 0.75
            enriched_by = "teacher_agent_kb"
            confidence = max(confidence, 0.72)
        elif not jp:
            jp, rd, zh = _grammar_example(raw.grammar_point, meaning or raw.grammar_point)
            enriched_by = "teacher_agent"
            confidence = 0.58 if raw.parse_status == "index_only" else confidence

    if not meaning:
        meaning = raw.grammar_point

    tags = [jlpt, "文法"]
    if raw.grammar_point.startswith("〜") or raw.grammar_point.startswith("~"):
        tags.append("句型")
    if any(p in raw.grammar_point for p in _PARTICLE_GRAMMAR):
        tags.append("助詞")
    if raw.parse_status == "index_only":
        tags.append("索引補齊")

    confidence = round(
        min(0.95, confidence + (0.1 if rule else 0) + (0.05 if len(raw.example_japanese.split(" | ")) > 1 else 0)),
        2,
    )

    return GrammarCuratedRow(
        entry_id=raw.entry_id,
        grammar_point=raw.grammar_point,
        semantic_concept=meaning,
        connection_rule=rule or meaning,
        meaning_zh=meaning,
        example_japanese=jp,
        example_reading=rd,
        example_chinese=zh,
        jlpt_level=jlpt,
        tags="|".join(tags),
        notes=notes,
        enriched_by=enriched_by,
        confidence=confidence,
    )
