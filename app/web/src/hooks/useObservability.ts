import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface ObservabilitySummary {
  project_id: string;
  verification_total: number;
  verification_passed: number;
  /** 后端已返回 0–100 的百分比 */
  verification_pass_rate: number;
  by_agent: Record<string, { total: number; passed: number }>;
}

export interface AgentQualityItem {
  agent_name: string;
  runs: number;
  passed: number;
  pass_rate: number;
}

export function useObservability(projectId: string, enabled: boolean) {
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [agentQuality, setAgentQuality] = useState<AgentQualityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const [s, q] = await Promise.all([
        fetch(`/v1/observability/summary?project_id=${encodeURIComponent(projectId)}`),
        fetch(`/v1/observability/agent-quality?project_id=${encodeURIComponent(projectId)}`),
      ]);
      if (s.ok) setSummary((await s.json()) as ObservabilitySummary);
      if (q.ok) {
        const data = (await q.json()) as { agents?: AgentQualityItem[] };
        setAgentQuality(data.agents ?? []);
      }
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { summary, agentQuality, loading, error, refresh };
}
