import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface DocumentInfo {
  doc_id: string;
  session_id: string;
  project_id?: string;
  title: string;
  source: string;
  chunk_count: number;
  created_at: string;
}

export function useDocuments(
  sessionId: string | null,
  enabled = true,
  projectId?: string | null,
) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled || (!sessionId && !projectId)) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (projectId) params.set("project_id", projectId);
      if (sessionId) params.set("session_id", sessionId);
      const res = await fetch(`/v1/documents?${params}`);
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
  }, [enabled, sessionId, projectId]);

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
            project_id: projectId || undefined,
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
    [refresh, sessionId, projectId],
  );

  const uploadFile = useCallback(
    async (file: File, title?: string) => {
      if (!sessionId) {
        setError("请先选择或创建会话");
        return false;
      }
      setUploading(true);
      setError(null);
      try {
        const form = new FormData();
        form.append("session_id", sessionId);
        if (projectId) form.append("project_id", projectId);
        form.append("file", file);
        if (title) form.append("title", title);
        const res = await fetch("/v1/documents/upload", {
          method: "POST",
          body: form,
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
    [refresh, sessionId, projectId],
  );

  const uploadFromArxiv = useCallback(
    async (arxivId: string, title?: string) => {
      if (!sessionId) {
        setError("请先选择或创建会话");
        return false;
      }
      setUploading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          session_id: sessionId,
          arxiv_id: arxivId,
        });
        if (title) params.set("title", title);
        if (projectId) params.set("project_id", projectId);
        const res = await fetch(`/v1/documents/from-arxiv?${params}`, { method: "POST" });
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
    [refresh, sessionId, projectId],
  );

  const deleteDocument = useCallback(
    async (docId: string) => {
      if (!sessionId) return false;
      try {
        const res = await fetch(
          `/v1/documents/${encodeURIComponent(docId)}?session_id=${encodeURIComponent(sessionId)}`,
          { method: "DELETE" },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await refresh();
        return true;
      } catch (err) {
        setError(formatBackendError(err));
        return false;
      }
    },
    [refresh, sessionId],
  );

  const clearSessionDocuments = useCallback(async () => {
    if (!sessionId) return false;
    try {
      const res = await fetch(
        `/v1/documents/session/${encodeURIComponent(sessionId)}`,
        { method: "DELETE" },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
    uploadFile,
    uploadFromArxiv,
    ingestArxiv: uploadFromArxiv,
    deleteDocument,
    clearSessionDocuments,
    clearAllDocuments: clearSessionDocuments,
  };
}
