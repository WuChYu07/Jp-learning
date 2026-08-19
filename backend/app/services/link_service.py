"""CRUD and neighborhood queries for content knowledge-graph links."""

from __future__ import annotations

from collections import deque
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.db.supabase import get_supabase_client
from app.models.schemas.links import (
    ContentLinkCreate,
    ContentLinkOut,
    GraphEdge,
    GraphNode,
    LinkEntityType,
    LinkRelationType,
    RelationGraphOut,
)


def _node_key(entity_type: str | LinkEntityType, entity_id: str | UUID) -> str:
    # str(Enum) on Python 3.11+ may yield "LinkEntityType.GRAMMAR"; always use .value
    et = entity_type.value if isinstance(entity_type, LinkEntityType) else str(entity_type)
    return f"{et}:{entity_id}"


def _jlpt_group(jlpt: str | None) -> str | None:
    if not jlpt:
        return None
    text = str(jlpt).upper()
    for level in ("N5", "N4", "N3", "N2", "N1"):
        if level in text:
            return level
    return text.split("/")[0].strip() or None


class LinkService:
    def __init__(self, db: Client | None = None) -> None:
        self.db = db or get_supabase_client()

    def create_link(self, payload: ContentLinkCreate) -> ContentLinkOut:
        if (
            payload.source_type == payload.target_type
            and payload.source_id == payload.target_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot link an entity to itself",
            )

        row = {
            "source_type": payload.source_type.value,
            "source_id": str(payload.source_id),
            "target_type": payload.target_type.value,
            "target_id": str(payload.target_id),
            "relation_type": payload.relation_type.value,
            "label_zh": payload.label_zh,
            "note_zh": payload.note_zh,
            "confidence": payload.confidence,
            "origin": payload.origin,
            "bidirectional": payload.bidirectional,
        }
        try:
            result = self.db.table("content_links").insert(row).execute()
        except Exception as exc:
            # Unique violation → return existing
            existing = self._find_exact(payload)
            if existing:
                return existing
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create link: {exc}",
            ) from exc

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Link insert returned no data",
            )
        return self._row_to_out(result.data[0])

    def create_links_batch(
        self, payloads: list[ContentLinkCreate]
    ) -> tuple[list[ContentLinkOut], int]:
        created: list[ContentLinkOut] = []
        skipped = 0
        for payload in payloads:
            existing = self._find_exact(payload)
            if existing:
                skipped += 1
                continue
            try:
                created.append(self.create_link(payload))
            except HTTPException:
                skipped += 1
        return created, skipped

    def delete_link(self, link_id: UUID) -> None:
        result = (
            self.db.table("content_links")
            .delete()
            .eq("id", str(link_id))
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
            )

    def get_neighborhood(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        depth: int = 1,
        relation_types: list[LinkRelationType] | None = None,
    ) -> RelationGraphOut:
        depth = max(1, min(depth, 3))
        center_key = _node_key(entity_type, entity_id)

        visited: set[str] = {center_key}
        edge_rows: dict[str, dict] = {}
        frontier: deque[tuple[str, LinkEntityType, UUID, int]] = deque(
            [(center_key, entity_type, entity_id, 0)]
        )

        while frontier:
            _key, etype, eid, d = frontier.popleft()
            if d >= depth:
                continue
            links = self._links_touching(etype, eid, relation_types)
            for link in links:
                edge_rows[link["id"]] = link
                for neighbor_type, neighbor_id in self._neighbors(link, etype, eid):
                    nkey = _node_key(neighbor_type, neighbor_id)
                    if nkey in visited:
                        continue
                    visited.add(nkey)
                    frontier.append(
                        (nkey, LinkEntityType(neighbor_type), UUID(neighbor_id), d + 1)
                    )

        nodes = self._resolve_nodes(visited)
        edges = [
            GraphEdge(
                id=row["id"],
                source=_node_key(row["source_type"], row["source_id"]),
                target=_node_key(row["target_type"], row["target_id"]),
                relation_type=LinkRelationType(row["relation_type"]),
                label_zh=row.get("label_zh"),
                note_zh=row.get("note_zh"),
                confidence=float(row.get("confidence") or 1.0),
            )
            for row in edge_rows.values()
        ]
        return RelationGraphOut(nodes=nodes, edges=edges, center_id=center_key)

    def get_global_graph(
        self,
        entity_types: list[LinkEntityType] | None = None,
        jlpt: str | None = None,
        relation_types: list[LinkRelationType] | None = None,
        limit: int = 200,
        min_confidence: float | None = None,
    ) -> RelationGraphOut:
        query = self.db.table("content_links").select("*").limit(limit)
        if relation_types:
            query = query.in_(
                "relation_type", [r.value for r in relation_types]
            )
        result = query.execute()
        rows = result.data or []

        if min_confidence is not None:
            rows = [
                row
                for row in rows
                if float(row.get("confidence") or 0.0) >= min_confidence
            ]

        allowed_types = {t.value for t in (entity_types or list(LinkEntityType))}
        filtered: list[dict] = []
        node_keys: set[str] = set()
        for row in rows:
            if (
                row["source_type"] not in allowed_types
                and row["target_type"] not in allowed_types
            ):
                continue
            filtered.append(row)
            node_keys.add(_node_key(row["source_type"], row["source_id"]))
            node_keys.add(_node_key(row["target_type"], row["target_id"]))

        nodes = self._resolve_nodes(node_keys)
        if jlpt:
            jlpt_upper = jlpt.upper()
            keep_ids = {
                n.id
                for n in nodes
                if not n.jlpt_level
                or jlpt_upper in (n.jlpt_level or "").upper()
                or n.type == LinkEntityType.CONCEPT
            }
            # Keep concept hubs and any node matching JLPT; drop others
            nodes = [n for n in nodes if n.id in keep_ids]
            keep = {n.id for n in nodes}
            filtered = [
                r
                for r in filtered
                if _node_key(r["source_type"], r["source_id"]) in keep
                and _node_key(r["target_type"], r["target_id"]) in keep
            ]

        edges = [
            GraphEdge(
                id=row["id"],
                source=_node_key(row["source_type"], row["source_id"]),
                target=_node_key(row["target_type"], row["target_id"]),
                relation_type=LinkRelationType(row["relation_type"]),
                label_zh=row.get("label_zh"),
                note_zh=row.get("note_zh"),
                confidence=float(row.get("confidence") or 1.0),
            )
            for row in filtered
        ]
        center = nodes[0].id if nodes else ""
        return RelationGraphOut(nodes=nodes, edges=edges, center_id=center)

    def list_concepts(self) -> list[dict]:
        result = (
            self.db.table("semantic_concepts")
            .select("*")
            .order("title_zh")
            .execute()
        )
        return result.data or []

    def upsert_concept(
        self,
        title_zh: str,
        description_zh: str | None = None,
        jlpt_level: str | None = None,
    ) -> dict:
        existing = (
            self.db.table("semantic_concepts")
            .select("*")
            .eq("title_zh", title_zh)
            .maybe_single()
            .execute()
        )
        if existing is not None and existing.data:
            return existing.data
        inserted = (
            self.db.table("semantic_concepts")
            .insert(
                {
                    "title_zh": title_zh,
                    "description_zh": description_zh,
                    "jlpt_level": jlpt_level,
                }
            )
            .execute()
        )
        return inserted.data[0]

    def find_grammar_by_pattern(self, pattern: str) -> dict | None:
        """Resolve a grammar_point string to a DB row via normalize + fuzzy match."""
        from app.services.grammar_kb import normalize_pattern

        key = normalize_pattern(pattern)
        result = (
            self.db.table("grammars")
            .select("id, grammar_point, jlpt_level, sync_status")
            .neq("sync_status", "archived")
            .execute()
        )
        rows = result.data or []
        # Exact / normalized exact
        for row in rows:
            if normalize_pattern(row["grammar_point"]) == key:
                return row
            if row["grammar_point"].strip() == pattern.strip():
                return row
        # Substring containment (prefer longer matches)
        candidates = []
        for row in rows:
            gp = row["grammar_point"]
            norm = normalize_pattern(gp)
            if key in norm or norm in key or key in gp or gp in key:
                candidates.append((len(norm), row))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            return candidates[0][1]
        return None

    def find_vocab_by_word(self, word: str) -> dict | None:
        result = (
            self.db.table("vocabularies")
            .select("id, word, reading, jlpt_level")
            .eq("word", word)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
        # Try reading match
        result = (
            self.db.table("vocabularies")
            .select("id, word, reading, jlpt_level")
            .eq("reading", word)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    # ── internals ──────────────────────────────────────────────────────────

    def _find_exact(self, payload: ContentLinkCreate) -> ContentLinkOut | None:
        result = (
            self.db.table("content_links")
            .select("*")
            .eq("source_type", payload.source_type.value)
            .eq("source_id", str(payload.source_id))
            .eq("target_type", payload.target_type.value)
            .eq("target_id", str(payload.target_id))
            .eq("relation_type", payload.relation_type.value)
            .maybe_single()
            .execute()
        )
        if result is not None and result.data:
            return self._row_to_out(result.data)
        return None

    def _links_touching(
        self,
        entity_type: LinkEntityType,
        entity_id: UUID,
        relation_types: list[LinkRelationType] | None,
    ) -> list[dict]:
        eid = str(entity_id)
        et = entity_type.value

        as_source = (
            self.db.table("content_links")
            .select("*")
            .eq("source_type", et)
            .eq("source_id", eid)
        )
        as_target = (
            self.db.table("content_links")
            .select("*")
            .eq("target_type", et)
            .eq("target_id", eid)
            .eq("bidirectional", True)
        )
        if relation_types:
            vals = [r.value for r in relation_types]
            as_source = as_source.in_("relation_type", vals)
            as_target = as_target.in_("relation_type", vals)

        src_rows = as_source.execute().data or []
        tgt_rows = as_target.execute().data or []
        by_id = {r["id"]: r for r in src_rows + tgt_rows}
        return list(by_id.values())

    @staticmethod
    def _neighbors(
        link: dict, from_type: LinkEntityType, from_id: UUID
    ) -> list[tuple[str, str]]:
        fid = str(from_id)
        ft = from_type.value
        out: list[tuple[str, str]] = []
        if link["source_type"] == ft and link["source_id"] == fid:
            out.append((link["target_type"], link["target_id"]))
        if link["target_type"] == ft and link["target_id"] == fid:
            out.append((link["source_type"], link["source_id"]))
        return out

    def _resolve_nodes(self, keys: set[str]) -> list[GraphNode]:
        by_type: dict[str, list[str]] = {
            "grammar": [],
            "vocabulary": [],
            "concept": [],
        }
        for key in keys:
            etype, eid = key.split(":", 1)
            if etype in by_type:
                by_type[etype].append(eid)

        nodes: list[GraphNode] = []

        if by_type["grammar"]:
            rows = (
                self.db.table("grammars")
                .select("id, grammar_point, jlpt_level")
                .in_("id", by_type["grammar"])
                .execute()
            ).data or []
            for row in rows:
                jlpt = row.get("jlpt_level")
                nodes.append(
                    GraphNode(
                        id=_node_key("grammar", row["id"]),
                        type=LinkEntityType.GRAMMAR,
                        label=row["grammar_point"],
                        jlpt_level=jlpt,
                        group=_jlpt_group(jlpt),
                    )
                )

        if by_type["vocabulary"]:
            rows = (
                self.db.table("vocabularies")
                .select("id, word, reading, jlpt_level")
                .in_("id", by_type["vocabulary"])
                .execute()
            ).data or []
            for row in rows:
                label = row["word"]
                if row.get("reading"):
                    label = f"{row['word']}（{row['reading']}）"
                jlpt = str(row.get("jlpt_level") or "")
                nodes.append(
                    GraphNode(
                        id=_node_key("vocabulary", row["id"]),
                        type=LinkEntityType.VOCABULARY,
                        label=label,
                        jlpt_level=jlpt,
                        group=_jlpt_group(jlpt),
                    )
                )

        if by_type["concept"]:
            rows = (
                self.db.table("semantic_concepts")
                .select("id, title_zh, jlpt_level")
                .in_("id", by_type["concept"])
                .execute()
            ).data or []
            for row in rows:
                jlpt = row.get("jlpt_level")
                nodes.append(
                    GraphNode(
                        id=_node_key("concept", row["id"]),
                        type=LinkEntityType.CONCEPT,
                        label=row["title_zh"],
                        jlpt_level=jlpt,
                        group=_jlpt_group(jlpt) or "concept",
                    )
                )

        # Preserve orphan keys as stubs so edges still render
        known = {n.id for n in nodes}
        for key in keys:
            if key not in known:
                etype, eid = key.split(":", 1)
                nodes.append(
                    GraphNode(
                        id=key,
                        type=LinkEntityType(etype),
                        label=eid[:8],
                        jlpt_level=None,
                        group=None,
                    )
                )
        return nodes

    @staticmethod
    def _row_to_out(row: dict) -> ContentLinkOut:
        return ContentLinkOut(
            id=UUID(row["id"]),
            source_type=LinkEntityType(row["source_type"]),
            source_id=UUID(row["source_id"]),
            target_type=LinkEntityType(row["target_type"]),
            target_id=UUID(row["target_id"]),
            relation_type=LinkRelationType(row["relation_type"]),
            label_zh=row.get("label_zh"),
            note_zh=row.get("note_zh"),
            confidence=float(row.get("confidence") or 1.0),
            origin=row.get("origin") or "manual",
            bidirectional=bool(row.get("bidirectional", True)),
        )


link_service = LinkService()
