import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface StructuredMemoryEntry {
  id: number;
  session_id: string | null;
  kind: string;
  title: string;
  body: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface ImportCandidate {
  kind: string;
  title: string;
  body: string;
  page?: number | null;
  confidence?: number;
  selected_default?: boolean;
}

export interface ImportPreviewResult {
  filename: string;
  text_chars: number;
  truncated: boolean;
  candidates: ImportCandidate[];
  warnings: string[];
}

export function useStructuredMemory(sessionId: string, enabled: boolean) {
  const [entries, setEntries] = useState<StructuredMemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const params = new URLSearchParams({ session_id: sessionId, limit: "50" });
      const res = await fetch(`/v1/memory/structured?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEntries(data.entries ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId, enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createEntry = useCallback(
    async (payload: {
      kind: string;
      title: string;
      body: string;
      metadata?: Record<string, unknown>;
    }) => {
      const res = await fetch("/v1/memory/structured", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId || null,
          kind: payload.kind,
          title: payload.title,
          body: payload.body,
          metadata: { source: "manual", status: "draft", ...(payload.metadata || {}) },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const created = (await res.json()) as StructuredMemoryEntry;
      await refresh();
      return created;
    },
    [sessionId, refresh],
  );

  const updateEntry = useCallback(
    async (
      id: number,
      payload: {
        kind?: string;
        title?: string;
        body?: string;
        metadata?: Record<string, unknown>;
      },
    ) => {
      const res = await fetch(`/v1/memory/structured/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated = (await res.json()) as StructuredMemoryEntry;
      await refresh();
      return updated;
    },
    [refresh],
  );

  const deleteEntry = useCallback(
    async (id: number) => {
      const res = await fetch(`/v1/memory/structured/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      await refresh();
    },
    [refresh],
  );

  const previewMarkdown = useCallback(async (content: string) => {
    const res = await fetch("/v1/memory/structured/preview-markdown", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(await res.text());
    return (await res.json()) as ImportPreviewResult;
  }, []);

  const previewFile = useCallback(
    async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      if (sessionId) form.append("session_id", sessionId);
      const res = await fetch("/v1/memory/structured/import-preview", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      return (await res.json()) as ImportPreviewResult;
    },
    [sessionId],
  );

  const confirmImport = useCallback(
    async (
      candidates: ImportCandidate[],
      source: "markdown_import" | "pdf_import",
      extraMeta?: Record<string, unknown>,
    ) => {
      let ok = 0;
      const errors: string[] = [];
      for (const c of candidates) {
        try {
          const res = await fetch("/v1/memory/structured", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId || null,
              kind: c.kind || "theorem",
              title: c.title || "",
              body: c.body,
              metadata: {
                source,
                status: "draft",
                import_page: c.page ?? undefined,
                ...(extraMeta || {}),
              },
            }),
          });
          if (!res.ok) throw new Error(await res.text());
          ok += 1;
        } catch (e) {
          errors.push(e instanceof Error ? e.message : String(e));
        }
      }
      await refresh();
      return { ok, errors };
    },
    [sessionId, refresh],
  );

  return {
    entries,
    loading,
    error,
    refresh,
    createEntry,
    updateEntry,
    deleteEntry,
    previewMarkdown,
    previewFile,
    confirmImport,
  };
}
