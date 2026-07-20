/**
 * API 实验室运行历史（localStorage）。
 */

const STORAGE_KEY = "ai4s_api_lab_history";
const MAX_ITEMS = 40;

export interface ApiLabHistoryItem {
  id: string;
  at: number;
  method: string;
  path: string;
  requestUrl: string;
  status: number;
  durationMs: number;
  kind: string;
  /** 回填用 */
  paramValues: Record<string, string>;
  bodyText: string;
  operationId?: string;
}

export function loadHistory(): ApiLabHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw) as ApiLabHistoryItem[];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function saveHistory(items: ApiLabHistoryItem[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
}

export function pushHistory(
  item: Omit<ApiLabHistoryItem, "id" | "at">,
): ApiLabHistoryItem[] {
  const entry: ApiLabHistoryItem = {
    ...item,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: Date.now(),
  };
  const next = [entry, ...loadHistory()].slice(0, MAX_ITEMS);
  saveHistory(next);
  return next;
}

export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY);
}
