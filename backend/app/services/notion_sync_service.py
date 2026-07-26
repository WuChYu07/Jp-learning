"""Orchestrates Notion fetch → parse → preview/confirm."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from supabase import Client

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.models.schemas.common import SourceType
from app.models.schemas.ingestion import IngestionParseResult, IngestionResponse
from app.models.schemas.notion import (
    NotionFocus,
    NotionOrphanedGrammar,
    NotionOrphanedVocab,
    NotionPageSource,
    NotionSyncPreview,
)
from app.services.grammar_service import grammar_service
from app.services.hash_service import sha256_hex, vocab_entry_hash
from app.services.ingestion_service import ingestion_service
from app.services.notion.analyzer import analyze_blocks
from app.services.notion.client import NotionClient, NotionClientError, extract_page_title
from app.services.notion.pages import NotionPageConfigError, resolve_page_targets
from app.services.notion.diff import (
    annotate_grammar_sync_changes,
    annotate_vocab_sync_changes,
    filter_sync_preview_items,
    find_orphaned_notion_grammars,
    find_orphaned_notion_vocab,
)
from app.services.notion.parser import parse_blocks
from app.services.vocab_service import vocab_service
from app.services import storage_service

logger = logging.getLogger(__name__)


class NotionSyncService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def sync_preview(
        self,
        *,
        focus: NotionFocus = "both",
        page_id: str | None = None,
        upload_images: bool = True,
    ) -> NotionSyncPreview:
        if not settings.NOTION_TOKEN:
            raise HTTPException(status_code=400, detail="NOTION_TOKEN is not configured")

        try:
            targets = resolve_page_targets(focus, page_id=page_id)
        except NotionPageConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        sources: list[NotionPageSource] = []
        merged = IngestionParseResult()
        total_images = 0
        total_sections = 0
        total_orphans = 0
        hash_parts: list[str] = []
        unchanged = True
        grammar_new = grammar_updated = grammar_unchanged = 0
        vocab_new = vocab_updated = vocab_unchanged = 0
        grammar_page_ids: list[str] = []
        vocab_page_ids: list[str] = []

        try:
            with NotionClient(settings.NOTION_TOKEN) as client:
                for page_focus, resolved_page_id in targets:
                    if page_focus in {"grammar", "both"}:
                        grammar_page_ids.append(resolved_page_id)
                    if page_focus in {"vocabulary", "both"}:
                        vocab_page_ids.append(resolved_page_id)
                    page = client.get_page(resolved_page_id)
                    blocks = client.fetch_all_blocks(resolved_page_id)
                    if upload_images:
                        self._persist_images(client, blocks)

                    analysis = analyze_blocks(blocks)
                    parsed = parse_blocks(
                        blocks,
                        focus=page_focus,
                        sections=analysis.sections,
                        notion_page_id=resolved_page_id,
                    )
                    if page_focus in {"grammar", "both"} and parsed.grammars:
                        try:
                            n, u, c = annotate_grammar_sync_changes(
                                parsed.grammars,
                                self.db,
                                notion_page_id=resolved_page_id,
                            )
                            grammar_new += n
                            grammar_updated += u
                            grammar_unchanged += c
                        except Exception:
                            logger.exception(
                                "annotate_grammar_sync_changes failed for page %s; "
                                "treating all %d parsed grammars as new",
                                resolved_page_id,
                                len(parsed.grammars),
                            )
                            for item in parsed.grammars:
                                item.sync_change = "new"
                            grammar_new += len(parsed.grammars)
                    if page_focus in {"vocabulary", "both"} and parsed.vocabularies:
                        try:
                            vn, vu, vc = annotate_vocab_sync_changes(parsed.vocabularies, self.db)
                            vocab_new += vn
                            vocab_updated += vu
                            vocab_unchanged += vc
                        except Exception:
                            logger.exception(
                                "annotate_vocab_sync_changes failed for page %s; "
                                "treating all %d parsed vocab entries as new",
                                resolved_page_id,
                                len(parsed.vocabularies),
                            )
                            for item in parsed.vocabularies:
                                item.sync_change = "new"
                            vocab_new += len(parsed.vocabularies)
                    page_hash = self._compute_sync_hash(resolved_page_id, page, blocks)
                    hash_parts.append(page_hash)

                    if self._find_cached_sync(page_hash) is None:
                        unchanged = False

                    merged.vocabularies.extend(parsed.vocabularies)
                    merged.grammars.extend(parsed.grammars)
                    total_images += analysis.image_count
                    total_sections += len(analysis.sections)
                    total_orphans += len(analysis.orphan_images)

                    sources.append(
                        NotionPageSource(
                            focus=page_focus,
                            page_id=resolved_page_id,
                            page_title=extract_page_title(page),
                            content_hash=page_hash,
                            last_edited_time=page.get("last_edited_time"),
                            image_count=analysis.image_count,
                            section_count=len(analysis.sections),
                        )
                    )
        except NotionClientError as exc:
            raise HTTPException(
                status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        content_hash = sha256_hex("|".join(hash_parts).encode("utf-8"))
        page_title = _combined_title(sources)
        display_page_id = "+".join(source.page_id for source in sources)

        present_block_ids = {
            g.notion_block_id for g in merged.grammars if g.notion_block_id
        }
        orphaned = find_orphaned_notion_grammars(
            self.db,
            notion_page_ids=grammar_page_ids,
            present_block_ids=present_block_ids,
        )

        present_vocab_hashes = {
            vocab_entry_hash(v.word, v.reading) for v in merged.vocabularies
        }
        orphaned_vocab = find_orphaned_notion_vocab(
            self.db,
            notion_page_ids=vocab_page_ids,
            present_hashes=present_vocab_hashes,
        )

        filter_sync_preview_items(merged.grammars, merged.vocabularies)

        return NotionSyncPreview(
            focus=focus,
            page_id=display_page_id,
            page_title=page_title,
            content_hash=content_hash,
            last_edited_time=sources[-1].last_edited_time if sources else None,
            parsed=merged,
            vocabulary_count=len(merged.vocabularies),
            grammar_count=len(merged.grammars),
            image_count=total_images,
            section_count=total_sections,
            orphan_image_count=total_orphans,
            unchanged=unchanged,
            grammar_new_count=grammar_new,
            grammar_updated_count=grammar_updated,
            grammar_unchanged_count=grammar_unchanged,
            vocab_new_count=vocab_new,
            vocab_updated_count=vocab_updated,
            vocab_unchanged_count=vocab_unchanged,
            orphaned_grammars=[
                NotionOrphanedGrammar(
                    id=o.id,
                    grammar_point=o.grammar_point,
                    notion_block_id=o.notion_block_id,
                    notion_page_id=o.notion_page_id,
                )
                for o in orphaned
            ],
            orphaned_vocabularies=[
                NotionOrphanedVocab(
                    id=o.id,
                    word=o.word,
                    reading=o.reading,
                    notion_page_id=o.notion_page_id,
                )
                for o in orphaned_vocab
            ],
            sources=sources,
        )

    def confirm_sync(
        self,
        parsed: IngestionParseResult,
        content_hash: str,
        page_id: str,
        page_title: str | None,
        user_id: str | None,
        *,
        focus: NotionFocus = "both",
        auto_approved: bool = False,
        force: bool = False,
        force_overwrite_grammar_block_ids: list[str] | None = None,
        archive_grammar_ids: list[str] | None = None,
        archive_vocab_ids: list[str] | None = None,
        vocab_field_overwrites: dict[str, list[str]] | None = None,
    ) -> IngestionResponse:
        force_blocks = set(force_overwrite_grammar_block_ids or [])
        for item in parsed.grammars:
            if item.notion_block_id and item.notion_block_id in force_blocks:
                item.force_overwrite = True

        for grammar_id in archive_grammar_ids or []:
            try:
                from uuid import UUID

                grammar_service.archive_grammar(UUID(grammar_id))
            except Exception:
                logger.exception("failed to archive grammar %s during Notion confirm", grammar_id)
                continue

        for vocabulary_id in archive_vocab_ids or []:
            try:
                from uuid import UUID

                vocab_service.archive_vocabulary(UUID(vocabulary_id))
            except Exception:
                logger.exception(
                    "failed to archive vocabulary %s during Notion confirm", vocabulary_id
                )
                continue

        effective_hash = content_hash
        if force:
            effective_hash = sha256_hex(
                f"{content_hash}|force|{len(parsed.grammars)}|{len(parsed.vocabularies)}".encode(
                    "utf-8"
                )
            )

        response = ingestion_service.process_parsed_data(
            parsed=parsed,
            content_hash=effective_hash,
            user_id=user_id,
            source_type=SourceType.NOTION,
            mime_type="application/notion",
            file_name=page_title or page_id,
            skip_ingestion_cache=force,
            vocab_field_overwrites=vocab_field_overwrites,
        )
        for source in _split_page_ids(page_id):
            self._write_sync_log(
                page_id=source,
                page_title=page_title,
                content_hash=content_hash,
                grammar_count=response.grammar_count,
                vocab_count=response.vocabulary_count,
                image_count=sum(len(g.image_urls) for g in parsed.grammars),
                auto_approved=auto_approved,
                focus=focus,
            )
        return response

    def get_status(self) -> dict:
        result = (
            self.db.table("notion_sync_log")
            .select("*")
            .order("synced_at", desc=True)
            .limit(10)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"synced": False, "pages": []}

        by_page: dict[str, dict] = {}
        for row in rows:
            pid = row.get("page_id")
            if pid and pid not in by_page:
                by_page[pid] = {
                    "page_id": pid,
                    "page_title": row.get("page_title"),
                    "focus": row.get("focus"),
                    "last_synced_at": row.get("synced_at"),
                    "grammar_count": row.get("grammar_count", 0),
                    "vocabulary_count": row.get("vocab_count", 0),
                    "image_count": row.get("image_count", 0),
                }

        return {
            "synced": True,
            "pages": list(by_page.values()),
            "last_synced_at": rows[0].get("synced_at"),
        }

    def _persist_images(self, client: NotionClient, blocks) -> None:
        for block in blocks:
            if block.type != "image" or not block.image_url:
                continue
            if block.image_url.startswith("http") and "supabase" in block.image_url:
                continue
            try:
                cached = (
                    self.db.table("notion_images")
                    .select("storage_url")
                    .eq("notion_block_id", block.id)
                    .maybe_single()
                    .execute()
                )
                if cached is not None and cached.data:
                    block.image_url = cached.data["storage_url"]
                    continue
            except Exception:
                logger.warning(
                    "notion_images cache lookup failed for block %s; will re-fetch", block.id
                )
            try:
                fresh_url = client.refresh_image_url(block.id) or block.image_url
                content, content_type = client.download_image(fresh_url)
                suffix = _suffix_from_content_type(content_type)
                permanent_url = storage_service.upload_image(
                    content, content_type=content_type, suffix=suffix
                )
                block.image_url = permanent_url
                try:
                    self.db.table("notion_images").upsert(
                        {
                            "notion_block_id": block.id,
                            "storage_url": permanent_url,
                        }
                    ).execute()
                except Exception:
                    logger.warning(
                        "notion_images cache upsert failed for block %s", block.id
                    )
            except Exception:
                logger.exception(
                    "failed to persist Notion image for block %s; keeping original (possibly "
                    "expiring) Notion URL",
                    block.id,
                )
                continue

    def _compute_sync_hash(self, page_id: str, page: dict, blocks) -> str:
        block_ids = ",".join(block.id for block in blocks)
        payload = f"{page_id}|{page.get('last_edited_time')}|{len(blocks)}|{block_ids}"
        return sha256_hex(payload.encode("utf-8"))

    def _find_cached_sync(self, content_hash: str) -> dict | None:
        result = (
            self.db.table("notion_sync_log")
            .select("id, content_hash")
            .eq("content_hash", content_hash)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return result.data

    def _write_sync_log(
        self,
        *,
        page_id: str,
        page_title: str | None,
        content_hash: str,
        grammar_count: int,
        vocab_count: int,
        image_count: int,
        auto_approved: bool,
        focus: NotionFocus,
    ) -> None:
        row = {
            "page_id": page_id,
            "page_title": page_title,
            "content_hash": content_hash,
            "grammar_count": grammar_count,
            "vocab_count": vocab_count,
            "image_count": image_count,
            "auto_approved": auto_approved,
            "focus": focus,
        }
        try:
            self.db.table("notion_sync_log").insert(row).execute()
        except Exception:
            logger.debug(
                "notion_sync_log insert failed with 'focus' column; retrying without it "
                "(migration 004 may not be applied yet)"
            )
            row.pop("focus", None)
            self.db.table("notion_sync_log").insert(row).execute()


def _combined_title(sources: list[NotionPageSource]) -> str:
    if not sources:
        return "Notion"
    if len(sources) == 1:
        return sources[0].page_title
    return " + ".join(f"{s.page_title} ({s.focus})" for s in sources)


def _split_page_ids(page_id: str) -> list[str]:
    if "+" in page_id:
        return page_id.split("+")
    return [page_id]


def _suffix_from_content_type(content_type: str | None) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    if content_type:
        base = content_type.split(";")[0].strip().lower()
        return mapping.get(base, ".jpg")
    return ".jpg"


notion_sync_service = NotionSyncService()
