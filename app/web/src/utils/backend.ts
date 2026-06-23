/**
 * 后端连接与错误提示工具。
 */

const BACKEND_HINT =
  "无法连接后端 API (http://127.0.0.1:8000)。请先启动：uvicorn server.main:app --reload --host 0.0.0.0 --port 8000";

/**
 * 将 fetch 异常格式化为用户可读的中文提示。
 *
 * @param err - 捕获的异常
 * @returns 友好错误文案
 */
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

/**
 * 探测 GET /health 是否可用。
 *
 * @returns true 表示 HTTP 2xx
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch("/health", { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * 轮询等待后端就绪（用于页面初始化）。
 *
 * @param maxAttempts - 最大尝试次数，默认 8
 * @param intervalMs - 每次间隔毫秒，默认 1500
 * @returns 是否在时限内连上后端
 */
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
