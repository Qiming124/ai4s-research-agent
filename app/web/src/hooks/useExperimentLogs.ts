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
  project_id?: string;
  session_id?: string | null;
}

export interface ExperimentRunUpdate {
  name?: string;
  summary?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  status?: string;
}

export function useExperimentLogs(enabled: boolean, projectId = "default") {
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pid = projectId || "default";

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const params = new URLSearchParams({ project_id: pid });
      const res = await fetch(`/v1/experiments/runs?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRuns(data.runs ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, pid]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const updateRun = useCallback(
    async (runId: string, patch: ExperimentRunUpdate) => {
      const params = new URLSearchParams({ project_id: pid });
      const res = await fetch(`/v1/experiments/runs/${encodeURIComponent(runId)}?${params}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) throw new Error(await res.text());
      await refresh();
    },
    [pid, refresh],
  );

  const deleteRun = useCallback(
    async (runId: string) => {
      const params = new URLSearchParams({ project_id: pid });
      const res = await fetch(`/v1/experiments/runs/${encodeURIComponent(runId)}?${params}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await res.text());
      await refresh();
    },
    [pid, refresh],
  );

  return { runs, loading, error, refresh, updateRun, deleteRun };
}
