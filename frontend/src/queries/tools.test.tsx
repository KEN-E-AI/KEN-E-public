import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { accountToolKeys, useAccountTools } from "./tools";

// ─── Mock API client ──────────────────────────────────────────────────────────

vi.mock("@/lib/api/tools", () => ({
  getAccountTools: vi.fn(),
}));

import { getAccountTools } from "@/lib/api/tools";

const mockGetAccountTools = getAccountTools as ReturnType<typeof vi.fn>;

// ─── Test helpers ─────────────────────────────────────────────────────────────

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function freshClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Query key factory ────────────────────────────────────────────────────────

describe("accountToolKeys", () => {
  it("list key is scoped by accountId", () => {
    expect(accountToolKeys.list("acc_test")).toEqual([
      "accountTools",
      "list",
      "acc_test",
    ]);
  });

  it("lists prefix matches every account variant", () => {
    // Prefix-match semantics: lists() returns a key that's a prefix of
    // list(accountId). TanStack treats this as a sub-tree for invalidation.
    const prefix = accountToolKeys.lists();
    const specific = accountToolKeys.list("acc_test");
    expect(specific.slice(0, prefix.length)).toEqual([...prefix]);
  });
});

// ─── useAccountTools ──────────────────────────────────────────────────────────

describe("useAccountTools", () => {
  it("fetches and returns tools when accountId is provided", async () => {
    const fixture = {
      tools: [
        {
          tool_id: "function.create_visualization",
          name: "create_visualization",
          description: "Render a chart.",
          category: "visualization",
          source: "global_default",
          mcp_server: null,
          integration_platform: null,
        },
      ],
    };
    mockGetAccountTools.mockResolvedValueOnce(fixture);

    const client = freshClient();
    const { result } = renderHook(() => useAccountTools("acc_test"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fixture);
    expect(mockGetAccountTools).toHaveBeenCalledWith("acc_test");
  });

  it("is disabled when accountId is null", () => {
    const client = freshClient();
    const { result } = renderHook(() => useAccountTools(null), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetAccountTools).not.toHaveBeenCalled();
  });

  it("is disabled when accountId is undefined", () => {
    const client = freshClient();
    const { result } = renderHook(() => useAccountTools(undefined), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetAccountTools).not.toHaveBeenCalled();
  });

  it("is disabled when accountId is empty string", () => {
    const client = freshClient();
    const { result } = renderHook(() => useAccountTools(""), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetAccountTools).not.toHaveBeenCalled();
  });
});
