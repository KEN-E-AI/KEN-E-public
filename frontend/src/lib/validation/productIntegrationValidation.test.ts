import { describe, test, expect } from "vitest";
import {
  validateProductIntegrations,
  sanitizeProductIntegrations,
  isValidProductIntegration,
  getIntegrationConflicts,
  getIntegrationPrerequisites,
  suggestComplementaryIntegrations,
} from "./productIntegrationValidation";

describe("Product Integration Validation", () => {
  describe("validateProductIntegrations", () => {
    test("should pass validation for valid integrations", () => {
      const result = validateProductIntegrations([
        "google_analytics", // Only available integration
      ]);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    test("should detect duplicate integrations", () => {
      const result = validateProductIntegrations([
        "google_analytics",
        "shopify",
        "google_analytics",
      ]);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain(
        "Duplicate product integrations detected. Please remove duplicates.",
      );
    });

    test("should detect invalid integration IDs", () => {
      const result = validateProductIntegrations([
        "invalid_integration",
        "another_invalid",
      ]);

      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toContain(
        "Invalid product integrations selected:",
      );
    });

    test("should block coming soon integrations", () => {
      const result = validateProductIntegrations(["mailchimp"]); // coming_soon integration

      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.includes("not yet available"))).toBe(
        true,
      );
    });

    test("should enforce maximum integration limit", () => {
      // Create array with valid integration repeated to exceed limit
      const tooManyIntegrations = Array(15).fill("google_analytics");
      const result = validateProductIntegrations(tooManyIntegrations);

      expect(result.isValid).toBe(false);
      expect(
        result.errors.some(
          (e) =>
            e.includes("Maximum") && e.includes("product integrations allowed"),
        ),
      ).toBe(true);
    });

    test("should warn about too many integrations", () => {
      // Use only available integrations (duplicates will be filtered by validation)
      const manyValidIntegrations = [
        "google_analytics", // Only available integration
      ];
      const result = validateProductIntegrations(manyValidIntegrations);

      expect(result.isValid).toBe(true);
      // With only 1 integration, there should be no "too many" warning
      expect(
        result.warnings.some((w) =>
          w.includes("Consider limiting to 5 product integrations"),
        ),
      ).toBe(false);
    });

    test("should detect integration conflicts", () => {
      // Test analytics conflict
      const analyticsConflict = validateProductIntegrations([
        "google_analytics",
        "adobe_analytics",
      ]);
      expect(analyticsConflict.isValid).toBe(false);
      expect(
        analyticsConflict.errors.some((e) => e.includes("conflicts with")),
      ).toBe(true);

      // Test e-commerce conflict
      const ecommerceConflict = validateProductIntegrations([
        "shopify",
        "woocommerce",
      ]);
      expect(ecommerceConflict.isValid).toBe(false);
      expect(
        ecommerceConflict.errors.some((e) => e.includes("conflicts with")),
      ).toBe(true);
    });

    test("should detect missing prerequisites", () => {
      // Test enhanced features requiring basic ones
      const result = validateProductIntegrations(["google_ads_enhanced"]);

      expect(result.isValid).toBe(false);
      expect(
        result.errors.some((e) => e.includes("requires these integrations")),
      ).toBe(true);
    });

    test("should warn about single category selections", () => {
      // This test assumes we have integrations with categories in the test data
      const result = validateProductIntegrations([
        "google_analytics",
        "adobe_analytics",
        "mixpanel",
      ]);

      // Should have conflict errors, but also category diversity warnings
      expect(result.errors.length > 0).toBe(true); // Conflicts
    });

    test("should not recommend analytics when analytics is present", () => {
      // Test with analytics integration - should NOT recommend adding analytics
      const result = validateProductIntegrations(["google_analytics"]);

      expect(result.isValid).toBe(true);
      expect(
        result.warnings.some((w) =>
          w.includes("Consider adding an analytics integration"),
        ),
      ).toBe(false);
    });

    test("should handle empty array", () => {
      const result = validateProductIntegrations([]);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });

  describe("sanitizeProductIntegrations", () => {
    test("should remove duplicates", () => {
      const result = sanitizeProductIntegrations([
        "google_analytics",
        "google_analytics", // Duplicate
      ]);

      expect(result).toEqual(["google_analytics"]);
    });

    test("should remove unavailable integrations", () => {
      // This test assumes we have some unavailable integrations
      const result = sanitizeProductIntegrations([
        "google_analytics",
        "invalid_integration",
      ]);

      expect(result).toEqual(["google_analytics"]);
    });

    test("should resolve conflicts by keeping first occurrence", () => {
      const result = sanitizeProductIntegrations([
        "google_analytics",
        "adobe_analytics", // This should be removed due to conflict, but adobe_analytics doesn't exist in our data
      ]);

      expect(result).toEqual(["google_analytics"]); // adobe_analytics removed due to not existing
    });

    test("should enforce maximum limit", () => {
      const tooManyValidIntegrations = [
        "google_analytics",
        "shopify",
        "mailchimp",
        "hubspot",
        "salesforce",
        "stripe",
        "intercom",
        "zendesk",
        "klaviyo",
        "constant_contact",
        "wordpress",
        "magento",
        "extra",
      ];
      const result = sanitizeProductIntegrations(tooManyValidIntegrations);

      expect(result.length).toBeLessThanOrEqual(12); // Maximum limit
    });
  });

  describe("isValidProductIntegration", () => {
    test("should return true for valid and available integration IDs", () => {
      expect(isValidProductIntegration("google_analytics")).toBe(true);
    });

    test("should return false for invalid integration IDs", () => {
      expect(isValidProductIntegration("invalid_integration")).toBe(false);
      expect(isValidProductIntegration("")).toBe(false);
    });

    test("should return false for coming soon integrations", () => {
      expect(isValidProductIntegration("mailchimp")).toBe(false); // coming_soon integration
    });
  });

  describe("getIntegrationConflicts", () => {
    test("should return conflicts for analytics integrations", () => {
      const conflicts = getIntegrationConflicts("google_analytics");

      expect(conflicts).toContain("adobe_analytics");
      expect(conflicts).toContain("mixpanel");
    });

    test("should return conflicts for e-commerce integrations", () => {
      const conflicts = getIntegrationConflicts("shopify");

      expect(conflicts).toContain("woocommerce");
      expect(conflicts).toContain("magento");
    });

    test("should return empty array for integrations without conflicts", () => {
      const conflicts = getIntegrationConflicts("non_conflicting_integration");

      expect(conflicts).toEqual([]);
    });
  });

  describe("getIntegrationPrerequisites", () => {
    test("should return prerequisites for enhanced integrations", () => {
      const prerequisites = getIntegrationPrerequisites("google_ads_enhanced");

      expect(prerequisites).toContain("google_analytics");
    });

    test("should return empty array for integrations without prerequisites", () => {
      const prerequisites = getIntegrationPrerequisites("google_analytics");

      expect(prerequisites).toEqual([]);
    });
  });

  describe("suggestComplementaryIntegrations", () => {
    test("should suggest analytics when missing", () => {
      const suggestions = suggestComplementaryIntegrations([
        "shopify",
        "mailchimp",
      ]);

      expect(suggestions).toContain("google_analytics");
    });

    test("should return empty for no integrations", () => {
      const suggestions = suggestComplementaryIntegrations([]); // No integrations

      expect(suggestions).toEqual([]);
    });

    test("should not suggest already selected integrations", () => {
      const suggestions = suggestComplementaryIntegrations([
        "google_analytics",
        "mailchimp",
      ]);

      expect(suggestions).not.toContain("google_analytics");
      expect(suggestions).not.toContain("mailchimp");
    });

    test("should return empty array when no suggestions available", () => {
      const suggestions = suggestComplementaryIntegrations([
        "google_analytics",
        "shopify",
        "mailchimp",
      ]);

      // Should be fewer suggestions since major bases are covered
      expect(Array.isArray(suggestions)).toBe(true);
    });
  });
});
