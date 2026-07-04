import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface AgentInfo {
  name: string;
  description: string;
  rag_enabled?: boolean;
}

export function useAgents(enabled: boolean) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [orchestrationBackend, setOrchestrationBackend] = useState("");

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/v1/agents");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAgents(data.agents ?? []);
      setOrchestrationBackend(data.orchestration_backend ?? "");
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { agents, loading, error, orchestrationBackend, refresh };
}
