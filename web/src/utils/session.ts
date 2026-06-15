const SESSION_KEY = "ai4s_session_id";

export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function setSessionId(id: string): void {
  localStorage.setItem(SESSION_KEY, id);
}

export function shortSessionId(id: string): string {
  return id.slice(0, 8);
}
