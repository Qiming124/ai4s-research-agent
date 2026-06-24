import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface DocumentInfo {
  doc_id: string;
  title: string;
  source: string;
  chunk_count: number;
  created_at: string;
}

export function useDocuments(enabled = true) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/v1/documents");
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
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const uploadDocument = useCallback(
    async (content: string, title?: string) => {
      setUploading(true);
      setError(null);
      try {
        const res = await fetch("/v1/documents", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content, title: title || undefined }),
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
    [refresh],
  );

  const deleteDocument = useCallback(
    async (docId: string) => {
      setError(null);
      try {
        const res = await fetch(`/v1/documents/${encodeURIComponent(docId)}`, {
          method: "DELETE",
        });
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
    [refresh],
  );

  const clearAllDocuments = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch("/v1/documents?purge=true", { method: "DELETE" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      await refresh();
      return true;
    } catch (err) {
      setError(formatBackendError(err));
      return false;
    }
  }, [refresh]);

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
