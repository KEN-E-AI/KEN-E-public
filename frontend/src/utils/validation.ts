/**
 * Validation utilities for keywords and monitoring data
 */

export const KeywordValidation = {
  MIN_LENGTH: 2,
  MAX_LENGTH: 100,
  VALID_PATTERN: /^[\w\s\-\.&]+$/u,

  /**
   * Validate a single keyword
   * @param keyword The keyword to validate
   * @returns Object with isValid and error message
   */
  validateKeyword(keyword: string): { isValid: boolean; error?: string } {
    // Trim whitespace
    const trimmed = keyword.trim();

    // Check if empty
    if (!trimmed) {
      return { isValid: false, error: "Keyword cannot be empty" };
    }

    // Check length
    if (trimmed.length < this.MIN_LENGTH) {
      return {
        isValid: false,
        error: `Keyword must be at least ${this.MIN_LENGTH} characters long`,
      };
    }
    if (trimmed.length > this.MAX_LENGTH) {
      return {
        isValid: false,
        error: `Keyword must not exceed ${this.MAX_LENGTH} characters`,
      };
    }

    // Check pattern
    if (!this.VALID_PATTERN.test(trimmed)) {
      return {
        isValid: false,
        error: "Keyword contains invalid characters. Only letters, numbers, spaces, hyphens, dots, and ampersands are allowed",
      };
    }

    // Check for excessive whitespace
    if (trimmed.includes("  ")) {
      return {
        isValid: false,
        error: "Keyword contains excessive whitespace",
      };
    }

    return { isValid: true };
  },

  /**
   * Normalize a keyword (trim and optionally lowercase)
   * @param keyword The keyword to normalize
   * @param lowercase Whether to convert to lowercase
   * @returns Normalized keyword
   */
  normalizeKeyword(keyword: string, lowercase = false): string {
    const normalized = keyword.trim();
    return lowercase ? normalized.toLowerCase() : normalized;
  },

  /**
   * Check if keyword already exists in list (case-insensitive)
   * @param keyword The keyword to check
   * @param existingKeywords List of existing keywords
   * @returns True if keyword already exists
   */
  isDuplicate(keyword: string, existingKeywords: string[]): boolean {
    const normalizedKeyword = this.normalizeKeyword(keyword, true);
    return existingKeywords.some(
      (existing) => this.normalizeKeyword(existing, true) === normalizedKeyword
    );
  },
};

export const CompetitorValidation = {
  /**
   * Validate a competitor name
   * @param name The competitor name to validate
   * @returns Object with isValid and error message
   */
  validateName(name: string): { isValid: boolean; error?: string } {
    const trimmed = name.trim();

    if (!trimmed) {
      return { isValid: false, error: "Competitor name cannot be empty" };
    }

    if (trimmed.length < 2) {
      return {
        isValid: false,
        error: "Competitor name must be at least 2 characters long",
      };
    }

    if (trimmed.length > 200) {
      return {
        isValid: false,
        error: "Competitor name must not exceed 200 characters",
      };
    }

    // Allow more characters in names than keywords
    const namePattern = /^[\w\s\-\.&,'"]+$/u;
    if (!namePattern.test(trimmed)) {
      return {
        isValid: false,
        error: "Competitor name contains invalid characters",
      };
    }

    return { isValid: true };
  },

  /**
   * Validate a website URL
   * @param website The website URL to validate
   * @returns Object with isValid, normalized URL, and error message
   */
  validateWebsite(
    website: string | null
  ): { isValid: boolean; url?: string; error?: string } {
    if (!website) {
      return { isValid: true };
    }

    let url = website.trim();
    if (!url) {
      return { isValid: true };
    }

    // Add protocol if missing
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      url = `https://${url}`;
    }

    // Basic URL validation
    try {
      const parsed = new URL(url);
      // Ensure it's http or https
      if (!["http:", "https:"].includes(parsed.protocol)) {
        return {
          isValid: false,
          error: "Website must use HTTP or HTTPS protocol",
        };
      }
      return { isValid: true, url };
    } catch {
      return {
        isValid: false,
        error: "Invalid website URL format",
      };
    }
  },
};