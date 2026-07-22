import { useMemo, useRef, useState } from "react";
import type { ExperimentRun } from "../hooks/useExperimentLogs";
import { buildExperimentCard } from "../utils/experimentDisplay";

export interface NotebookUploadPayload {
  name: string;
  project_id: string;
  session_id?: string | null;
  summary: Record<string, unknown>;
  metrics: Record<string, unknown>;
}

export interface ExperimentFileUploadMeta {
  name: string;
  project_id: string;
  session_id?: string | null;
}

interface ExperimentLogPanelProps {
  runs: ExperimentRun[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  sessionId?: string;
  projectId?: string;
  /** 调用 POST /v1/jupyter/upload-result */
  onJupyterUpload?: (payload: NotebookUploadPayload) => Promise<void>;
  /** 调用 POST /v1/jupyter/upload-file（Excel/CSV/JSON 等） */
  onExperimentFileUpload?: (file: File, meta: ExperimentFileUploadMeta) => Promise<void>;
}

const DEFAULT_SUMMARY = '{\n  "passed": true\n}';
const DEFAULT_METRICS = '{\n  "min_loss": 0.0,\n  "min_eigen": 0.01\n}';

function parseJsonObject(raw: string, label: string): Record<string, unknown> {
  const text = raw.trim() || "{}";
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`${label} 不是合法 JSON`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} 须为 JSON 对象`);
  }
  return parsed as Record<string, unknown>;
}

export function ExperimentLogPanel({
  runs,
  loading,
  error,
  onRefresh,
  sessionId,
  projectId = "default",
  onJupyterUpload,
  onExperimentFileUpload,
}: ExperimentLogPanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [jupyterBusy, setJupyterBusy] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadName, setUploadName] = useState("notebook_result");
  const [summaryText, setSummaryText] = useState(DEFAULT_SUMMARY);
  const [metricsText, setMetricsText] = useState(DEFAULT_METRICS);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const cards = useMemo(() => runs.map(buildExperimentCard), [runs]);

  const loadJsonFile = async (file: File) => {
    const text = await file.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      setUploadError("文件不是合法 JSON");
      return;
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      setUploadError("文件须为 JSON 对象");
      return;
    }
    const obj = data as Record<string, unknown>;
    if (typeof obj.name === "string" && obj.name.trim()) {
      setUploadName(obj.name.trim());
    } else if (file.name) {
      setUploadName(file.name.replace(/\.json$/i, "") || "notebook_result");
    }
    if (obj.summary && typeof obj.summary === "object" && !Array.isArray(obj.summary)) {
      setSummaryText(JSON.stringify(obj.summary, null, 2));
    } else if (obj.summary === undefined && obj.metrics === undefined) {
      // 整个文件当作 metrics
      setMetricsText(JSON.stringify(obj, null, 2));
      setUploadError(null);
      return;
    }
    if (obj.metrics && typeof obj.metrics === "object" && !Array.isArray(obj.metrics)) {
      setMetricsText(JSON.stringify(obj.metrics, null, 2));
    }
    setUploadError(null);
  };

  const handlePickFile = async (file: File) => {
    setUploadError(null);
    const lower = file.name.toLowerCase();
    const isTable =
      lower.endsWith(".xlsx") ||
      lower.endsWith(".xlsm") ||
      lower.endsWith(".csv") ||
      lower.endsWith(".tsv");
    if (isTable) {
      if (!onExperimentFileUpload) {
        setUploadError("当前界面未接入文件上传接口");
        return;
      }
      const name = uploadName.trim() || file.name.replace(/\.[^.]+$/, "") || "file_result";
      setJupyterBusy(true);
      try {
        await onExperimentFileUpload(file, {
          name,
          project_id: projectId || "default",
          session_id: sessionId || null,
        });
        await onRefresh();
        setShowUpload(false);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      } finally {
        setJupyterBusy(false);
      }
      return;
    }
    if (lower.endsWith(".json") || file.type.includes("json")) {
      await loadJsonFile(file);
      return;
    }
    setUploadError("支持格式：.xlsx / .csv / .tsv / .json");
  };

  const handleUploadSubmit = async () => {
    if (!onJupyterUpload) return;
    setUploadError(null);
    let summary: Record<string, unknown>;
    let metrics: Record<string, unknown>;
    try {
      summary = parseJsonObject(summaryText, "summary");
      metrics = parseJsonObject(metricsText, "metrics");
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
      return;
    }
    const name = uploadName.trim() || "notebook_result";
    setJupyterBusy(true);
    try {
      await onJupyterUpload({
        name,
        project_id: projectId || "default",
        session_id: sessionId || null,
        summary,
        metrics,
      });
      await onRefresh();
      setShowUpload(false);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setJupyterBusy(false);
    }
  };

  return (
    <div className="experiment-log-panel">
      <p className="panel-muted experiment-intro">
        提交你在本机/Notebook 得到的指标，供实验顾问解读（DataPacket）。系统不以代跑训练为核心。
      </p>

      <div className="experiment-toolbar">
        {onJupyterUpload && (
          <button
            type="button"
            className="btn-small"
            disabled={jupyterBusy || loading}
            onClick={() => {
              setShowUpload((v) => !v);
              setUploadError(null);
            }}
          >
            {showUpload ? "收起回传" : "回传结果"}
          </button>
        )}
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>

      {showUpload && onJupyterUpload && (
        <div className="notebook-upload-form">
          <p className="panel-muted">
            可手填 JSON，或导入 <strong>.xlsx / .csv / .tsv / .json</strong>。
            Excel/CSV 会按表格解析（两列键值→指标；多列表格→末行数值作指标）。课题：
            <code>{projectId || "default"}</code>
            {sessionId ? (
              <>
                {" "}
                · 会话：<code>{sessionId.slice(0, 8)}</code>
              </>
            ) : null}
          </p>
          <label className="notebook-upload-field">
            <span>结果名称</span>
            <input
              type="text"
              value={uploadName}
              disabled={jupyterBusy}
              onChange={(e) => setUploadName(e.target.value)}
              placeholder="hessian_scan_nb"
            />
          </label>
          <label className="notebook-upload-field">
            <span>summary（JSON）</span>
            <textarea
              rows={4}
              value={summaryText}
              disabled={jupyterBusy}
              onChange={(e) => setSummaryText(e.target.value)}
              spellCheck={false}
            />
          </label>
          <label className="notebook-upload-field">
            <span>metrics（JSON）</span>
            <textarea
              rows={5}
              value={metricsText}
              disabled={jupyterBusy}
              onChange={(e) => setMetricsText(e.target.value)}
              spellCheck={false}
            />
          </label>
          <div className="notebook-upload-actions">
            <input
              ref={fileRef}
              type="file"
              accept=".json,.csv,.tsv,.xlsx,.xlsm,application/json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="visually-hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handlePickFile(file);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              className="btn-small"
              disabled={jupyterBusy}
              onClick={() => fileRef.current?.click()}
            >
              导入文件（Excel/CSV/JSON）
            </button>
            <button
              type="button"
              className="btn-small btn-primary"
              disabled={jupyterBusy || loading}
              onClick={() => void handleUploadSubmit()}
            >
              {jupyterBusy ? "提交中…" : "提交回传"}
            </button>
          </div>
          {uploadError && <p className="panel-error">{uploadError}</p>}
        </div>
      )}

      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}
      {!loading && cards.length === 0 && (
        <p className="panel-muted">暂无记录。点「回传结果」提交第一条实验数据。</p>
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
