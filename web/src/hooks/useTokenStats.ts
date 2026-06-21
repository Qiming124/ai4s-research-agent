import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface TokenUsageTotals {
  event_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface TokenUsageAgentBreakdown {
  agent_name: string;
  event_count: number;
  total_tokens: number;
}

export interface TokenStats {
  totals: TokenUsageTotals;
  by_agent: TokenUsageAgentBreakdown[];
}

const EMPTY_TOTALS: TokenUsageTotals = {
  event_count: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
};

export function useTokenStats(sessionId: string, enabled = true) {
  const [stats, setStats] = useState<TokenStats>({ totals: EMPTY_TOTALS, by_agent: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ session_id: sessionId });
      const res = await fetch(`/v1/stats/tokens?${params}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as TokenStats;
      setStats({
        totals: data.totals ?? EMPTY_TOTALS,
        by_agent: data.by_agent ?? [],
      });
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId, enabled]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30_000);
    return () => clearInterval(timer);
  }, [refresh]);

  return { stats, loading, error, refresh };
}
