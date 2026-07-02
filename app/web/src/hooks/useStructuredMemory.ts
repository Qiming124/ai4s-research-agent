import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface StructuredMemoryEntry {
  id: number;
  session_id: string | null;
  kind: string;
  title: string;
  body: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export function useStructuredMemory(sessionId: string, enabled: boolean) {
  const [entries, setEntries] = useState<StructuredMemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const params = new URLSearchParams({ session_id: sessionId, limit: "50" });
      const res = await fetch(`/v1/memory/structured?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEntries(data.entries ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId, enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { entries, loading, error, refresh };
}
