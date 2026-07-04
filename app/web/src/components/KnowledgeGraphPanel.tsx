import { useState } from "react";
import type { MemoryEdge } from "../hooks/useMemoryGraph";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import { MarkdownContent } from "./MarkdownContent";

interface KnowledgeGraphPanelProps {
  nodes: StructuredMemoryEntry[];
  edges: MemoryEdge[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelectNode?: (node: StructuredMemoryEntry) => void;
}

export function KnowledgeGraphPanel({
  nodes,
  edges,
  loading,
  error,
  onRefresh,
  onSelectNode,
}: KnowledgeGraphPanelProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const selected = selectedId ? nodeMap.get(selectedId) : null;

  return (
    <div className="knowledge-graph-panel">
      <div className="panel-header">
        <h4>关系网络</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      <p className="panel-muted">{nodes.length} 节点 · {edges.length} 边</p>
      <div className="graph-viz-area">
        <ul className="graph-node-list">
          {nodes.slice(0, 30).map((n) => (
            <li
              key={n.id}
              className={selectedId === n.id ? "graph-node selected" : "graph-node"}
              onClick={() => {
                setSelectedId(n.id ?? null);
                onSelectNode?.(n);
              }}
            >
              {n.title || `#${n.id}`}
            </li>
          ))}
        </ul>
        <ul className="graph-edge-list">
          {edges.map((e) => (
            <li key={e.id}>
              {nodeMap.get(e.from_id)?.title ?? `#${e.from_id}`}
              {" → "}
              <em>{e.relation}</em>
              {" → "}
              {nodeMap.get(e.to_id)?.title ?? `#${e.to_id}`}
            </li>
          ))}
        </ul>
      </div>
      {selected && (
        <div className="graph-node-detail">
          <strong>{selected.title}</strong>
          <MarkdownContent content={selected.body} className="panel-markdown" />
        </div>
      )}
    </div>
  );
}
