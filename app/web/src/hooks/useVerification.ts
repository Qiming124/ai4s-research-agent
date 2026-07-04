import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface VerificationRecord {
  id: number;
  tier: string;
  passed: boolean;
  executor: string;
  agent_name: string;
  result: Record<string, unknown>;
  created_at: string | null;
  claim_id: string;
}

export interface VerificationDashboard {
  project_id: string;
  total_records: number;
  passed: number;
  failed: number;
  by_tier: Record<string, number>;
  recent: VerificationRecord[];
}

export function useVerification(sessionId: string, projectId: string, enabled: boolean) {
  const [dashboard, setDashboard] = useState<VerificationDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const params = new URLSearchParams({ project_id: projectId });
      if (sessionId) params.set("session_id", sessionId);
      const res = await fetch(`/v1/verification/dashboard?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDashboard(data);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId, sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { dashboard, loading, error, refresh };
}
