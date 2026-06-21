const BACKEND_HINT =
  "无法连接后端 API (http://127.0.0.1:8000)。请先启动：uvicorn server.main:app --reload --host 0.0.0.0 --port 8000";

export function formatBackendError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (
    msg === "Failed to fetch" ||
    msg.includes("NetworkError") ||
    msg.includes("ECONNREFUSED") ||
    msg.includes("502")
  ) {
    return BACKEND_HINT;
  }
  return msg;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch("/health", { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

export async function waitForBackend(
  maxAttempts = 8,
  intervalMs = 1500,
): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    if (await checkBackendHealth()) return true;
    if (i < maxAttempts - 1) {
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
  return false;
}
