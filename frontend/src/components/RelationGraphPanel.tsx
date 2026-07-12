import { useEffect, useMemo, useRef, useState } from "react";
import {
  GraphEdge,
  GraphNode,
  LinkRelationType,
  RelationGraph,
} from "../lib/api";
import { RELATION_COLORS, RELATION_LABELS } from "./RelationLinkList";

type SimNode = GraphNode & {
  x: number;
  y: number;
  vx: number;
  vy: number;
};

type Props = {
  graph: RelationGraph;
  height?: number;
  pinCenter?: boolean;
  onSelectNode: (node: GraphNode) => void;
};

const JLPT_COLORS: Record<string, string> = {
  N5: "#16a34a",
  N4: "#ea580c",
  N3: "#0284c7",
  N2: "#7c3aed",
  N1: "#dc2626",
};

function nodeColor(node: GraphNode, isCenter: boolean): string {
  if (isCenter) return "#c2410c";
  if (node.type === "concept") return "#7c3aed";
  const group = (node.group || node.jlpt_level || "").toUpperCase();
  for (const level of ["N5", "N4", "N3", "N2", "N1"]) {
    if (group.includes(level)) return JLPT_COLORS[level];
  }
  if (node.type === "vocabulary") return "#0369a1";
  return "#44403c";
}

export default function RelationGraphPanel({
  graph,
  height = 280,
  pinCenter = true,
  onSelectNode,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoverEdge, setHoverEdge] = useState<GraphEdge | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [size, setSize] = useState({ w: 640, h: height });
  const nodesRef = useRef<SimNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const rafRef = useRef<number>(0);

  const nodeIds = useMemo(
    () => graph.nodes.map((n) => n.id).join("|"),
    [graph.nodes],
  );
  const edgeIds = useMemo(
    () => graph.edges.map((e) => e.id).join("|"),
    [graph.edges],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas?.parentElement) return;
    const parent = canvas.parentElement;
    const update = () => {
      const w = parent.clientWidth || 640;
      setSize({ w, h: height });
      canvas.width = w * devicePixelRatio;
      canvas.height = height * devicePixelRatio;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${height}px`;
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [height]);

  useEffect(() => {
    const w = size.w;
    const h = size.h;
    const cx = w / 2;
    const cy = h / 2;
    const center = graph.nodes.find((n) => n.id === graph.center_id);
    const others = graph.nodes.filter((n) => n.id !== graph.center_id);

    const sims: SimNode[] = [];
    if (center) {
      sims.push({ ...center, x: cx, y: cy, vx: 0, vy: 0 });
    }
    others.forEach((n, i) => {
      const angle = (i / Math.max(others.length, 1)) * Math.PI * 2 - Math.PI / 2;
      const r = Math.min(w, h) * 0.32;
      sims.push({
        ...n,
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        vx: 0,
        vy: 0,
      });
    });
    nodesRef.current = sims;
    edgesRef.current = graph.edges;
  }, [nodeIds, edgeIds, graph.center_id, graph.nodes, graph.edges, size.w, size.h]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const tick = () => {
      const nodes = nodesRef.current;
      const edges = edgesRef.current;
      const w = size.w;
      const h = size.h;
      const dpr = devicePixelRatio || 1;

      // Simple force simulation
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let dist = Math.hypot(dx, dy) || 1;
          const force = 800 / (dist * dist);
          dx = (dx / dist) * force;
          dy = (dy / dist) * force;
          if (a.id !== graph.center_id || !pinCenter) {
            a.vx -= dx;
            a.vy -= dy;
          }
          if (b.id !== graph.center_id || !pinCenter) {
            b.vx += dx;
            b.vy += dy;
          }
        }
      }

      const byId = new Map(nodes.map((n) => [n.id, n]));
      for (const edge of edges) {
        const a = byId.get(edge.source);
        const b = byId.get(edge.target);
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 1;
        const desired = 110;
        const force = (dist - desired) * 0.02;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (a.id !== graph.center_id || !pinCenter) {
          a.vx += fx;
          a.vy += fy;
        }
        if (b.id !== graph.center_id || !pinCenter) {
          b.vx -= fx;
          b.vy -= fy;
        }
      }

      // Center gravity + damping
      for (const n of nodes) {
        if (pinCenter && n.id === graph.center_id) {
          n.x = w / 2;
          n.y = h / 2;
          n.vx = 0;
          n.vy = 0;
          continue;
        }
        n.vx += (w / 2 - n.x) * 0.004;
        n.vy += (h / 2 - n.y) * 0.004;
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(36, Math.min(w - 36, n.x));
        n.y = Math.max(24, Math.min(h - 24, n.y));
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // Edges
      for (const edge of edges) {
        const a = byId.get(edge.source);
        const b = byId.get(edge.target);
        if (!a || !b) continue;
        const color = RELATION_COLORS[edge.relation_type as LinkRelationType] || "#a8a29e";
        const lowConf = (edge.confidence ?? 1) < 0.7;
        const conf = Math.max(0.35, Math.min(1, edge.confidence ?? 1));
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = color;
        ctx.globalAlpha = hoverEdge?.id === edge.id ? 1 : 0.35 + conf * 0.45;
        ctx.lineWidth = hoverEdge?.id === edge.id ? 2.8 : 1 + conf * 1.8;
        if (lowConf) ctx.setLineDash([5, 4]);
        else ctx.setLineDash([]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;

        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;
        const label = edge.label_zh || RELATION_LABELS[edge.relation_type];
        if (label) {
          ctx.font = "10px sans-serif";
          ctx.fillStyle = "#78716c";
          ctx.textAlign = "center";
          ctx.fillText(label, mx, my - 4);
        }
      }

      // Nodes
      for (const n of nodes) {
        const isCenter = n.id === graph.center_id;
        const r = isCenter ? 18 : n.type === "concept" ? 14 : 12;
        const color = nodeColor(n, isCenter && pinCenter);

        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = hoverNode?.id === n.id || isCenter ? 1 : 0.9;
        ctx.fill();
        ctx.globalAlpha = 1;
        if (isCenter) {
          ctx.strokeStyle = "#fff7ed";
          ctx.lineWidth = 3;
          ctx.stroke();
        }

        ctx.font = isCenter ? "bold 12px sans-serif" : "11px sans-serif";
        ctx.fillStyle = "#1c1917";
        ctx.textAlign = "center";
        const label =
          n.label.length > 14 ? `${n.label.slice(0, 13)}…` : n.label;
        ctx.fillText(label, n.x, n.y + r + 14);
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [size.w, size.h, graph.center_id, hoverEdge, hoverNode, pinCenter]);

  const pick = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return { node: null as GraphNode | null, edge: null as GraphEdge | null };
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    const nodes = nodesRef.current;
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      const r = n.id === graph.center_id ? 20 : 14;
      if (Math.hypot(n.x - x, n.y - y) <= r + 4) {
        return { node: n, edge: null };
      }
    }
    // Edge hover near midpoint
    const byId = new Map(nodes.map((n) => [n.id, n]));
    for (const edge of edgesRef.current) {
      const a = byId.get(edge.source);
      const b = byId.get(edge.target);
      if (!a || !b) continue;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      if (Math.hypot(mx - x, my - y) < 16) {
        return { node: null, edge };
      }
    }
    return { node: null, edge: null };
  };

  return (
    <div className="relative overflow-hidden rounded-xl bg-gradient-to-b from-orange-50/80 to-stone-50 ring-1 ring-orange-100">
      <canvas
        ref={canvasRef}
        className="block w-full cursor-pointer"
        onMouseMove={(e) => {
          const { node, edge } = pick(e.clientX, e.clientY);
          setHoverNode(node);
          setHoverEdge(edge);
        }}
        onMouseLeave={() => {
          setHoverNode(null);
          setHoverEdge(null);
        }}
        onClick={(e) => {
          const { node } = pick(e.clientX, e.clientY);
          if (node && node.id !== graph.center_id) onSelectNode(node);
        }}
      />
      {(hoverEdge?.note_zh || hoverNode) && (
        <div className="pointer-events-none absolute bottom-2 left-2 right-2 rounded-lg bg-white/95 px-3 py-2 text-xs text-stone-600 shadow-sm ring-1 ring-stone-200">
          {hoverNode && hoverNode.id !== graph.center_id && (
            <p>
              點擊前往：<span className="font-semibold">{hoverNode.label}</span>
            </p>
          )}
          {hoverEdge?.note_zh && <p className="mt-0.5">{hoverEdge.note_zh}</p>}
        </div>
      )}
    </div>
  );
}
