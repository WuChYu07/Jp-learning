"""Extract example_vocab links from grammar example sentences."""

from __future__ import annotations

from uuid import UUID

from app.db.supabase import get_supabase_client
from app.models.schemas.links import (
    ContentLinkCreate,
    LinkEntityType,
    LinkRelationType,
)
from app.services.link_service import link_service

# Prefer longer words first when matching inside Japanese text
_MIN_WORD_LEN = 2


class ExampleVocabLinkService:
    def sync_for_grammar(self, grammar_id: UUID) -> dict:
        """Create example_vocab edges from this grammar's example sentences."""
        db = get_supabase_client()
        usages = (
            db.table("grammar_usages")
            .select("example_sentences")
            .eq("grammar_id", str(grammar_id))
            .execute()
        )
        texts: list[str] = []
        for usage in usages.data or []:
            for ex in usage.get("example_sentences") or []:
                jp = (ex.get("japanese") or "").strip()
                if jp:
                    texts.append(jp)

        if not texts:
            return {"created": 0, "skipped": 0, "matched_words": []}

        vocab_rows = (
            db.table("vocabularies")
            .select("id, word, reading")
            .execute()
        ).data or []

        # Sort by word length descending for greedy match
        vocab_rows = sorted(
            [v for v in vocab_rows if len(v.get("word") or "") >= _MIN_WORD_LEN],
            key=lambda v: len(v["word"]),
            reverse=True,
        )

        matched: dict[str, dict] = {}
        combined = "\n".join(texts)
        for vocab in vocab_rows:
            word = vocab["word"]
            if word in combined:
                matched[vocab["id"]] = vocab
            elif vocab.get("reading") and len(vocab["reading"]) >= _MIN_WORD_LEN:
                if vocab["reading"] in combined:
                    matched[vocab["id"]] = vocab

        # Cap per grammar to avoid dense graphs
        matched_items = list(matched.values())[:12]

        payloads = [
            ContentLinkCreate(
                source_type=LinkEntityType.GRAMMAR,
                source_id=grammar_id,
                target_type=LinkEntityType.VOCABULARY,
                target_id=UUID(v["id"]),
                relation_type=LinkRelationType.EXAMPLE_VOCAB,
                label_zh="例句單字",
                note_zh=f"出現於例句：{v['word']}",
                confidence=0.85,
                origin="cooccurrence",
                bidirectional=True,
            )
            for v in matched_items
        ]
        created, skipped = link_service.create_links_batch(payloads)
        return {
            "created": len(created),
            "skipped": skipped,
            "matched_words": [v["word"] for v in matched_items],
        }

    def sync_all(self, limit: int = 200) -> dict:
        db = get_supabase_client()
        grammars = (
            db.table("grammars")
            .select("id")
            .neq("sync_status", "archived")
            .limit(limit)
            .execute()
        )
        total_created = 0
        total_skipped = 0
        for row in grammars.data or []:
            result = self.sync_for_grammar(UUID(row["id"]))
            total_created += result["created"]
            total_skipped += result["skipped"]
        return {
            "grammars_processed": len(grammars.data or []),
            "created": total_created,
            "skipped": total_skipped,
        }


example_vocab_link_service = ExampleVocabLinkService()
