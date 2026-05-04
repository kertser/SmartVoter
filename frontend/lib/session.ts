/**
 * Anonymous session management using localStorage.
 * No login required. (AGENTS.MD Section 14C.1)
 */

const SESSION_KEY = "sv_session_id";

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const newId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, newId);
  return newId;
}

export function clearSession(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(SESSION_KEY);
  }
}

