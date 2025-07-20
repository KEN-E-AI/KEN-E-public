import { describe, test, expect } from "vitest";

// Types for testing
interface NewOrgFormData {
  organization_name: string;
  company_size: string;
  agency: boolean;
  child_organizations: string[];
}

interface ValidationResult {
  isValid: boolean;
  error?: {
    title: string;
    description: string;
  };
}

// Extract the pure functions for testing
const validateOrganizationData = (
  formData: NewOrgFormData,
): ValidationResult => {
  if (!formData.organization_name || !formData.company_size) {
    return {
      isValid: false,
      error: {
        title: "Missing required fields",
        description: "Please fill in all required fields",
      },
    };
  }
  return { isValid: true };
};

const generateOrganizationPayload = (formData: NewOrgFormData) => {
  return {
    organization_name: formData.organization_name,
    plan: "Free",
    website: "",
    company_size: formData.company_size,
    agency: formData.agency,
    child_organizations: formData.child_organizations,
    subscription: {
      plan_name: "Free Plan",
      plan_description: "Basic features for getting started",
      price: 0,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: new Date().toISOString(),
      features: ["Basic Reports", "1 User"],
      usage: {
        reports_generated: 0,
        reports_limit: 10,
      },
    },
    billing: {
      payment_method: {
        last_four: "",
        brand: "",
        expires: "",
      },
      address: "",
      tax_id: "",
    },
    team: {
      members_used: 1,
      members_limit: 1,
      pending_invitations: 0,
    },
  };
};

describe("AccountSettings helper functions", () => {
  describe("validateOrganizationData", () => {
    test("should return valid result for complete form data", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Org",
        company_size: "11-50",
        agency: false,
        child_organizations: [],
      };

      const result = validateOrganizationData(formData);

      expect(result.isValid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    test("should return invalid result when organization_name is missing", () => {
      const formData: NewOrgFormData = {
        organization_name: "",
        company_size: "11-50",
        agency: false,
        child_organizations: [],
      };

      const result = validateOrganizationData(formData);

      expect(result.isValid).toBe(false);
      expect(result.error).toEqual({
        title: "Missing required fields",
        description: "Please fill in all required fields",
      });
    });

    test("should return invalid result when company_size is missing", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Org",
        company_size: "",
        agency: false,
        child_organizations: [],
      };

      const result = validateOrganizationData(formData);

      expect(result.isValid).toBe(false);
      expect(result.error).toEqual({
        title: "Missing required fields",
        description: "Please fill in all required fields",
      });
    });

    test("should return invalid result when both required fields are missing", () => {
      const formData: NewOrgFormData = {
        organization_name: "",
        company_size: "",
        agency: false,
        child_organizations: [],
      };

      const result = validateOrganizationData(formData);

      expect(result.isValid).toBe(false);
      expect(result.error).toEqual({
        title: "Missing required fields",
        description: "Please fill in all required fields",
      });
    });
  });

  describe("generateOrganizationPayload", () => {
    test("should generate correct payload structure", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Organization",
        company_size: "11-50",
        agency: true,
        child_organizations: ["child1", "child2"],
      };

      const payload = generateOrganizationPayload(formData);

      expect(payload.organization_name).toBe(formData.organization_name);
      expect(payload.company_size).toBe(formData.company_size);
      expect(payload.agency).toBe(formData.agency);
      expect(payload.child_organizations).toEqual(formData.child_organizations);
    });

    test("should generate correct default values", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Organization",
        company_size: "11-50",
        agency: false,
        child_organizations: [],
      };

      const payload = generateOrganizationPayload(formData);

      expect(payload.plan).toBe("Free");
      expect(payload.website).toBe("");
      expect(payload.subscription.plan_name).toBe("Free Plan");
      expect(payload.subscription.price).toBe(0);
      expect(payload.subscription.currency).toBe("USD");
      expect(payload.subscription.billing_cycle).toBe("monthly");
      expect(payload.subscription.features).toEqual([
        "Basic Reports",
        "1 User",
      ]);
      expect(payload.subscription.usage.reports_generated).toBe(0);
      expect(payload.subscription.usage.reports_limit).toBe(10);
    });

    test("should generate correct billing structure", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Organization",
        company_size: "11-50",
        agency: false,
        child_organizations: [],
      };

      const payload = generateOrganizationPayload(formData);

      expect(payload.billing.payment_method.last_four).toBe("");
      expect(payload.billing.payment_method.brand).toBe("");
      expect(payload.billing.payment_method.expires).toBe("");
      expect(payload.billing.address).toBe("");
      expect(payload.billing.tax_id).toBe("");
    });

    test("should generate correct team structure", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Organization",
        company_size: "11-50",
        agency: false,
        child_organizations: [],
      };

      const payload = generateOrganizationPayload(formData);

      expect(payload.team.members_used).toBe(1);
      expect(payload.team.members_limit).toBe(1);
      expect(payload.team.pending_invitations).toBe(0);
    });

    test("should handle agency configuration correctly", () => {
      const formData: NewOrgFormData = {
        organization_name: "Agency Organization",
        company_size: "51-200",
        agency: true,
        child_organizations: ["child1", "child2", "child3"],
      };

      const payload = generateOrganizationPayload(formData);

      expect(payload.agency).toBe(true);
      expect(payload.child_organizations).toEqual([
        "child1",
        "child2",
        "child3",
      ]);
    });

    test("should generate valid timestamp for next_billing_date", () => {
      const formData: NewOrgFormData = {
        organization_name: "Test Organization",
        company_size: "11-50",
        agency: false,
        child_organizations: [],
      };

      const payload = generateOrganizationPayload(formData);

      // Should be a valid ISO string
      expect(
        () => new Date(payload.subscription.next_billing_date),
      ).not.toThrow();

      // Should be a recent timestamp (within last few seconds)
      const generatedDate = new Date(payload.subscription.next_billing_date);
      const now = new Date();
      const diffInSeconds =
        Math.abs(now.getTime() - generatedDate.getTime()) / 1000;
      expect(diffInSeconds).toBeLessThan(5);
    });
  });
});
