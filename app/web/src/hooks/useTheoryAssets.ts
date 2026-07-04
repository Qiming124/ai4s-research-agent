import { useCallback, useEffect, useState } from "react";
import { formatBackendError } from "../utils/backend";

export function useTheoryAssets(enabled: boolean) {
  const [symbols, setSymbols] = useState("");
  const [assumptions, setAssumptions] = useState("");
  const [matrix, setMatrix] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const [sym, asm, mat] = await Promise.all([
        fetch("/v1/theory/symbols"),
        fetch("/v1/theory/assumptions"),
        fetch("/v1/theory/assumption-matrix"),
      ]);
      if (sym.ok) setSymbols(await sym.text());
      if (asm.ok) setAssumptions(await asm.text());
      if (mat.ok) setMatrix(await mat.text());
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { symbols, assumptions, matrix, loading, error, refresh };
}
