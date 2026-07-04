import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface ProjectTask {
  id: number;
  project_id: string;
  title: string;
  description: string;
  assignee_role: string;
  status: string;
  related_entry_id: number | null;
}

async function fetchTasks(projectId: string): Promise<Response> {
  return fetch(`/v1/projects/${encodeURIComponent(projectId)}/tasks`);
}

export function useProjectTasks(projectId: string, enabled: boolean) {
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolvedProjectId, setResolvedProjectId] = useState(projectId);

  const refresh = useCallback(async () => {
    if (!enabled || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      let res = await fetchTasks(projectId);
      let pid = projectId;
      if (res.status === 404 && projectId !== "default") {
        res = await fetchTasks("default");
        pid = "default";
      }
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(
            "HTTP 404 — 课题 API 不可用，请重启后端（需包含 /v1/projects 路由）",
          );
        }
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      setResolvedProjectId(pid);
      setTasks(data.tasks ?? []);
    } catch (err) {
      setError(formatBackendError(err));
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const updateStatus = async (taskId: number, status: string) => {
    const pid = resolvedProjectId || projectId || "default";
    const res = await fetch(
      `/v1/projects/${encodeURIComponent(pid)}/tasks/${taskId}?status=${encodeURIComponent(status)}`,
      { method: "PATCH" },
    );
    if (res.ok) await refresh();
  };

  const createTask = async (title: string, assigneeRole = "theorist") => {
    const pid = resolvedProjectId || projectId || "default";
    const res = await fetch(`/v1/projects/${encodeURIComponent(pid)}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim(), assignee_role: assigneeRole }),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `HTTP ${res.status}`);
    }
    await refresh();
  };

  return { tasks, loading, error, refresh, updateStatus, createTask, resolvedProjectId };
}
