import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import {
  readDevOverrides,
  getDevOverride,
  SESSION_STORAGE_KEY,
} from "./devOverride";

const SESSION_KEY = SESSION_STORAGE_KEY;

function setUrl(search: string): void {
  window.history.replaceState({}, "", search || "/");
}

beforeEach(() => {
  sessionStorage.clear();
  setUrl("/");
  vi.unstubAllEnvs();
  vi.stubEnv("VITE_ENVIRONMENT", "development");
});

afterEach(() => {
  vi.unstubAllEnvs();
  sessionStorage.clear();
  setUrl("/");
});

describe("readDevOverrides", () => {
  describe("URL param parsing", () => {
    it("parses ?ff.foo=on → { foo: true }", () => {
      setUrl("/?ff.foo=on");
      expect(readDevOverrides()).toEqual({ foo: true });
    });

    it("parses ?ff.foo=off → { foo: false }", () => {
      setUrl("/?ff.foo=off");
      expect(readDevOverrides()).toEqual({ foo: false });
    });

    it("parses ?ff.foo=off&ff.bar=on → { foo: false, bar: true }", () => {
      setUrl("/?ff.foo=off&ff.bar=on");
      expect(readDevOverrides()).toEqual({ foo: false, bar: true });
    });

    it("ignores ?ff.foo=maybe (non-binary value)", () => {
      setUrl("/?ff.foo=maybe");
      const result = readDevOverrides();
      expect(result).not.toHaveProperty("foo");
    });

    it("ignores params that do not start with ff.", () => {
      setUrl("/?other=on&notff.foo=on");
      expect(readDevOverrides()).toEqual({});
    });

    it("ignores invalid FlagKey (uppercase / hyphens) and warns in dev", () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      setUrl("/?ff.BAD-KEY=on");
      const result = readDevOverrides();
      expect(result).not.toHaveProperty("BAD-KEY");
      expect(warn).toHaveBeenCalledOnce();
      warn.mockRestore();
    });

    it("ignores invalid FlagKey without warning in production", () => {
      vi.stubEnv("VITE_ENVIRONMENT", "production");
      setUrl("/?ff.BAD-KEY=on");
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      const result = readDevOverrides();
      // production returns {} regardless
      expect(result).toEqual({});
      expect(warn).not.toHaveBeenCalled();
      warn.mockRestore();
    });
  });

  describe("sessionStorage persistence", () => {
    it("writes parsed overrides to sessionStorage under kene.ff-overrides", () => {
      setUrl("/?ff.foo=on");
      readDevOverrides();
      const stored = sessionStorage.getItem(SESSION_KEY);
      expect(stored).not.toBeNull();
      expect(JSON.parse(stored!)).toEqual({ foo: true });
    });

    it("returns persisted override when URL param is absent (clearing the URL does not clear the override)", () => {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ foo: true }));
      setUrl("/"); // no URL params
      expect(readDevOverrides()).toEqual({ foo: true });
    });

    it("URL override shadows sessionStorage: prior {foo:true} + URL ?ff.foo=off → { foo: false }", () => {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ foo: true }));
      setUrl("/?ff.foo=off");
      expect(readDevOverrides()).toEqual({ foo: false });
    });

    it("merges URL and sessionStorage: persisted {bar:true} + URL ?ff.foo=on → { foo: true, bar: true }", () => {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ bar: true }));
      setUrl("/?ff.foo=on");
      expect(readDevOverrides()).toEqual({ foo: true, bar: true });
    });
  });

  describe("sessionStorage key re-validation", () => {
    it("strips invalid keys when restoring from sessionStorage", () => {
      sessionStorage.setItem(
        SESSION_KEY,
        JSON.stringify({ "BAD-KEY": true, foo: false }),
      );
      setUrl("/");
      const result = readDevOverrides();
      expect(result).not.toHaveProperty("BAD-KEY");
      expect(result).toEqual({ foo: false });
    });

    it("strips __proto__ keys from stored JSON (prototype pollution guard)", () => {
      // JSON.parse of {"__proto__": true} technically sets a key named "__proto__";
      // tryFlagKey rejects it since it does not match FLAG_KEY_REGEX.
      sessionStorage.setItem(SESSION_KEY, '{"__proto__": true, "foo": false}');
      setUrl("/");
      const result = readDevOverrides();
      expect(result).not.toHaveProperty("__proto__");
      expect(result).toEqual({ foo: false });
    });
  });

  describe("production hard-gate", () => {
    it("returns {} in production", () => {
      vi.stubEnv("VITE_ENVIRONMENT", "production");
      setUrl("/?ff.foo=on");
      expect(readDevOverrides()).toEqual({});
    });

    it("never reads sessionStorage in production", () => {
      vi.stubEnv("VITE_ENVIRONMENT", "production");
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ foo: true }));
      const getSpy = vi.spyOn(Storage.prototype, "getItem");
      readDevOverrides();
      expect(getSpy).not.toHaveBeenCalled();
      getSpy.mockRestore();
    });

    it("never writes sessionStorage in production", () => {
      vi.stubEnv("VITE_ENVIRONMENT", "production");
      setUrl("/?ff.foo=on");
      const setSpy = vi.spyOn(Storage.prototype, "setItem");
      readDevOverrides();
      expect(setSpy).not.toHaveBeenCalled();
      setSpy.mockRestore();
    });
  });

  describe("error resilience", () => {
    it("falls back to URL-only parsing when sessionStorage contains corrupted JSON", () => {
      sessionStorage.setItem(SESSION_KEY, "NOT_VALID_JSON{{{");
      setUrl("/?ff.foo=on");
      const result = readDevOverrides();
      // URL override still visible; corrupted storage silently ignored
      expect(result).toEqual({ foo: true });
    });

    it("does not throw when sessionStorage.getItem throws", () => {
      vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
        throw new Error("storage error");
      });
      setUrl("/?ff.foo=on");
      expect(() => readDevOverrides()).not.toThrow();
      vi.restoreAllMocks();
    });
  });
});

describe("getDevOverride", () => {
  it("returns true for an on-override", () => {
    setUrl("/?ff.foo=on");
    expect(getDevOverride("foo")).toBe(true);
  });

  it("returns false for an off-override", () => {
    setUrl("/?ff.foo=off");
    expect(getDevOverride("foo")).toBe(false);
  });

  it("returns undefined for a key with no override", () => {
    setUrl("/");
    expect(getDevOverride("foo")).toBeUndefined();
  });

  it("returns undefined in production regardless of URL params", () => {
    vi.stubEnv("VITE_ENVIRONMENT", "production");
    setUrl("/?ff.foo=on");
    expect(getDevOverride("foo")).toBeUndefined();
  });

  it("reads from sessionStorage when URL param is absent", () => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ foo: true }));
    setUrl("/");
    expect(getDevOverride("foo")).toBe(true);
  });
});
