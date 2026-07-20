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
  const selected = selectedId != null ? nodeMap.get(selectedId) : null;

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
      <p className="panel-muted">
        {nodes.length} 节点 · {edges.length} 边
        {edges.length === 0 && nodes.length > 0
          ? "（暂无 depends_on / supports 等显式边；正文含「依据：引理/定理」时刷新可自动建边）"
          : ""}
      </p>
      {!loading && nodes.length === 0 && (
        <p className="panel-muted">当前会话暂无结构化记忆节点。</p>
      )}
      <div className="graph-viz-area">
        <ul className="graph-node-list">
          {nodes.slice(0, 40).map((n) => (
            <li
              key={n.id}
              className={selectedId === n.id ? "graph-node selected" : "graph-node"}
              onClick={() => {
                setSelectedId(n.id ?? null);
                onSelectNode?.(n);
              }}
            >
              <span className="role-tag">{n.kind}</span> {n.title || `#${n.id}`}
            </li>
          ))}
        </ul>
        {edges.length > 0 && (
          <ul className="graph-edge-list">
            {edges.map((e) => (
              <li key={e.id ?? `${e.from_id}-${e.to_id}-${e.relation}`}>
                {nodeMap.get(e.from_id)?.title ?? `#${e.from_id}`}
                {" → "}
                <em>{e.relation}</em>
                {" → "}
                {nodeMap.get(e.to_id)?.title ?? `#${e.to_id}`}
              </li>
            ))}
          </ul>
        )}
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
