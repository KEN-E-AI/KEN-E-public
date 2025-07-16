import { describe, test, expect, vi } from "vitest";
import {
  resolveOrganizationAndAccount,
  getTargetOrganizationId,
  validateAccountCreationRequirements,
  formatWorkspaceMetadata,
  processAccountsForDisplay,
  isAgencyOrganization,
  getAvailableAccounts,
} from "./organizationUtils";

describe("organizationUtils", () => {
  const mockOrgMetadata = {
    "org-1": {
      organization_id: "org-1",
      organization_name: "Regular Org",
      agency: false,
      accounts: [
        { account_id: "acc-1", account_name: "Account 1", industry: "Tech" },
      ],
    },
    "agency-org": {
      organization_id: "agency-org",
      organization_name: "Agency Org",
      agency: true,
      child_organizations: ["child-org-1"],
    },
  };

  const mockChildOrganizations = [
    {
      organization_id: "child-org-1",
      organization_name: "Child Org 1",
      accounts: [
        {
          account_id: "child-acc-1",
          account_name: "Child Account 1",
          industry: "Finance",
        },
      ],
    },
  ];

  const mockFirestoreOrgs = {
    "org-1": "admin",
    "agency-org": "admin",
  };

  describe("resolveOrganizationAndAccount", () => {
    test("resolves regular organization correctly", () => {
      const result = resolveOrganizationAndAccount(
        "org-1",
        "acc-1",
        "",
        mockOrgMetadata,
        mockChildOrganizations,
      );

      expect(result.organizationId).toBe("org-1");
      expect(result.organization).toBe(mockOrgMetadata["org-1"]);
      expect(result.account.account_id).toBe("acc-1");
    });

    test("resolves agency organization with child org correctly", () => {
      const result = resolveOrganizationAndAccount(
        "agency-org",
        "child-acc-1",
        "child-org-1",
        mockOrgMetadata,
        mockChildOrganizations,
      );

      expect(result.organizationId).toBe("child-org-1");
      expect(result.organization).toBe(mockChildOrganizations[0]);
      expect(result.account.account_id).toBe("child-acc-1");
    });

    test("handles agency organization without child org selection", () => {
      const result = resolveOrganizationAndAccount(
        "agency-org",
        "child-acc-1",
        "",
        mockOrgMetadata,
        mockChildOrganizations,
      );

      expect(result.organizationId).toBe("agency-org");
      expect(result.organization).toBe(mockOrgMetadata["agency-org"]);
      expect(result.account).toBeUndefined();
    });
  });

  describe("getTargetOrganizationId", () => {
    test("returns child org ID for agency organization", () => {
      const result = getTargetOrganizationId(
        "agency-org",
        "child-org-1",
        mockOrgMetadata,
      );

      expect(result).toBe("child-org-1");
    });

    test("returns selected org ID for regular organization", () => {
      const result = getTargetOrganizationId(
        "org-1",
        "child-org-1",
        mockOrgMetadata,
      );

      expect(result).toBe("org-1");
    });

    test("returns selected org ID when no child org selected", () => {
      const result = getTargetOrganizationId("agency-org", "", mockOrgMetadata);

      expect(result).toBe("agency-org");
    });
  });

  describe("validateAccountCreationRequirements", () => {
    test("validates successful case for regular organization", () => {
      const result = validateAccountCreationRequirements(
        "org-1",
        "",
        mockOrgMetadata,
        "Test Account",
        "Production",
      );

      expect(result.isValid).toBe(true);
      expect(result.errorMessage).toBeUndefined();
    });

    test("validates successful case for agency organization with child org", () => {
      const result = validateAccountCreationRequirements(
        "agency-org",
        "child-org-1",
        mockOrgMetadata,
        "Test Account",
        "Production",
      );

      expect(result.isValid).toBe(true);
      expect(result.errorMessage).toBeUndefined();
    });

    test("fails when no organization selected", () => {
      const result = validateAccountCreationRequirements(
        "",
        "",
        mockOrgMetadata,
        "Test Account",
        "Production",
      );

      expect(result.isValid).toBe(false);
      expect(result.errorMessage).toBe("Please select an organization first.");
    });

    test("fails when agency organization but no child org selected", () => {
      const result = validateAccountCreationRequirements(
        "agency-org",
        "",
        mockOrgMetadata,
        "Test Account",
        "Production",
      );

      expect(result.isValid).toBe(false);
      expect(result.errorMessage).toBe(
        "Please select a client organization first.",
      );
    });

    test("fails when account name is missing", () => {
      const result = validateAccountCreationRequirements(
        "org-1",
        "",
        mockOrgMetadata,
        "",
        "Production",
      );

      expect(result.isValid).toBe(false);
      expect(result.errorMessage).toBe("Please fill in all required fields");
    });

    test("fails when account type is missing", () => {
      const result = validateAccountCreationRequirements(
        "org-1",
        "",
        mockOrgMetadata,
        "Test Account",
        "",
      );

      expect(result.isValid).toBe(false);
      expect(result.errorMessage).toBe("Please fill in all required fields");
    });
  });

  describe("formatWorkspaceMetadata", () => {
    test("formats metadata with all fields", () => {
      const result = formatWorkspaceMetadata(
        "Test Org",
        "Test Account",
        "Technology",
        "Active",
        "America/New_York",
        "Premium",
      );

      expect(result).toEqual({
        organization_name: "Test Org",
        account_name: "Test Account",
        industry: "Technology",
        status: "Active",
        timezone: "America/New_York",
        plan: "Premium",
      });
    });

    test("formats metadata with defaults for missing fields", () => {
      const result = formatWorkspaceMetadata(
        "Test Org",
        "Test Account",
        "",
        "",
      );

      expect(result).toEqual({
        organization_name: "Test Org",
        account_name: "Test Account",
        industry: "Unknown",
        status: "Active",
        timezone: undefined,
        plan: undefined,
      });
    });
  });

  describe("processAccountsForDisplay", () => {
    test("processes accounts correctly", () => {
      const accounts = [
        {
          account_id: "acc-1",
          account_name: "Account 1",
          industry: "Tech",
          status: "Active",
        },
        { account_id: "acc-2", industry: "Finance" },
      ];

      const result = processAccountsForDisplay(accounts, "admin");

      expect(result).toEqual([
        {
          account_id: "acc-1",
          account_name: "Account 1",
          industry: "Tech",
          status: "Active",
          permission: "admin",
        },
        {
          account_id: "acc-2",
          account_name: "acc 2",
          industry: "Finance",
          status: "Active",
          permission: "admin",
        },
      ]);
    });

    test("handles empty accounts array", () => {
      const result = processAccountsForDisplay([], "admin");

      expect(result).toEqual([]);
    });
  });

  describe("isAgencyOrganization", () => {
    test("returns true for agency organization", () => {
      const result = isAgencyOrganization({ agency: true });

      expect(result).toBe(true);
    });

    test("returns false for regular organization", () => {
      const result = isAgencyOrganization({ agency: false });

      expect(result).toBe(false);
    });

    test("returns false for organization without agency field", () => {
      const result = isAgencyOrganization({});

      expect(result).toBe(false);
    });

    test("returns false for null/undefined", () => {
      expect(isAgencyOrganization(null)).toBe(false);
      expect(isAgencyOrganization(undefined)).toBe(false);
    });
  });

  describe("getAvailableAccounts", () => {
    const mockGetAccountsByOrganizationIdFromLocal = vi.fn();

    beforeEach(() => {
      mockGetAccountsByOrganizationIdFromLocal.mockClear();
    });

    test("returns empty array when no organization selected", () => {
      const result = getAvailableAccounts(
        "",
        "",
        mockOrgMetadata,
        mockChildOrganizations,
        mockFirestoreOrgs,
        mockGetAccountsByOrganizationIdFromLocal,
      );

      expect(result).toEqual([]);
    });

    test("returns accounts for regular organization", () => {
      const mockAccounts = [{ account_id: "acc-1", account_name: "Account 1" }];
      mockGetAccountsByOrganizationIdFromLocal.mockReturnValue(mockAccounts);

      const result = getAvailableAccounts(
        "org-1",
        "",
        mockOrgMetadata,
        mockChildOrganizations,
        mockFirestoreOrgs,
        mockGetAccountsByOrganizationIdFromLocal,
      );

      expect(result).toBe(mockAccounts);
      expect(mockGetAccountsByOrganizationIdFromLocal).toHaveBeenCalledWith(
        "org-1",
      );
    });

    test("returns empty array for agency organization without child org", () => {
      const result = getAvailableAccounts(
        "agency-org",
        "",
        mockOrgMetadata,
        mockChildOrganizations,
        mockFirestoreOrgs,
        mockGetAccountsByOrganizationIdFromLocal,
      );

      expect(result).toEqual([]);
    });

    test("returns processed accounts for agency organization with child org", () => {
      const result = getAvailableAccounts(
        "agency-org",
        "child-org-1",
        mockOrgMetadata,
        mockChildOrganizations,
        mockFirestoreOrgs,
        mockGetAccountsByOrganizationIdFromLocal,
      );

      expect(result).toEqual([
        {
          account_id: "child-acc-1",
          account_name: "Child Account 1",
          industry: "Finance",
          status: "Active",
          permission: "admin",
        },
      ]);
    });
  });
});
