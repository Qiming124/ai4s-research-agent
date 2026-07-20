import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface VerificationRecord {
  id: number;
  tier: string;
  claim_id: string;
  executor: string;
  passed: boolean;
  created_at: string;
}

export function useVerificationRecords(
  projectId: string,
  sessionId: string | null,
  enabled: boolean,
) {
  const [records, setRecords] = useState<VerificationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        project_id: projectId || "default",
        limit: "50",
      });
      const res = await fetch(`/v1/verification/records?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRecords(data.records ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runVerification = async (payload: Record<string, unknown>) => {
    const body = {
      ...payload,
      project_id: (payload.project_id as string) || projectId || "default",
      session_id: (payload.session_id as string) || sessionId || undefined,
    };
    const res = await fetch("/v1/verification/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
    return res.json();
  };

  return { records, loading, error, refresh, runVerification };
}
