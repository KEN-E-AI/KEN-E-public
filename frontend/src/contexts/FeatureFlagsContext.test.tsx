import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  FeatureFlagsProvider,
  useFeatureFlag,
  useFeatureFlagsContext,
} from "./FeatureFlagsContext";
import { toFlagKey } from "@/lib/featureFlags/types";
import type { FlagKey, FlagEvaluation } from "@/lib/featureFlags/types";

// ─── Module mocks ─────────────────────────────────────────────────────────────

// KNOWN_FLAGS is exposed via a getter so individual tests can swap the array
// after the provider module has been imported.
let mockKnownFlags: FlagKey[] = [];
vi.mock("@/lib/featureFlags/registry", () => ({
  get KNOWN_FLAGS() {
    return mockKnownFlags;
  },
}));

vi.mock("@/lib/featureFlags/client", () => ({
  evaluate: vi.fn(),
}));

vi.mock("@/lib/featureFlags/devOverride", () => ({
  getDevOverride: vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { evaluate } from "@/lib/featureFlags/client";
import { getDevOverride } from "@/lib/featureFlags/devOverride";
import { useAuth } from "@/contexts/AuthContext";

const mockEvaluate = evaluate as ReturnType<typeof vi.fn>;
const mockGetDevOverride = getDevOverride as ReturnType<typeof vi.fn>;
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;

// ─── Fixtures & helpers ───────────────────────────────────────────────────────

const flagA = toFlagKey("automations_beta");

function evalFor(
  key: FlagKey,
  enabled: boolean,
  reason: FlagEvaluation["reason"] = "default",
): FlagEvaluation {
  return { key, enabled, reason };
}

function authFor(userId: string | null, accountId: string | null): unknown {
  return {
    user: userId ? { id: userId } : null,
    selectedOrgAccount: accountId ? { accountId } : null,
  };
}

function freshClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <FeatureFlagsProvider>{children}</FeatureFlagsProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  mockKnownFlags = [];
  mockGetDevOverride.mockReset();
  mockGetDevOverride.mockReturnValue(undefined);
  mockEvaluate.mockReset();
  // Default: the query, if it runs at all, resolves to an empty record.
  // Individual tests override with mockResolvedValueOnce / mockReturnValue.
  mockEvaluate.mockResolvedValue({});
  mockUseAuth.mockReset();
  mockUseAuth.mockReturnValue(authFor("user_1", "acc_1"));
  vi.unstubAllEnvs();
});

// ─── Dev override (PRD §5.2 — short-circuits everything) ──────────────────────

describe("useFeatureFlag — dev override", () => {
  it("returns enabled:true, reason:dev_override, isLoading:false when override is true", () => {
    mockGetDevOverride.mockReturnValue(true);
    // Override must short-circuit even when the key isn't in KNOWN_FLAGS.
    mockKnownFlags = [];

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(result.current).toEqual({
      enabled: true,
      reason: "dev_override",
      isLoading: false,
    });
    expect(mockEvaluate).not.toHaveBeenCalled();
  });

  it("returns enabled:false, reason:dev_override when override is false", () => {
    mockGetDevOverride.mockReturnValue(false);
    mockKnownFlags = [flagA];

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(result.current).toEqual({
      enabled: false,
      reason: "dev_override",
      isLoading: false,
    });
  });
});

// ─── Unknown flag fallback ────────────────────────────────────────────────────

describe("useFeatureFlag — unknown flag", () => {
  it("returns enabled:false, reason:unknown_flag, isLoading:false when key is not in KNOWN_FLAGS", () => {
    mockKnownFlags = [];
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(result.current).toEqual({
      enabled: false,
      reason: "unknown_flag",
      isLoading: false,
    });
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("not in KNOWN_FLAGS"),
    );

    warnSpy.mockRestore();
  });

  it("does not warn when VITE_ENVIRONMENT is production", () => {
    mockKnownFlags = [];
    vi.stubEnv("VITE_ENVIRONMENT", "production");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(warnSpy).not.toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});

// ─── In-flight vs evaluated isLoading (pins the 11d414fc regression fix) ──────

describe("useFeatureFlag — isLoading lifecycle", () => {
  it("returns isLoading:true with reason:default while evaluate() is pending", () => {
    mockKnownFlags = [flagA];
    let resolveEvaluate: (v: Record<string, FlagEvaluation>) => void = () => {};
    mockEvaluate.mockReturnValue(
      new Promise((resolve) => {
        resolveEvaluate = resolve;
      }),
    );

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(result.current).toEqual({
      enabled: false,
      reason: "default",
      isLoading: true,
    });

    // Resolve to avoid a dangling promise across the test boundary.
    resolveEvaluate({});
  });

  it("returns isLoading:false with the server reason once evaluate() resolves", async () => {
    mockKnownFlags = [flagA];
    mockEvaluate.mockResolvedValue({
      [flagA]: evalFor(flagA, true, "rollout"),
    });

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    await waitFor(() =>
      expect(result.current).toEqual({
        enabled: true,
        reason: "rollout",
        isLoading: false,
      }),
    );
  });
});

// ─── Provider fetch lifecycle (AC-2, AC-3, AC-10 guards) ──────────────────────

describe("FeatureFlagsProvider — fetch lifecycle", () => {
  it("re-fetches when accountId changes (AC-3)", async () => {
    mockKnownFlags = [flagA];
    mockEvaluate
      .mockResolvedValueOnce({ [flagA]: evalFor(flagA, true, "rollout") })
      .mockResolvedValueOnce({ [flagA]: evalFor(flagA, false, "default") });

    mockUseAuth.mockReturnValue(authFor("user_1", "acc_1"));

    const { rerender, result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockEvaluate).toHaveBeenCalledTimes(1);

    mockUseAuth.mockReturnValue(authFor("user_1", "acc_2"));
    rerender();

    await waitFor(() => expect(mockEvaluate).toHaveBeenCalledTimes(2));
  });

  it("does not fetch when user is null (Firebase auth-loading window)", () => {
    mockKnownFlags = [flagA];
    mockUseAuth.mockReturnValue(authFor(null, null));

    renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(mockEvaluate).not.toHaveBeenCalled();
  });

  it("does not fetch when KNOWN_FLAGS is empty (avoids FF-PRD-01 AC-10 422)", () => {
    mockKnownFlags = [];
    // Hook also fires the unknown-flag warn — silence it, it's covered above.
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    expect(mockEvaluate).not.toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it("issues exactly one POST on mount when user and KNOWN_FLAGS are non-empty (AC-2)", async () => {
    mockKnownFlags = [flagA];
    mockEvaluate.mockResolvedValue({
      [flagA]: evalFor(flagA, false, "default"),
    });

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockEvaluate).toHaveBeenCalledTimes(1);
    expect(mockEvaluate).toHaveBeenCalledWith([flagA]);
  });
});

// ─── Dev override precedence over server (PRD §8 scenario 3) ─────────────────

describe("useFeatureFlag — dev override precedence over server", () => {
  it("wins even when evaluate() returned enabled:true", async () => {
    mockKnownFlags = [flagA];
    // Server says enabled: true, but the local override says false.
    mockEvaluate.mockResolvedValue({
      [flagA]: evalFor(flagA, true, "domain_match"),
    });
    mockGetDevOverride.mockReturnValue(false);

    const { result } = renderHook(() => useFeatureFlag(flagA), {
      wrapper: makeWrapper(freshClient()),
    });

    // Prove the query ran (flagA is in KNOWN_FLAGS and user is set), so this
    // is genuinely "override wins over server" rather than "override short-circuits
    // before the query".
    await waitFor(() => expect(mockEvaluate).toHaveBeenCalledTimes(1));

    await waitFor(() =>
      expect(result.current).toEqual({
        enabled: false,
        reason: "dev_override",
        isLoading: false,
      }),
    );
  });
});

// ─── refetch() invalidates query (PRD §8 scenario 5) ─────────────────────────

describe("FeatureFlagsProvider — refetch()", () => {
  it("invalidates the query and triggers a second evaluate call", async () => {
    mockKnownFlags = [flagA];
    mockEvaluate.mockResolvedValue({
      [flagA]: evalFor(flagA, false, "default"),
    });

    const { result } = renderHook(
      () => ({
        flag: useFeatureFlag(flagA),
        refetch: useFeatureFlagsContext().refetch,
      }),
      { wrapper: makeWrapper(freshClient()) },
    );

    await waitFor(() => expect(mockEvaluate).toHaveBeenCalledTimes(1));

    await act(async () => {
      await result.current.refetch();
    });

    await waitFor(() => expect(mockEvaluate).toHaveBeenCalledTimes(2));
  });
});
