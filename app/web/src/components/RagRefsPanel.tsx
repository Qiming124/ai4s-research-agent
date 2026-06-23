import type { RagRef } from "../hooks/useRagRefs";

interface RagRefsPanelProps {
  refs: RagRef[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  disabled?: boolean;
}

export function RagRefsPanel({
  refs,
  loading,
  error,
  onRefresh,
  disabled = false,
}: RagRefsPanelProps) {
  return (
    <div className="rag-refs-panel">
      <div className="settings-section-head">
        <h3>RAG 引用</h3>
        <button
          type="button"
          className="btn-link"
          onClick={onRefresh}
          disabled={loading || disabled}
        >
          {loading ? "加载中…" : "刷新"}
        </button>
      </div>
      <p className="settings-hint">本会话检索注入的文档片段（需 ENABLE_RAG=true）</p>
      {error && <p className="settings-error">加载失败：{error}</p>}
      {refs.length === 0 && !loading && !error && (
        <p className="settings-hint">暂无引用记录</p>
      )}
      <ul className="rag-refs-list">
        {refs.map((ref, idx) => (
          <li key={`${ref.doc_id}-${idx}`} className="rag-ref-item">
            <code className="rag-ref-doc">{ref.doc_id}</code>
            {ref.snippet && <p className="rag-ref-snippet">{ref.snippet}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
