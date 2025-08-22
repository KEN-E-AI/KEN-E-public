import { describe, test, expect } from "vitest";
import {
  validateMarketingChannels,
  validateMarketingChannelsWithBudget,
  sanitizeMarketingChannels,
  isValidMarketingChannel,
} from "./marketingChannelValidation";

describe("Marketing Channel Validation", () => {
  describe("validateMarketingChannels", () => {
    test("should pass validation for valid channels", () => {
      const result = validateMarketingChannels([
        "Search Engine Marketing",
        "Social Media",
        "Email Marketing",
      ]);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    test("should detect duplicate channels", () => {
      const result = validateMarketingChannels([
        "Search Engine Marketing",
        "Social Media",
        "Search Engine Marketing",
      ]);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain(
        "Duplicate marketing channels detected. Please remove duplicates.",
      );
    });

    test("should detect invalid channel IDs", () => {
      const result = validateMarketingChannels([
        "invalid_channel",
        "another_invalid",
      ]);

      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toContain(
        "Invalid marketing channels selected:",
      );
      expect(result.errors[0]).toContain("invalid_channel, another_invalid");
    });

    test("should enforce maximum channel limit", () => {
      const tooManyChannels = Array(10)
        .fill(0)
        .map((_, i) => `channel_${i}`);
      const result = validateMarketingChannels(tooManyChannels);

      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toContain("Invalid marketing channels selected");
    });

    test("should not warn about channel count since the warning was removed", () => {
      const manyChannels = [
        "Search Engine Marketing",
        "Social Media",
        "Display Advertising",
        "LinkedIn Advertising",
      ];
      const result = validateMarketingChannels(manyChannels);

      expect(result.isValid).toBe(true);
      expect(result.warnings.length).toBeLessThanOrEqual(1); // May have other warnings but not count warning
    });

    test("should suggest mixing paid and organic channels", () => {
      // Only paid channels
      const paidOnlyResult = validateMarketingChannels([
        "Search Engine Marketing",
        "Social Media",
      ]);
      expect(
        paidOnlyResult.warnings.some((w) =>
          w.includes("organic marketing channels"),
        ),
      ).toBe(true);

      // Only organic channels
      const organicOnlyResult = validateMarketingChannels([
        "Content Marketing",
        "Email Marketing",
      ]);
      expect(
        organicOnlyResult.warnings.some((w) =>
          w.includes("paid marketing channels"),
        ),
      ).toBe(true);
    });

    test("should handle empty array", () => {
      const result = validateMarketingChannels([]);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
      expect(result.warnings).toHaveLength(0);
    });
  });

  describe("validateMarketingChannelsWithBudget", () => {
    test("should not warn when paid channels selected without budget", () => {
      const result = validateMarketingChannelsWithBudget(
        ["Search Engine Marketing", "Social Media"],
        null,
      );

      expect(result.isValid).toBe(true);
      // Warning about paid channels without budget has been removed
      expect(
        result.warnings.some((w) => w.includes("no advertising budget")),
      ).toBe(false);
    });

    test("should warn when budget set without paid channels", () => {
      const result = validateMarketingChannelsWithBudget(
        ["Content Marketing", "Email Marketing"],
        50000,
      );

      expect(result.isValid).toBe(true);
      expect(
        result.warnings.some((w) => w.includes("no paid marketing channels")),
      ).toBe(true);
    });

    test("should warn about low budget per channel", () => {
      const result = validateMarketingChannelsWithBudget(
        ["Search Engine Marketing", "Social Media"],
        1500,
      );

      expect(result.isValid).toBe(true);
      expect(result.warnings.some((w) => w.includes("each channel gets"))).toBe(
        true,
      );
    });

    test("should warn about too many channels with limited budget", () => {
      const result = validateMarketingChannelsWithBudget(
        [
          "Search Engine Marketing",
          "Social Media",
          "LinkedIn Advertising",
          "Display Advertising",
        ],
        30000,
      );

      expect(result.isValid).toBe(true);
      expect(
        result.warnings.some((w) => w.includes("Managing many paid channels")),
      ).toBe(true);
    });

    test("should not warn for appropriate budget allocation", () => {
      const result = validateMarketingChannelsWithBudget(
        ["Search Engine Marketing", "Social Media"],
        100000,
      );

      expect(result.isValid).toBe(true);
      // Should not have low budget warnings
      expect(
        result.warnings.every((w) => !w.includes("each channel gets")),
      ).toBe(true);
      expect(
        result.warnings.every(
          (w) => !w.includes("Managing many paid channels"),
        ),
      ).toBe(true);
    });
  });

  describe("sanitizeMarketingChannels", () => {
    test("should remove duplicates", () => {
      const result = sanitizeMarketingChannels([
        "Search Engine Marketing",
        "Social Media",
        "Search Engine Marketing",
      ]);

      expect(result).toEqual(["Search Engine Marketing", "Social Media"]);
    });

    test("should remove invalid channels", () => {
      const result = sanitizeMarketingChannels([
        "Search Engine Marketing",
        "invalid_channel",
        "Social Media",
      ]);

      expect(result).toEqual(["Search Engine Marketing", "Social Media"]);
    });

    test("should enforce maximum limit", () => {
      const tooManyValidChannels = [
        "Search Engine Marketing",
        "Social Media",
        "Email Marketing",
        "Content Marketing",
        "Display Advertising",
        "LinkedIn Advertising",
        "Shopping Ads",
        "Mobile App Advertising",
        "Video Marketing", // This should be truncated
      ];
      const result = sanitizeMarketingChannels(tooManyValidChannels);

      expect(result).toHaveLength(8); // Maximum limit
      expect(result.slice(0, 8)).toEqual(tooManyValidChannels.slice(0, 8));
    });

    test("should handle empty array", () => {
      const result = sanitizeMarketingChannels([]);

      expect(result).toEqual([]);
    });
  });

  describe("isValidMarketingChannel", () => {
    test("should return true for valid channel names", () => {
      expect(isValidMarketingChannel("Search Engine Marketing")).toBe(true);
      expect(isValidMarketingChannel("Social Media")).toBe(true);
      expect(isValidMarketingChannel("Email Marketing")).toBe(true);
    });

    test("should return false for invalid channel names", () => {
      expect(isValidMarketingChannel("invalid_channel")).toBe(false);
      expect(isValidMarketingChannel("")).toBe(false);
      expect(isValidMarketingChannel("random_string")).toBe(false);
    });
  });
});
