import { describe, it, expect, vi, beforeEach } from "vitest";
import { evaluate } from "./client";
import { toFlagKey } from "./types";
import type { FlagEvaluation } from "./types";

// ─── Mock the shared axios instance ──────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  default: {
    post: vi.fn(),
  },
}));

import api from "@/lib/api";

const mockApi = api as {
  post: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

const newUiKey = toFlagKey("new_ui_enabled");
const betaKey = toFlagKey("automations_beta");

const newUiEval: FlagEvaluation = {
  key: newUiKey,
  enabled: true,
  reason: "domain_match",
};

const betaEval: FlagEvaluation = {
  key: betaKey,
  enabled: false,
  reason: "default",
};

// ─── evaluate ─────────────────────────────────────────────────────────────────

describe("evaluate", () => {
  it("POSTs to /api/v1/feature-flags/evaluate with snake_case flag_keys body", async () => {
    mockApi.post.mockResolvedValueOnce({
      data: { evaluations: { new_ui_enabled: newUiEval } },
    });

    await evaluate([newUiKey]);

    expect(mockApi.post).toHaveBeenCalledWith(
      "/api/v1/feature-flags/evaluate",
      { flag_keys: [newUiKey] },
    );
  });

  it("issues exactly one POST per call", async () => {
    mockApi.post.mockResolvedValueOnce({
      data: { evaluations: { new_ui_enabled: newUiEval } },
    });

    await evaluate([newUiKey]);

    expect(mockApi.post).toHaveBeenCalledTimes(1);
  });

  it("returns the unwrapped evaluations record", async () => {
    const evaluations = {
      new_ui_enabled: newUiEval,
      automations_beta: betaEval,
    };
    mockApi.post.mockResolvedValueOnce({ data: { evaluations } });

    const result = await evaluate([newUiKey, betaKey]);

    expect(result).toEqual(evaluations);
  });

  it("propagates rejections without retrying or swallowing", async () => {
    const networkError = new Error("Network Error");
    mockApi.post.mockRejectedValueOnce(networkError);

    await expect(evaluate([newUiKey])).rejects.toThrow("Network Error");
    expect(mockApi.post).toHaveBeenCalledTimes(1);
  });

  it("returns keys not in KNOWN_FLAGS as-is (no client-side filtering)", async () => {
    const unknownKey = toFlagKey("some_unknown_flag");
    const unknownEval: FlagEvaluation = {
      key: unknownKey,
      enabled: false,
      reason: "unknown_flag",
    };
    mockApi.post.mockResolvedValueOnce({
      data: { evaluations: { some_unknown_flag: unknownEval } },
    });

    const result = await evaluate([unknownKey]);

    expect(result).toEqual({ some_unknown_flag: unknownEval });
  });
});
