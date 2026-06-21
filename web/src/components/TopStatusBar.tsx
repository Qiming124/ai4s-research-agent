import type { TokenStats } from "../hooks/useTokenStats";
import { shortSessionId } from "../utils/session";

interface TopStatusBarProps {
  sessionId: string;
  backendOffline: boolean;
  activeAgentName: string | null;
  isStreaming: boolean;
  tokenStats: TokenStats;
  tokenLoading: boolean;
  onStop?: () => void;
  onRetryBackend?: () => void;
  retryingBackend?: boolean;
}

export function TopStatusBar({
  sessionId,
  backendOffline,
  activeAgentName,
  isStreaming,
  tokenStats,
  tokenLoading,
  onStop,
  onRetryBackend,
  retryingBackend = false,
}: TopStatusBarProps) {
  const connectionLabel = backendOffline ? "离线" : "已连接";
  const connectionClass = backendOffline ? "status-offline" : "status-online";

  return (
    <div className="top-status-bar">
      <span className={`status-pill ${connectionClass}`} title="后端连接">
        {connectionLabel}
      </span>
      <span className="status-pill status-session" title="当前会话">
        {shortSessionId(sessionId)}
      </span>
      {activeAgentName && (
        <span className="status-pill status-agent" title="当前 Agent">
          {activeAgentName}
        </span>
      )}
      <span className="status-pill status-tokens" title="本会话 token 用量">
        {tokenLoading ? "tokens…" : `${tokenStats.totals.total_tokens.toLocaleString()} tok`}
      </span>
      {backendOffline && onRetryBackend && (
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={onRetryBackend}
          disabled={retryingBackend}
        >
          {retryingBackend ? "连接中…" : "重试"}
        </button>
      )}
      {isStreaming && onStop && (
        <button type="button" className="btn-stop btn-sm" onClick={onStop}>
          停止
        </button>
      )}
    </div>
  );
}
