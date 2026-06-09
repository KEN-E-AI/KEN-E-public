import { describe, test, expect, vi, beforeEach } from "vitest";
import apiPublic from "@/lib/api-public";
import {
  getSignupPolicy,
  validateAccessCode,
  EARLY_RELEASE_CODE_STORAGE_KEY,
} from "./earlyReleaseApi";

vi.mock("@/lib/api-public", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiPublic = vi.mocked(apiPublic);

describe("earlyReleaseApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("EARLY_RELEASE_CODE_STORAGE_KEY", () => {
    test("is the string literal kene_early_release_code", () => {
      expect(EARLY_RELEASE_CODE_STORAGE_KEY).toBe("kene_early_release_code");
    });
  });

  describe("getSignupPolicy", () => {
    test("returns policy from the API on success", async () => {
      (mockedApiPublic.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: { invite_only: true },
      });

      const result = await getSignupPolicy();

      expect(mockedApiPublic.get).toHaveBeenCalledWith(
        "/api/v1/auth/signup-policy",
      );
      expect(result).toEqual({ invite_only: true });
    });

    test("returns { invite_only: false } when the request rejects (fail-open)", async () => {
      (mockedApiPublic.get as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error("Network error"),
      );

      const result = await getSignupPolicy();

      expect(result).toEqual({ invite_only: false });
    });

    test("returns { invite_only: false } when the API responds with flag OFF", async () => {
      (mockedApiPublic.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: { invite_only: false },
      });

      const result = await getSignupPolicy();

      expect(result).toEqual({ invite_only: false });
    });
  });

  describe("validateAccessCode", () => {
    test("calls POST /api/v1/early-release/validate with the code and returns parsed response", async () => {
      (mockedApiPublic.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: { valid: true },
      });

      const result = await validateAccessCode("EARLY-RELEASE-CODE");

      expect(mockedApiPublic.post).toHaveBeenCalledWith(
        "/api/v1/early-release/validate",
        { code: "EARLY-RELEASE-CODE" },
      );
      expect(result).toEqual({ valid: true });
    });

    test("returns { valid: false } when the code is invalid", async () => {
      (mockedApiPublic.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: { valid: false },
      });

      const result = await validateAccessCode("BAD-CODE");

      expect(result).toEqual({ valid: false });
    });

    test("re-throws when the request fails (lets the caller handle 429 etc.)", async () => {
      const err = Object.assign(new Error("Rate limited"), {
        response: { status: 429 },
      });
      (mockedApiPublic.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        err,
      );

      await expect(validateAccessCode("ANY")).rejects.toThrow("Rate limited");
    });
  });
});
