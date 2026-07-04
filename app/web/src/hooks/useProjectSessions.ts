import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface ProjectSession {
  session_id: string;
  project_id: string;
}

export function useProjectSessions(projectId: string, enabled: boolean) {
  const [sessions, setSessions] = useState<ProjectSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !projectId) {
      setSessions([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/v1/projects/${encodeURIComponent(projectId)}/sessions`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch (err) {
      setError(formatBackendError(err));
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const linkSession = useCallback(
    async (sessionId: string): Promise<boolean> => {
      if (!projectId || !sessionId) return false;
      try {
        const res = await fetch(
          `/v1/projects/${encodeURIComponent(projectId)}/sessions/${encodeURIComponent(sessionId)}`,
          { method: "POST" },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await refresh();
        return true;
      } catch {
        return false;
      }
    },
    [projectId, refresh],
  );

  return { sessions, loading, error, refresh, linkSession };
}
