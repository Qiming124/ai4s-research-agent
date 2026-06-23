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
    id = crypto.randomUUID();
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

function readSessionList(): SessionMeta[] {
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

export function createNewSession(): string {
  const id = crypto.randomUUID();
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
