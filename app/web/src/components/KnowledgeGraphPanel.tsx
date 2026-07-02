import type { MemoryEdge } from "../hooks/useMemoryGraph";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";

interface KnowledgeGraphPanelProps {
  nodes: StructuredMemoryEntry[];
  edges: MemoryEdge[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function KnowledgeGraphPanel({
  nodes,
  edges,
  loading,
  error,
  onRefresh,
}: KnowledgeGraphPanelProps) {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  return (
    <div className="knowledge-graph-panel">
      <div className="panel-header">
        <h4>知识图谱</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      <p className="panel-muted">{nodes.length} 节点 · {edges.length} 边</p>
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
  );
}
