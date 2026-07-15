import { randomUUID } from "./id";

const SESSION_KEY = "ai4s_session_id";
const SESSION_LIST_KEY = "ai4s_session_list";

export interface SessionMeta {
  id: string;
  title: string;
  updatedAt: number;
}

export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = randomUUID();
    localStorage.setItem(SESSION_KEY, id);
    ensureSessionInList(id);
  }
  return id;
}

export function setSessionId(id: string): void {
  localStorage.setItem(SESSION_KEY, id);
  ensureSessionInList(id);
}

export function shortSessionId(id: string): string {
  return id.slice(0, 8);
}

/** 读取 localStorage 会话列表（无副作用，不会自动补全当前会话） */
export function readSessionList(): SessionMeta[] {
  try {
    const raw = localStorage.getItem(SESSION_LIST_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SessionMeta[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeSessionList(list: SessionMeta[]): void {
  localStorage.setItem(SESSION_LIST_KEY, JSON.stringify(list));
}

function ensureSessionInList(id: string): void {
  const list = readSessionList();
  if (list.some((s) => s.id === id)) return;
  list.unshift({
    id,
    title: `会话 ${shortSessionId(id)}`,
    updatedAt: Date.now(),
  });
  writeSessionList(list);
}

export function getSessionList(): SessionMeta[] {
  const currentId = getSessionId();
  const list = readSessionList();
  if (!list.some((s) => s.id === currentId)) {
    ensureSessionInList(currentId);
    return readSessionList().sort((a, b) => b.updatedAt - a.updatedAt);
  }
  return list.sort((a, b) => b.updatedAt - a.updatedAt);
}

export function updateSessionMeta(id: string, patch: Partial<Pick<SessionMeta, "title" | "updatedAt">>): void {
  const list = readSessionList();
  const idx = list.findIndex((s) => s.id === id);
  if (idx === -1) {
    list.unshift({
      id,
      title: patch.title ?? `会话 ${shortSessionId(id)}`,
      updatedAt: patch.updatedAt ?? Date.now(),
    });
  } else {
    list[idx] = { ...list[idx], ...patch, updatedAt: patch.updatedAt ?? Date.now() };
  }
  writeSessionList(list);
}

export function removeSessionFromList(id: string): void {
  writeSessionList(readSessionList().filter((s) => s.id !== id));
}

export async function fetchServerSessions(): Promise<SessionMeta[]> {
  const res = await fetch("/v1/sessions");
  if (!res.ok) return [];
  const data = await res.json();
  const sessions = Array.isArray(data.sessions) ? data.sessions : [];
  return sessions.map((item: { session_id: string; updated_at?: string }) => ({
    id: item.session_id,
    title: `会话 ${shortSessionId(item.session_id)}`,
    updatedAt: item.updated_at ? Date.parse(item.updated_at) : Date.now(),
  }));
}

export function mergeSessionLists(local: SessionMeta[], server: SessionMeta[]): SessionMeta[] {
  const map = new Map<string, SessionMeta>();
  for (const item of [...local, ...server]) {
    const existing = map.get(item.id);
    if (!existing) {
      map.set(item.id, item);
      continue;
    }
    const newer =
      item.updatedAt >= existing.updatedAt
        ? { ...item, title: existing.title.startsWith("会话") ? item.title : existing.title }
        : existing;
    map.set(item.id, newer);
  }
  return Array.from(map.values()).sort((a, b) => b.updatedAt - a.updatedAt);
}

/** 同步 localStorage：仅保留服务端有记录的会话 + 当前活跃会话（去掉历史孤儿 UUID） */
export function syncSessionListWithServer(
  server: SessionMeta[],
  currentSessionId: string,
): SessionMeta[] {
  const serverIds = new Set(server.map((s) => s.id));
  const merged = mergeSessionLists(readSessionList(), server);
  const pruned = merged.filter((s) => serverIds.has(s.id) || s.id === currentSessionId);
  writeSessionList(pruned);
  return pruned;
}

export function createNewSession(): string {
  const id = randomUUID();
  const meta: SessionMeta = {
    id,
    title: `新会话 ${shortSessionId(id)}`,
    updatedAt: Date.now(),
  };
  const list = readSessionList();
  list.unshift(meta);
  writeSessionList(list);
  localStorage.setItem(SESSION_KEY, id);
  return id;
}
