"""Enrich grammar items from Notion images or AI teacher explanation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from google.genai import types

from app.core.config import settings
from app.core.http_client import create_sync_client
from app.db.supabase import get_supabase_client
from app.models.schemas.grammar import GrammarEnrichmentOutput, GrammarOut
from app.services.gemini_client import is_quota_error, run_with_key_failover
from app.services.grammar_service import grammar_service
from app.services.text_sanitize import clean_text

_IMAGE_PROMPT = """你是一位日文文法老師，擅長把學習筆記圖片整理成結構化中文教材。

你會收到：一個文法標題、既有稀疏文字、以及 1–N 張筆記圖片（可能對應不同用法或補充說明）。
請綜合**所有圖片**與既有文字中「看得見」的內容，回傳單一 GrammarEnrichmentOutput JSON。

## 語言
- 全部使用繁體中文（semantic_concept、meaning_zh、meaning_blocks、supplementary_blocks）。
- 不要輸出英文說明或英文翻譯；meaning_en 留空；例句不要填 english。

## 文法層級
- grammar_point 必須與輸入完全一致，不可改寫。
- jlpt_level 請依文法難度推估，可填 N5、N4、N3、N2、N1、unknown。
- 若文法橫跨多個級別，可填組合，例如 N3/N2（用斜線，不要空格）。

## 用法 usages
- 圖上有多個用法（用法A/B、疑問 vs 拜託、不同語意）時，**必須**拆成多筆 usages，不可合併成一句。
- 每張圖若代表不同用法卡，各自對應一筆 usage。
- semantic_concept：簡短中文標題（例如「每隔固定間隔」），不要用英文。
- connection_rule：接續規則，每條規則各占一行，以「* 」開頭（與筆記【接続】格式一致）。例如：
  * V（タ形 / ている形）＋ つもりだ
  * イA い ＋ つもりだ
  * ナA ＋ な ＋ つもりだ
  * N ＋ の ＋ つもりだ
  若只有一條規則，仍可用單行（例如「數量詞＋おきに」），不必加 *。
- meaning_blocks：把中文說明拆成 1–4 個色塊段落，每段含：
  - text：該段中文（可含重點，用自然語句即可）
  - variant：emphasis（核心語意）、note（補充說明）、caution（易混淆/注意）、default（一般說明）
- meaning_zh：可填 meaning_blocks 各段 text 以換行合併，方便搜尋。
- example_sentences：只收圖上出現的例句；保留日文原文；有假名注音才填 reading；有中文翻譯才填 chinese。
  每句務必填 highlight：例句 japanese 中「屬於此文法」的連續子字串（如「おきに」「つもりだった」），必須能在 japanese 中原樣找到。

## 補充圖片 supplementary_blocks
- 若部分圖片是「補充、對比、易錯點、延伸說明」（而非主文法卡），為這些內容另建 1+ 個 supplementary_blocks。
- 每個 block 含：title（如「補充說明」「與〜ごとに的差別」）、summary_zh（中文總結）、example_sentences（圖上相關例句）。
- 若所有圖片都是同一文法主卡，supplementary_blocks 可為空陣列。

## 禁止
- 不要憑空捏造圖上沒有的例句或規則。
- 看不清就省略，保持簡短。

## JSON 輸出
- 只回傳可解析的 JSON，不要 markdown 圍欄。
- connection_rule 多行請用 \\n 連接，字串內不要出現未跳脫的換行或引號。
- 每個 usage 例句最多 3 句；內容過多時優先保留接續規則與核心例句。
"""

_EXPLAIN_PROMPT = """你是一位日文文法老師，請為學習者撰寫完整、清楚的繁體中文文法筆記。

你會收到：一個文法標題，以及目前資料庫中可能不完整的既有內容。
請以教師知識補全／重寫成結構化 GrammarEnrichmentOutput JSON，**直接覆寫**成完整筆記（不必遷就既有殘缺內容，但可參考其中正確的部分）。

## 語言
- 全部使用繁體中文（semantic_concept、meaning_zh、meaning_blocks、supplementary_blocks）。
- 不要輸出英文說明或英文翻譯；meaning_en 留空；例句不要填 english。

## 文法層級
- grammar_point 必須與輸入完全一致，不可改寫。
- jlpt_level 請依文法難度推估，可填 N5、N4、N3、N2、N1、unknown。
- 若文法橫跨多個級別，可填組合，例如 N3/N2（用斜線，不要空格）。

## 用法 usages
- 若該文法有多個常見用法／語意，拆成多筆 usages。
- semantic_concept：簡短中文標題。
- connection_rule：接續規則，多條時每行以「* 」開頭，用 \\n 連接。
- meaning_blocks：1–4 個色塊：
  - variant：emphasis（核心語意）、note（補充）、caution（易混淆）、default
- meaning_zh：各段 text 換行合併。
- example_sentences：每用法 2–3 句自然例句；japanese 必填；盡量附 reading（平假名）與 chinese。
  每句務必填 highlight：japanese 中屬於此文法的連續子字串（活用形也要標完整，如「つもりだった」），必須能在 japanese 中原樣找到。

## 補充 supplementary_blocks
- 若有重要對比（如與相似文法差別）、使用時機、常見錯誤，可放 0–2 個補充區塊。
- 每個含 title、summary_zh、可選 example_sentences。

## 禁止
- 不要編造罕見或錯誤用法。
- 保持簡潔、適合 JLPT 學習筆記。

## JSON 輸出
- 只回傳可解析的 JSON，不要 markdown 圍欄。
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _blocks_to_meaning_zh(blocks: list[dict[str, str]]) -> str | None:
    texts = [clean_text(block.get("text", "")) for block in blocks]
    joined = "\n".join(text for text in texts if text)
    return joined or None


def _normalize_json_payload(raw: str | None) -> str:
    if not raw:
        raise ValueError("Gemini returned an empty response")
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return text


def _parse_enrichment_payload(raw: str | None) -> GrammarEnrichmentOutput:
    payload = _normalize_json_payload(raw)
    try:
        return GrammarEnrichmentOutput.model_validate_json(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"AI 回傳的 JSON 不完整或格式錯誤：{exc}") from exc


def _generate_enrichment(
    contents: list[object],
    *,
    max_output_tokens: int,
) -> GrammarEnrichmentOutput:
    response = run_with_key_failover(
        lambda client: client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GrammarEnrichmentOutput,
                temperature=0.1,
                max_output_tokens=max_output_tokens,
            ),
        )
    )
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, GrammarEnrichmentOutput):
        return parsed
    if isinstance(parsed, dict):
        return GrammarEnrichmentOutput.model_validate(parsed)
    return _parse_enrichment_payload(response.text)


def _raise_gemini_http_error(exc: Exception, *, action_label: str) -> None:
    message = str(exc)
    if is_quota_error(exc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Gemini API 額度已用完（所有 key 皆無法使用）。"
                "請在 .env / Render 新增 GEMINI_API_KEYS 備援 key，"
                f"之後再按「{action_label}」。"
            ),
        ) from exc
    if "JSON" in message or "Unterminated string" in message:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{action_label}失敗：AI 回傳內容過長被截斷，請再試一次。",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"{action_label}失敗：{message}",
    ) from exc


class GrammarEnrichmentService:
    def __init__(self) -> None:
        self.db = get_supabase_client()

    def enrich_grammar(self, grammar_id: UUID, *, dry_run: bool = False) -> GrammarOut:
        data = self._load_grammar_row(grammar_id)
        image_urls = data.get("image_urls") or []
        if not image_urls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This grammar has no stored images to enrich from.",
            )

        existing_usages = self._load_existing_usages(grammar_id)
        image_parts: list[types.Part] = []
        http = create_sync_client(timeout=90.0)
        max_images = min(len(image_urls), 8)
        for url in image_urls[:max_images]:
            response = http.get(url)
            response.raise_for_status()
            mime = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            image_parts.append(types.Part.from_bytes(data=response.content, mime_type=mime))

        existing_summary = json.dumps(existing_usages, ensure_ascii=False)
        contents: list[object] = [
            f"grammar_point={data['grammar_point']}\n"
            f"jlpt_level={data.get('jlpt_level') or 'unknown'}\n"
            f"existing_usages={existing_summary}\n"
            "Return a single GrammarEnrichmentOutput JSON object.",
            *image_parts,
            _IMAGE_PROMPT,
        ]

        try:
            token_limits = (8192, 12288) if max_images > 4 else (8192,)
            item = self._run_generation(contents, token_limits)
        except Exception as exc:
            _raise_gemini_http_error(exc, action_label="從圖片補全")

        if dry_run:
            return self._draft_from_enrichment(grammar_id, data, item)
        return self._persist_enrichment(
            grammar_id,
            data,
            item,
            lock_manual=False,
        )

    def explain_grammar(self, grammar_id: UUID, *, dry_run: bool = False) -> GrammarOut:
        """Text-only AI teacher rewrite; dry_run returns draft without DB write."""
        data = self._load_grammar_row(grammar_id)
        if data.get("sync_status") == "archived":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")

        existing_usages = self._load_existing_usages(grammar_id)
        existing_summary = json.dumps(existing_usages, ensure_ascii=False)
        contents: list[object] = [
            f"grammar_point={data['grammar_point']}\n"
            f"jlpt_level={data.get('jlpt_level') or 'unknown'}\n"
            f"existing_usages={existing_summary}\n"
            "Return a single GrammarEnrichmentOutput JSON object. Overwrite with a complete note.",
            _EXPLAIN_PROMPT,
        ]

        try:
            item = self._run_generation(contents, (8192,))
        except Exception as exc:
            _raise_gemini_http_error(exc, action_label="AI 解釋補全")

        if dry_run:
            return self._draft_from_enrichment(grammar_id, data, item)
        return self._persist_enrichment(
            grammar_id,
            data,
            item,
            lock_manual=True,
        )

    def _draft_from_enrichment(
        self,
        grammar_id: UUID,
        data: dict,
        item: GrammarEnrichmentOutput,
    ) -> GrammarOut:
        from uuid import uuid4

        from app.models.schemas.grammar import GrammarOut, GrammarUsageOut

        if item.grammar_point.strip() != data["grammar_point"].strip():
            item.grammar_point = data["grammar_point"]

        usages: list[GrammarUsageOut] = []
        for index, usage in enumerate(item.usages):
            meaning_blocks = list(usage.meaning_blocks or [])
            block_dicts = [
                b.model_dump(mode="json") if hasattr(b, "model_dump") else b
                for b in meaning_blocks
            ]
            meaning_zh = clean_text(usage.meaning_zh) or _blocks_to_meaning_zh(block_dicts)
            usages.append(
                GrammarUsageOut(
                    id=uuid4(),
                    sort_order=index,
                    semantic_concept=clean_text(usage.semantic_concept) or item.grammar_point,
                    connection_rule=clean_text(usage.connection_rule) or "",
                    meaning_zh=meaning_zh,
                    meaning_en=None,
                    meaning_blocks=meaning_blocks,
                    example_sentences=list(usage.example_sentences or []),
                )
            )

        return GrammarOut(
            id=grammar_id,
            grammar_point=data["grammar_point"],
            jlpt_level=item.jlpt_level or data.get("jlpt_level") or "unknown",
            usages=usages,
            image_urls=data.get("image_urls") or [],
            supplementary_blocks=list(item.supplementary_blocks or []),
            sync_status=data.get("sync_status") or "synced",
            needs_enrichment=False,
            manual_edited=True,
        )

    def _load_grammar_row(self, grammar_id: UUID) -> dict:
        row = (
            self.db.table("grammars")
            .select(
                "id, grammar_point, jlpt_level, image_urls, source_content_hash, sync_status"
            )
            .eq("id", str(grammar_id))
            .maybe_single()
            .execute()
        )
        if row is None or not row.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar not found")
        return row.data

    def _load_existing_usages(self, grammar_id: UUID) -> list[dict]:
        existing_usages = (
            self.db.table("grammar_usages")
            .select(
                "semantic_concept, connection_rule, meaning_zh, meaning_blocks, example_sentences"
            )
            .eq("grammar_id", str(grammar_id))
            .order("sort_order")
            .execute()
        )
        return existing_usages.data or []

    def _run_generation(
        self,
        contents: list[object],
        token_limits: tuple[int, ...],
    ) -> GrammarEnrichmentOutput:
        last_error: Exception | None = None
        for max_tokens in token_limits:
            try:
                return _generate_enrichment(contents, max_output_tokens=max_tokens)
            except ValueError as exc:
                last_error = exc
                if max_tokens != token_limits[-1]:
                    continue
                raise
        raise ValueError(str(last_error or "AI 補全失敗"))

    def _persist_enrichment(
        self,
        grammar_id: UUID,
        data: dict,
        item: GrammarEnrichmentOutput,
        *,
        lock_manual: bool,
    ) -> GrammarOut:
        if item.grammar_point.strip() != data["grammar_point"].strip():
            item.grammar_point = data["grammar_point"]

        supplementary_rows = [
            block.model_dump(mode="json") for block in item.supplementary_blocks
        ]
        update_row: dict = {
            "jlpt_level": item.jlpt_level,
            "supplementary_blocks": supplementary_rows,
            "ai_content_hash": data.get("source_content_hash"),
            "sync_status": "synced",
        }
        if lock_manual:
            update_row["manual_edited_at"] = _now_iso()

        self.db.table("grammars").update(update_row).eq("id", str(grammar_id)).execute()

        self.db.table("grammar_usages").delete().eq("grammar_id", str(grammar_id)).execute()
        rows = []
        for index, usage in enumerate(item.usages):
            meaning_blocks = [block.model_dump(mode="json") for block in usage.meaning_blocks]
            meaning_zh = clean_text(usage.meaning_zh) or _blocks_to_meaning_zh(meaning_blocks)
            rows.append(
                {
                    "grammar_id": str(grammar_id),
                    "sort_order": index,
                    "semantic_concept": clean_text(usage.semantic_concept),
                    "connection_rule": clean_text(usage.connection_rule),
                    "meaning_zh": meaning_zh,
                    "meaning_en": None,
                    "meaning_blocks": meaning_blocks,
                    "example_sentences": [
                        {
                            "japanese": ex.japanese,
                            "reading": ex.reading,
                            "chinese": ex.chinese,
                            "highlight": ex.highlight,
                        }
                        for ex in usage.example_sentences
                    ],
                }
            )
        if rows:
            self.db.table("grammar_usages").insert(rows).execute()

        from app.models.schemas.links import LinkEntityType
        from app.services.semantic_link_service import semantic_link_service

        semantic_link_service.sync_entity_safe(LinkEntityType.GRAMMAR, grammar_id)
        return grammar_service.get_grammar(grammar_id)


grammar_enrichment_service = GrammarEnrichmentService()
