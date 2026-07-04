import { useState } from "react";
import type { VerificationDashboard } from "../hooks/useVerification";
import type { VerificationRecord } from "../hooks/useVerificationRecords";

interface VerificationDashboardPanelProps {
  dashboard: VerificationDashboard | null;
  records: VerificationRecord[];
  loading: boolean;
  recordsLoading: boolean;
  error: string | null;
  sessionId: string;
  onRefresh: () => void;
  onRefreshRecords: () => void;
  onRunVerification: (claim: Record<string, unknown>) => Promise<unknown>;
}

export function VerificationDashboardPanel({
  dashboard,
  records,
  loading,
  recordsLoading,
  error,
  sessionId,
  onRefresh,
  onRefreshRecords,
  onRunVerification,
}: VerificationDashboardPanelProps) {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const handleQuickVerify = async () => {
    setRunning(true);
    setRunError(null);
    try {
      await onRunVerification({
        claim: {
          expression: "x0**2 + x1**2",
          point: "0,0",
          variables: "x0,x1",
          expected: { classification: "local_minimum" },
          tier_hint: "numerical",
        },
        session_id: sessionId,
      });
      onRefresh();
      onRefreshRecords();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "验证失败");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="verification-dashboard">
      <div className="panel-header">
        <h4>验证仪表盘</h4>
        <div className="panel-header-actions">
          <button
            type="button"
            className="btn-small"
            onClick={() => void handleQuickVerify()}
            disabled={running}
          >
            {running ? "验证中…" : "重跑验证"}
          </button>
          <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
            刷新
          </button>
        </div>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {runError && <p className="panel-error">{runError}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {dashboard && (
        <>
          <div className="verify-stats-row">
            <div className="verify-stat pass">
              <span className="verify-stat-num">
                {dashboard.total_records > 0
                  ? Math.round((dashboard.passed / dashboard.total_records) * 100)
                  : 0}
                %
              </span>
              <span className="verify-stat-label">通过率</span>
            </div>
            <div className="verify-stat">
              <span className="verify-stat-num">{dashboard.total_records}</span>
              <span className="verify-stat-label">总验证</span>
            </div>
            <div className="verify-stat pass">
              <span className="verify-stat-num">{dashboard.passed}</span>
              <span className="verify-stat-label">通过</span>
            </div>
            <div className="verify-stat fail">
              <span className="verify-stat-num">{dashboard.failed}</span>
              <span className="verify-stat-label">失败</span>
            </div>
          </div>
          <div className="verify-tier-bars">
            {Object.entries(dashboard.by_tier).map(([tier, count]) => (
              <div key={tier} className="verify-tier-item">
                <span>{tier}</span>
                <span className="verify-tier-count">{count}</span>
              </div>
            ))}
          </div>
          {dashboard.recent.length > 0 && (
            <ul className="verify-recent-list">
              {dashboard.recent.slice(0, 8).map((r) => (
                <li key={r.id} className={r.passed ? "verify-pass" : "verify-fail"}>
                  <span className="verify-tier-tag">{r.tier}</span>
                  <span>{r.claim_id || r.executor}</span>
                  <span>{r.passed ? "✓" : "✗"}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {!loading && !dashboard && !error && (
        <p className="panel-muted">暂无验证记录；Theory 推导后将自动记录。</p>
      )}
      <h5 className="panel-subtitle">验证账本</h5>
      {recordsLoading && <p className="panel-muted">加载账本…</p>}
      <ul className="verify-recent-list">
        {records.slice(0, 12).map((r) => (
          <li key={r.id} className={r.passed ? "verify-pass" : "verify-fail"}>
            <span className="verify-tier-tag">{r.tier}</span>
            <span>{r.claim_id || r.executor}</span>
            <span>{r.passed ? "✓" : "✗"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
