import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, GraphNode, RelationGraph } from "../lib/api";
import { vocabDisplay } from "../lib/vocabDisplay";
import { RELATION_COLORS, RELATION_LABELS } from "./RelationLinkList";

type Props = {
  vocabularyId: string;
};

/** Parse backend graph label `word` or `word（reading）` into display parts. */
function formatVocabNodeLabel(label: string, jlpt?: string): string {
  const m = label.match(/^(.+?)（(.+)）$/);
  const word = m ? m[1] : label;
  const reading = m ? m[2] : undefined;
  const { primary } = vocabDisplay(word, reading);
  return jlpt ? `${primary} · ${jlpt}` : primary;
}

export default function VocabRelationHints({ vocabularyId }: Props) {
  const navigate = useNavigate();
  const [graph, setGraph] = useState<RelationGraph | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = () => {
    api
      .getVocabRelations(vocabularyId, 1)
      .then((data) => setGraph(data))
      .catch(() => setGraph(null));
  };

  useEffect(() => {
    let cancelled = false;
    api
      .getVocabRelations(vocabularyId, 1)
      .then((data) => {
        if (!cancelled) setGraph(data);
      })
      .catch(() => {
        if (!cancelled) setGraph(null);
      });
    return () => {
      cancelled = true;
    };
  }, [vocabularyId]);

  const relatedGrammars: Array<{ node: GraphNode; label: string; color: string }> = [];
  const relatedVocab: Array<{ node: GraphNode; label: string; color: string }> = [];

  if (graph) {
    const center = graph.center_id;
    const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));
    for (const edge of graph.edges) {
      const otherId = edge.source === center ? edge.target : edge.source;
      const node = nodeMap.get(otherId);
      if (!node) continue;
      const item = {
        node,
        label: edge.label_zh || RELATION_LABELS[edge.relation_type],
        color: RELATION_COLORS[edge.relation_type],
      };
      if (node.type === "grammar") relatedGrammars.push(item);
      if (node.type === "vocabulary") relatedVocab.push(item);
    }
  }

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncVocabSemanticLinks(vocabularyId);
      load();
    } finally {
      setSyncing(false);
    }
  };

  const goVocab = (node: GraphNode) => {
    navigate("/vocab", {
      state: { vocabularyId: node.id.replace(/^vocabulary:/, "") },
    });
  };

  if (!graph) return null;
  if (relatedGrammars.length === 0 && relatedVocab.length === 0) {
    return (
      <div className="mt-4 w-full max-w-md rounded-xl bg-sky-50/80 px-4 py-3 text-left ring-1 ring-sky-100">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-sky-900">尚無語意近義單字／文法連結</p>
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing}
            className="rounded-full bg-sky-600 px-3 py-1 text-[11px] font-semibold text-white disabled:opacity-50"
          >
            {syncing ? "計算中..." : "計算語意關聯"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4 w-full max-w-md space-y-3 rounded-xl bg-sky-50/80 px-4 py-3 text-left ring-1 ring-sky-100">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-sky-900">語意關聯（跨 JLPT）</p>
        <button
          type="button"
          onClick={handleSync}
          disabled={syncing}
          className="rounded-full bg-sky-600 px-3 py-1 text-[11px] font-semibold text-white disabled:opacity-50"
        >
          {syncing ? "計算中..." : "重新計算"}
        </button>
      </div>
      {relatedVocab.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] text-sky-800">近義單字</p>
          <ul className="flex flex-wrap gap-2">
            {relatedVocab.slice(0, 8).map(({ node, color }) => (
              <li key={node.id}>
                <button
                  type="button"
                  onClick={() => goVocab(node)}
                  title="前往該單字"
                  className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-medium text-sky-900 underline-offset-2 ring-1 ring-sky-100 transition hover:bg-sky-100 hover:underline"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {formatVocabNodeLabel(node.label, node.jlpt_level)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {relatedGrammars.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] text-sky-800">相關文法</p>
          <ul className="flex flex-wrap gap-2">
            {relatedGrammars.slice(0, 8).map(({ node, color }) => (
              <li key={node.id}>
                <button
                  type="button"
                  onClick={() =>
                    navigate("/grammar", {
                      state: { grammarId: node.id.replace(/^grammar:/, "") },
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-medium text-stone-700 ring-1 ring-sky-100 transition hover:bg-sky-100"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {node.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
