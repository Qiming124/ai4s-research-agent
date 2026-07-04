import { useRef, useState } from "react";
import type { DocumentInfo } from "../hooks/useDocuments";

interface DocumentPanelProps {
  documents: DocumentInfo[];
  loading: boolean;
  uploading: boolean;
  error: string | null;
  disabled?: boolean;
  onRefresh: () => void;
  onUpload: (content: string, title?: string) => Promise<boolean>;
  onUploadFile?: (file: File, title?: string) => Promise<boolean>;
  onIngestArxiv?: (arxivId: string, title?: string) => Promise<boolean>;
  onDelete: (docId: string) => Promise<boolean>;
  onClearAll?: () => Promise<boolean>;
}

const BINARY_ACCEPT = ".pdf,.docx,.md,.txt,.markdown";

export function DocumentPanel({
  documents,
  loading,
  uploading,
  error,
  disabled = false,
  onRefresh,
  onUpload,
  onUploadFile,
  onIngestArxiv,
  onDelete,
  onClearAll,
}: DocumentPanelProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const textFileRef = useRef<HTMLInputElement>(null);
  const binaryFileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    if (!content.trim()) return;
    const ok = await onUpload(content.trim(), title.trim() || undefined);
    if (ok) {
      setTitle("");
      setContent("");
    }
  };

  const handleTextFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setContent(text);
    if (!title) {
      setTitle(file.name.replace(/\.[^.]+$/, ""));
    }
    e.target.value = "";
  };

  const handleBinaryFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onUploadFile) return;
    const ok = await onUploadFile(file, title.trim() || file.name.replace(/\.[^.]+$/, ""));
    if (ok) {
      setTitle("");
      setContent("");
    }
    e.target.value = "";
  };

  const [arxivId, setArxivId] = useState("");

  const handleArxiv = async () => {
    if (!onIngestArxiv || !arxivId.trim()) return;
    const ok = await onIngestArxiv(arxivId.trim(), title.trim() || undefined);
    if (ok) {
      setArxivId("");
      setTitle("");
    }
  };

  return (
    <div className="document-panel">
      <div className="settings-section-head">
        <h3>RAG 文档</h3>
        <div className="doc-list-actions">
          {onClearAll && documents.length > 0 && (
            <button
              type="button"
              className="btn-link doc-clear-all-btn"
              onClick={() => {
                if (window.confirm("确定清空全部 RAG 索引文档？")) {
                  void onClearAll();
                }
              }}
              disabled={disabled}
            >
              清空全部
            </button>
          )}
          <button type="button" className="btn-link" onClick={onRefresh} disabled={loading}>
            {loading ? "刷新中…" : "刷新"}
          </button>
        </div>
      </div>

      <label className="settings-field doc-upload-field">
        标题（可选）
        <input
          type="text"
          className="doc-title-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={disabled || uploading}
          placeholder="文档标题"
        />
      </label>

      <label className="settings-field doc-upload-field">
        内容（文本粘贴）
        <textarea
          className="doc-content-input"
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={disabled || uploading}
          placeholder="粘贴 Markdown 或纯文本…"
        />
      </label>

      <div className="inline-form">
        <input
          className="inline-form-input"
          placeholder="arXiv ID（如 2301.00001）"
          value={arxivId}
          disabled={disabled || uploading || !onIngestArxiv}
          onChange={(e) => setArxivId(e.target.value)}
        />
        <button
          type="button"
          className="btn-small btn-primary"
          disabled={disabled || uploading || !arxivId.trim() || !onIngestArxiv}
          onClick={() => void handleArxiv()}
        >
          {uploading ? "导入中…" : "arXiv 导入"}
        </button>
      </div>

      <div className="doc-upload-actions">
        <input
          ref={textFileRef}
          type="file"
          accept=".md,.txt,.markdown"
          className="doc-file-input"
          onChange={handleTextFileChange}
          disabled={disabled || uploading}
        />
        <input
          ref={binaryFileRef}
          type="file"
          accept={BINARY_ACCEPT}
          className="doc-file-input"
          onChange={handleBinaryFileChange}
          disabled={disabled || uploading || !onUploadFile}
        />
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => textFileRef.current?.click()}
          disabled={disabled || uploading}
        >
          文本文件
        </button>
        {onUploadFile && (
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => binaryFileRef.current?.click()}
            disabled={disabled || uploading}
          >
            PDF / Word
          </button>
        )}
        <button
          type="button"
          className="btn-primary btn-sm"
          onClick={handleUpload}
          disabled={disabled || uploading || !content.trim()}
        >
          {uploading ? "索引中…" : "上传索引"}
        </button>
      </div>

      {error && <p className="settings-error">{error}</p>}
      <p className="settings-hint">
        支持 PDF、DOCX、Markdown、纯文本导入并自动解析入库；也可粘贴文本后上传索引。
      </p>

      <ul className="doc-list">
        {documents.length === 0 && !loading && (
          <li className="doc-empty">暂无已索引文档</li>
        )}
        {documents.map((doc) => (
          <li key={doc.doc_id} className="doc-item">
            <div className="doc-item-main">
              <span className="doc-item-title">{doc.title || doc.doc_id}</span>
              <span className="doc-item-meta">
                {doc.chunk_count} 块 · {doc.doc_id.slice(0, 8)}
              </span>
            </div>
            <button
              type="button"
              className="btn-link doc-delete-btn"
              onClick={() => onDelete(doc.doc_id)}
              disabled={disabled}
            >
              删除
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
