"""Quiz generation: 4-choice vocab questions + translation prompts."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from uuid import UUID

from supabase import Client

from app.db.supabase import get_supabase_client


@dataclass
class ChoiceOption:
    id: str
    text: str
    sub_text: str | None = None


@dataclass
class FourChoiceQuestion:
    question_id: str
    word: str
    reading: str | None
    prompt: str  # e.g. "選出正確的讀音" / "選出正確的意思"
    mode: str  # "reading" | "meaning"
    options: list[ChoiceOption] = field(default_factory=list)
    correct_option_id: str = ""


@dataclass
class TranslationPrompt:
    question_id: str
    source_zh: str
    source_en: str | None
    hint_word: str
    hint_reading: str | None


@dataclass
class QuizBatch:
    questions: list[FourChoiceQuestion]
    total_available: int


@dataclass
class TranslationBatch:
    prompts: list[TranslationPrompt]
    total_available: int


class QuizService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def generate_4choice(self, count: int = 10) -> QuizBatch:
        all_vocab = (
            self.db.table("vocabularies")
            .select("id, word, reading")
            .execute()
        ).data or []

        all_defs = (
            self.db.table("vocabulary_definitions")
            .select("vocabulary_id, meaning_zh")
            .order("sort_order")
            .execute()
        ).data or []

        meaning_map: dict[str, str] = {}
        for d in all_defs:
            if d["vocabulary_id"] not in meaning_map:
                meaning_map[d["vocabulary_id"]] = d["meaning_zh"]

        eligible = [v for v in all_vocab if meaning_map.get(v["id"])]
        if len(eligible) < 2:
            return QuizBatch(questions=[], total_available=len(eligible))

        sample_size = min(count, len(eligible))
        selected = random.sample(eligible, sample_size)

        questions: list[FourChoiceQuestion] = []
        for i, vocab in enumerate(selected):
            mode = "reading" if (i % 2 == 0 and vocab.get("reading")) else "meaning"
            if mode == "reading" and not vocab.get("reading"):
                mode = "meaning"

            q = self._build_question(vocab, mode, eligible, meaning_map)
            questions.append(q)

        return QuizBatch(questions=questions, total_available=len(eligible))

    def generate_translation_prompts(self, count: int = 5) -> TranslationBatch:
        all_defs = (
            self.db.table("vocabulary_definitions")
            .select("vocabulary_id, meaning_zh, meaning_en, example_sentences")
            .order("sort_order")
            .execute()
        ).data or []

        candidates: list[dict] = []
        for d in all_defs:
            sentences = d.get("example_sentences") or []
            for s in sentences:
                if isinstance(s, dict) and s.get("chinese") and s.get("japanese"):
                    candidates.append({
                        "vocabulary_id": d["vocabulary_id"],
                        "chinese": s["chinese"],
                        "english": s.get("english"),
                        "meaning_zh": d["meaning_zh"],
                    })

        if not candidates:
            for d in all_defs:
                if d.get("meaning_zh"):
                    candidates.append({
                        "vocabulary_id": d["vocabulary_id"],
                        "chinese": d["meaning_zh"],
                        "english": d.get("meaning_en"),
                        "meaning_zh": d["meaning_zh"],
                    })

        vocab_map: dict[str, dict] = {}
        if candidates:
            vocab_rows = (
                self.db.table("vocabularies")
                .select("id, word, reading")
                .execute()
            ).data or []
            vocab_map = {v["id"]: v for v in vocab_rows}

        sample_size = min(count, len(candidates))
        selected = random.sample(candidates, sample_size) if candidates else []

        prompts: list[TranslationPrompt] = []
        for c in selected:
            vocab = vocab_map.get(c["vocabulary_id"], {})
            prompts.append(TranslationPrompt(
                question_id=c["vocabulary_id"],
                source_zh=c["chinese"],
                source_en=c.get("english"),
                hint_word=vocab.get("word", ""),
                hint_reading=vocab.get("reading"),
            ))

        return TranslationBatch(prompts=prompts, total_available=len(candidates))

    def _build_question(
        self,
        vocab: dict,
        mode: str,
        pool: list[dict],
        meaning_map: dict[str, str],
    ) -> FourChoiceQuestion:
        vid = vocab["id"]

        if mode == "reading":
            correct_text = vocab["reading"] or ""
            prompt = "選出正確的讀音"
            distractors_pool = [
                v["reading"]
                for v in pool
                if v["id"] != vid and v.get("reading") and v["reading"] != correct_text
            ]
        else:
            correct_text = meaning_map.get(vid, "")
            prompt = "選出正確的意思"
            distractors_pool = [
                meaning_map[v["id"]]
                for v in pool
                if v["id"] != vid and meaning_map.get(v["id"]) and meaning_map[v["id"]] != correct_text
            ]

        unique_distractors = list(set(distractors_pool))
        num_distractors = min(3, len(unique_distractors))
        chosen_distractors = random.sample(unique_distractors, num_distractors)

        options: list[ChoiceOption] = [
            ChoiceOption(id="correct", text=correct_text)
        ]
        for j, d in enumerate(chosen_distractors):
            options.append(ChoiceOption(id=f"d{j}", text=d))

        while len(options) < 4:
            options.append(ChoiceOption(id=f"pad{len(options)}", text="—"))

        random.shuffle(options)

        correct_id = next(o.id for o in options if o.text == correct_text)

        return FourChoiceQuestion(
            question_id=vid,
            word=vocab["word"],
            reading=vocab.get("reading"),
            prompt=prompt,
            mode=mode,
            options=options,
            correct_option_id=correct_id,
        )


quiz_service = QuizService()
