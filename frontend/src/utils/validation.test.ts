import { describe, it, expect } from "vitest";
import { KeywordValidation, CompetitorValidation } from "./validation";

describe("KeywordValidation", () => {
  describe("validateKeyword", () => {
    it("accepts valid keywords", () => {
      const validKeywords = [
        "AI",
        "artificial intelligence",
        "machine-learning",
        "ML.AI",
        "R&D",
        "research & development",
        "2024",
        "GPT-4",
      ];

      for (const keyword of validKeywords) {
        const result = KeywordValidation.validateKeyword(keyword);
        expect(result.isValid).toBe(true);
        expect(result.error).toBeUndefined();
      }
    });

    it("rejects empty or whitespace-only keywords", () => {
      const invalidKeywords = ["", " ", "  ", "\t", "\n"];

      for (const keyword of invalidKeywords) {
        const result = KeywordValidation.validateKeyword(keyword);
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("empty");
      }
    });

    it("enforces minimum length", () => {
      const result = KeywordValidation.validateKeyword("a");
      expect(result.isValid).toBe(false);
      expect(result.error).toContain("at least 2 characters");
    });

    it("enforces maximum length", () => {
      const longKeyword = "a".repeat(101);
      const result = KeywordValidation.validateKeyword(longKeyword);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain("must not exceed 100 characters");
    });

    it("rejects invalid characters", () => {
      const invalidKeywords = [
        "test@email",
        "keyword#tag",
        "test!",
        "keyword?",
        "test/slash",
        "keyword\\backslash",
        "test<>",
        "keyword[]",
      ];

      for (const keyword of invalidKeywords) {
        const result = KeywordValidation.validateKeyword(keyword);
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("invalid characters");
      }
    });

    it("rejects excessive whitespace", () => {
      const result = KeywordValidation.validateKeyword("test  keyword");
      expect(result.isValid).toBe(false);
      expect(result.error).toContain("excessive whitespace");
    });
  });

  describe("normalizeKeyword", () => {
    it("trims whitespace", () => {
      expect(KeywordValidation.normalizeKeyword("  test  ")).toBe("test");
      expect(KeywordValidation.normalizeKeyword("\ttest\n")).toBe("test");
    });

    it("preserves case by default", () => {
      expect(KeywordValidation.normalizeKeyword("TestKeyword")).toBe(
        "TestKeyword",
      );
    });

    it("converts to lowercase when requested", () => {
      expect(KeywordValidation.normalizeKeyword("TestKeyword", true)).toBe(
        "testkeyword",
      );
    });
  });

  describe("isDuplicate", () => {
    const existingKeywords = ["AI", "Machine Learning", "deep-learning"];

    it("detects exact duplicates", () => {
      expect(KeywordValidation.isDuplicate("AI", existingKeywords)).toBe(true);
    });

    it("detects case-insensitive duplicates", () => {
      expect(KeywordValidation.isDuplicate("ai", existingKeywords)).toBe(true);
      expect(
        KeywordValidation.isDuplicate("MACHINE LEARNING", existingKeywords),
      ).toBe(true);
    });

    it("correctly identifies non-duplicates", () => {
      expect(
        KeywordValidation.isDuplicate("neural networks", existingKeywords),
      ).toBe(false);
      expect(KeywordValidation.isDuplicate("ML", existingKeywords)).toBe(false);
    });

    it("handles whitespace differences", () => {
      expect(KeywordValidation.isDuplicate("  AI  ", existingKeywords)).toBe(
        true,
      );
      expect(
        KeywordValidation.isDuplicate("Machine  Learning", existingKeywords),
      ).toBe(false);
    });
  });
});

describe("CompetitorValidation", () => {
  describe("validateName", () => {
    it("accepts valid competitor names", () => {
      const validNames = [
        "Google",
        "Microsoft Corporation",
        "Tesla, Inc.",
        "AT&T",
        "Johnson & Johnson",
        "O'Reilly Media",
        'Company "ABC"',
      ];

      for (const name of validNames) {
        const result = CompetitorValidation.validateName(name);
        expect(result.isValid).toBe(true);
        expect(result.error).toBeUndefined();
      }
    });

    it("rejects empty names", () => {
      const result = CompetitorValidation.validateName("");
      expect(result.isValid).toBe(false);
      expect(result.error).toContain("empty");
    });

    it("enforces minimum length", () => {
      const result = CompetitorValidation.validateName("A");
      expect(result.isValid).toBe(false);
      expect(result.error).toContain("at least 2 characters");
    });

    it("enforces maximum length", () => {
      const longName = "A".repeat(201);
      const result = CompetitorValidation.validateName(longName);
      expect(result.isValid).toBe(false);
      expect(result.error).toContain("must not exceed 200 characters");
    });
  });

  describe("validateWebsite", () => {
    it("accepts valid URLs", () => {
      const validUrls = [
        "https://example.com",
        "http://example.com",
        "https://www.example.com",
        "https://example.com/path",
        "https://sub.example.com",
        "https://example.co.uk",
      ];

      for (const url of validUrls) {
        const result = CompetitorValidation.validateWebsite(url);
        expect(result.isValid).toBe(true);
        expect(result.error).toBeUndefined();
      }
    });

    it("adds https:// to URLs without protocol", () => {
      const result = CompetitorValidation.validateWebsite("example.com");
      expect(result.isValid).toBe(true);
      expect(result.url).toBe("https://example.com");
    });

    it("handles null and empty URLs", () => {
      expect(CompetitorValidation.validateWebsite(null).isValid).toBe(true);
      expect(CompetitorValidation.validateWebsite("").isValid).toBe(true);
      expect(CompetitorValidation.validateWebsite("  ").isValid).toBe(true);
    });

    it("rejects invalid URLs", () => {
      const invalidUrls = [
        "not a url",
        "ftp://example.com",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "example",
        "://example.com",
      ];

      for (const url of invalidUrls) {
        const result = CompetitorValidation.validateWebsite(url);
        expect(result.isValid).toBe(false);
        expect(result.error).toBeDefined();
      }
    });
  });
});
