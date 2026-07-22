import { useEffect, useState } from "react";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import { MarkdownContent } from "./MarkdownContent";

export type TheoremStatus =
  | "draft"
  | "symbolically_verified"
  | "numerically_verified"
  | "experiment_verified"
  | "proved"
  | "refuted";

export function getEntryStatus(entry: StructuredMemoryEntry): TheoremStatus {
  const status = (entry.metadata?.status as string) || "draft";
  if (
    status === "symbolically_verified" ||
    status === "numerically_verified" ||
    status === "experiment_verified" ||
    status === "proved" ||
    status === "refuted"
  ) {
    return status as TheoremStatus;
  }
  return "draft";
}

const STATUS_LABELS: Record<TheoremStatus, string> = {
  draft: "草稿",
  symbolically_verified: "符号验证",
  numerically_verified: "数值验证",
  experiment_verified: "实验支持",
  proved: "已证实",
  refuted: "反例",
};

const SOURCE_LABELS: Record<string, string> = {
  manual: "手工",
  markdown_import: "Markdown",
  pdf_import: "PDF",
  ai_extract: "AI 抽取",
};

interface StatusBadgeProps {
  status: TheoremStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge status-${status}`}>{STATUS_LABELS[status]}</span>;
}

interface TheoremDetailDrawerProps {
  entry: StructuredMemoryEntry | null;
  onClose: () => void;
  onCreateTask?: (title: string, entryId: number) => Promise<void>;
  onUpdate?: (
    id: number,
    payload: {
      kind?: string;
      title?: string;
      body?: string;
      metadata?: Record<string, unknown>;
    },
  ) => Promise<StructuredMemoryEntry>;
  onDelete?: (id: number) => Promise<void>;
}

export function TheoremDetailDrawer({
  entry,
  onClose,
  onCreateTask,
  onUpdate,
  onDelete,
}: TheoremDetailDrawerProps) {
  const [editing, setEditing] = useState(false);
  const [kind, setKind] = useState("theorem");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entry) return;
    setEditing(false);
    setKind(entry.kind);
    setTitle(entry.title || "");
    setBody(entry.body || "");
    setError(null);
  }, [entry]);

  if (!entry) return null;
  const status = getEntryStatus(entry);
  const ledger = (entry.metadata?.verification_ledger as unknown[]) ?? [];
  const source = typeof entry.metadata?.source === "string" ? entry.metadata.source : "";

  async function handleSave() {
    if (!onUpdate || !entry) return;
    if (!body.trim()) {
      setError("正文不能为空");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const meta = {
        ...(entry.metadata || {}),
        edited_by: "user",
      };
      await onUpdate(entry.id, { kind, title: title.trim(), body: body.trim(), metadata: meta });
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!onDelete || !entry) return;
    if (!window.confirm(`确认删除「${entry.title || `#${entry.id}`}」？`)) return;
    setBusy(true);
    setError(null);
    try {
      await onDelete(entry.id);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="theorem-drawer-overlay" onClick={onClose} role="presentation">
      <aside
        className="theorem-drawer"
        onClick={(e) => e.stopPropagation()}
        aria-label="定理详情"
      >
        <header className="theorem-drawer-header">
          <div>
            <StatusBadge status={status} />
            {source && (
              <span className="theorem-source-tag">
                {SOURCE_LABELS[source] || source}
              </span>
            )}
            <h3>{entry.title || `条目 #${entry.id}`}</h3>
            <span className="theorem-kind-tag">{entry.kind}</span>
          </div>
          <button type="button" className="btn-small" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="theorem-drawer-body">
          {editing ? (
            <div className="theorem-create-form">
              <label>
                类型
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  <option value="theorem">theorem</option>
                  <option value="hypothesis">hypothesis</option>
                  <option value="conclusion">conclusion</option>
                  <option value="note">note</option>
                  <option value="citation">citation</option>
                </select>
              </label>
              <label>
                标题
                <input value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <label>
                正文
                <textarea rows={12} value={body} onChange={(e) => setBody(e.target.value)} />
              </label>
            </div>
          ) : (
            <MarkdownContent content={entry.body} className="panel-markdown theorem-full-body" />
          )}
          {Array.isArray(ledger) && ledger.length > 0 && !editing && (
            <section>
              <h4>验证记录</h4>
              <ul className="verification-ledger-list">
                {ledger.map((item, i) => (
                  <li key={i}>
                    <code>{JSON.stringify(item).slice(0, 200)}</code>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {error && <p className="panel-error">{error}</p>}
          <div className="theorem-drawer-actions">
            {onUpdate && (
              <button
                type="button"
                className="btn-secondary"
                disabled={busy}
                onClick={() => {
                  if (editing) void handleSave();
                  else setEditing(true);
                }}
              >
                {editing ? (busy ? "保存中…" : "保存") : "编辑"}
              </button>
            )}
            {editing && (
              <button type="button" className="btn-small" disabled={busy} onClick={() => setEditing(false)}>
                取消编辑
              </button>
            )}
            {!editing && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => navigator.clipboard.writeText(entry.body)}
              >
                复制正文
              </button>
            )}
            {onDelete && !editing && (
              <button type="button" className="btn-small" disabled={busy} onClick={() => void handleDelete()}>
                删除
              </button>
            )}
            {onCreateTask && entry.id != null && !editing && (
              <button
                type="button"
                className="btn-primary"
                onClick={() =>
                  void onCreateTask(
                    `跟进：${entry.title || `定理 #${entry.id}`}`,
                    entry.id as number,
                  )
                }
              >
                生成课题任务
              </button>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
