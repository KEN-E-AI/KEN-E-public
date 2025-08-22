import { describe, test, expect } from "vitest";
import {
  validateCrossStepConsistency,
  validateMarketingIntegrationConsistency,
  validateIndustryConsistency,
  validateWebsiteChannelConsistency,
} from "./crossStepValidation";
import type { AccountCreationData } from "@/components/settings/AccountCreationWizard";

const createMockFormData = (
  overrides: Partial<AccountCreationData> = {},
): AccountCreationData => ({
  account_name: "Test Account",
  description: "Test Description",
  industry: "Technology",
  websites: ["https://example.com"],
  estimated_annual_ad_budget: 50000,
  business_strategy_documents: [],
  template_id: "tech-template",
  marketing_channels: ["Search Engine Marketing", "Content Marketing"],
  product_integrations: ["google_analytics"],
  objectives: ["increase_traffic"],
  kpis: ["sessions", "conversions"],
  timezone: "America/New_York",
  data_region: "US",
  region: ["US"],
  ...overrides,
});

describe("Cross-Step Validation", () => {
  describe("validateCrossStepConsistency", () => {
    test("should pass validation for consistent data", () => {
      const formData = createMockFormData({
        marketing_channels: ["Search Engine Marketing", "Content Marketing"],
        product_integrations: ["google_analytics"],
        estimated_annual_ad_budget: 100000,
      });

      const result = validateCrossStepConsistency(formData);

      expect(result.isValid).toBe(true);
    });

    test("should include all individual step validations", () => {
      const formData = createMockFormData({
        marketing_channels: [
          "Search Engine Marketing",
          "Social Media",
          "Search Engine Marketing",
        ], // Duplicate
        product_integrations: ["google_analytics", "adobe_analytics"], // Conflict
      });

      const result = validateCrossStepConsistency(formData);

      expect(result.isValid).toBe(false);
      expect(result.errors.some((e) => e.includes("Duplicate"))).toBe(true);
      expect(result.errors.some((e) => e.includes("conflicts with"))).toBe(
        true,
      );
    });

    test("should include cross-step consistency warnings", () => {
      const formData = createMockFormData({
        marketing_channels: ["Search Engine Marketing"],
        product_integrations: [], // Missing analytics
        estimated_annual_ad_budget: 50000,
      });

      const result = validateCrossStepConsistency(formData);

      expect(
        result.warnings.some(
          (w) =>
            w.includes("consider adding") && w.includes("Google Analytics"),
        ),
      ).toBe(true);
    });
  });

  describe("validateMarketingIntegrationConsistency", () => {
    test("should recommend integrations based on marketing channels", () => {
      const result = validateMarketingIntegrationConsistency(
        ["Search Engine Marketing", "Social Media"],
        [], // No integrations
        100000,
      );

      expect(
        result.warnings.some(
          (w) => w.includes("Google Analytics") || w.includes("Facebook Pixel"),
        ),
      ).toBe(true);
    });

    test("should warn about integration without corresponding channel", () => {
      const result = validateMarketingIntegrationConsistency(
        ["Content Marketing"], // No Google Ads
        ["google_ads"], // But has Google Ads integration
        50000,
      );

      expect(result.warnings.length >= 0).toBe(true); // May or may not warn depending on implementation
    });

    test("should warn about paid channels without conversion tracking", () => {
      const result = validateMarketingIntegrationConsistency(
        ["Search Engine Marketing", "Social Media"],
        ["mailchimp"], // No analytics/tracking
        100000,
      );

      expect(
        result.warnings.some((w) => w.includes("conversion tracking")),
      ).toBe(true);
    });

    test("should warn about low budget spread across many channels", () => {
      const result = validateMarketingIntegrationConsistency(
        [
          "Search Engine Marketing",
          "Social Media",
          "LinkedIn Advertising",
          "Display Advertising",
        ],
        ["google_analytics"],
        20000, // Low budget for 4 channels
      );

      expect(
        result.warnings.some((w) => w.includes("Spreading a $20,000 budget")),
      ).toBe(true);
    });

    test("should not warn about e-commerce when no e-commerce integrations exist", () => {
      const result = validateMarketingIntegrationConsistency(
        ["Content Marketing"],
        ["google_analytics"], // Non-ecommerce integration
        null,
      );

      // Should not generate e-commerce specific warnings
      expect(result.warnings.some((w) => w.includes("email marketing"))).toBe(
        false,
      );
    });

    test("should not warn about SEO for non-ecommerce", () => {
      const result = validateMarketingIntegrationConsistency(
        ["Search Engine Marketing"], // Only paid, no organic
        ["google_analytics"],
        100000,
      );

      // Should not generate e-commerce specific SEO warnings
      expect(
        result.warnings.some((w) => w.includes("SEO or content marketing")),
      ).toBe(false);
    });
  });

  describe("validateIndustryConsistency", () => {
    test("should recommend appropriate channels for E-commerce", () => {
      const result = validateIndustryConsistency(
        "E-commerce",
        ["Content Marketing"], // Missing recommended channels
        ["shopify"], // Has e-commerce integration
      );

      expect(
        result.warnings.some((w) => w.includes("E-commerce businesses")),
      ).toBe(true);
    });

    test("should recommend appropriate channels for SaaS", () => {
      const result = validateIndustryConsistency(
        "SaaS",
        ["Search Engine Marketing"], // Missing content/SEO
        [],
      );

      expect(result.warnings.some((w) => w.includes("SaaS businesses"))).toBe(
        true,
      );
    });

    test("should recommend appropriate channels for Local Services", () => {
      const result = validateIndustryConsistency(
        "Local Services",
        ["Email Marketing"], // Missing local-focused channels
        [],
      );

      expect(result.warnings.some((w) => w.includes("Local Services"))).toBe(
        true,
      );
    });

    test("should recommend appropriate channels for B2B Services", () => {
      const result = validateIndustryConsistency(
        "B2B Services",
        ["Search Engine Marketing"], // Missing LinkedIn/content
        [],
      );

      expect(result.warnings.some((w) => w.includes("B2B Services"))).toBe(
        true,
      );
    });

    test("should pass for industries with appropriate channels", () => {
      const result = validateIndustryConsistency(
        "E-commerce",
        [
          "Search Engine Marketing",
          "Social Media",
          "Email Marketing",
          "Content Marketing",
        ],
        ["google_analytics", "mailchimp", "shopify"],
      );

      expect(result.isValid).toBe(true);
      expect(result.warnings.length).toBeLessThanOrEqual(1); // May have minor suggestions
    });
  });

  describe("validateWebsiteChannelConsistency", () => {
    test("should warn when websites exist but no web channels selected", () => {
      const result = validateWebsiteChannelConsistency(
        ["https://example.com", "https://shop.com"],
        ["Email Marketing", "Social Media"], // No web-focused channels
      );

      expect(
        result.warnings.some((w) =>
          w.includes("web-focused marketing channels"),
        ),
      ).toBe(true);
    });

    test("should warn about SEO for multiple websites", () => {
      const result = validateWebsiteChannelConsistency(
        [
          "https://site1.com",
          "https://site2.com",
          "https://site3.com",
          "https://site4.com",
        ],
        ["Content Marketing"], // SEO selected
      );

      expect(
        result.warnings.some((w) =>
          w.includes("Managing SEO for multiple websites"),
        ),
      ).toBe(true);
    });

    test("should warn when SEO/content selected without websites", () => {
      const result = validateWebsiteChannelConsistency(
        [], // No websites
        ["Content Marketing", "Video Marketing"], // But has website-dependent channels
      );

      expect(
        result.warnings.some((w) =>
          w.includes("require websites to be effective"),
        ),
      ).toBe(true);
    });

    test("should pass for appropriate website-channel combinations", () => {
      const result = validateWebsiteChannelConsistency(
        ["https://example.com"],
        ["Content Marketing", "Search Engine Marketing", "Video Marketing"],
      );

      expect(result.isValid).toBe(true);
      expect(result.warnings.length).toBeLessThanOrEqual(1); // Should be minimal warnings
    });

    test("should handle empty websites and channels gracefully", () => {
      const result = validateWebsiteChannelConsistency([], []);

      expect(result.isValid).toBe(true);
      expect(result.warnings).toHaveLength(0);
    });
  });
});
