import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface McpToolInfo {
  qualified_name: string;
  tool_name: string;
  description: string;
}

export interface McpServerInfo {
  name: string;
  enabled: boolean;
  connected: boolean;
  tools: McpToolInfo[];
}

export interface McpStatus {
  server_enabled: boolean;
  connected: boolean;
  servers: McpServerInfo[];
}

export function useMcpStatus(enabled = true) {
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ready = await waitForBackend(3, 1000);
      if (!ready) {
        throw new Error(formatBackendError(new Error("Failed to fetch")));
      }
      const res = await fetch("/v1/mcp/status");
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as McpStatus;
      setStatus(data);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    refresh();
  }, [enabled, refresh]);

  return { status, loading, error, refresh };
}
