import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  featureFlagKeys,
  useFeatureFlags,
  useFeatureFlagConfig,
  useFlagAudit,
  useCreateFlag,
  useUpdateFlag,
  useDeleteFlag,
} from "./hooks";
import { toFlagKey } from "./types";
import type { FeatureFlag } from "./types";

// ─── Mock the admin client ────────────────────────────────────────────────────

vi.mock("./adminClient", () => ({
  listFlags: vi.fn(),
  getFlag: vi.fn(),
  getFlagAudit: vi.fn(),
  createFlag: vi.fn(),
  updateFlag: vi.fn(),
  deleteFlag: vi.fn(),
}));

import {
  listFlags,
  getFlag,
  getFlagAudit,
  createFlag,
  updateFlag,
  deleteFlag,
} from "./adminClient";
import type { FeatureFlagCreate } from "./adminClient";

const mockListFlags = listFlags as ReturnType<typeof vi.fn>;
const mockGetFlag = getFlag as ReturnType<typeof vi.fn>;
const mockGetFlagAudit = getFlagAudit as ReturnType<typeof vi.fn>;
const mockCreateFlag = createFlag as ReturnType<typeof vi.fn>;
const mockUpdateFlag = updateFlag as ReturnType<typeof vi.fn>;
const mockDeleteFlag = deleteFlag as ReturnType<typeof vi.fn>;

// ─── Test helpers ─────────────────────────────────────────────────────────────

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function freshClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Fixtures ─────────────────────────────────────────────────────────────────

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

// ─── featureFlagKeys factory ──────────────────────────────────────────────────

describe("featureFlagKeys", () => {
  it("generates stable query keys", () => {
    expect(featureFlagKeys.all).toEqual(["featureFlags"]);
    expect(featureFlagKeys.list()).toEqual(["featureFlags", "list"]);
    expect(featureFlagKeys.detail(testKey)).toEqual([
      "featureFlags",
      "detail",
      testKey,
    ]);
    expect(featureFlagKeys.audit(testKey, "cursor123")).toEqual([
      "featureFlags",
      "detail",
      testKey,
      "audit",
      "cursor123",
    ]);
    expect(featureFlagKeys.audit(testKey)).toEqual([
      "featureFlags",
      "detail",
      testKey,
      "audit",
      null,
    ]);
  });
});

// ─── useFeatureFlags ──────────────────────────────────────────────────────────

describe("useFeatureFlags", () => {
  it("fetches and returns the flags list", async () => {
    mockListFlags.mockResolvedValueOnce([baseFlag]);
    const client = freshClient();
    const { result } = renderHook(() => useFeatureFlags(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([baseFlag]);
    expect(mockListFlags).toHaveBeenCalledOnce();
  });
});

// ─── useFeatureFlagConfig ─────────────────────────────────────────────────────

describe("useFeatureFlagConfig", () => {
  it("fetches a single flag when key is provided", async () => {
    mockGetFlag.mockResolvedValueOnce(baseFlag);
    const client = freshClient();
    const { result } = renderHook(() => useFeatureFlagConfig(testKey), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(baseFlag);
    expect(mockGetFlag).toHaveBeenCalledWith(testKey);
  });

  it("is disabled when key is undefined and uses a non-colliding cache key", () => {
    const client = freshClient();
    const { result } = renderHook(() => useFeatureFlagConfig(undefined), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetFlag).not.toHaveBeenCalled();
    // Cache key must be in the detail namespace, not the list root, to avoid collisions.
    const cachedList = client.getQueryData(featureFlagKeys.list());
    expect(cachedList).toBeUndefined();
  });
});

// ─── useFlagAudit ─────────────────────────────────────────────────────────────

describe("useFlagAudit", () => {
  it("fetches audit entries for a key", async () => {
    const auditResponse = { entries: [], next_cursor: null };
    mockGetFlagAudit.mockResolvedValueOnce(auditResponse);
    const client = freshClient();
    const { result } = renderHook(() => useFlagAudit(testKey), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(auditResponse);
    expect(mockGetFlagAudit).toHaveBeenCalledWith(testKey, { cursor: null });
  });

  it("includes cursor in query key for pagination", async () => {
    mockGetFlagAudit.mockResolvedValueOnce({ entries: [], next_cursor: null });
    const client = freshClient();
    renderHook(() => useFlagAudit(testKey, "page2cursor"), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(mockGetFlagAudit).toHaveBeenCalled());
    expect(mockGetFlagAudit).toHaveBeenCalledWith(testKey, {
      cursor: "page2cursor",
    });
  });
});

// ─── useCreateFlag ────────────────────────────────────────────────────────────

describe("useCreateFlag", () => {
  it("calls createFlag and invalidates the list query on success", async () => {
    mockCreateFlag.mockResolvedValueOnce(baseFlag);
    const client = freshClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

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

    const { result } = renderHook(() => useCreateFlag(), {
      wrapper: makeWrapper(client),
    });
    result.current.mutate(body);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockCreateFlag).toHaveBeenCalledWith(body);
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: featureFlagKeys.list() }),
    );
  });
});

// ─── useUpdateFlag ────────────────────────────────────────────────────────────

describe("useUpdateFlag", () => {
  it("calls updateFlag and invalidates list + detail on success", async () => {
    mockUpdateFlag.mockResolvedValueOnce({ ...baseFlag, is_active: false });
    const client = freshClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateFlag(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      key: testKey,
      body: { ...baseFlag, is_active: false },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockUpdateFlag).toHaveBeenCalledWith(testKey, {
      ...baseFlag,
      is_active: false,
    });
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: featureFlagKeys.list() }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: featureFlagKeys.detail(testKey) }),
    );
  });
});

// ─── useDeleteFlag ────────────────────────────────────────────────────────────

describe("useDeleteFlag", () => {
  it("calls deleteFlag and invalidates list + detail on success", async () => {
    mockDeleteFlag.mockResolvedValueOnce(undefined);
    const client = freshClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteFlag(), {
      wrapper: makeWrapper(client),
    });
    result.current.mutate(testKey);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockDeleteFlag).toHaveBeenCalledWith(testKey);
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: featureFlagKeys.list() }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: featureFlagKeys.detail(testKey) }),
    );
  });
});
