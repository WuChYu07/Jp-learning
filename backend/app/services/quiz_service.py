"""Quiz generation: 4-choice vocab questions + translation prompts + exam persist."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.db.supabase import get_supabase_client
from app.models.schemas.vocab import ExamAttemptCreate, ExamAttemptOut
from app.services.score_service import score_service


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

    def generate_4choice(
        self, count: int = 10, user_id: str | None = None
    ) -> QuizBatch:
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
        score_map = score_service.score_map_for_user(user_id) if user_id else {}
        selected_ids = score_service.weighted_sample_ids(
            [v["id"] for v in eligible],
            score_map,
            count=sample_size,
        )
        by_id = {v["id"]: v for v in eligible}
        selected = [by_id[vid] for vid in selected_ids if vid in by_id]

        questions: list[FourChoiceQuestion] = []
        for i, vocab in enumerate(selected):
            mode = "reading" if (i % 2 == 0 and vocab.get("reading")) else "meaning"
            if mode == "reading" and not vocab.get("reading"):
                mode = "meaning"

            q = self._build_question(vocab, mode, eligible, meaning_map)
            questions.append(q)

        return QuizBatch(questions=questions, total_available=len(eligible))

    def generate_grammar_4choice(
        self, count: int = 10, user_id: str | None = None
    ) -> QuizBatch:
        grammars = (
            self.db.table("grammars")
            .select("id, grammar_point, jlpt_level")
            .neq("sync_status", "archived")
            .execute()
        ).data or []
        if not grammars:
            return QuizBatch(questions=[], total_available=0)

        usage_rows = (
            self.db.table("grammar_usages")
            .select("grammar_id, semantic_concept, meaning_zh, sort_order")
            .order("sort_order")
            .execute()
        ).data or []
        meaning_map: dict[str, str] = {}
        for u in usage_rows:
            gid = u["grammar_id"]
            if gid in meaning_map:
                continue
            meaning = (u.get("meaning_zh") or "").strip() or (
                u.get("semantic_concept") or ""
            ).strip()
            if meaning:
                meaning_map[gid] = meaning

        eligible = [g for g in grammars if meaning_map.get(g["id"])]
        if len(eligible) < 2:
            return QuizBatch(questions=[], total_available=len(eligible))

        sample_size = min(count, len(eligible))
        score_map = (
            score_service.grammar_score_map_for_user(user_id) if user_id else {}
        )
        selected_ids = score_service.weighted_sample_ids(
            [g["id"] for g in eligible],
            score_map,
            count=sample_size,
        )
        by_id = {g["id"]: g for g in eligible}
        selected = [by_id[gid] for gid in selected_ids if gid in by_id]

        questions: list[FourChoiceQuestion] = []
        for i, grammar in enumerate(selected):
            mode = "meaning" if i % 2 == 0 else "point"
            q = self._build_grammar_question(grammar, mode, eligible, meaning_map)
            questions.append(q)

        return QuizBatch(questions=questions, total_available=len(eligible))

    def _build_grammar_question(
        self,
        grammar: dict,
        mode: str,
        pool: list[dict],
        meaning_map: dict[str, str],
    ) -> FourChoiceQuestion:
        gid = grammar["id"]
        if mode == "point":
            # Show meaning, pick grammar_point
            prompt = "選出正確的文法"
            correct_text = grammar["grammar_point"]
            stem = meaning_map.get(gid, "")
            distractors_pool = [
                g["grammar_point"]
                for g in pool
                if g["id"] != gid and g.get("grammar_point") != correct_text
            ]
            display_word = stem
            display_reading = grammar.get("jlpt_level")
        else:
            prompt = "選出正確的意思"
            correct_text = meaning_map.get(gid, "")
            stem = grammar["grammar_point"]
            distractors_pool = [
                meaning_map[g["id"]]
                for g in pool
                if g["id"] != gid
                and meaning_map.get(g["id"])
                and meaning_map[g["id"]] != correct_text
            ]
            display_word = stem
            display_reading = grammar.get("jlpt_level")

        unique_distractors = list(set(distractors_pool))
        num_distractors = min(3, len(unique_distractors))
        chosen_distractors = random.sample(unique_distractors, num_distractors)
        options: list[ChoiceOption] = [ChoiceOption(id="correct", text=correct_text)]
        for j, d in enumerate(chosen_distractors):
            options.append(ChoiceOption(id=f"d{j}", text=d))
        while len(options) < 4:
            options.append(ChoiceOption(id=f"pad{len(options)}", text="—"))
        random.shuffle(options)
        correct_id = next(o.id for o in options if o.text == correct_text)
        return FourChoiceQuestion(
            question_id=gid,
            word=display_word,
            reading=display_reading,
            prompt=prompt,
            mode=mode,
            options=options,
            correct_option_id=correct_id,
        )

    def generate_translation_prompts(
        self, count: int = 5, user_id: str | None = None
    ) -> TranslationBatch:
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

        # Prefer low-score vocabularies, then pick one prompt per vocab
        unique_vids = list({c["vocabulary_id"] for c in candidates})
        score_map = score_service.score_map_for_user(user_id) if user_id else {}
        sample_size = min(count, len(unique_vids))
        picked_vids = score_service.weighted_sample_ids(
            unique_vids, score_map, count=sample_size
        )
        by_vid: dict[str, list[dict]] = {}
        for c in candidates:
            by_vid.setdefault(c["vocabulary_id"], []).append(c)

        selected: list[dict] = []
        for vid in picked_vids:
            opts = by_vid.get(vid) or []
            if opts:
                selected.append(random.choice(opts))

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

    def save_exam_attempt(
        self, user_id: str | None, payload: ExamAttemptCreate
    ) -> ExamAttemptOut:
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User required to save exam results",
            )
        from app.services.owner_service import ensure_owner_user

        ensure_owner_user(self.db)
        total = max(payload.total_count, 0)
        correct = max(0, min(payload.correct_count, total))
        percent = round((correct / total) * 100, 2) if total else 0.0
        row = {
            "user_id": user_id,
            "subject": payload.subject,
            "mode": payload.mode,
            "correct_count": correct,
            "total_count": total,
            "score_percent": percent,
            "detail": payload.detail or {},
        }
        result = self.db.table("exam_attempts").insert(row).execute()
        data = (result.data or [None])[0]
        if not data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save exam attempt",
            )
        return ExamAttemptOut(
            id=UUID(data["id"]),
            subject=data["subject"],
            mode=data["mode"],
            correct_count=data["correct_count"],
            total_count=data["total_count"],
            score_percent=float(data["score_percent"]),
            completed_at=str(data.get("completed_at") or ""),
        )

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
