import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface WorkspaceFile {
  path: string;
  kind: string;
}

export function useWorkspaceFiles(enabled: boolean, projectId = "default") {
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const params = new URLSearchParams({ project_id: projectId || "default" });
      const res = await fetch(`/v1/theory/workspace?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setFiles(data.files ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { files, loading, error, refresh };
}
