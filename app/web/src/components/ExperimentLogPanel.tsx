import type { ExperimentRun } from "../hooks/useExperimentLogs";

interface ExperimentLogPanelProps {
  runs: ExperimentRun[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function ExperimentLogPanel({
  runs,
  loading,
  error,
  onRefresh,
}: ExperimentLogPanelProps) {
  return (
    <div className="experiment-log-panel">
      <div className="panel-header">
        <h4>实验日志</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {!loading && runs.length === 0 && (
        <p className="panel-muted">暂无实验记录。</p>
      )}
      <ul className="experiment-list">
        {runs.map((r) => (
          <li key={r.run_id}>
            <strong>{r.name}</strong>
            <span className="run-status">{r.status}</span>
            {r.created_at && <time>{r.created_at}</time>}
          </li>
        ))}
      </ul>
    </div>
  );
}
