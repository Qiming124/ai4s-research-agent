import type { AgentQualityItem, ObservabilitySummary } from "../hooks/useObservability";

interface ObservabilityPanelProps {
  summary: ObservabilitySummary | null;
  agentQuality: AgentQualityItem[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function ObservabilityPanel({
  summary,
  agentQuality,
  loading,
  error,
  onRefresh,
}: ObservabilityPanelProps) {
  const passRate = summary?.verification_pass_rate ?? 0;

  return (
    <div className="observability-panel">
      <div className="panel-header">
        <h4>Agent 质量</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {summary && (
        <div className="verify-stats-row">
          <div className="verify-stat pass">
            <span className="verify-stat-num">{passRate.toFixed(0)}%</span>
            <span className="verify-stat-label">验证通过率</span>
          </div>
          <div className="verify-stat">
            <span className="verify-stat-num">{summary.verification_total}</span>
            <span className="verify-stat-label">总验证</span>
          </div>
          <div className="verify-stat">
            <span className="verify-stat-num">{summary.verification_passed}</span>
            <span className="verify-stat-label">通过</span>
          </div>
        </div>
      )}
      {agentQuality.length > 0 && (
        <ul className="verify-recent-list">
          {agentQuality.map((a) => (
            <li key={a.agent_name}>
              <span>{a.agent_name}</span>
              <span>
                {a.pass_rate.toFixed(0)}% ({a.passed}/{a.runs})
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
