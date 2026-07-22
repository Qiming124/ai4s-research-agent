import { useMemo, useState } from "react";
import type { ImportCandidate, ImportPreviewResult } from "../hooks/useStructuredMemory";

type Mode = "markdown" | "pdf";

interface TheoremImportModalProps {
  mode: Mode;
  sessionId: string;
  onClose: () => void;
  onPreviewMarkdown: (content: string) => Promise<ImportPreviewResult>;
  onPreviewFile: (file: File) => Promise<ImportPreviewResult>;
  onConfirm: (
    candidates: ImportCandidate[],
    source: "markdown_import" | "pdf_import",
    extraMeta?: Record<string, unknown>,
  ) => Promise<{ ok: number; errors: string[] }>;
  onAlsoUploadRag?: (file: File) => Promise<void>;
}

interface EditableCandidate extends ImportCandidate {
  selected: boolean;
}

export function TheoremImportModal({
  mode,
  sessionId,
  onClose,
  onPreviewMarkdown,
  onPreviewFile,
  onConfirm,
  onAlsoUploadRag,
}: TheoremImportModalProps) {
  const [markdown, setMarkdown] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [alsoRag, setAlsoRag] = useState(true);
  const [candidates, setCandidates] = useState<EditableCandidate[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [filename, setFilename] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultMsg, setResultMsg] = useState<string | null>(null);

  const selectedCount = useMemo(
    () => candidates.filter((c) => c.selected).length,
    [candidates],
  );

  async function runPreview() {
    setBusy(true);
    setError(null);
    setResultMsg(null);
    try {
      let preview: ImportPreviewResult;
      if (mode === "markdown") {
        if (!markdown.trim()) throw new Error("请粘贴 Markdown 内容");
        preview = await onPreviewMarkdown(markdown);
      } else {
        if (!file) throw new Error("请选择文件");
        preview = await onPreviewFile(file);
      }
      setFilename(preview.filename || "");
      setWarnings(preview.warnings || []);
      setCandidates(
        (preview.candidates || []).map((c) => ({
          ...c,
          selected: c.selected_default !== false,
        })),
      );
      if (!preview.candidates?.length) {
        setError("未得到候选条目");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runConfirm() {
    const picked = candidates.filter((c) => c.selected && c.body.trim());
    if (!picked.length) {
      setError("请至少勾选一条候选");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const source = mode === "markdown" ? "markdown_import" : "pdf_import";
      const { ok, errors } = await onConfirm(picked, source, {
        import_filename: filename || file?.name || undefined,
      });
      if (alsoRag && mode === "pdf" && file && onAlsoUploadRag) {
        try {
          await onAlsoUploadRag(file);
        } catch (e) {
          errors.push(`RAG 上传失败: ${e instanceof Error ? e.message : String(e)}`);
        }
      }
      setResultMsg(`已写入 ${ok} 条` + (errors.length ? `；失败 ${errors.length}` : ""));
      if (errors.length) setError(errors.slice(0, 3).join("；"));
      if (ok > 0 && errors.length === 0) {
        onClose();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="theorem-drawer-overlay" onClick={onClose} role="presentation">
      <aside
        className="theorem-drawer theorem-import-modal"
        onClick={(e) => e.stopPropagation()}
        aria-label={mode === "markdown" ? "Markdown 导入" : "PDF 导入"}
      >
        <header className="theorem-drawer-header">
          <div>
            <h3>{mode === "markdown" ? "从 Markdown 导入" : "从 PDF/文档导入"}</h3>
            <p className="panel-muted">会话 {sessionId || "—"} · 确认前不写库</p>
          </div>
          <button type="button" className="btn-small" onClick={onClose}>
            关闭
          </button>
        </header>

        <div className="theorem-drawer-body">
          {mode === "markdown" ? (
            <label className="import-field">
              <span>粘贴含 ## 定理 / ## 引理 的 Markdown</span>
              <textarea
                rows={8}
                value={markdown}
                onChange={(e) => setMarkdown(e.target.value)}
                placeholder={"## 定理 1\n若 ...\n\n## 引理 1\n..."}
              />
            </label>
          ) : (
            <>
              <label className="import-field">
                <span>选择 PDF / DOCX / MD / TXT</span>
                <input
                  type="file"
                  accept=".pdf,.docx,.md,.txt,.markdown"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <label className="import-check">
                <input
                  type="checkbox"
                  checked={alsoRag}
                  onChange={(e) => setAlsoRag(e.target.checked)}
                />
                确认入库时同时加入文献库 (RAG)
              </label>
            </>
          )}

          <div className="import-actions">
            <button type="button" className="btn-secondary" disabled={busy} onClick={() => void runPreview()}>
              {busy ? "处理中…" : "生成候选"}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || selectedCount === 0}
              onClick={() => void runConfirm()}
            >
              确认入库（{selectedCount}）
            </button>
          </div>

          {warnings.map((w) => (
            <p key={w} className="panel-muted">
              {w}
            </p>
          ))}
          {error && <p className="panel-error">{error}</p>}
          {resultMsg && <p className="panel-muted">{resultMsg}</p>}

          {candidates.length > 0 && (
            <ul className="import-candidate-list">
              {candidates.map((c, i) => (
                <li key={i} className="import-candidate">
                  <label className="import-check">
                    <input
                      type="checkbox"
                      checked={c.selected}
                      onChange={(e) => {
                        const next = [...candidates];
                        next[i] = { ...c, selected: e.target.checked };
                        setCandidates(next);
                      }}
                    />
                    选中
                  </label>
                  <input
                    className="import-title"
                    value={c.title}
                    onChange={(e) => {
                      const next = [...candidates];
                      next[i] = { ...c, title: e.target.value };
                      setCandidates(next);
                    }}
                  />
                  <select
                    value={c.kind}
                    onChange={(e) => {
                      const next = [...candidates];
                      next[i] = { ...c, kind: e.target.value };
                      setCandidates(next);
                    }}
                  >
                    <option value="theorem">theorem</option>
                    <option value="hypothesis">hypothesis</option>
                    <option value="conclusion">conclusion</option>
                    <option value="note">note</option>
                    <option value="citation">citation</option>
                  </select>
                  <textarea
                    rows={4}
                    value={c.body}
                    onChange={(e) => {
                      const next = [...candidates];
                      next[i] = { ...c, body: e.target.value };
                      setCandidates(next);
                    }}
                  />
                  <p className="panel-muted">
                    {c.page != null ? `页 ${c.page} · ` : ""}
                    置信度 {((c.confidence ?? 0) * 100).toFixed(0)}%
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
