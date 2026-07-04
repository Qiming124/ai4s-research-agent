import { useMemo, useState } from "react";
import type { ExperimentRun } from "../hooks/useExperimentLogs";
import { buildExperimentCard } from "../utils/experimentDisplay";

interface ExperimentLogPanelProps {
  runs: ExperimentRun[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onRunExperiment?: () => Promise<void>;
  onJupyterTemplate?: () => Promise<void>;
  onJupyterUpload?: () => Promise<void>;
}

export function ExperimentLogPanel({
  runs,
  loading,
  error,
  onRefresh,
  onRunExperiment,
  onJupyterTemplate,
  onJupyterUpload,
}: ExperimentLogPanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [jupyterBusy, setJupyterBusy] = useState(false);

  const cards = useMemo(() => runs.map(buildExperimentCard), [runs]);

  const handleRun = async () => {
    if (!onRunExperiment) return;
    setRunning(true);
    try {
      await onRunExperiment();
      await onRefresh();
    } finally {
      setRunning(false);
    }
  };

  const handleJupyter = async (action: "template" | "upload") => {
    const fn = action === "template" ? onJupyterTemplate : onJupyterUpload;
    if (!fn) return;
    setJupyterBusy(true);
    try {
      await fn();
      await onRefresh();
    } finally {
      setJupyterBusy(false);
    }
  };

  return (
    <div className="experiment-log-panel">
      <p className="panel-muted experiment-intro">
        记录数值验证与 Notebook 实验结果：例如损失函数临界点分类、二次函数最小值验证等。
      </p>

      <div className="experiment-toolbar">
        {onRunExperiment && (
          <button
            type="button"
            className="btn-small btn-primary"
            onClick={() => void handleRun()}
            disabled={running || loading}
          >
            {running ? "运行中…" : "运行示例实验"}
          </button>
        )}
        {onJupyterTemplate && (
          <button
            type="button"
            className="btn-small"
            disabled={jupyterBusy || loading}
            onClick={() => void handleJupyter("template")}
          >
            Notebook 模板
          </button>
        )}
        {onJupyterUpload && (
          <button
            type="button"
            className="btn-small"
            disabled={jupyterBusy || loading}
            onClick={() => void handleJupyter("upload")}
          >
            回传示例
          </button>
        )}
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>

      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {!loading && cards.length === 0 && (
        <p className="panel-muted">暂无记录。可点「运行示例实验」或「回传示例」生成第一条。</p>
      )}

      <ul className="experiment-list">
        {cards.map((card) => {
          const isOpen = expanded === card.id;
          return (
            <li key={card.id} className={`experiment-card tone-${card.tone}`}>
              <button
                type="button"
                className="experiment-card-head"
                onClick={() => setExpanded(isOpen ? null : card.id)}
                aria-expanded={isOpen}
              >
                <div className="experiment-card-title-row">
                  <strong>{card.title}</strong>
                  <span className={`experiment-status tone-${card.tone}`}>{card.statusLabel}</span>
                </div>
                <p className="experiment-card-headline">{card.headline}</p>
                {card.timeLabel && <time className="experiment-card-time">{card.timeLabel}</time>}
              </button>

              {isOpen && (
                <div className="experiment-card-body">
                  {card.highlights.length > 0 && (
                    <dl className="experiment-kv">
                      {card.highlights.map((row) => (
                        <div key={`${card.id}-${row.label}`} className="experiment-kv-row">
                          <dt>{row.label}</dt>
                          <dd className={row.tone ? `tone-${row.tone}` : undefined}>{row.value}</dd>
                        </div>
                      ))}
                    </dl>
                  )}

                  {card.tiers.length > 0 && (
                    <div className="experiment-tiers">
                      <p className="experiment-section-label">验证分层</p>
                      <ul>
                        {card.tiers.map((tier) => (
                          <li key={`${card.id}-${tier.name}`} className={`experiment-tier tone-${tier.tone}`}>
                            <span className="experiment-tier-name">{tier.name}</span>
                            <span className="experiment-tier-status">{tier.statusLabel}</span>
                            <span className="experiment-tier-msg">{tier.message}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {card.notes.map((note) => (
                    <p key={note} className="panel-muted experiment-note">
                      {note}
                    </p>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
