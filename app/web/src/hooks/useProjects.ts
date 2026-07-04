import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface ProjectInfo {
  id: string;
  name: string;
  description: string;
  created_by: string;
  workspace_path: string;
  rag_namespace: string;
}

const PROJECT_KEY = "ai4s_current_project";

export function getCurrentProjectId(): string {
  return localStorage.getItem(PROJECT_KEY) || "default";
}

export function setCurrentProjectId(id: string) {
  localStorage.setItem(PROJECT_KEY, id);
}

export function useProjects(enabled: boolean) {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [currentProjectId, setCurrentProjectIdState] = useState(getCurrentProjectId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const res = await fetch("/v1/projects");
      if (res.status === 404) {
        throw new Error("HTTP 404 — 请重启后端以加载课题 API（/v1/projects）");
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list: ProjectInfo[] = data.projects ?? [];
      setProjects(list);

      const stored = getCurrentProjectId();
      const valid = list.some((p) => p.id === stored);
      if (!valid && list.length > 0) {
        const fallback = list.find((p) => p.id === "default")?.id ?? list[0].id;
        setCurrentProjectId(fallback);
        setCurrentProjectIdState(fallback);
      }
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectProject = (id: string) => {
    setCurrentProjectId(id);
    setCurrentProjectIdState(id);
  };

  const createProject = async (name: string, description = "") => {
    const res = await fetch("/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), description: description.trim() }),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `HTTP ${res.status}`);
    }
    const project: ProjectInfo = await res.json();
    await refresh();
    selectProject(project.id);
    return project;
  };

  const currentProject = projects.find((p) => p.id === currentProjectId) ?? {
    id: currentProjectId || "default",
    name: "默认课题",
    description: "",
    created_by: "",
    workspace_path: "",
    rag_namespace: "default",
  };

  return {
    projects,
    currentProject,
    currentProjectId,
    loading,
    error,
    refresh,
    selectProject,
    createProject,
  };
}
