import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import RelationGraphPanel from "../components/RelationGraphPanel";
import { RELATION_COLORS, RELATION_LABELS } from "../components/RelationLinkList";
import {
  api,
  GraphEdge,
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
];

const CONFIDENCE_PRESETS = [
  { value: 0, label: "全部信心" },
  { value: 0.85, label: "≥ 0.85（含可能相關）" },
  { value: 0.9, label: "≥ 0.90" },
  { value: 0.93, label: "≥ 0.93（建議）" },
  { value: 0.95, label: "≥ 0.95" },
] as const;

export default function KnowledgeMapPage() {
  const navigate = useNavigate();
  const [graph, setGraph] = useState<RelationGraph | null>(null);
  const [jlpt, setJlpt] = useState("");
  const [relation, setRelation] = useState<LinkRelationType | "">("");
  const [includeVocab, setIncludeVocab] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0.93);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
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
        min_confidence: minConfidence > 0 ? minConfidence : undefined,
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
  }, [jlpt, relation, includeVocab, minConfidence]);

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

  const handleDeleteEdge = async (edge: GraphEdge) => {
    if (!confirm("確定刪除此關聯？")) return;
    try {
      await api.deleteLink(edge.id);
      setInfo("已刪除關聯");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除失敗");
    }
  };

  const handlePrune = async () => {
    if (
      !confirm(
        `修剪信心值低於 ${minConfidence || 0.93} 的自動語意連線？\n（手動／AI 建立的關聯不會動）`,
      )
    ) {
      return;
    }
    setBusy("prune");
    setError("");
    setInfo("");
    try {
      const res = await api.pruneWeakLinks(minConfidence || 0.93);
      setInfo(`已掃描 ${res.scanned} 條，刪除弱連線 ${res.removed} 條`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "修剪失敗");
    } finally {
      setBusy("");
    }
  };

  const handleRecompute = async () => {
    if (
      !confirm(
        "重算近期約 40 筆文法／單字的語意關聯？\n會呼叫 embedding（消耗少量 Gemini 額度），學習流程不受影響。",
      )
    ) {
      return;
    }
    setBusy("recompute");
    setError("");
    setInfo("");
    try {
      const res = await api.recomputeSemanticLinks({
        entity_types: includeVocab ? "grammar,vocabulary" : "grammar",
        limit: 40,
        force: true,
      });
      setInfo(
        `重算 ${res.entities} 筆：新增 ${res.links_created}、更新 ${res.links_updated}、移除 ${res.links_removed}` +
          (res.failed ? `、失敗 ${res.failed}` : ""),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重算失敗");
    } finally {
      setBusy("");
    }
  };

  const handleRecomputeAllNew = async () => {
    if (
      !confirm(
        "重算「所有從未計算過」的文法／單字語意關聯？\n" +
          "不設數量上限，適合大量匯入後一次清完積壓。\n" +
          "會依未處理數量呼叫對應次數的 Gemini embedding，數量多時可能需要幾分鐘，且花費較多額度。",
      )
    ) {
      return;
    }
    setBusy("recompute-all");
    setError("");
    setInfo("");
    try {
      const res = await api.recomputeSemanticLinks({
        entity_types: includeVocab ? "grammar,vocabulary" : "grammar",
        force: true,
        scope: "all_new",
      });
      setInfo(
        `處理 ${res.entities} 筆從未計算過的項目：新增 ${res.links_created}、更新 ${res.links_updated}、移除 ${res.links_removed}` +
          (res.failed ? `、失敗 ${res.failed}` : ""),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重算失敗");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--color-primary-dark)]">
          知識地圖
        </h1>
        <p className="mt-1 text-sm text-stone-600">
          全局檢視語意關聯。學習頁不會自動重算；在這裡修剪弱連線或批次重算。
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
        <select
          value={minConfidence}
          onChange={(e) => setMinConfidence(Number(e.target.value))}
          className="rounded-full bg-white px-4 py-2 text-sm ring-1 ring-orange-100"
        >
          {CONFIDENCE_PRESETS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
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

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void handlePrune()}
          disabled={Boolean(busy)}
          className="rounded-full bg-amber-100 px-4 py-2 text-sm font-semibold text-amber-900 disabled:opacity-50"
        >
          {busy === "prune" ? "修剪中…" : "修剪弱連線"}
        </button>
        <button
          type="button"
          onClick={() => void handleRecompute()}
          disabled={Boolean(busy)}
          className="rounded-full bg-violet-100 px-4 py-2 text-sm font-semibold text-violet-900 disabled:opacity-50"
        >
          {busy === "recompute" ? "重算中…" : "重算語意關聯"}
        </button>
        <button
          type="button"
          onClick={() => void handleRecomputeAllNew()}
          disabled={Boolean(busy)}
          className="rounded-full bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          title="不設上限，處理所有從未計算過的項目"
        >
          {busy === "recompute-all" ? "重算中…" : "全部重算（未曾處理過的）"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {info && <p className="text-sm text-emerald-700">{info}</p>}
      {loading && <p className="text-sm text-stone-400">載入中...</p>}

      {!loading && filtered && (
        <div className="rounded-2xl bg-white p-4 ring-1 ring-orange-100">
          <p className="mb-3 text-xs text-stone-500">
            {filtered.nodes.length} 個節點 · {filtered.edges.length} 條關聯
            {minConfidence > 0 ? ` · 信心 ≥ ${minConfidence.toFixed(2)}` : ""}
          </p>
          {filtered.nodes.length === 0 ? (
            <p className="py-12 text-center text-sm text-stone-400">
              尚無圖譜資料。可按「重算語意關聯」，或到文法／單字詳情按「計算語意關聯」。
            </p>
          ) : listMode ? (
            <MapEdgeList
              graph={filtered}
              onSelectNode={handleSelect}
              onDeleteEdge={handleDeleteEdge}
            />
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

/** Flat edge list for global map maintenance (confidence + delete). */
function MapEdgeList({
  graph,
  onSelectNode,
  onDeleteEdge,
}: {
  graph: RelationGraph;
  onSelectNode: (node: GraphNode) => void;
  onDeleteEdge: (edge: GraphEdge) => void;
}) {
  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));
  const rows = graph.edges
    .map((edge) => {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) return null;
      return { edge, source, target };
    })
    .filter(
      (row): row is { edge: GraphEdge; source: GraphNode; target: GraphNode } =>
        Boolean(row),
    )
    .sort((a, b) => (a.edge.confidence ?? 1) - (b.edge.confidence ?? 1));

  if (rows.length === 0) {
    return <p className="text-sm text-stone-400">目前沒有符合條件的關聯。</p>;
  }

  return (
    <ul className="max-h-[520px] space-y-2 overflow-y-auto">
      {rows.map(({ edge, source, target }) => (
        <li
          key={edge.id}
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2 ring-1 ring-stone-100"
        >
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold text-white"
                style={{ backgroundColor: RELATION_COLORS[edge.relation_type] }}
              >
                {edge.label_zh || RELATION_LABELS[edge.relation_type]}
              </span>
              <span className="text-[11px] text-stone-400">
                信心 {(edge.confidence ?? 1).toFixed(2)}
              </span>
            </div>
            <p className="mt-1 text-sm text-stone-700">
              <button
                type="button"
                className="font-medium text-[var(--color-primary-dark)] hover:underline"
                onClick={() => onSelectNode(source)}
              >
                {source.label}
              </button>
              <span className="mx-1 text-stone-400">↔</span>
              <button
                type="button"
                className="font-medium text-[var(--color-primary-dark)] hover:underline"
                onClick={() => onSelectNode(target)}
              >
                {target.label}
              </button>
            </p>
          </div>
          <button
            type="button"
            onClick={() => void onDeleteEdge(edge)}
            className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-red-600 ring-1 ring-red-100"
          >
            刪除
          </button>
        </li>
      ))}
    </ul>
  );
}
