import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  agentConfigKeys,
  useAgentConfigsList,
  useAgentConfig,
  useUpsertAgentConfigOverlay,
  useCreateAgentConfig,
  useDeleteAgentConfig,
} from "./agentConfigs";

// ─── Mock API client ──────────────────────────────────────────────────────────

vi.mock("@/lib/api/agentConfigs", () => ({
  listAgentConfigs: vi.fn(),
  getAgentConfig: vi.fn(),
  upsertAgentConfigOverlay: vi.fn(),
  createAgentConfig: vi.fn(),
  deleteAgentConfig: vi.fn(),
}));

import {
  listAgentConfigs,
  getAgentConfig,
  upsertAgentConfigOverlay,
  createAgentConfig,
  deleteAgentConfig,
} from "@/lib/api/agentConfigs";

const mockListAgentConfigs = listAgentConfigs as ReturnType<typeof vi.fn>;
const mockGetAgentConfig = getAgentConfig as ReturnType<typeof vi.fn>;
const mockUpsertAgentConfigOverlay = upsertAgentConfigOverlay as ReturnType<
  typeof vi.fn
>;
const mockCreateAgentConfig = createAgentConfig as ReturnType<typeof vi.fn>;
const mockDeleteAgentConfig = deleteAgentConfig as ReturnType<typeof vi.fn>;

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

// ─── Query key factory ────────────────────────────────────────────────────────

describe("agentConfigKeys", () => {
  it("list key contains accountId and opts", () => {
    expect(agentConfigKeys.list("acc_test")).toEqual([
      "agentConfigs",
      "list",
      "acc_test",
      undefined,
    ]);
    expect(
      agentConfigKeys.list("acc_test", { visibleInFrontend: true }),
    ).toEqual([
      "agentConfigs",
      "list",
      "acc_test",
      { visibleInFrontend: true },
    ]);
  });

  it("detail key contains accountId and configId", () => {
    expect(agentConfigKeys.detail("acc_test", "ga")).toEqual([
      "agentConfigs",
      "detail",
      "acc_test",
      "ga",
    ]);
  });
});

// ─── useAgentConfigsList ──────────────────────────────────────────────────────

describe("useAgentConfigsList", () => {
  it("fetches and returns agent configs when accountId is provided", async () => {
    const fixture = [{ config_id: "ga", customization_status: "default" }];
    mockListAgentConfigs.mockResolvedValueOnce(fixture);

    const client = freshClient();
    const { result } = renderHook(
      () => useAgentConfigsList("acc_test", { visibleInFrontend: true }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fixture);
    expect(mockListAgentConfigs).toHaveBeenCalledWith("acc_test", {
      visibleInFrontend: true,
    });
  });

  it("is disabled when accountId is null", () => {
    const client = freshClient();
    const { result } = renderHook(() => useAgentConfigsList(null), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockListAgentConfigs).not.toHaveBeenCalled();
  });

  it("is disabled when accountId is empty string", () => {
    const client = freshClient();
    const { result } = renderHook(() => useAgentConfigsList(""), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockListAgentConfigs).not.toHaveBeenCalled();
  });
});

// ─── useAgentConfig ───────────────────────────────────────────────────────────

describe("useAgentConfig", () => {
  it("fetches a single config when both ids are provided", async () => {
    const fixture = { config_id: "ga", customization_status: "default" };
    mockGetAgentConfig.mockResolvedValueOnce(fixture);

    const client = freshClient();
    const { result } = renderHook(() => useAgentConfig("acc_test", "ga"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fixture);
  });

  it("is disabled when configId is null", () => {
    const client = freshClient();
    const { result } = renderHook(() => useAgentConfig("acc_test", null), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetAgentConfig).not.toHaveBeenCalled();
  });
});

// ─── useUpsertAgentConfigOverlay ──────────────────────────────────────────────

describe("useUpsertAgentConfigOverlay", () => {
  it("calls upsertAgentConfigOverlay with the right args", async () => {
    const updated = { config_id: "ga", customization_status: "customized" };
    mockUpsertAgentConfigOverlay.mockResolvedValueOnce(updated);

    const client = freshClient();
    const { result } = renderHook(
      () => useUpsertAgentConfigOverlay("acc_test"),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({ configId: "ga", body: { temperature: 0.5 } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockUpsertAgentConfigOverlay).toHaveBeenCalledWith(
      "acc_test",
      "ga",
      { temperature: 0.5 },
    );
  });

  it("updates the detail cache with the freshly-saved config", async () => {
    const updated = {
      config_id: "ga",
      name: "Dave",
      title: "Business Researcher",
      customization_status: "customized",
    };
    mockUpsertAgentConfigOverlay.mockResolvedValueOnce(updated);

    const client = freshClient();
    // Pre-seed the detail cache with stale data so we can prove it gets
    // replaced (vs. relying on a no-op invalidation that happens to refetch).
    client.setQueryData(agentConfigKeys.detail("acc_test", "ga"), {
      config_id: "ga",
      name: null,
      title: null,
      customization_status: "default",
    });

    const { result } = renderHook(
      () => useUpsertAgentConfigOverlay("acc_test"),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({ configId: "ga", body: { name: "Dave" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(
      client.getQueryData(agentConfigKeys.detail("acc_test", "ga")),
    ).toEqual(updated);
  });

  it("updates every list variant for the account by config_id", async () => {
    const updated = {
      config_id: "ga",
      name: "Dave",
      title: "Business Researcher",
      customization_status: "customized",
    };
    const other = { config_id: "other", name: null, title: null };
    mockUpsertAgentConfigOverlay.mockResolvedValueOnce(updated);

    const client = freshClient();
    // Pre-seed two list variants that AgentsListView and any other consumer
    // might use — one with visibleInFrontend=true, one without opts.
    client.setQueryData(
      agentConfigKeys.list("acc_test", { visibleInFrontend: true }),
      [{ config_id: "ga", name: null, title: null }, other],
    );
    client.setQueryData(agentConfigKeys.list("acc_test"), [
      { config_id: "ga", name: null, title: null },
      other,
    ]);

    const { result } = renderHook(
      () => useUpsertAgentConfigOverlay("acc_test"),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({ configId: "ga", body: { name: "Dave" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Both list variants should have the updated entry replaced in place.
    // Other entries in the list are untouched.
    const visibleList = client.getQueryData(
      agentConfigKeys.list("acc_test", { visibleInFrontend: true }),
    );
    expect(visibleList).toEqual([updated, other]);
    const allList = client.getQueryData(agentConfigKeys.list("acc_test"));
    expect(allList).toEqual([updated, other]);
  });

  it("leaves the list untouched when the saved config is not in it", async () => {
    const updated = {
      config_id: "ga",
      name: "Dave",
      title: "Business Researcher",
      customization_status: "customized",
    };
    mockUpsertAgentConfigOverlay.mockResolvedValueOnce(updated);

    const client = freshClient();
    const seedList = [{ config_id: "other", name: null, title: null }];
    client.setQueryData(agentConfigKeys.list("acc_test"), seedList);

    const { result } = renderHook(
      () => useUpsertAgentConfigOverlay("acc_test"),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({ configId: "ga", body: { name: "Dave" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getQueryData(agentConfigKeys.list("acc_test"))).toEqual(
      seedList,
    );
  });
});

// ─── useCreateAgentConfig ─────────────────────────────────────────────────────

describe("useCreateAgentConfig", () => {
  const validCreateBody = {
    title: "New Config",
    instruction: "You are a helpful test assistant.",
    model: "gemini-2.5-flash",
  };

  it("calls createAgentConfig and invalidates the list key on success", async () => {
    const created = { config_id: "ga-new", customization_status: "default" };
    mockCreateAgentConfig.mockResolvedValueOnce(created);

    const client = freshClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateAgentConfig("acc_test"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate(validCreateBody);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockCreateAgentConfig).toHaveBeenCalledWith(
      "acc_test",
      validCreateBody,
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: agentConfigKeys.listsForAccount("acc_test"),
      }),
    );
  });

  it("rejects with 'No account selected' when accountId is null", async () => {
    const client = freshClient();

    const { result } = renderHook(() => useCreateAgentConfig(null), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate(validCreateBody);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(new Error("No account selected"));
    expect(mockCreateAgentConfig).not.toHaveBeenCalled();
  });
});

// ─── useDeleteAgentConfig ─────────────────────────────────────────────────────

describe("useDeleteAgentConfig", () => {
  it("calls deleteAgentConfig and invalidates the list and detail keys", async () => {
    mockDeleteAgentConfig.mockResolvedValueOnce(undefined);

    const client = freshClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteAgentConfig("acc_test"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ configId: "ga" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockDeleteAgentConfig).toHaveBeenCalledWith("acc_test", "ga");
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: agentConfigKeys.listsForAccount("acc_test"),
      }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: agentConfigKeys.detail("acc_test", "ga"),
      }),
    );
  });
});
