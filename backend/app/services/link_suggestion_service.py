"""Gemini-powered link suggestions between grammar points."""

from __future__ import annotations

import json
import re
from uuid import UUID

from fastapi import HTTPException, status
from google.genai import types

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.models.schemas.links import (
    LinkEntityType,
    LinkRelationType,
    SuggestedLink,
    SuggestLinksResponse,
)
from app.services.gemini_client import is_quota_error, run_with_key_failover
from app.services.link_service import link_service

_SUGGEST_PROMPT = """你是日文文法老師。根據「中心文法」與「候選文法列表」，建議語意關聯。

只回傳 JSON：
{
  "suggestions": [
    {
      "target_grammar_point": "候選列表中的原文法標題（必須完全一致）",
      "relation_type": "same_meaning|contrast|confusable|prerequisite|derived",
      "label_zh": "邊上短標籤（4字以內，如「更口語」「傳聞」）",
      "note_zh": "一句繁體中文說明差異或關聯原因",
      "confidence": 0.0到1.0
    }
  ]
}

規則：
- 最多回傳 6 筆；沒有合理關聯就回傳空陣列。
- target_grammar_point 必須出自候選列表，不可捏造。
- same_meaning：近義/同義群；contrast：用法差異對比；confusable：易混淆；
  prerequisite：應先學會的基礎；derived：由此延伸的句型。
- 全部使用繁體中文。不要 markdown 圍欄。
"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class LinkSuggestionService:
    def suggest_for_grammar(self, grammar_id: UUID) -> SuggestLinksResponse:
        db = get_supabase_client()
        center = (
            db.table("grammars")
            .select("id, grammar_point, jlpt_level")
            .eq("id", str(grammar_id))
            .neq("sync_status", "archived")
            .maybe_single()
            .execute()
        )
        if center is None or not center.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found"
            )

        center_row = center.data
        # Prefer same JLPT band, then fill with others
        jlpt = (center_row.get("jlpt_level") or "").split("/")[0].strip() or None
        candidates_q = (
            db.table("grammars")
            .select("id, grammar_point, jlpt_level")
            .neq("sync_status", "archived")
            .neq("id", str(grammar_id))
            .order("grammar_point")
            .limit(80)
        )
        if jlpt and jlpt != "unknown":
            same = (
                db.table("grammars")
                .select("id, grammar_point, jlpt_level")
                .neq("sync_status", "archived")
                .neq("id", str(grammar_id))
                .ilike("jlpt_level", f"%{jlpt}%")
                .order("grammar_point")
                .limit(40)
                .execute()
            )
            others = candidates_q.execute().data or []
            seen = {r["id"] for r in (same.data or [])}
            candidates = list(same.data or [])
            for row in others:
                if row["id"] not in seen:
                    candidates.append(row)
                if len(candidates) >= 60:
                    break
        else:
            candidates = candidates_q.execute().data or []

        if not candidates:
            return SuggestLinksResponse(
                suggestions=[],
                center_id=grammar_id,
                center_label=center_row["grammar_point"],
            )

        # Exclude already-linked targets
        existing = link_service.get_neighborhood(
            LinkEntityType.GRAMMAR, grammar_id, depth=1
        )
        linked_labels = {
            n.label for n in existing.nodes if n.type == LinkEntityType.GRAMMAR
        }
        candidates = [
            c for c in candidates if c["grammar_point"] not in linked_labels
        ][:50]

        label_to_id = {c["grammar_point"]: c["id"] for c in candidates}
        candidate_list = "\n".join(f"- {c['grammar_point']}" for c in candidates)

        usages = (
            db.table("grammar_usages")
            .select("semantic_concept, meaning_zh, connection_rule")
            .eq("grammar_id", str(grammar_id))
            .order("sort_order")
            .limit(5)
            .execute()
        )
        usage_summary = "\n".join(
            f"- {(u.get('semantic_concept') or '')}: {(u.get('meaning_zh') or '')[:80]}"
            for u in (usages.data or [])
        )

        prompt = (
            f"{_SUGGEST_PROMPT}\n\n"
            f"## 中心文法\n"
            f"標題：{center_row['grammar_point']}\n"
            f"JLPT：{center_row.get('jlpt_level')}\n"
            f"用法摘要：\n{usage_summary or '（無）'}\n\n"
            f"## 候選文法\n{candidate_list}\n"
        )

        try:
            response = run_with_key_failover(
                lambda client: client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
            )
            raw = response.text or "{}"
            data = _parse_json(raw)
        except Exception as exc:
            if is_quota_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Gemini API 額度已用完（所有 key 皆無法使用）。"
                        "請設定 GEMINI_API_KEYS 備援 key 後再試。"
                    ),
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI suggestion failed: {exc}",
            ) from exc

        suggestions: list[SuggestedLink] = []
        for item in data.get("suggestions") or []:
            target_label = (item.get("target_grammar_point") or "").strip()
            if not target_label or target_label not in label_to_id:
                continue
            rel_raw = (item.get("relation_type") or "contrast").strip()
            try:
                relation = LinkRelationType(rel_raw)
            except ValueError:
                relation = LinkRelationType.CONTRAST
            confidence = float(item.get("confidence") or 0.7)
            confidence = max(0.0, min(1.0, confidence))
            suggestions.append(
                SuggestedLink(
                    target_type=LinkEntityType.GRAMMAR,
                    target_id=UUID(label_to_id[target_label]),
                    target_label=target_label,
                    relation_type=relation,
                    label_zh=item.get("label_zh"),
                    note_zh=item.get("note_zh"),
                    confidence=confidence,
                )
            )

        return SuggestLinksResponse(
            suggestions=suggestions,
            center_id=grammar_id,
            center_label=center_row["grammar_point"],
        )


link_suggestion_service = LinkSuggestionService()
