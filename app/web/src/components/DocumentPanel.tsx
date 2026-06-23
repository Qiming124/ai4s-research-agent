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
  onDelete: (docId: string) => Promise<boolean>;
}

export function DocumentPanel({
  documents,
  loading,
  uploading,
  error,
  disabled = false,
  onRefresh,
  onUpload,
  onDelete,
}: DocumentPanelProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    if (!content.trim()) return;
    const ok = await onUpload(content.trim(), title.trim() || undefined);
    if (ok) {
      setTitle("");
      setContent("");
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setContent(text);
    if (!title) {
      setTitle(file.name.replace(/\.[^.]+$/, ""));
    }
    e.target.value = "";
  };

  return (
    <div className="document-panel">
      <div className="settings-section-head">
        <h3>RAG 文档</h3>
        <button type="button" className="btn-link" onClick={onRefresh} disabled={loading}>
          {loading ? "刷新中…" : "刷新"}
        </button>
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
        内容
        <textarea
          className="doc-content-input"
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={disabled || uploading}
          placeholder="粘贴 Markdown 或纯文本…"
        />
      </label>

      <div className="doc-upload-actions">
        <input
          ref={fileRef}
          type="file"
          accept=".md,.txt,.markdown"
          className="doc-file-input"
          onChange={handleFileChange}
          disabled={disabled || uploading}
        />
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => fileRef.current?.click()}
          disabled={disabled || uploading}
        >
          选择文件
        </button>
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
