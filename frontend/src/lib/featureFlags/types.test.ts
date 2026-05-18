import { describe, it, expect } from "vitest";
import { isFlagKey, toFlagKey, tryFlagKey } from "./types";

describe("FlagKey branded type", () => {
  describe("isFlagKey", () => {
    it("accepts valid snake_case keys", () => {
      expect(isFlagKey("automations_beta")).toBe(true);
      expect(isFlagKey("chat_v2_enabled")).toBe(true);
      expect(isFlagKey("abc")).toBe(true); // min length 3
    });

    it("rejects keys that are too short", () => {
      expect(isFlagKey("ab")).toBe(false);
      expect(isFlagKey("a")).toBe(false);
      expect(isFlagKey("")).toBe(false);
    });

    it("rejects keys with uppercase letters", () => {
      expect(isFlagKey("BAD-KEY")).toBe(false);
      expect(isFlagKey("MyFlag")).toBe(false);
      expect(isFlagKey("bad_Key")).toBe(false);
    });

    it("rejects keys with hyphens or spaces", () => {
      expect(isFlagKey("bad-key")).toBe(false);
      expect(isFlagKey("bad key")).toBe(false);
    });

    it("rejects keys starting with underscore", () => {
      expect(isFlagKey("_bad_key")).toBe(false);
    });

    it("accepts keys starting with a digit", () => {
      expect(isFlagKey("0ab")).toBe(true);
    });

    it("rejects keys longer than 64 characters", () => {
      // max total length: 64 chars (1 + up to 63)
      const tooLong = "a" + "_".repeat(63); // 64 chars = valid
      const wayTooLong = "a" + "_".repeat(64); // 65 chars = invalid
      expect(isFlagKey(tooLong)).toBe(true);
      expect(isFlagKey(wayTooLong)).toBe(false);
    });
  });

  describe("toFlagKey", () => {
    it("returns branded value for valid key", () => {
      const key = toFlagKey("automations_beta");
      expect(key).toBe("automations_beta");
    });

    it("throws for invalid key", () => {
      expect(() => toFlagKey("x")).toThrow(/Invalid flag key "x"/);
      expect(() => toFlagKey("BAD-KEY")).toThrow();
    });
  });

  describe("tryFlagKey", () => {
    it("returns FlagKey for valid key", () => {
      expect(tryFlagKey("automations_beta")).toBe("automations_beta");
    });

    it("returns undefined for invalid key", () => {
      expect(tryFlagKey("x")).toBeUndefined();
      expect(tryFlagKey("BAD-KEY")).toBeUndefined();
      expect(tryFlagKey("")).toBeUndefined();
    });
  });
});
