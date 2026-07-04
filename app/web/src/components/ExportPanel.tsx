import { useCallback, useEffect, useState } from "react";
import { MarkdownContent } from "./MarkdownContent";

interface ExportPreview {
  entry_count: number;
  session_structured_count: number;
  global_structured_count: number;
  chat_message_count: number;
  source: string;
  hint: string;
}

interface ExportPanelProps {
  sessionId: string;
  projectId: string;
}

type ExportFormat = "md" | "latex" | "docx" | "pdf";

async function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function parseFilename(res: Response, fallback: string): string {
  const cd = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/i.exec(cd);
  return match?.[1] || fallback;
}

export function ExportPanel({ sessionId, projectId }: ExportPanelProps) {
  const [loading, setLoading] = useState<ExportFormat | "polish" | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [title, setTitle] = useState("研究报告");
  const [useAi, setUseAi] = useState(false);
  const [aiInstructions, setAiInstructions] = useState("");
  const [polishPreview, setPolishPreview] = useState<string | null>(null);

  const refreshPreview = useCallback(async () => {
    if (!sessionId) return;
    try {
      const params = new URLSearchParams({
        session_id: sessionId,
        include_global: "true",
        include_chat: "true",
      });
      const res = await fetch(`/v1/export/preview?${params}`);
      if (res.ok) setPreview((await res.json()) as ExportPreview);
    } catch {
      /* 预览失败不阻塞导出 */
    }
  }, [sessionId]);

  useEffect(() => {
    void refreshPreview();
  }, [refreshPreview]);

  const buildPayload = () => ({
    session_id: sessionId,
    title: title.trim() || "研究报告",
    include_global: true,
    include_chat: true,
    project_id: projectId || "default",
    use_ai: useAi && aiInstructions.trim().length > 0,
    ai_instructions: aiInstructions.trim() || null,
  });

  const handlePolishPreview = async () => {
    if (!sessionId) {
      setError("请先选择或新建一个会话");
      return;
    }
    if (!aiInstructions.trim()) {
      setError("请先填写 AI 润色要求");
      return;
    }
    if (preview && preview.entry_count === 0) {
      setError("暂无可导出内容，请先完成一轮研究对话");
      return;
    }
    setLoading("polish");
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/v1/export/polish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...buildPayload(), use_ai: true }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { markdown: string; ai_applied: boolean; message: string };
      setPolishPreview(data.markdown);
      setResult(data.message || (data.ai_applied ? "AI 润色预览已生成" : "已显示原稿预览"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 润色失败");
    } finally {
      setLoading(null);
    }
  };

  const handleExport = async (format: ExportFormat) => {
    if (!sessionId) {
      setError("请先选择或新建一个会话");
      return;
    }
    if (preview && preview.entry_count === 0) {
      setError("暂无可导出内容，请先完成一轮研究对话");
      return;
    }
    if (useAi && aiInstructions.trim() && format === "latex") {
      setError("LaTeX 导出暂不走 AI 润色，请使用 Markdown / Word / PDF");
      return;
    }
    setLoading(format);
    setError(null);
    setResult(null);
    const payload = buildPayload();
    try {
      if (format === "latex") {
        const res = await fetch("/v1/export/latex", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setResult(data.path || "已导出");
        if (data.latex) {
          await downloadBlob(new Blob([data.latex], { type: "text/plain" }), "export.tex");
        }
        await refreshPreview();
        return;
      }

      const res = await fetch(`/v1/export/${format}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const fallbackMap: Record<Exclude<ExportFormat, "latex">, string> = {
        md: "export.md",
        docx: "export.docx",
        pdf: "export.pdf",
      };
      const filename = parseFilename(res, fallbackMap[format as Exclude<ExportFormat, "latex">]);
      await downloadBlob(blob, filename);
      const aiNote = payload.use_ai ? "（已 AI 润色）" : "";
      setResult(`已下载 ${filename}${aiNote}`);
      await refreshPreview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="export-panel">
      <div className="panel-header">
        <h4>论文导出</h4>
      </div>

      <label className="settings-label">
        论文标题
        <input
          type="text"
          className="settings-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="研究报告"
        />
      </label>

      <div className="export-ai-box">
        <label className="pref-toggle">
          <input
            type="checkbox"
            checked={useAi}
            onChange={(e) => setUseAi(e.target.checked)}
          />
          导出前使用 AI 按以下要求润色
        </label>
        <label className="settings-label">
          AI 润色要求
          <textarea
            className="settings-input export-ai-input"
            rows={3}
            value={aiInstructions}
            onChange={(e) => setAiInstructions(e.target.value)}
            placeholder="例如：整理成论文摘要+引言+定理+结论；语言更学术；补充过渡句；保留所有公式"
            disabled={!useAi}
          />
        </label>
        {useAi && (
          <button
            type="button"
            className="btn-small"
            onClick={() => void handlePolishPreview()}
            disabled={loading !== null || !preview?.entry_count || !aiInstructions.trim()}
          >
            {loading === "polish" ? "润色中…" : "预览 AI 润色"}
          </button>
        )}
      </div>

      {polishPreview && useAi && (
        <div className="export-polish-preview">
          <p className="experiment-section-label">AI 润色预览</p>
          <MarkdownContent content={polishPreview} className="panel-markdown export-polish-md" />
        </div>
      )}

      {preview && (
        <div className="export-preview-box">
          <p>
            可导出 <strong>{preview.entry_count}</strong> 条内容
            {preview.session_structured_count > 0 && (
              <>（本会话定理 {preview.session_structured_count} 条</>
            )}
            {preview.global_structured_count > 0 && (
              <>，全局引理 {preview.global_structured_count} 条</>
            )}
            {preview.chat_message_count > 0 && preview.source === "chat_fallback" && (
              <>，对话记录 {preview.chat_message_count} 条</>
            )}
            {preview.session_structured_count > 0 || preview.global_structured_count > 0 ? (
              <>）</>
            ) : null}
          </p>
          <p className="panel-muted">{preview.hint}</p>
        </div>
      )}

      <div className="export-actions">
        <button
          type="button"
          className="btn-primary btn-block"
          onClick={() => handleExport("md")}
          disabled={loading !== null || !preview?.entry_count}
        >
          {loading === "md" ? "导出中…" : useAi && aiInstructions.trim() ? "AI 润色并导出 MD" : "导出 Markdown (.md)"}
        </button>
        <button
          type="button"
          className="btn-secondary btn-block"
          onClick={() => handleExport("latex")}
          disabled={loading !== null || !preview?.entry_count}
        >
          {loading === "latex" ? "导出中…" : "导出 LaTeX"}
        </button>
        <button
          type="button"
          className="btn-secondary btn-block"
          onClick={() => handleExport("docx")}
          disabled={loading !== null || !preview?.entry_count}
        >
          {loading === "docx" ? "导出中…" : useAi && aiInstructions.trim() ? "AI 润色并导出 Word" : "导出 Word (.docx)"}
        </button>
        <button
          type="button"
          className="btn-secondary btn-block"
          onClick={() => handleExport("pdf")}
          disabled={loading !== null || !preview?.entry_count}
        >
          {loading === "pdf" ? "导出中…" : useAi && aiInstructions.trim() ? "AI 润色并导出 PDF" : "导出 PDF"}
        </button>
      </div>
      {result && <p className="panel-success">{result}</p>}
      {error && <p className="panel-error">{error}</p>}

      <details className="export-help">
        <summary>如何使用导出？</summary>
        <ol className="export-help-list">
          <li>
            <strong>推荐流程</strong>：勾选 AI 润色并填写要求 → 预览 → 导出 Word/PDF。
          </li>
          <li>
            <strong>内容来源</strong>：优先导出定理库（L4）；无定理库时回退本会话 AI 回答。
          </li>
          <li>
            <strong>AI 润色</strong>：导出前额外调用一次大模型，按你的要求改写 Markdown，再转 Word/PDF。
          </li>
        </ol>
      </details>
    </div>
  );
}
