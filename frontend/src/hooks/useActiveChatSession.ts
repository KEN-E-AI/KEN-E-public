/**
 * Shared active-session resolver for the chat system.
 *
 * Both the /chat page (Chat.tsx) and the mini-widget (LayoutC.tsx) use the same
 * two storage keys so they share one continuous session across surfaces.
 *
 * Storage design:
 * - LAST_SESSION_KEY (localStorage) — persists the most recently active session
 *   id across browser sessions for the same login, enabling "resume where you left
 *   off" within a login. Supports two formats:
 *     New:    JSON {"id":"...", "accountId":"..."} — written when accountId is provided
 *     Legacy: plain string                          — written without accountId
 * - BOOT_UID_KEY (sessionStorage) — per-tab marker that records which user already
 *   has an active chat in *this* browser session. Resets on new login (fresh
 *   sessionStorage) so the user starts fresh on each login.
 *
 * SESSION_ID_RE validates session ids before reading or writing them — prevents
 * XSS or unexpected values from reaching the API.
 */

export const LAST_SESSION_KEY = "kene_chat_last_session";
export const BOOT_UID_KEY = "kene_chat_boot_uid";
export const SESSION_ID_RE = /^[a-zA-Z0-9_-]{1,128}$/;

/**
 * Read the last-active session id for the given user.
 * When `accountId` is provided, the stored accountId must match to return a value
 * (cross-account isolation). Legacy plain-string values (written without accountId)
 * skip the account check for backward compatibility.
 * Returns null when:
 * - No id is stored (new login or first visit).
 * - The stored boot uid doesn't match the current user.
 * - The stored id fails the SESSION_ID_RE validation.
 * - accountId is provided, storage has a different accountId (account isolation).
 */
export function getActiveSessionId(
  userId: string,
  accountId?: string,
): string | null {
  try {
    if (sessionStorage.getItem(BOOT_UID_KEY) !== userId) return null;
    const rawValue = localStorage.getItem(LAST_SESSION_KEY);
    if (!rawValue) return null;

    // Parse stored value — supports two formats:
    //   New:    JSON {"id":"...", "accountId":"..."} — written when accountId is provided
    //   Legacy: plain string                          — written without accountId
    let sid: string;
    let storedAccountId: string | undefined;
    try {
      const parsed: unknown = JSON.parse(rawValue);
      if (
        parsed !== null &&
        typeof parsed === "object" &&
        "id" in parsed &&
        typeof (parsed as { id: unknown }).id === "string"
      ) {
        sid = (parsed as { id: string; accountId?: string }).id;
        storedAccountId = (parsed as { id: string; accountId?: string })
          .accountId;
      } else {
        sid = rawValue; // unexpected JSON shape — treat as legacy
      }
    } catch {
      sid = rawValue; // not JSON — legacy plain-string format
    }

    // Account isolation: when both caller and storage have an accountId, reject mismatches.
    // Legacy plain-string values (storedAccountId === undefined) skip this check.
    if (
      accountId !== undefined &&
      storedAccountId !== undefined &&
      storedAccountId !== accountId
    ) {
      return null;
    }

    return SESSION_ID_RE.test(sid) ? sid : null;
  } catch {
    return null;
  }
}

/**
 * Persist a session id as the active session for the given user.
 * When `accountId` is provided, it is stored alongside the id so that
 * a later getActiveSessionId call with a different accountId is rejected.
 * Writes both keys so that a later getActiveSessionId call with the same
 * userId resumes this session.
 */
export function setActiveSessionId(
  id: string,
  userId: string,
  accountId?: string,
): void {
  if (!SESSION_ID_RE.test(id)) return; // reject invalid ids at the write boundary
  // Defense-in-depth: never durably persist a pending_ placeholder. A pending_
  // id passes SESSION_ID_RE but is valid for only a single /completions call;
  // storing it would poison the resume marker and silently create a new empty
  // session on every reload, for both /chat and the mini-widget (CH-62).
  if (id.startsWith("pending_")) return;
  try {
    const value =
      accountId !== undefined ? JSON.stringify({ id, accountId }) : id;
    localStorage.setItem(LAST_SESSION_KEY, value);
    sessionStorage.setItem(BOOT_UID_KEY, userId);
  } catch {
    // Storage unavailable (sandboxed / private browsing) — ignore.
  }
}
