import { describe, test, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useCreateAccount } from "./accounts";
import * as organizationApi from "@/data/organizationApi";

// Mock the organizationApi
vi.mock("@/data/organizationApi", () => ({
  createAccount: vi.fn(),
}));

// Mock console.error to avoid noise in test output
vi.spyOn(console, "error").mockImplementation(() => {});

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useCreateAccount", () => {
  const mockCreateAccount = organizationApi.createAccount as any;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("should transform camelCase fields to snake_case for API call", async () => {
    // Setup
    const mockAccount = {
      account_id: "acc-123",
      account_name: "Test Account",
      organization_id: "org-456",
      industry: "Technology",
      status: "Active",
      websites: ["https://example.com"],
      timezone: "America/New_York",
      data_region: "United States",
      region: ["US"],
      marketing_channels: ["google_ads", "facebook"],
      product_integrations: ["google_analytics", "shopify"],
      estimated_annual_ad_budget: 100000,
    };

    mockCreateAccount.mockResolvedValue(mockAccount);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Execute
    const inputData = {
      accountName: "Test Account",
      organizationId: "org-456",
      industry: "Technology",
      status: "Active",
      websites: ["https://example.com"],
      timezone: "America/New_York",
      dataRegion: "United States",
      region: ["US"],
      marketing_channels: ["google_ads", "facebook"],
      product_integrations: ["google_analytics", "shopify"],
      estimatedAnnualAdBudget: 100000,
      businessStrategyDocuments: [],
    };

    await result.current.mutateAsync(inputData);

    // Verify API was called with snake_case fields
    expect(mockCreateAccount).toHaveBeenCalledWith({
      account_name: "Test Account",
      organization_id: "org-456",
      industry: "Technology",
      status: "Active",
      websites: ["https://example.com"],
      timezone: "America/New_York",
      data_region: "United States",
      region: ["US"],
      marketing_channels: ["google_ads", "facebook"],
      product_integrations: ["google_analytics", "shopify"],
      estimated_annual_ad_budget: 100000,
      business_strategy_documents: [],
    });
  });

  test("should include marketing_channels and product_integrations in API call", async () => {
    // Setup
    const mockAccount = { account_id: "acc-123" };
    mockCreateAccount.mockResolvedValue(mockAccount);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Execute with specific focus on the new fields
    const inputData = {
      accountName: "Test Account",
      organizationId: "org-456",
      industry: "Technology",
      status: "Active",
      websites: [],
      timezone: "America/New_York",
      dataRegion: "United States",
      region: ["US"],
      marketing_channels: ["social_media", "email", "seo"],
      product_integrations: ["google_ads", "meta_ads", "shopify"],
      estimatedAnnualAdBudget: null,
      businessStrategyDocuments: [],
    };

    await result.current.mutateAsync(inputData);

    // Verify the new fields are included in the API call
    const apiCallArgs = mockCreateAccount.mock.calls[0][0];
    expect(apiCallArgs).toHaveProperty("marketing_channels");
    expect(apiCallArgs).toHaveProperty("product_integrations");
    expect(apiCallArgs.marketing_channels).toEqual([
      "social_media",
      "email",
      "seo",
    ]);
    expect(apiCallArgs.product_integrations).toEqual([
      "google_ads",
      "meta_ads",
      "shopify",
    ]);
  });

  test("should handle empty arrays for marketing_channels and product_integrations", async () => {
    // Setup
    const mockAccount = { account_id: "acc-123" };
    mockCreateAccount.mockResolvedValue(mockAccount);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Execute with empty arrays
    const inputData = {
      accountName: "Test Account",
      organizationId: "org-456",
      industry: "Technology",
      status: "Active",
      websites: [],
      timezone: "America/New_York",
      dataRegion: "United States",
      region: ["US"],
      marketing_channels: [],
      product_integrations: [],
      estimatedAnnualAdBudget: null,
      businessStrategyDocuments: [],
    };

    await result.current.mutateAsync(inputData);

    // Verify empty arrays are preserved
    const apiCallArgs = mockCreateAccount.mock.calls[0][0];
    expect(apiCallArgs.marketing_channels).toEqual([]);
    expect(apiCallArgs.product_integrations).toEqual([]);
  });

  test("should handle null and undefined budget values", async () => {
    // Setup
    const mockAccount = { account_id: "acc-123" };
    mockCreateAccount.mockResolvedValue(mockAccount);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Test with null budget
    const inputDataNull = {
      accountName: "Test Account",
      organizationId: "org-456",
      industry: "Technology",
      status: "Active",
      websites: [],
      timezone: "America/New_York",
      dataRegion: "United States",
      region: ["US"],
      marketing_channels: [],
      product_integrations: [],
      estimatedAnnualAdBudget: null,
      businessStrategyDocuments: [],
    };

    await result.current.mutateAsync(inputDataNull);

    expect(mockCreateAccount.mock.calls[0][0].estimated_annual_ad_budget).toBe(
      null,
    );

    // Test with undefined budget
    const inputDataUndefined = {
      ...inputDataNull,
      estimatedAnnualAdBudget: undefined,
    };

    await result.current.mutateAsync(inputDataUndefined);

    expect(mockCreateAccount.mock.calls[1][0].estimated_annual_ad_budget).toBe(
      undefined,
    );
  });

  test("should preserve all other existing fields", async () => {
    // Setup
    const mockAccount = { account_id: "acc-123" };
    mockCreateAccount.mockResolvedValue(mockAccount);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Execute with all possible fields
    const inputData = {
      accountName: "Complete Test Account",
      organizationId: "org-789",
      industry: "E-commerce",
      status: "Active",
      websites: ["https://shop.example.com", "https://blog.example.com"],
      timezone: "America/Los_Angeles",
      dataRegion: "Europe",
      region: ["FR", "DE", "IT"],
      marketing_channels: ["ppc", "social_media"],
      product_integrations: ["google_analytics", "stripe"],
      estimatedAnnualAdBudget: 250000,
      businessStrategyDocuments: [],
    };

    await result.current.mutateAsync(inputData);

    const apiCallArgs = mockCreateAccount.mock.calls[0][0];

    // Verify all fields are properly transformed
    expect(apiCallArgs).toEqual({
      account_name: "Complete Test Account",
      organization_id: "org-789",
      industry: "E-commerce",
      status: "Active",
      websites: ["https://shop.example.com", "https://blog.example.com"],
      timezone: "America/Los_Angeles",
      data_region: "Europe",
      region: ["FR", "DE", "IT"],
      marketing_channels: ["ppc", "social_media"],
      product_integrations: ["google_analytics", "stripe"],
      estimated_annual_ad_budget: 250000,
      business_strategy_documents: [],
    });
  });

  test("should handle API errors appropriately", async () => {
    // Setup
    const apiError = new Error("Account creation failed");
    mockCreateAccount.mockRejectedValue(apiError);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Execute and expect error
    const inputData = {
      accountName: "Test Account",
      organizationId: "org-456",
      industry: "Technology",
      status: "Active",
      websites: [],
      timezone: "America/New_York",
      dataRegion: "United States",
      region: ["US"],
      marketing_channels: [],
      product_integrations: [],
      estimatedAnnualAdBudget: null,
      businessStrategyDocuments: [],
    };

    await expect(result.current.mutateAsync(inputData)).rejects.toThrow(
      "Account creation failed",
    );
  });

  test("should provide runtime validation for marketing_channels and product_integrations", async () => {
    // Setup
    const mockAccount = { account_id: "acc-123" };
    mockCreateAccount.mockResolvedValue(mockAccount);

    const { result } = renderHook(() => useCreateAccount(), {
      wrapper: createWrapper(),
    });

    // Execute with potentially invalid array data (simulating runtime issues)
    const inputData = {
      accountName: "Test Account",
      organizationId: "org-456",
      industry: "Technology",
      status: "Active",
      websites: [],
      timezone: "America/New_York",
      dataRegion: "United States",
      region: ["US"],
      marketing_channels: null as any, // Simulate runtime null value
      product_integrations: undefined as any, // Simulate runtime undefined value
      estimatedAnnualAdBudget: null,
      businessStrategyDocuments: [],
    };

    await result.current.mutateAsync(inputData);

    // Verify runtime validation converts non-arrays to empty arrays
    const apiCallArgs = mockCreateAccount.mock.calls[0][0];
    expect(apiCallArgs.marketing_channels).toEqual([]);
    expect(apiCallArgs.product_integrations).toEqual([]);
    expect(Array.isArray(apiCallArgs.marketing_channels)).toBe(true);
    expect(Array.isArray(apiCallArgs.product_integrations)).toBe(true);
  });
});
