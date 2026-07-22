import { useCallback, useEffect, useState } from "react";

export interface ArtifactSummary {
  id: string;
  type: string;
  project_id: string;
  session_id?: string | null;
  title: string;
  created_at: string;
}

export function useArtifacts(
  projectId: string,
  types?: string[],
  options?: { limit?: number },
) {
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const limit = options?.limit ?? 30;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        project_id: projectId || "default",
        limit: String(limit),
      });
      if (types?.length) params.set("types", types.join(","));
      const res = await fetch(`/v1/artifacts?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { artifacts: ArtifactSummary[] };
      setArtifacts(data.artifacts || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, types?.join(","), limit]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = useCallback(
    async (type: string, data: Record<string, unknown>, sessionId?: string) => {
      const res = await fetch("/v1/artifacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type,
          project_id: projectId || "default",
          session_id: sessionId || null,
          data,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const body = (await res.json()) as { data: Record<string, unknown> };
      await refresh();
      return body.data;
    },
    [projectId, refresh],
  );

  const update = useCallback(
    async (id: string, data: Record<string, unknown>) => {
      const res = await fetch(`/v1/artifacts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId || "default",
          data,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const body = (await res.json()) as { data: Record<string, unknown> };
      await refresh();
      return body.data;
    },
    [projectId, refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      const params = new URLSearchParams({ project_id: projectId || "default" });
      const res = await fetch(`/v1/artifacts/${encodeURIComponent(id)}?${params}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await res.text());
      await refresh();
    },
    [projectId, refresh],
  );

  return { artifacts, loading, error, refresh, create, update, remove };
}
