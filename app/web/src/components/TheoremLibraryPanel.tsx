import { useState } from "react";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import { getEntryStatus, StatusBadge } from "./TheoremDetailDrawer";
import { MarkdownContent } from "./MarkdownContent";

/** 预览截断：避免在 $ / $$ / \( \) / \[ \] 未闭合处截断 */
function truncateTheoremPreview(body: string, max = 480): string {
  if (body.length <= max) return body;

  let cutEnd = max;
  const window = body.slice(0, max);
  const para = window.lastIndexOf("\n\n");
  if (para >= Math.floor(max * 0.55)) cutEnd = para;
  else {
    const sentence = Math.max(
      window.lastIndexOf("。"),
      window.lastIndexOf(". "),
      window.lastIndexOf("；"),
    );
    if (sentence >= Math.floor(max * 0.55)) cutEnd = sentence + 1;
  }

  let cut = body.slice(0, cutEnd);

  const ddCount = (cut.match(/\$\$/g) || []).length;
  if (ddCount % 2 !== 0) {
    const last = cut.lastIndexOf("$$");
    if (last >= 0) cut = cut.slice(0, last);
  }

  const dCount = (cut.match(/(?<!\$)\$(?!\$)/g) || []).length;
  if (dCount % 2 !== 0) {
    const last = cut.lastIndexOf("$");
    if (last >= 0) cut = cut.slice(0, last);
  }

  const parenOpen = (cut.match(/\\\(/g) || []).length;
  const parenClose = (cut.match(/\\\)/g) || []).length;
  if (parenOpen > parenClose) {
    const last = cut.lastIndexOf("\\(");
    if (last >= 0) cut = cut.slice(0, last);
  }

  const bracketOpen = (cut.match(/\\\[/g) || []).length;
  const bracketClose = (cut.match(/\\\]/g) || []).length;
  if (bracketOpen > bracketClose) {
    const last = cut.lastIndexOf("\\[");
    if (last >= 0) cut = cut.slice(0, last);
  }

  cut = cut.trimEnd();
  return cut ? `${cut}\n\n…` : "…";
}

interface TheoremLibraryPanelProps {
  entries: StructuredMemoryEntry[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelect?: (entry: StructuredMemoryEntry) => void;
  onCreate?: (payload: {
    kind: string;
    title: string;
    body: string;
  }) => Promise<void>;
  onOpenMarkdownImport?: () => void;
  onOpenPdfImport?: () => void;
}

export function TheoremLibraryPanel({
  entries,
  loading,
  error,
  onRefresh,
  onSelect,
  onCreate,
  onOpenMarkdownImport,
  onOpenPdfImport,
}: TheoremLibraryPanelProps) {
  const [creating, setCreating] = useState(false);
  const [kind, setKind] = useState("theorem");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleCreate() {
    if (!onCreate || !body.trim()) {
      setFormError("正文不能为空");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await onCreate({ kind, title: title.trim(), body: body.trim() });
      setTitle("");
      setBody("");
      setCreating(false);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="theorem-library-panel">
      <div className="panel-header">
        <h4>定理库 (L4)</h4>
        <div className="panel-header-actions">
          {onCreate && (
            <button type="button" className="btn-small" onClick={() => setCreating((v) => !v)}>
              {creating ? "取消" : "新建"}
            </button>
          )}
          {onOpenMarkdownImport && (
            <button type="button" className="btn-small" onClick={onOpenMarkdownImport}>
              Markdown
            </button>
          )}
          {onOpenPdfImport && (
            <button type="button" className="btn-small" onClick={onOpenPdfImport}>
              PDF 导入
            </button>
          )}
          <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
            刷新
          </button>
        </div>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {creating && onCreate && (
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
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="可选标题" />
          </label>
          <label>
            正文
            <textarea
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="定理/引理正文（支持 Markdown / LaTeX）"
            />
          </label>
          {formError && <p className="panel-error">{formError}</p>}
          <button type="button" className="btn-primary" disabled={saving} onClick={() => void handleCreate()}>
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      )}
      {loading && <p className="panel-muted">加载中…</p>}
      {!loading && entries.length === 0 && (
        <p className="panel-muted">
          暂无定理/引理。可点「新建」、导入 Markdown/PDF，或使用 Theory Agent（回答含{" "}
          <code>## 引理 1</code> / <code>## 定理 1</code>）。
        </p>
      )}
      <ul className="theorem-list">
        {entries.map((e) => (
          <li
            key={e.id}
            className="theorem-item clickable"
            onClick={() => onSelect?.(e)}
            onKeyDown={(ev) => ev.key === "Enter" && onSelect?.(e)}
            role="button"
            tabIndex={0}
          >
            <div className="theorem-item-head">
              <span className="theorem-kind">{e.kind}</span>
              <StatusBadge status={getEntryStatus(e)} />
              {typeof e.metadata?.source === "string" && (
                <span className="theorem-source-tag">{String(e.metadata.source)}</span>
              )}
            </div>
            <strong>{e.title || `条目 #${e.id}`}</strong>
            <div className="theorem-body theorem-body-preview">
              <MarkdownContent
                content={truncateTheoremPreview(e.body || "")}
                className="panel-markdown"
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
