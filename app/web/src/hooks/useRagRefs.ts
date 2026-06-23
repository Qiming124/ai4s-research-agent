import { useCallback, useEffect, useState } from "react";

export interface RagRef {
  doc_id: string;
  snippet: string;
  created_at?: string | null;
}

export function useRagRefs(sessionId: string, enabled: boolean) {
  const [refs, setRefs] = useState<RagRef[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/v1/sessions/${sessionId}/rag-refs`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      setRefs(Array.isArray(data.refs) ? data.refs : []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sessionId, enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { refs, loading, error, refresh };
}
