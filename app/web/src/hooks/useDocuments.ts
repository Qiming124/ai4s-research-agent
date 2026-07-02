import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface DocumentInfo {
  doc_id: string;
  session_id: string;
  title: string;
  source: string;
  chunk_count: number;
  created_at: string;
}

export function useDocuments(sessionId: string | null, enabled = true) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled || !sessionId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/v1/documents?session_id=${encodeURIComponent(sessionId)}`,
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as { documents: DocumentInfo[] };
      setDocuments(data.documents ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const uploadDocument = useCallback(
    async (content: string, title?: string) => {
      if (!sessionId) {
        setError("请先选择或创建会话");
        return false;
      }
      setUploading(true);
      setError(null);
      try {
        const res = await fetch("/v1/documents", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            content,
            title: title || undefined,
          }),
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        await refresh();
        return true;
      } catch (err) {
        setError(formatBackendError(err));
        return false;
      } finally {
        setUploading(false);
      }
    },
    [refresh, sessionId],
  );

  const deleteDocument = useCallback(
    async (docId: string) => {
      if (!sessionId) {
        return false;
      }
      setError(null);
      try {
        const res = await fetch(
          `/v1/documents/${encodeURIComponent(docId)}?session_id=${encodeURIComponent(sessionId)}`,
          { method: "DELETE" },
        );
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        await refresh();
        return true;
      } catch (err) {
        setError(formatBackendError(err));
        return false;
      }
    },
    [refresh, sessionId],
  );

  const clearAllDocuments = useCallback(async () => {
    if (!sessionId) {
      return false;
    }
    setError(null);
    try {
      const res = await fetch(
        `/v1/documents/session/${encodeURIComponent(sessionId)}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      await refresh();
      return true;
    } catch (err) {
      setError(formatBackendError(err));
      return false;
    }
  }, [refresh, sessionId]);

  return {
    documents,
    loading,
    error,
    uploading,
    refresh,
    uploadDocument,
    deleteDocument,
    clearAllDocuments,
  };
}
