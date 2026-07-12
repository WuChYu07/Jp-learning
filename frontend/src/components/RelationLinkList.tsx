import {
  GraphEdge,
  GraphNode,
  LinkRelationType,
  RelationGraph,
} from "../lib/api";

export const RELATION_LABELS: Record<LinkRelationType, string> = {
  same_meaning: "同義",
  contrast: "對比",
  confusable: "易混淆",
  prerequisite: "先修",
  derived: "延伸",
  example_vocab: "例句單字",
};

export const RELATION_COLORS: Record<LinkRelationType, string> = {
  same_meaning: "#ea580c",
  contrast: "#0284c7",
  confusable: "#d97706",
  prerequisite: "#7c3aed",
  derived: "#059669",
  example_vocab: "#78716c",
};

type Props = {
  graph: RelationGraph;
  onSelectNode: (node: GraphNode) => void;
  onDeleteEdge?: (edge: GraphEdge) => void;
};

export default function RelationLinkList({ graph, onSelectNode, onDeleteEdge }: Props) {
  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));
  const neighbors = graph.edges
    .map((edge) => {
      const neighborId =
        edge.source === graph.center_id
          ? edge.target
          : edge.target === graph.center_id
            ? edge.source
            : edge.source;
      const neighbor = nodeMap.get(neighborId);
      if (!neighbor || neighbor.id === graph.center_id) return null;
      return { edge, neighbor };
    })
    .filter((row): row is { edge: GraphEdge; neighbor: GraphNode } => Boolean(row));

  // Deduplicate by neighbor id (keep first edge)
  const seen = new Set<string>();
  const unique = neighbors.filter(({ neighbor }) => {
    if (seen.has(neighbor.id)) return false;
    seen.add(neighbor.id);
    return true;
  });

  if (unique.length === 0) {
    return (
      <p className="text-sm text-stone-400">
        尚無關聯。可執行 AI 建議或手動新增。
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {unique.map(({ edge, neighbor }) => (
        <li
          key={`${edge.id}-${neighbor.id}`}
          className="flex items-start justify-between gap-3 rounded-xl bg-stone-50 px-3 py-2 ring-1 ring-stone-100"
        >
          <button
            type="button"
            onClick={() => onSelectNode(neighbor)}
            className="min-w-0 flex-1 text-left"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold text-white"
                style={{ backgroundColor: RELATION_COLORS[edge.relation_type] }}
              >
                {edge.label_zh || RELATION_LABELS[edge.relation_type]}
              </span>
              <span className="truncate text-sm font-semibold text-stone-800">
                {neighbor.label}
              </span>
              {neighbor.jlpt_level && (
                <span className="text-xs text-stone-400">{neighbor.jlpt_level}</span>
              )}
            </div>
            {edge.note_zh && (
              <p className="mt-1 text-xs leading-relaxed text-stone-500">{edge.note_zh}</p>
            )}
          </button>
          {onDeleteEdge && (
            <button
              type="button"
              onClick={() => onDeleteEdge(edge)}
              className="shrink-0 text-xs text-stone-400 hover:text-red-600"
              title="刪除關聯"
            >
              刪除
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
