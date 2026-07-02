import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";
import type { StructuredMemoryEntry } from "./useStructuredMemory";

export interface MemoryEdge {
  id: number;
  from_id: number;
  to_id: number;
  relation: string;
}

export function useMemoryGraph(sessionId: string, enabled: boolean) {
  const [nodes, setNodes] = useState<StructuredMemoryEntry[]>([]);
  const [edges, setEdges] = useState<MemoryEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const params = new URLSearchParams({ session_id: sessionId });
      const res = await fetch(`/v1/memory/structured/graph?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setNodes(data.nodes ?? []);
      setEdges(data.edges ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId, enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { nodes, edges, loading, error, refresh };
}
