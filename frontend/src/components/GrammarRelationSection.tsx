import { useCallback, useEffect, useState } from "react";
import {
  api,
  GraphEdge,
  GraphNode,
  Grammar,
  GrammarSummary,
  LinkRelationType,
  RelationGraph,
} from "../lib/api";
import RelationGraphPanel from "./RelationGraphPanel";
import RelationLinkList, { RELATION_LABELS } from "./RelationLinkList";

type Props = {
  grammar: Grammar;
  grammarList: GrammarSummary[];
  onNavigateGrammar: (grammarId: string) => void;
};

const RELATION_OPTIONS: LinkRelationType[] = [
  "same_meaning",
  "contrast",
  "confusable",
  "prerequisite",
  "derived",
];

export default function GrammarRelationSection({
  grammar,
  grammarList,
  onNavigateGrammar,
}: Props) {
  const [graph, setGraph] = useState<RelationGraph | null>(null);
  const [depth, setDepth] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [showList, setShowList] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualTargetId, setManualTargetId] = useState("");
  const [manualRelation, setManualRelation] = useState<LinkRelationType>("contrast");
  const [manualLabel, setManualLabel] = useState("");
  const [manualNote, setManualNote] = useState("");
  const [savingManual, setSavingManual] = useState(false);
  const [syncingVocab, setSyncingVocab] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getGrammarRelations(grammar.id, depth);
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入關聯失敗");
      setGraph(null);
    } finally {
      setLoading(false);
    }
  }, [grammar.id, depth]);

  useEffect(() => {
    setManualOpen(false);
    setInfo("");
    void load();
  }, [load]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const apply = () => setShowList(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  const handleSelectNode = (node: GraphNode) => {
    if (node.type === "grammar") {
      const id = node.id.replace(/^grammar:/, "");
      onNavigateGrammar(id);
    }
  };

  const handleDeleteEdge = async (edge: GraphEdge) => {
    if (!confirm("確定刪除此關聯？")) return;
    try {
      await api.deleteLink(edge.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除失敗");
    }
  };

  const handleSemanticSync = async () => {
    setSyncing(true);
    setError("");
    setInfo("");
    try {
      const res = await api.syncGrammarSemanticLinks(grammar.id);
      await load();
      setInfo(
        `語意同步完成：新增 ${res.links_created ?? 0}、更新 ${res.links_updated ?? 0}、移除 ${res.links_removed ?? 0}` +
          (res.skipped_embed ? "（內容未變，略過重新向量化）" : ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "語意同步失敗");
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncExampleVocab = async () => {
    setSyncingVocab(true);
    setError("");
    try {
      const res = await api.syncExampleVocab(grammar.id);
      await load();
      if (res.created === 0 && res.matched_words.length === 0) {
        setError("例句中未匹配到資料庫單字");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步例句單字失敗");
    } finally {
      setSyncingVocab(false);
    }
  };

  const handleManualCreate = async () => {
    if (!manualTargetId) return;
    setSavingManual(true);
    setError("");
    try {
      await api.createLink({
        source_type: "grammar",
        source_id: grammar.id,
        target_type: "grammar",
        target_id: manualTargetId,
        relation_type: manualRelation,
        label_zh: manualLabel || RELATION_LABELS[manualRelation],
        note_zh: manualNote || undefined,
        origin: "manual",
      });
      setManualOpen(false);
      setManualTargetId("");
      setManualLabel("");
      setManualNote("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "新增失敗");
    } finally {
      setSavingManual(false);
    }
  };

  const otherGrammars = grammarList.filter((g) => g.id !== grammar.id);

  return (
    <section className="rounded-2xl bg-white p-5 ring-1 ring-orange-100">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-stone-800">關聯網絡</h3>
          <p className="text-xs text-stone-500">
            跨 JLPT 近義會自動相連；節點顏色僅標示級別，點擊可跳轉
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="rounded-full border-0 bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-700"
          >
            <option value={1}>深度 1</option>
            <option value={2}>深度 2</option>
          </select>
          <button
            type="button"
            onClick={() => setShowList((v) => !v)}
            className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-semibold text-stone-700"
          >
            {showList ? "顯示圖譜" : "顯示列表"}
          </button>
          <button
            type="button"
            onClick={() => setManualOpen((v) => !v)}
            className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-semibold text-stone-700"
          >
            手動新增
          </button>
          <button
            type="button"
            onClick={handleSemanticSync}
            disabled={syncing}
            className="rounded-full bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            {syncing ? "計算中..." : "重新計算語意關聯"}
          </button>
          <button
            type="button"
            onClick={handleSyncExampleVocab}
            disabled={syncingVocab}
            className="rounded-full bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            {syncingVocab ? "同步中..." : "連結例句單字"}
          </button>
        </div>
      </div>

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      {info && <p className="mb-2 text-sm text-emerald-700">{info}</p>}
      {loading && <p className="text-sm text-stone-400">載入關聯中...</p>}

      {!loading && graph && (
        <>
          {showList ? (
            <RelationLinkList
              graph={graph}
              onSelectNode={handleSelectNode}
              onDeleteEdge={handleDeleteEdge}
            />
          ) : graph.edges.length === 0 && graph.nodes.length <= 1 ? (
            <p className="rounded-xl bg-stone-50 px-4 py-6 text-center text-sm text-stone-400">
              尚無關聯。新增／編輯後會依語意自動連邊，也可按「重新計算語意關聯」。
            </p>
          ) : (
            <RelationGraphPanel graph={graph} onSelectNode={handleSelectNode} />
          )}
        </>
      )}

      {manualOpen && (
        <div className="mt-4 space-y-3 rounded-xl bg-stone-50 p-4 ring-1 ring-stone-200">
          <p className="text-xs font-semibold text-stone-700">手動新增關聯</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <select
              value={manualTargetId}
              onChange={(e) => setManualTargetId(e.target.value)}
              className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
            >
              <option value="">選擇目標文法</option>
              {otherGrammars.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.grammar_point}（{g.jlpt_level}）
                </option>
              ))}
            </select>
            <select
              value={manualRelation}
              onChange={(e) => setManualRelation(e.target.value as LinkRelationType)}
              className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
            >
              {RELATION_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {RELATION_LABELS[r]}
                </option>
              ))}
            </select>
            <input
              value={manualLabel}
              onChange={(e) => setManualLabel(e.target.value)}
              placeholder="邊標籤（可選）"
              className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
            />
            <input
              value={manualNote}
              onChange={(e) => setManualNote(e.target.value)}
              placeholder="差異說明（可選）"
              className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
            />
          </div>
          <button
            type="button"
            onClick={handleManualCreate}
            disabled={!manualTargetId || savingManual}
            className="rounded-full bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {savingManual ? "儲存中..." : "建立關聯"}
          </button>
        </div>
      )}
    </section>
  );
}
