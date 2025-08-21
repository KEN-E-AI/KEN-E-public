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
        "google_ads",
        "facebook",
        "email",
      ]);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    test("should detect duplicate channels", () => {
      const result = validateMarketingChannels([
        "google_ads",
        "facebook",
        "google_ads",
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
      expect(result.errors[0]).toContain(
        "Maximum 8 marketing channels allowed",
      );
    });

    test("should warn about too many channels for performance", () => {
      const manyChannels = [
        "google_ads",
        "facebook",
        "email",
        "seo",
        "content",
      ];
      const result = validateMarketingChannels(manyChannels);

      expect(result.isValid).toBe(true);
      expect(result.warnings[0]).toContain(
        "Consider limiting to 3 marketing channels for optimal performance",
      );
    });

    test("should suggest mixing paid and organic channels", () => {
      // Only paid channels
      const paidOnlyResult = validateMarketingChannels([
        "google_ads",
        "facebook",
      ]);
      expect(
        paidOnlyResult.warnings.some((w) =>
          w.includes("organic marketing channels"),
        ),
      ).toBe(true);

      // Only organic channels
      const organicOnlyResult = validateMarketingChannels(["seo", "content"]);
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
    test("should warn when paid channels selected without budget", () => {
      const result = validateMarketingChannelsWithBudget(
        ["google_ads", "facebook"],
        null,
      );

      expect(result.isValid).toBe(true);
      expect(
        result.warnings.some((w) => w.includes("no advertising budget")),
      ).toBe(true);
    });

    test("should warn when budget set without paid channels", () => {
      const result = validateMarketingChannelsWithBudget(
        ["seo", "content"],
        50000,
      );

      expect(result.isValid).toBe(true);
      expect(
        result.warnings.some((w) => w.includes("no paid marketing channels")),
      ).toBe(true);
    });

    test("should warn about low budget per channel", () => {
      const result = validateMarketingChannelsWithBudget(
        ["google_ads", "facebook"],
        1500,
      );

      expect(result.isValid).toBe(true);
      expect(result.warnings.some((w) => w.includes("each channel gets"))).toBe(
        true,
      );
    });

    test("should warn about too many channels with limited budget", () => {
      const result = validateMarketingChannelsWithBudget(
        ["google_ads", "facebook", "linkedin_ads", "twitter_ads"],
        30000,
      );

      expect(result.isValid).toBe(true);
      expect(
        result.warnings.some((w) => w.includes("Managing many paid channels")),
      ).toBe(true);
    });

    test("should not warn for appropriate budget allocation", () => {
      const result = validateMarketingChannelsWithBudget(
        ["google_ads", "facebook"],
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
        "google_ads",
        "facebook",
        "google_ads",
      ]);

      expect(result).toEqual(["google_ads", "facebook"]);
    });

    test("should remove invalid channels", () => {
      const result = sanitizeMarketingChannels([
        "google_ads",
        "invalid_channel",
        "facebook",
      ]);

      expect(result).toEqual(["google_ads", "facebook"]);
    });

    test("should enforce maximum limit", () => {
      const tooManyValidChannels = [
        "google_ads",
        "facebook",
        "email",
        "seo",
        "content",
        "social_media",
        "ppc",
        "display",
        "affiliate",
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
    test("should return true for valid channel IDs", () => {
      expect(isValidMarketingChannel("google_ads")).toBe(true);
      expect(isValidMarketingChannel("facebook")).toBe(true);
      expect(isValidMarketingChannel("email")).toBe(true);
    });

    test("should return false for invalid channel IDs", () => {
      expect(isValidMarketingChannel("invalid_channel")).toBe(false);
      expect(isValidMarketingChannel("")).toBe(false);
      expect(isValidMarketingChannel("random_string")).toBe(false);
    });
  });
});
