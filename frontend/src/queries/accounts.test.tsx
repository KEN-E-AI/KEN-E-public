import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  accountKeys,
  useAccounts,
  useCreateAccount,
  useUpdateAccount,
  useDeleteAccount,
} from "./accounts";
import { toAccountId, toOrganizationId } from "@/lib/branded-types";
import * as organizationApi from "@/data/organizationApi";

// Mock organizationApi
vi.mock("@/data/organizationApi");

// Test data
const testOrgId = toOrganizationId("org_test123");
const testAccountId = toAccountId("acc_test123");
const testAccount = {
  account_id: testAccountId,
  account_name: "Test Account",
  organization_id: testOrgId,
  industry: "Technology",
  status: "active",
  websites: ["https://example.com"],
  timezone: "America/New_York",
  data_region: "US",
  region: ["North America"],
};

describe("Account Query Hooks", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const createWrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe("accountKeys", () => {
    it("generates correct query keys", () => {
      expect(accountKeys.all).toEqual(["accounts"]);
      expect(accountKeys.lists()).toEqual(["accounts", "list"]);
      expect(accountKeys.list(testOrgId)).toEqual([
        "accounts",
        "list",
        testOrgId,
      ]);
      expect(accountKeys.details()).toEqual(["accounts", "detail"]);
      expect(accountKeys.detail(testAccountId)).toEqual([
        "accounts",
        "detail",
        testAccountId,
      ]);
    });
  });

  describe("useAccounts", () => {
    it("fetches accounts for an organization", async () => {
      const mockAccounts = [testAccount];
      vi.mocked(
        organizationApi.getAccountsByOrganizationId,
      ).mockResolvedValueOnce(mockAccounts);

      const { result } = renderHook(() => useAccounts(testOrgId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockAccounts);
      expect(organizationApi.getAccountsByOrganizationId).toHaveBeenCalledWith(
        testOrgId,
      );
    });

    it("returns empty array when orgId is null", async () => {
      const { result } = renderHook(() => useAccounts(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toEqual([]);
      expect(result.current.isSuccess).toBe(true);
      expect(
        organizationApi.getAccountsByOrganizationId,
      ).not.toHaveBeenCalled();
    });

    it("handles API errors gracefully", async () => {
      const errorMessage = "Network error";
      vi.mocked(
        organizationApi.getAccountsByOrganizationId,
      ).mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useAccounts(testOrgId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });

    it("returns empty array when API returns no accounts", async () => {
      vi.mocked(
        organizationApi.getAccountsByOrganizationId,
      ).mockResolvedValueOnce([]);

      const { result } = renderHook(() => useAccounts(testOrgId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([]);
    });
  });

  describe("useCreateAccount", () => {
    it("creates an account successfully", async () => {
      const newAccount = { ...testAccount };
      vi.mocked(organizationApi.createAccount).mockResolvedValueOnce(
        newAccount,
      );

      const { result } = renderHook(() => useCreateAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_name: "New Account",
        organization_id: testOrgId,
        industry: "Technology",
        websites: ["https://example.com"],
        timezone: "America/New_York",
        data_region: "US",
        region: ["North America"],
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(newAccount);
      expect(organizationApi.createAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          account_name: "New Account",
          organization_id: testOrgId,
          status: "active",
        }),
      );
    });

    it("invalidates queries on successful creation", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      vi.mocked(organizationApi.createAccount).mockResolvedValueOnce(
        testAccount,
      );

      const { result } = renderHook(() => useCreateAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_name: "New Account",
        organization_id: testOrgId,
        industry: "Technology",
        websites: ["https://example.com"],
        timezone: "America/New_York",
        data_region: "US",
        region: ["North America"],
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: accountKeys.list(testOrgId),
      });
    });

    it("handles creation errors", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const errorMessage = "Creation failed";
      vi.mocked(organizationApi.createAccount).mockRejectedValueOnce(
        new Error(errorMessage),
      );

      const { result } = renderHook(() => useCreateAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_name: "New Account",
        organization_id: testOrgId,
        industry: "Technology",
        websites: ["https://example.com"],
        timezone: "America/New_York",
        data_region: "US",
        region: ["North America"],
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
      expect(consoleSpy).toHaveBeenCalledWith(
        "[useCreateAccount] Error:",
        expect.any(Error),
      );

      consoleSpy.mockRestore();
    });
  });

  describe("useUpdateAccount", () => {
    it("updates an account successfully", async () => {
      const updatedAccount = {
        ...testAccount,
        account_name: "Updated Account",
      };
      vi.mocked(organizationApi.updateAccount).mockResolvedValueOnce(
        updatedAccount,
      );

      const { result } = renderHook(() => useUpdateAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        account_name: "Updated Account",
        organization_id: testOrgId,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(updatedAccount);
      expect(organizationApi.updateAccount).toHaveBeenCalledWith(
        testAccountId,
        expect.objectContaining({
          account_name: "Updated Account",
        }),
      );
    });

    it("invalidates queries on successful update", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      vi.mocked(organizationApi.updateAccount).mockResolvedValueOnce(
        testAccount,
      );

      const { result } = renderHook(() => useUpdateAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        account_name: "Updated Account",
        organization_id: testOrgId,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: accountKeys.list(testOrgId),
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: accountKeys.detail(testAccountId),
      });
    });
  });

  describe("useDeleteAccount", () => {
    it("deletes an account successfully", async () => {
      vi.mocked(organizationApi.deleteAccount).mockResolvedValueOnce();

      const { result } = renderHook(() => useDeleteAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({ orgId: testOrgId, accountId: testAccountId });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(organizationApi.deleteAccount).toHaveBeenCalledWith(testAccountId);
    });

    it("invalidates queries on successful deletion", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      vi.mocked(organizationApi.deleteAccount).mockResolvedValueOnce();

      const { result } = renderHook(() => useDeleteAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({ orgId: testOrgId, accountId: testAccountId });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: accountKeys.list(testOrgId),
      });
    });

    it("handles deletion errors", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const errorMessage = "Deletion failed";
      vi.mocked(organizationApi.deleteAccount).mockRejectedValueOnce(
        new Error(errorMessage),
      );

      const { result } = renderHook(() => useDeleteAccount(), {
        wrapper: createWrapper,
      });

      result.current.mutate({ orgId: testOrgId, accountId: testAccountId });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
      expect(consoleSpy).toHaveBeenCalledWith(
        "[useDeleteAccount] Error:",
        expect.any(Error),
      );

      consoleSpy.mockRestore();
    });
  });
});
