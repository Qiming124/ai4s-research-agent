import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  API_LAB_PRESETS,
  buildDefaultBody,
  buildDefaultParamValues,
  clearHistory,
  downloadBlob,
  executeApiRequest,
  fetchOpenApiCatalog,
  loadHistory,
  pushHistory,
  TAG_LABELS,
  type ApiLabHistoryItem,
  type ApiOperation,
  type ExecuteResult,
  type OpenApiCatalog,
} from "../apiLab";
import {
  adjustCatalogWidth,
  adjustEditorWidth,
  loadApiLabLayout,
  saveApiLabLayout,
} from "../apiLab/layout";
import type { SseLabEvent } from "../apiLab/sseRunner";
import { ResizeHandle } from "./ResizeHandle";

interface ApiLabPageProps {
  onBack: () => void;
}

export function ApiLabPage({ onBack }: ApiLabPageProps) {
  const [catalog, setCatalog] = useState<OpenApiCatalog | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [bodyText, setBodyText] = useState("");
  const [forceSse, setForceSse] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ExecuteResult | null>(null);
  const [liveSse, setLiveSse] = useState<SseLabEvent[]>([]);
  const [history, setHistory] = useState<ApiLabHistoryItem[]>(() => loadHistory());
  const [layout, setLayout] = useState(() => loadApiLabLayout());
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    saveApiLabLayout(layout);
  }, [layout]);

  const resizeCatalog = useCallback((delta: number) => {
    setLayout((prev) => ({
      ...prev,
      catalogWidth: adjustCatalogWidth(prev.catalogWidth, delta),
    }));
  }, []);

  const resizeEditor = useCallback((delta: number) => {
    setLayout((prev) => ({
      ...prev,
      editorWidth: adjustEditorWidth(prev.editorWidth, delta),
    }));
  }, []);

  const selectOperation = useCallback((
    op: ApiOperation,
    extras?: {
      paramValues?: Record<string, string>;
      bodyText?: string;
      forceSse?: boolean;
    },
  ) => {
    setSelectedId(op.id);
    setParamValues(extras?.paramValues ?? buildDefaultParamValues(op));
    setBodyText(extras?.bodyText ?? buildDefaultBody(op));
    setForceSse(extras?.forceSse ?? op.likelySse);
    setResult(null);
    setLiveSse([]);
  }, []);

  const reloadCatalog = useCallback(async () => {
    setLoadingCatalog(true);
    setLoadError(null);
    try {
      const cat = await fetchOpenApiCatalog();
      setCatalog(cat);
      setSelectedId((prev) => {
        if (prev && cat.operations.some((o) => o.id === prev)) return prev;
        const health =
          cat.operations.find((o) => o.path === "/health") || cat.operations[0];
        if (health) {
          setParamValues(buildDefaultParamValues(health));
          setBodyText(buildDefaultBody(health));
          setForceSse(health.likelySse);
          return health.id;
        }
        return null;
      });
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingCatalog(false);
    }
  }, []);

  useEffect(() => {
    void reloadCatalog();
  }, [reloadCatalog]);

  const selected = useMemo(
    () => catalog?.operations.find((o) => o.id === selectedId) ?? null,
    [catalog, selectedId],
  );

  const filteredByTag = useMemo(() => {
    if (!catalog) return {} as Record<string, ApiOperation[]>;
    const q = search.trim().toLowerCase();
    const out: Record<string, ApiOperation[]> = {};
    for (const [tag, ops] of Object.entries(catalog.byTag)) {
      const filtered = ops.filter((o) => {
        if (!q) return true;
        return (
          o.path.toLowerCase().includes(q) ||
          o.summary.toLowerCase().includes(q) ||
          o.method.includes(q) ||
          tag.toLowerCase().includes(q)
        );
      });
      if (filtered.length) out[tag] = filtered;
    }
    return out;
  }, [catalog, search]);

  const applyPreset = (presetId: string) => {
    if (!catalog) return;
    const preset = API_LAB_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    const op = catalog.operations.find(
      (o) =>
        o.method === preset.match.method && o.path === preset.match.path,
    );
    if (!op) {
      setLoadError(`预设未找到接口：${preset.match.method.toUpperCase()} ${preset.match.path}`);
      return;
    }
    selectOperation(op, {
      paramValues: { ...buildDefaultParamValues(op), ...preset.paramValues },
      bodyText: preset.bodyText ?? buildDefaultBody(op),
      forceSse: preset.forceSse ?? op.likelySse,
    });
  };

  const run = async () => {
    if (!selected || running) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setRunning(true);
    setLiveSse([]);
    setResult(null);
    try {
      const res = await executeApiRequest({
        method: selected.method,
        pathTemplate: selected.path,
        paramValues,
        bodyText,
        signal: ac.signal,
        forceSse,
        onSseEvent: (ev) => setLiveSse((prev) => [...prev, ev]),
      });
      setResult(res);
      setHistory(
        pushHistory({
          method: selected.method,
          path: selected.path,
          requestUrl: res.requestUrl,
          status: res.status,
          durationMs: res.durationMs,
          kind: res.kind,
          paramValues: { ...paramValues },
          bodyText,
          operationId: selected.id,
        }),
      );
    } finally {
      setRunning(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const restoreHistory = (item: ApiLabHistoryItem) => {
    if (!catalog) return;
    const op =
      catalog.operations.find((o) => o.id === item.operationId) ||
      catalog.operations.find(
        (o) => o.method === item.method && o.path === item.path,
      );
    if (!op) return;
    selectOperation(op, {
      paramValues: item.paramValues,
      bodyText: item.bodyText,
      forceSse: item.kind === "sse" || op.likelySse,
    });
  };

  return (
    <div className="api-lab">
      <header className="api-lab-header">
        <div className="api-lab-brand">
          <h1>API 测试实验室</h1>
          <p className="api-lab-sub">
            {catalog
              ? `${catalog.title} v${catalog.version} · ${catalog.operations.length} 个接口`
              : "从 /openapi.json 加载接口"}
          </p>
        </div>
        <div className="api-lab-header-actions">
          <button type="button" className="btn-secondary" onClick={() => void reloadCatalog()}>
            刷新目录
          </button>
          <a className="btn-secondary" href="/docs" target="_blank" rel="noreferrer">
            OpenAPI /docs
          </a>
          <button type="button" className="btn-secondary" onClick={onBack}>
            返回聊天
          </button>
        </div>
      </header>

      <div className="api-lab-presets" role="group" aria-label="快捷场景">
        {API_LAB_PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className="btn-small api-lab-preset-btn"
            title={p.hint}
            onClick={() => applyPreset(p.id)}
            disabled={!catalog}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loadError && <div className="api-lab-banner-error">{loadError}</div>}
      {loadingCatalog && <div className="api-lab-banner-muted">正在加载 OpenAPI…</div>}

      <div className="api-lab-body">
        <aside
          className="api-lab-catalog"
          style={{ width: layout.catalogWidth, flex: `0 0 ${layout.catalogWidth}px` }}
        >
          <input
            className="api-lab-search"
            placeholder="搜索 path / 摘要 / tag…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="api-lab-catalog-scroll">
            {Object.entries(filteredByTag).map(([tag, ops]) => (
              <details key={tag} open className="api-lab-tag-group">
                <summary>
                  {TAG_LABELS[tag] || tag}
                  <span className="api-lab-tag-count">{ops.length}</span>
                </summary>
                <ul>
                  {ops.map((op) => (
                    <li key={op.id}>
                      <button
                        type="button"
                        className={
                          selectedId === op.id
                            ? "api-lab-op active"
                            : "api-lab-op"
                        }
                        onClick={() => selectOperation(op)}
                      >
                        <span className={`api-lab-method m-${op.method}`}>
                          {op.method.toUpperCase()}
                        </span>
                        <span className="api-lab-op-path">{op.path}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </aside>

        <ResizeHandle
          direction="horizontal"
          onResize={resizeCatalog}
          className="api-lab-resize"
          title="拖拽调整目录栏宽度"
        />

        <section
          className="api-lab-editor"
          style={{ width: layout.editorWidth, flex: `0 0 ${layout.editorWidth}px` }}
        >
          {selected ? (
            <>
              <div className="api-lab-op-head">
                <span className={`api-lab-method m-${selected.method}`}>
                  {selected.method.toUpperCase()}
                </span>
                <code>{selected.path}</code>
              </div>
              <p className="api-lab-summary">{selected.summary}</p>
              {selected.description && (
                <p className="panel-muted api-lab-desc">{selected.description}</p>
              )}

              {selected.parameters.length > 0 && (
                <div className="api-lab-params">
                  <h3>参数</h3>
                  {selected.parameters.map((p) => {
                    const key = `${p.in}:${p.name}`;
                    return (
                      <label key={key} className="api-lab-field">
                        <span>
                          {p.name}
                          <em>
                            ({p.in}
                            {p.required ? ", 必填" : ""})
                          </em>
                        </span>
                        <input
                          value={paramValues[key] ?? ""}
                          onChange={(e) =>
                            setParamValues((prev) => ({
                              ...prev,
                              [key]: e.target.value,
                            }))
                          }
                          placeholder={p.description || p.name}
                        />
                      </label>
                    );
                  })}
                </div>
              )}

              {(selected.hasJsonBody ||
                selected.method === "post" ||
                selected.method === "put" ||
                selected.method === "patch") && (
                <label className="api-lab-field">
                  <span>请求体 (JSON)</span>
                  <textarea
                    className="api-lab-textarea"
                    rows={14}
                    value={bodyText}
                    onChange={(e) => setBodyText(e.target.value)}
                    spellCheck={false}
                  />
                </label>
              )}

              <label className="api-lab-check">
                <input
                  type="checkbox"
                  checked={forceSse}
                  onChange={(e) => setForceSse(e.target.checked)}
                />
                按 SSE 解析响应（chat/stream 等）
              </label>

              <div className="api-lab-run-row">
                <button
                  type="button"
                  className="btn-primary"
                  disabled={running}
                  onClick={() => void run()}
                >
                  {running ? "执行中…" : "执行"}
                </button>
                {running && (
                  <button type="button" className="btn-secondary" onClick={stop}>
                    停止
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className="panel-muted">请从左侧选择一个接口</p>
          )}
        </section>

        <ResizeHandle
          direction="horizontal"
          onResize={resizeEditor}
          className="api-lab-resize"
          title="拖拽调整请求栏宽度"
        />

        <section className="api-lab-result">
          <div className="api-lab-result-head">
            <h3>执行结果</h3>
            {result && (
              <span className="api-lab-meta">
                {result.durationMs} ms · {result.requestUrl}
              </span>
            )}
          </div>

          {running && liveSse.length > 0 && (
            <div className="api-lab-sse-live">
              <p className="experiment-section-label">SSE 实时事件 ({liveSse.length})</p>
              <ul className="api-lab-sse-list">
                {liveSse.slice(-30).map((ev) => (
                  <li key={ev.seq}>
                    <code>{ev.type}</code> {ev.contentPreview}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result && <ResultPanel result={result} />}

          {!result && !running && (
            <p className="panel-muted">点击「执行」后在此查看状态码、JSON、SSE 或下载文件</p>
          )}

          <div className="api-lab-history">
            <div className="api-lab-history-head">
              <h3>历史</h3>
              <button
                type="button"
                className="btn-small"
                onClick={() => {
                  clearHistory();
                  setHistory([]);
                }}
              >
                清空
              </button>
            </div>
            {history.length === 0 ? (
              <p className="panel-muted">暂无记录</p>
            ) : (
              <ul className="api-lab-history-list">
                {history.map((h) => (
                  <li key={h.id}>
                    <button type="button" onClick={() => restoreHistory(h)}>
                      <span className={`api-lab-method m-${h.method}`}>{h.method.toUpperCase()}</span>
                      <span className="api-lab-hist-path">{h.path}</span>
                      <span
                        className={
                          h.status >= 200 && h.status < 300
                            ? "api-lab-status ok"
                            : "api-lab-status bad"
                        }
                      >
                        {h.status || "ERR"}
                      </span>
                      <span className="api-lab-hist-ms">{h.durationMs}ms</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function ResultPanel({ result }: { result: ExecuteResult }) {
  const statusClass =
    result.status >= 200 && result.status < 300
      ? "ok"
      : result.status === 0
        ? "bad"
        : "bad";

  return (
    <div className="api-lab-result-body">
      <div className="api-lab-status-row">
        <span className={`api-lab-status ${statusClass}`}>
          {result.status || "—"} {result.statusText}
        </span>
        <span className="api-lab-kind">{result.kind}</span>
        {result.errorMessage && (
          <span className="panel-error">{result.errorMessage}</span>
        )}
      </div>

      <details className="api-lab-headers">
        <summary>Response Headers</summary>
        <pre>{JSON.stringify(result.headers, null, 2)}</pre>
      </details>

      {result.kind === "json" && (
        <pre className="api-lab-pre">{JSON.stringify(result.json, null, 2)}</pre>
      )}
      {result.kind === "text" && (
        <pre className="api-lab-pre">{result.text}</pre>
      )}
      {result.kind === "empty" && <p className="panel-muted">空响应体</p>}
      {result.kind === "sse" && (
        <>
          <p className="experiment-section-label">
            SSE 事件 ({result.sseEvents?.length ?? 0})
          </p>
          <ul className="api-lab-sse-list">
            {(result.sseEvents || []).map((ev) => (
              <li key={ev.seq}>
                <code>{ev.type}</code>
                <span>{ev.contentPreview}</span>
                <details>
                  <summary>raw</summary>
                  <pre>{JSON.stringify(ev.raw, null, 2)}</pre>
                </details>
              </li>
            ))}
          </ul>
        </>
      )}
      {result.kind === "blob" && result.blob && (
        <div className="api-lab-blob">
          <p>
            二进制响应 · {result.blob.type || "unknown"} ·{" "}
            {(result.blob.size / 1024).toFixed(1)} KB
          </p>
          <button
            type="button"
            className="btn-primary"
            onClick={() =>
              downloadBlob(result.blob!, result.filename || "download.bin")
            }
          >
            下载 {result.filename || "文件"}
          </button>
        </div>
      )}
    </div>
  );
}
