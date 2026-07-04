import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface DagNode {
  id: string;
  label: string;
  status?: string;
}

export interface DagEdge {
  source: string;
  target: string;
}

export function useAssumptionDag(enabled: boolean) {
  const [nodes, setNodes] = useState<DagNode[]>([]);
  const [edges, setEdges] = useState<DagEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/v1/theory/assumption-dag");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setNodes(data.nodes ?? []);
      setEdges(data.edges ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const fetchImpact = async (assumptionId: string) => {
    const res = await fetch(`/v1/theory/assumption-dag/impact/${encodeURIComponent(assumptionId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  };

  return { nodes, edges, loading, error, refresh, fetchImpact };
}
