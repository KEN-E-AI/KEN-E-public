import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getActiveSessionId,
  setActiveSessionId,
  SESSION_ID_RE,
  LAST_SESSION_KEY,
  BOOT_UID_KEY,
} from "../useActiveChatSession";

// Deterministic in-memory storage (same helper pattern as Chat.spec.tsx).
function memoryStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => void store.clear(),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  };
}

function installMemoryStorage() {
  vi.stubGlobal("localStorage", memoryStorage());
  vi.stubGlobal("sessionStorage", memoryStorage());
}

describe("useActiveChatSession", () => {
  beforeEach(installMemoryStorage);
  afterEach(() => vi.unstubAllGlobals());

  describe("SESSION_ID_RE validator", () => {
    it("accepts valid alphanumeric session ids", () => {
      expect(SESSION_ID_RE.test("abc123")).toBe(true);
      expect(SESSION_ID_RE.test("session_id-foo")).toBe(true);
    });

    it("rejects ids with invalid characters", () => {
      expect(SESSION_ID_RE.test("bad id")).toBe(false);
      expect(SESSION_ID_RE.test("bad/id")).toBe(false);
      expect(SESSION_ID_RE.test("")).toBe(false);
    });

    it("rejects ids longer than 128 characters", () => {
      expect(SESSION_ID_RE.test("a".repeat(129))).toBe(false);
    });

    it("accepts ids up to 128 characters", () => {
      expect(SESSION_ID_RE.test("a".repeat(128))).toBe(true);
    });
  });

  describe("setActiveSessionId", () => {
    it("writes the session id to localStorage and the uid to sessionStorage", () => {
      setActiveSessionId("sess_abc", "user_1");
      expect(localStorage.getItem(LAST_SESSION_KEY)).toBe("sess_abc");
      expect(sessionStorage.getItem(BOOT_UID_KEY)).toBe("user_1");
    });

    it("overwrites previous values on a second call", () => {
      setActiveSessionId("sess_first", "user_1");
      setActiveSessionId("sess_second", "user_2");
      expect(localStorage.getItem(LAST_SESSION_KEY)).toBe("sess_second");
      expect(sessionStorage.getItem(BOOT_UID_KEY)).toBe("user_2");
    });

    it("does NOT write when the id fails SESSION_ID_RE (write-boundary guard)", () => {
      setActiveSessionId("bad id with spaces", "user_1");
      expect(localStorage.getItem(LAST_SESSION_KEY)).toBeNull();
      expect(sessionStorage.getItem(BOOT_UID_KEY)).toBeNull();
    });

    it("does NOT write when the id is empty", () => {
      setActiveSessionId("", "user_1");
      expect(localStorage.getItem(LAST_SESSION_KEY)).toBeNull();
    });
  });

  describe("getActiveSessionId", () => {
    it("returns null when nothing is stored", () => {
      expect(getActiveSessionId("user_1")).toBeNull();
    });

    it("returns null when the boot uid does not match the requested user", () => {
      setActiveSessionId("sess_abc", "user_other");
      expect(getActiveSessionId("user_1")).toBeNull();
    });

    it("returns the stored session id when the boot uid matches", () => {
      setActiveSessionId("sess_abc", "user_1");
      expect(getActiveSessionId("user_1")).toBe("sess_abc");
    });

    it("returns null when the stored session id fails the regex validator", () => {
      // Manually inject a bad id to simulate tampering.
      localStorage.setItem(LAST_SESSION_KEY, "bad id with spaces");
      sessionStorage.setItem(BOOT_UID_KEY, "user_1");
      expect(getActiveSessionId("user_1")).toBeNull();
    });

    it("returns null when sessionStorage throws (sandboxed environment)", () => {
      vi.stubGlobal("sessionStorage", {
        getItem: () => {
          throw new Error("QuotaExceededError");
        },
      });
      expect(getActiveSessionId("user_1")).toBeNull();
    });

    it("returns null when localStorage throws (sandboxed environment)", () => {
      // Boot uid is readable, but localStorage throws on the session read.
      vi.stubGlobal("sessionStorage", {
        getItem: () => "user_1",
      });
      vi.stubGlobal("localStorage", {
        getItem: () => {
          throw new Error("QuotaExceededError");
        },
      });
      expect(getActiveSessionId("user_1")).toBeNull();
    });
  });

  describe("round-trip: setActiveSessionId / getActiveSessionId", () => {
    it("setActiveSessionId → getActiveSessionId returns the same id for the same user", () => {
      setActiveSessionId("sess_roundtrip", "user_1");
      expect(getActiveSessionId("user_1")).toBe("sess_roundtrip");
    });

    it("a different user cannot read the stored session (boot uid gate)", () => {
      setActiveSessionId("sess_roundtrip", "user_1");
      expect(getActiveSessionId("user_2")).toBeNull();
    });
  });

  describe("account-scoped storage (backward compat)", () => {
    it("setActiveSessionId with accountId stores JSON; getActiveSessionId with same accountId returns the id", () => {
      setActiveSessionId("sess_1", "user_1", "acct_1");
      expect(getActiveSessionId("user_1", "acct_1")).toBe("sess_1");
    });

    it("getActiveSessionId with a different accountId returns null (account isolation)", () => {
      setActiveSessionId("sess_1", "user_1", "acct_1");
      expect(getActiveSessionId("user_1", "acct_2")).toBeNull();
    });

    it("getActiveSessionId without accountId returns the id even when storage has accountId (no restriction)", () => {
      setActiveSessionId("sess_1", "user_1", "acct_1");
      expect(getActiveSessionId("user_1")).toBe("sess_1");
    });

    it("legacy plain-string value is readable by a caller that provides accountId (backward compat)", () => {
      // Simulate storage written by the old code that didn't store accountId.
      localStorage.setItem(LAST_SESSION_KEY, "legacy_sess");
      sessionStorage.setItem(BOOT_UID_KEY, "user_1");
      // No storedAccountId → skip isolation check → return the id.
      expect(getActiveSessionId("user_1", "any_acct")).toBe("legacy_sess");
    });

    it("raw-injected JSON with mismatched accountId is rejected", () => {
      localStorage.setItem(
        LAST_SESSION_KEY,
        JSON.stringify({ id: "sess_acct_A", accountId: "acct_A" }),
      );
      sessionStorage.setItem(BOOT_UID_KEY, "user_1");
      expect(getActiveSessionId("user_1", "acct_B")).toBeNull();
    });

    it("setActiveSessionId without accountId still writes plain string (backward compat)", () => {
      setActiveSessionId("sess_plain", "user_1");
      expect(localStorage.getItem(LAST_SESSION_KEY)).toBe("sess_plain");
    });

    it("setActiveSessionId with accountId writes JSON with id field", () => {
      setActiveSessionId("sess_json", "user_1", "acct_1");
      const raw = localStorage.getItem(LAST_SESSION_KEY);
      const parsed = JSON.parse(raw!);
      expect(parsed.id).toBe("sess_json");
      expect(parsed.accountId).toBe("acct_1");
    });
  });
});
