/**
 * Tests for Agent Configuration Service Helper Functions
 */

import { describe, it, expect } from "vitest";
import { agentConfigService } from "./agentConfigService";

describe("AgentConfigService", () => {
  describe("formatAgentName", () => {
    it("should format snake_case to Title Case", () => {
      const testCases = [
        ["business_researcher", "Business Researcher"],
        ["marketing_formatter", "Marketing Formatter"],
        ["competitive_researcher", "Competitive Researcher"],
        ["brand_formatter", "Brand Formatter"],
      ];

      for (const [input, expected] of testCases) {
        expect(agentConfigService.formatAgentName(input)).toBe(expected);
      }
    });

    it("should handle single word", () => {
      expect(agentConfigService.formatAgentName("researcher")).toBe(
        "Researcher",
      );
    });

    it("should handle empty segments", () => {
      expect(agentConfigService.formatAgentName("business__researcher")).toBe(
        "Business  Researcher",
      );
    });
  });

  describe("categorizeConfigs", () => {
    it("should categorize all four strategy types", () => {
      const configIds = [
        "business_researcher",
        "business_formatter",
        "competitive_researcher",
        "competitive_formatter",
        "marketing_researcher",
        "marketing_formatter",
        "brand_researcher",
        "brand_formatter",
      ];

      const result = agentConfigService.categorizeConfigs(configIds);

      expect(result.business).toEqual({
        researcher: "business_researcher",
        formatter: "business_formatter",
      });
      expect(result.competitive).toEqual({
        researcher: "competitive_researcher",
        formatter: "competitive_formatter",
      });
      expect(result.marketing).toEqual({
        researcher: "marketing_researcher",
        formatter: "marketing_formatter",
      });
      expect(result.brand).toEqual({
        researcher: "brand_researcher",
        formatter: "brand_formatter",
      });
    });

    it("should handle partial configs", () => {
      const configIds = [
        "business_researcher",
        "marketing_formatter",
        "competitive_formatter",
      ];

      const result = agentConfigService.categorizeConfigs(configIds);

      expect(result.business).toEqual({
        researcher: "business_researcher",
        formatter: "",
      });
      expect(result.marketing).toEqual({
        researcher: "",
        formatter: "marketing_formatter",
      });
      expect(result.competitive).toEqual({
        researcher: "",
        formatter: "competitive_formatter",
      });
    });

    it("should handle empty array", () => {
      const result = agentConfigService.categorizeConfigs([]);
      expect(result).toEqual({});
    });

    it("should ignore unknown config types", () => {
      const configIds = [
        "business_researcher",
        "unknown_type",
        "another_unknown",
      ];

      const result = agentConfigService.categorizeConfigs(configIds);

      expect(result.business).toEqual({
        researcher: "business_researcher",
        formatter: "",
      });
      expect(result.unknown_type).toBeUndefined();
      expect(result.another_unknown).toBeUndefined();
    });
  });
});
