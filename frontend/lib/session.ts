/**
 * Anonymous session management using localStorage.
 * No login required. (AGENTS.MD Section 14C.1)
 */

const SESSION_KEY = "sv_session_id";
const COMPLETED_SESSION_KEY = "sv_completed_session_id";

/**
 * Generate a UUID v4.
 * Uses crypto.randomUUID() when available (secure context: HTTPS / localhost).
 * Falls back to a Math.random()-based implementation for plain-HTTP deployments
 * where the Web Crypto API is not available.
 */
function generateUUID(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  // RFC 4122 v4 fallback (Math.random — sufficient for anonymous session IDs)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

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
  const newId = generateUUID();
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
