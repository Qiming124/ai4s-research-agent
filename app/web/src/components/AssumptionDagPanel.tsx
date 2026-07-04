import { useState } from "react";
import type { DagEdge, DagNode } from "../hooks/useAssumptionDag";

interface AssumptionDagPanelProps {
  nodes: DagNode[];
  edges: DagEdge[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onImpact: (id: string) => Promise<unknown>;
}

export function AssumptionDagPanel({
  nodes,
  edges,
  loading,
  error,
  onRefresh,
  onImpact,
}: AssumptionDagPanelProps) {
  const [impact, setImpact] = useState<string | null>(null);

  const handleImpact = async (id: string) => {
    try {
      const data = await onImpact(id);
      setImpact(JSON.stringify(data, null, 2));
    } catch (err) {
      setImpact(err instanceof Error ? err.message : "查询失败");
    }
  };

  return (
    <div className="assumption-dag-panel">
      <div className="panel-header">
        <h4>假设依赖图</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      <ul className="dag-node-list">
        {nodes.map((n) => (
          <li key={n.id} className="dag-node-item">
            <button type="button" className="btn-link" onClick={() => void handleImpact(n.id)}>
              {n.id}
            </button>
            <span>{n.label}</span>
            {n.status && <span className="role-tag">{n.status}</span>}
          </li>
        ))}
      </ul>
      {edges.length > 0 && (
        <p className="panel-muted">{edges.length} 条依赖边</p>
      )}
      {impact && <pre className="workspace-content">{impact}</pre>}
    </div>
  );
}
