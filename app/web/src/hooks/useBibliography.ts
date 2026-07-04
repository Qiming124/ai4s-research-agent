import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export interface BibEntry {
  id: string;
  title: string;
  authors: string;
  year: string;
  arxiv_id: string;
  notes: string;
}

export function useBibliography(projectId: string, enabled: boolean) {
  const [entries, setEntries] = useState<BibEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/v1/bibliography?project_id=${encodeURIComponent(projectId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEntries(data.entries ?? []);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const exportBib = async () => {
    const res = await fetch(`/v1/bibliography/export.bib?project_id=${encodeURIComponent(projectId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "references.bib";
    a.click();
    URL.revokeObjectURL(url);
  };

  return { entries, loading, error, refresh, exportBib };
}
