import { describe, test, expect, vi, beforeEach } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import {
  validateAccountCreation,
  transformWizardData,
  updateContextsAfterCreation,
  refreshAccountQueries,
} from "./AccountsManagement.helpers";
import type { AccountCreationData } from "@/components/settings/AccountCreationWizard";

// Local factory for AccountCreationData fixtures. The shape grew template_id,
// marketing_channels, product_integrations, enabled_strategies, etc. after
// these tests were written; this helper supplies sensible defaults so each
// test only declares the fields it actually exercises.
const makeAccountCreationData = (
  overrides: Partial<AccountCreationData> = {},
): AccountCreationData => ({
  account_name: "Test Account",
  industry: "Technology",
  websites: [],
  estimated_annual_ad_budget: null,
  business_strategy_documents: [],
  template_id: "",
  marketing_channels: [],
  product_integrations: [],
  enabled_strategies: [],
  override_product_categories: [],
  timezone: "America/New_York",
  data_region: "United States",
  region: ["US"],
  objectives: [],
  kpis: [],
  ...overrides,
});

// Mock the accountKeys
vi.mock("@/queries/accounts", () => ({
  accountKeys: {
    list: vi.fn((orgId: string) => ["accounts", "list", orgId]),
  },
}));

describe("AccountsManagement Helper Functions - Unit Tests", () => {
  describe("validateAccountCreation", () => {
    test("should return null for valid data with organization", () => {
      const validData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = validateAccountCreation(validData, "org-123");
      expect(result).toBeNull();
    });

    test("should return error for missing organization ID", () => {
      const validData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = validateAccountCreation(validData, null);
      expect(result).toBe(
        "No organization selected. Please select an organization first.",
      );
    });

    test("should return error for missing account name", () => {
      const invalidData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = validateAccountCreation(invalidData, "org-123");
      expect(result).toBe(
        "Please fill in required fields: account name and industry.",
      );
    });

    test("should return error for missing industry", () => {
      const invalidData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = validateAccountCreation(invalidData, "org-123");
      expect(result).toBe(
        "Please fill in required fields: account name and industry.",
      );
    });

    test("should return error for both missing name and industry", () => {
      const invalidData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "",
        industry: "",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = validateAccountCreation(invalidData, "org-123");
      expect(result).toBe(
        "Please fill in required fields: account name and industry.",
      );
    });
  });

  describe("transformWizardData", () => {
    test("should correctly transform all wizard data fields", () => {
      const wizardData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/Los_Angeles",
        data_region: "Europe",
        region: ["FR"],
        websites: ["https://example.com", "https://test.com"],
        estimated_annual_ad_budget: 100000,
        business_strategy_documents: [],
      };

      const result = transformWizardData(wizardData, "org-456");

      expect(result).toEqual({
        accountName: "Test Account",
        organizationId: "org-456",
        industry: "Technology",
        status: "Active",
        websites: ["https://example.com", "https://test.com"],
        timezone: "America/Los_Angeles",
        dataRegion: "Europe",
        region: ["FR"],
        estimatedAnnualAdBudget: 100000,
        businessStrategyDocuments: [],
      });
    });

    test("should handle null and undefined values with defaults", () => {
      const wizardDataWithNulls: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: null as any,
        estimated_annual_ad_budget: null,
        business_strategy_documents: null as any,
      };

      const result = transformWizardData(wizardDataWithNulls, "org-789");

      expect(result).toEqual({
        accountName: "Test Account",
        organizationId: "org-789",
        industry: "Technology",
        status: "Active",
        websites: [],
        timezone: "America/New_York",
        dataRegion: "United States",
        region: ["US"],
        estimatedAnnualAdBudget: null,
        businessStrategyDocuments: [],
      });
    });

    test("should preserve status as Active constant", () => {
      const wizardData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = transformWizardData(wizardData, "org-123");
      expect(result.status).toBe("Active");
      expect(typeof result.status).toBe("string");
    });

    test("should handle zero budget value", () => {
      const wizardData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: 0,
        business_strategy_documents: [],
      };

      const result = transformWizardData(wizardData, "org-123");
      expect(result.estimatedAnnualAdBudget).toBe(null);
    });

    test("should handle positive budget value", () => {
      const wizardData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: 50000,
        business_strategy_documents: [],
      };

      const result = transformWizardData(wizardData, "org-123");
      expect(result.estimatedAnnualAdBudget).toBe(50000);
    });
  });

  describe("updateContextsAfterCreation", () => {
    test("should update account metadata with new account", () => {
      const mockSetAccountMetadata = vi.fn();
      const mockSetOrgMetadata = vi.fn();

      const newAccount = {
        account_id: "acc-456",
        account_name: "New Account",
        industry: "Technology",
        status: "Active",
      };

      updateContextsAfterCreation(
        newAccount,
        "org-123",
        mockSetAccountMetadata,
        mockSetOrgMetadata,
      );

      // Check that setAccountMetadata was called with updater function
      expect(mockSetAccountMetadata).toHaveBeenCalledTimes(1);
      const accountUpdater = mockSetAccountMetadata.mock.calls[0][0];

      // Test the updater function
      const prevAccountMetadata = { "acc-123": { account_id: "acc-123" } };
      const newAccountMetadata = accountUpdater(prevAccountMetadata);

      expect(newAccountMetadata).toEqual({
        "acc-123": { account_id: "acc-123" },
        "acc-456": newAccount,
      });
    });

    test("should update org metadata with new account", () => {
      const mockSetAccountMetadata = vi.fn();
      const mockSetOrgMetadata = vi.fn();

      const newAccount = {
        account_id: "acc-456",
        account_name: "New Account",
        industry: "Technology",
        status: "Active",
      };

      updateContextsAfterCreation(
        newAccount,
        "org-123",
        mockSetAccountMetadata,
        mockSetOrgMetadata,
      );

      // Check that setOrgMetadata was called with updater function
      expect(mockSetOrgMetadata).toHaveBeenCalledTimes(1);
      const orgUpdater = mockSetOrgMetadata.mock.calls[0][0];

      // Test the updater function with existing accounts
      const existingAccounts = [
        { account_id: "acc-123", account_name: "Existing Account" },
      ];
      const prevOrgMetadata = {
        "org-123": { accounts: existingAccounts },
      };
      const newOrgMetadata = orgUpdater(prevOrgMetadata);

      expect(newOrgMetadata).toEqual({
        "org-123": {
          accounts: [...existingAccounts, newAccount],
        },
      });
    });

    test("should handle organization with no existing accounts", () => {
      const mockSetAccountMetadata = vi.fn();
      const mockSetOrgMetadata = vi.fn();

      const newAccount = {
        account_id: "acc-456",
        account_name: "First Account",
        industry: "Technology",
        status: "Active",
      };

      updateContextsAfterCreation(
        newAccount,
        "org-new",
        mockSetAccountMetadata,
        mockSetOrgMetadata,
      );

      const orgUpdater = mockSetOrgMetadata.mock.calls[0][0];

      // Test with empty org metadata
      const prevOrgMetadata = {};
      const newOrgMetadata = orgUpdater(prevOrgMetadata);

      expect(newOrgMetadata).toEqual({
        "org-new": {
          accounts: [newAccount],
        },
      });
    });

    test("should handle organization with undefined accounts array", () => {
      const mockSetAccountMetadata = vi.fn();
      const mockSetOrgMetadata = vi.fn();

      const newAccount = {
        account_id: "acc-456",
        account_name: "First Account",
        industry: "Technology",
        status: "Active",
      };

      updateContextsAfterCreation(
        newAccount,
        "org-123",
        mockSetAccountMetadata,
        mockSetOrgMetadata,
      );

      const orgUpdater = mockSetOrgMetadata.mock.calls[0][0];

      // Test with org that has no accounts property
      const prevOrgMetadata = {
        "org-123": { organization_name: "Test Org" },
      };
      const newOrgMetadata = orgUpdater(prevOrgMetadata);

      expect(newOrgMetadata).toEqual({
        "org-123": {
          organization_name: "Test Org",
          accounts: [newAccount],
        },
      });
    });
  });

  describe("refreshAccountQueries", () => {
    let mockQueryClient: QueryClient;

    beforeEach(() => {
      mockQueryClient = {
        invalidateQueries: vi.fn().mockResolvedValue(undefined),
        refetchQueries: vi.fn().mockResolvedValue(undefined),
      } as any;
    });

    test("should call invalidateQueries with correct query key", async () => {
      await refreshAccountQueries(mockQueryClient, "org-123");

      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["accounts", "list", "org-123"],
      });
    });

    test("should call refetchQueries with correct query key", async () => {
      await refreshAccountQueries(mockQueryClient, "org-123");

      expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
        queryKey: ["accounts", "list", "org-123"],
      });
    });

    test("should call both operations in sequence", async () => {
      await refreshAccountQueries(mockQueryClient, "org-456");

      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledTimes(1);
      expect(mockQueryClient.refetchQueries).toHaveBeenCalledTimes(1);
    });

    test("should handle different organization IDs", async () => {
      await refreshAccountQueries(mockQueryClient, "org-different");

      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["accounts", "list", "org-different"],
      });
      expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
        queryKey: ["accounts", "list", "org-different"],
      });
    });

    test("should handle query client errors gracefully", async () => {
      const error = new Error("Query failed");
      mockQueryClient.invalidateQueries = vi.fn().mockRejectedValue(error);

      // Should propagate the error for caller to handle
      await expect(
        refreshAccountQueries(mockQueryClient, "org-123"),
      ).rejects.toThrow("Query failed");
    });

    test("should handle async operations correctly", async () => {
      // Mock async behavior
      let invalidateResolved = false;
      mockQueryClient.invalidateQueries = vi.fn().mockImplementation(() => {
        return new Promise((resolve) => {
          setTimeout(() => {
            invalidateResolved = true;
            resolve(undefined);
          }, 10);
        });
      });

      mockQueryClient.refetchQueries = vi.fn().mockImplementation(() => {
        // This should only be called after invalidate is done
        expect(invalidateResolved).toBe(true);
        return Promise.resolve(undefined);
      });

      await refreshAccountQueries(mockQueryClient, "org-123");

      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledTimes(1);
      expect(mockQueryClient.refetchQueries).toHaveBeenCalledTimes(1);
    });
  });

  describe("Helper functions edge cases", () => {
    test("validateAccountCreation should handle whitespace-only strings", () => {
      const dataWithWhitespace: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "   ",
        industry: "\t\n",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      // The function checks for falsy values, so whitespace should be treated as truthy
      // This is intentional behavior - trim() is not used here to avoid over-processing
      const result = validateAccountCreation(dataWithWhitespace, "org-123");
      expect(result).toBeNull(); // Passes validation (whitespace is truthy)
    });

    test("transformWizardData should handle complex website arrays", () => {
      const wizardData: AccountCreationData = {
        ...makeAccountCreationData(),
        account_name: "Test Account",
        industry: "Technology",
        timezone: "America/New_York",
        data_region: "United States",
        region: ["US"],
        websites: [
          "https://example.com",
          "https://subdomain.example.com",
          "http://legacy.example.com",
          "https://example.co.uk",
        ],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
      };

      const result = transformWizardData(wizardData, "org-123");
      expect(result.websites).toEqual([
        "https://example.com",
        "https://subdomain.example.com",
        "http://legacy.example.com",
        "https://example.co.uk",
      ]);
      expect(result.websites.length).toBe(4);
    });

    test("updateContextsAfterCreation should handle accounts with complex metadata", () => {
      const mockSetAccountMetadata = vi.fn();
      const mockSetOrgMetadata = vi.fn();

      const complexAccount = {
        account_id: "acc-complex",
        account_name: "Complex Account",
        industry: "Technology",
        status: "Active",
        websites: ["https://example.com", "https://test.com"],
        timezone: "America/Los_Angeles",
        data_region: "Europe",
        region: ["FR", "DE", "IT"],
        estimated_annual_ad_budget: 250000,
        custom_field: "custom_value",
        nested: {
          property: "nested_value",
          array: [1, 2, 3],
        },
      };

      updateContextsAfterCreation(
        complexAccount,
        "org-123",
        mockSetAccountMetadata,
        mockSetOrgMetadata,
      );

      const accountUpdater = mockSetAccountMetadata.mock.calls[0][0];
      const newAccountMetadata = accountUpdater({});

      expect(newAccountMetadata["acc-complex"]).toEqual(complexAccount);
    });
  });
});
