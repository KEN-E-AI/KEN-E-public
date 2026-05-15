import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWorkspaceOptions } from "./useWorkspaceOptions";
import {
  getOrganizations,
  getOrganizationsBatch,
} from "@/data/organizationApi";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/data/organizationApi");
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockGetOrganizations = getOrganizations as ReturnType<typeof vi.fn>;
const mockGetOrganizationsBatch = getOrganizationsBatch as ReturnType<
  typeof vi.fn
>;
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;

const wrapper = ({ children }: { children: ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useWorkspaceOptions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: "user-1" },
      isAuthenticated: true,
    });
  });

  it("merges every accessible org and its accounts into metadata records", async () => {
    mockGetOrganizations.mockResolvedValue([
      { organization_id: "org-1", organization_name: "Org One" },
      { organization_id: "org-2", organization_name: "Org Two" },
    ]);
    mockGetOrganizationsBatch.mockResolvedValue({
      "org-1": {
        organization_id: "org-1",
        organization_name: "Org One",
        accounts: [
          {
            account_id: "acct-1",
            account_name: "A1",
            organization_id: "org-1",
          },
        ],
      },
      "org-2": {
        organization_id: "org-2",
        organization_name: "Org Two",
        accounts: [
          {
            account_id: "acct-2",
            account_name: "A2",
            organization_id: "org-2",
          },
          {
            account_id: "acct-3",
            account_name: "A3",
            organization_id: "org-2",
          },
        ],
      },
    });

    const { result } = renderHook(() => useWorkspaceOptions(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual({
      orgMetadata: {
        "org-1": {
          organization_id: "org-1",
          organization_name: "Org One",
          accounts: [
            {
              account_id: "acct-1",
              account_name: "A1",
              organization_id: "org-1",
            },
          ],
        },
        "org-2": {
          organization_id: "org-2",
          organization_name: "Org Two",
          accounts: [
            {
              account_id: "acct-2",
              account_name: "A2",
              organization_id: "org-2",
            },
            {
              account_id: "acct-3",
              account_name: "A3",
              organization_id: "org-2",
            },
          ],
        },
      },
      accountMetadata: {
        "acct-1": {
          account_id: "acct-1",
          account_name: "A1",
          organization_id: "org-1",
        },
        "acct-2": {
          account_id: "acct-2",
          account_name: "A2",
          organization_id: "org-2",
        },
        "acct-3": {
          account_id: "acct-3",
          account_name: "A3",
          organization_id: "org-2",
        },
      },
    });
  });

  it("falls back to the bare org record when the batch omits an org", async () => {
    mockGetOrganizations.mockResolvedValue([
      { organization_id: "org-1", organization_name: "Org One" },
    ]);
    mockGetOrganizationsBatch.mockResolvedValue({});

    const { result } = renderHook(() => useWorkspaceOptions(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual({
      orgMetadata: {
        "org-1": { organization_id: "org-1", organization_name: "Org One" },
      },
      accountMetadata: {},
    });
  });

  it("does not fetch until the user is authenticated", () => {
    mockUseAuth.mockReturnValue({ user: null, isAuthenticated: false });

    const { result } = renderHook(() => useWorkspaceOptions(), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetOrganizations).not.toHaveBeenCalled();
  });
});
