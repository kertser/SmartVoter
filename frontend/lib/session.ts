/**
 * Anonymous session management using localStorage.
 * No login required. (AGENTS.MD Section 14C.1)
 */

const SESSION_KEY = "sv_session_id";
const COMPLETED_SESSION_KEY = "sv_completed_session_id";

/**
 * Active session ID is stored in sessionStorage (tab-scoped) so that each
 * new browser tab / fresh page load starts with a clean slate.
 * A returning user's previous *completed* session remains in localStorage
 * and is offered separately via the "View previous results" button.
 */
export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const newId = crypto.randomUUID();
  sessionStorage.setItem(SESSION_KEY, newId);
  return newId;
}

export function clearSession(): void {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(SESSION_KEY);
  }
}

/** Call when results are successfully loaded — marks this session as "completed". */
export function saveCompletedSessionId(id: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(COMPLETED_SESSION_KEY, id);
  }
}

/** Returns the last session for which results were loaded, or null. */
export function getCompletedSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(COMPLETED_SESSION_KEY);
}

/** Removes the stored completed-session reference. */
export function clearCompletedSession(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(COMPLETED_SESSION_KEY);
  }
}
