import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listFlags,
  getFlag,
  createFlag,
  updateFlag,
  deleteFlag,
  getFlagAudit,
} from "./adminClient";
import type { FeatureFlagCreate, FeatureFlagUpdate } from "./adminClient";
import { toFlagKey } from "./types";
import type { FeatureFlag } from "./types";

// ─── Mock the shared axios instance ──────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from "@/lib/api";

const mockApi = api as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

const testKey = toFlagKey("automations_beta");

const baseFlag: FeatureFlag = {
  key: testKey,
  description: "Automations beta",
  default_enabled: false,
  is_active: true,
  targeting_rules: {
    user_emails: [],
    email_domains: [],
    organization_ids: [],
    account_ids: [],
    rollout_percentage: 0,
  },
  bucketing_entity: "account",
  owner: "test@ken-e.ai",
  expected_ga_release: null,
  created_at: "2026-05-18T00:00:00Z",
  updated_at: "2026-05-18T00:00:00Z",
};

// ─── listFlags ────────────────────────────────────────────────────────────────

describe("listFlags", () => {
  it("calls GET /api/v1/admin/feature-flags and returns flags array", async () => {
    mockApi.get.mockResolvedValueOnce({ data: { flags: [baseFlag] } });
    const result = await listFlags();
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/admin/feature-flags");
    expect(result).toEqual([baseFlag]);
  });
});

// ─── getFlag ──────────────────────────────────────────────────────────────────

describe("getFlag", () => {
  it("calls GET /api/v1/admin/feature-flags/{key}", async () => {
    mockApi.get.mockResolvedValueOnce({ data: baseFlag });
    const result = await getFlag(testKey);
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/admin/feature-flags/automations_beta",
    );
    expect(result).toEqual(baseFlag);
  });
});

// ─── createFlag ───────────────────────────────────────────────────────────────

describe("createFlag", () => {
  it("calls POST /api/v1/admin/feature-flags with body", async () => {
    const body: FeatureFlagCreate = {
      key: testKey,
      description: "Automations beta",
      default_enabled: false,
      is_active: true,
      targeting_rules: {
        user_emails: [],
        email_domains: [],
        organization_ids: [],
        account_ids: [],
        rollout_percentage: 0,
      },
      bucketing_entity: "account",
      owner: "test@ken-e.ai",
      expected_ga_release: null,
    };
    mockApi.post.mockResolvedValueOnce({ data: baseFlag });
    const result = await createFlag(body);
    expect(mockApi.post).toHaveBeenCalledWith(
      "/api/v1/admin/feature-flags",
      body,
    );
    expect(result).toEqual(baseFlag);
  });
});

// ─── updateFlag ───────────────────────────────────────────────────────────────

describe("updateFlag", () => {
  it("calls PUT /api/v1/admin/feature-flags/{key} with body", async () => {
    const body: FeatureFlagUpdate = {
      key: testKey,
      description: "Updated",
      default_enabled: false,
      is_active: false,
      targeting_rules: {
        user_emails: [],
        email_domains: [],
        organization_ids: [],
        account_ids: [],
        rollout_percentage: 0,
      },
      bucketing_entity: "account",
      owner: "test@ken-e.ai",
      expected_ga_release: "Release 2",
    };
    mockApi.put.mockResolvedValueOnce({
      data: { ...baseFlag, is_active: false },
    });
    const result = await updateFlag(testKey, body);
    expect(mockApi.put).toHaveBeenCalledWith(
      "/api/v1/admin/feature-flags/automations_beta",
      body,
    );
    expect(result.is_active).toBe(false);
  });
});

// ─── deleteFlag ───────────────────────────────────────────────────────────────

describe("deleteFlag", () => {
  it("calls DELETE /api/v1/admin/feature-flags/{key}", async () => {
    mockApi.delete.mockResolvedValueOnce({ data: undefined });
    await deleteFlag(testKey);
    expect(mockApi.delete).toHaveBeenCalledWith(
      "/api/v1/admin/feature-flags/automations_beta",
    );
  });
});

// ─── getFlagAudit ─────────────────────────────────────────────────────────────

describe("getFlagAudit", () => {
  it("calls GET /api/v1/admin/feature-flags/{key}/audit with default limit=50", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { entries: [], next_cursor: null },
    });
    await getFlagAudit(testKey);
    const callUrl: string = mockApi.get.mock.calls[0][0];
    expect(callUrl).toContain(
      "/api/v1/admin/feature-flags/automations_beta/audit",
    );
    expect(callUrl).toContain("limit=50");
    expect(callUrl).not.toContain("cursor=");
  });

  it("includes cursor param when provided", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { entries: [], next_cursor: null },
    });
    await getFlagAudit(testKey, { limit: 20, cursor: "abc123" });
    const callUrl: string = mockApi.get.mock.calls[0][0];
    expect(callUrl).toContain("limit=20");
    expect(callUrl).toContain("cursor=abc123");
  });

  it("omits cursor param when cursor is null", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { entries: [], next_cursor: null },
    });
    await getFlagAudit(testKey, { cursor: null });
    const callUrl: string = mockApi.get.mock.calls[0][0];
    expect(callUrl).not.toContain("cursor=");
  });
});
