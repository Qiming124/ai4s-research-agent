import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

/** 与后端 build_assumption_dag 对齐 */
export interface DagNode {
  id: string | number;
  kind: string;
  title: string;
  status?: string;
  assumptions?: string[];
}

export interface DagEdge {
  from_id: string | number;
  to_id: string | number;
  relation: string;
}

export function useAssumptionDag(sessionId: string | null, enabled: boolean) {
  const [nodes, setNodes] = useState<DagNode[]>([]);
  const [edges, setEdges] = useState<DagEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (sessionId) params.set("session_id", sessionId);
      const qs = params.toString();
      const res = await fetch(`/v1/theory/assumption-dag${qs ? `?${qs}` : ""}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const rawNodes = (data.nodes ?? []) as Record<string, unknown>[];
      const rawEdges = (data.edges ?? []) as Record<string, unknown>[];
      setNodes(
        rawNodes.map((n) => ({
          id: n.id as string | number,
          kind: String(n.kind ?? "note"),
          title: String(n.title ?? n.label ?? n.id ?? ""),
          status: n.status != null ? String(n.status) : undefined,
          assumptions: Array.isArray(n.assumptions)
            ? (n.assumptions as string[])
            : undefined,
        })),
      );
      setEdges(
        rawEdges.map((e) => ({
          from_id: (e.from_id ?? e.source) as string | number,
          to_id: (e.to_id ?? e.target) as string | number,
          relation: String(e.relation ?? "depends_on"),
        })),
      );
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const fetchImpact = async (assumptionId: string) => {
    const params = new URLSearchParams();
    if (sessionId) params.set("session_id", sessionId);
    const qs = params.toString();
    const res = await fetch(
      `/v1/theory/assumption-dag/impact/${encodeURIComponent(assumptionId)}${qs ? `?${qs}` : ""}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  };

  return { nodes, edges, loading, error, refresh, fetchImpact };
}
