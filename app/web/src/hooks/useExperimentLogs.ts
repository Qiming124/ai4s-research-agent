import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface ExperimentRun {
  run_id: string;
  name: string;
  config_path: string;
  status: string;
  log_path: string;
  created_at: string | null;
  summary: Record<string, unknown>;
  metrics?: Record<string, unknown>;
}

export function useExperimentLogs(enabled: boolean) {
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const res = await fetch("/v1/experiments/runs");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRuns(data.runs ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { runs, loading, error, refresh };
}
