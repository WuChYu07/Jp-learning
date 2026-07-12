import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import RelationGraphPanel from "../components/RelationGraphPanel";
import RelationLinkList, { RELATION_LABELS } from "../components/RelationLinkList";
import {
  api,
  GraphNode,
  LinkRelationType,
  RelationGraph,
} from "../lib/api";

const JLPT_OPTIONS = ["", "N5", "N4", "N3", "N2", "N1"];
const RELATION_FILTERS: Array<LinkRelationType | ""> = [
  "",
  "same_meaning",
  "contrast",
  "confusable",
  "prerequisite",
  "derived",
  "example_vocab",
];

export default function KnowledgeMapPage() {
  const navigate = useNavigate();
  const [graph, setGraph] = useState<RelationGraph | null>(null);
  const [jlpt, setJlpt] = useState("");
  const [relation, setRelation] = useState<LinkRelationType | "">("");
  const [includeVocab, setIncludeVocab] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [listMode, setListMode] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const types = includeVocab
        ? "grammar,vocabulary,concept"
        : "grammar,concept";
      const data = await api.getGlobalGraph({
        entity_types: types,
        jlpt: jlpt || undefined,
        relation_types: relation || undefined,
        limit: 300,
      });
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入地圖失敗");
      setGraph(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jlpt, relation, includeVocab]);

  const filtered = useMemo(() => {
    if (!graph) return null;
    const q = query.trim().toLowerCase();
    if (!q) return graph;
    const keep = new Set(
      graph.nodes.filter((n) => n.label.toLowerCase().includes(q)).map((n) => n.id),
    );
    // Also keep neighbors of matches
    for (const e of graph.edges) {
      if (keep.has(e.source)) keep.add(e.target);
      if (keep.has(e.target)) keep.add(e.source);
    }
    return {
      ...graph,
      nodes: graph.nodes.filter((n) => keep.has(n.id)),
      edges: graph.edges.filter((e) => keep.has(e.source) && keep.has(e.target)),
      center_id: graph.nodes.find((n) => keep.has(n.id))?.id || graph.center_id,
    };
  }, [graph, query]);

  const handleSelect = (node: GraphNode) => {
    if (node.type === "grammar") {
      navigate("/grammar", { state: { grammarId: node.id.replace(/^grammar:/, "") } });
    } else if (node.type === "vocabulary") {
      navigate("/vocab", { state: { vocabularyId: node.id.replace(/^vocabulary:/, "") } });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--color-primary-dark)]">
          知識地圖
        </h1>
        <p className="mt-1 text-sm text-stone-600">
          全局檢視跨 JLPT 的語意關聯；節點顏色標示級別，點節點可跳到詳情複習
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={jlpt}
          onChange={(e) => setJlpt(e.target.value)}
          className="rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        >
          <option value="">全部 JLPT</option>
          {JLPT_OPTIONS.filter(Boolean).map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>
        <select
          value={relation}
          onChange={(e) => setRelation(e.target.value as LinkRelationType | "")}
          className="rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        >
          <option value="">全部關係</option>
          {RELATION_FILTERS.filter(Boolean).map((r) => (
            <option key={r} value={r}>
              {RELATION_LABELS[r as LinkRelationType]}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100">
          <input
            type="checkbox"
            checked={includeVocab}
            onChange={(e) => setIncludeVocab(e.target.checked)}
          />
          含單字
        </label>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜尋節點…"
          className="min-w-[160px] flex-1 rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        />
        <button
          type="button"
          onClick={() => setListMode((v) => !v)}
          className="rounded-full bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700"
        >
          {listMode ? "圖譜模式" : "列表模式"}
        </button>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-full bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
        >
          重新整理
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && <p className="text-sm text-stone-400">載入中...</p>}

      {!loading && filtered && (
        <div className="rounded-2xl bg-white p-4 ring-1 ring-orange-100">
          <p className="mb-3 text-xs text-stone-500">
            {filtered.nodes.length} 個節點 · {filtered.edges.length} 條關聯
          </p>
          {filtered.nodes.length === 0 ? (
            <p className="py-12 text-center text-sm text-stone-400">
              尚無圖譜資料。請先執行 migration 007 與 seed_content_links.py。
            </p>
          ) : listMode ? (
            <RelationLinkList graph={filtered} onSelectNode={handleSelect} />
          ) : (
            <RelationGraphPanel
              graph={filtered}
              height={520}
              pinCenter={false}
              onSelectNode={handleSelect}
            />
          )}
        </div>
      )}
    </div>
  );
}
