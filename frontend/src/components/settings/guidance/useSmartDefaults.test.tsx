import { describe, test, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useSmartDefaults } from "./useSmartDefaults";

// Mock the auth context
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    selectedOrgAccount: {
      accountId: "test-account",
      metadata: {
        organization_name: "Test Org",
        account_name: "Test Account",
      },
    },
    user: {
      id: "test-user",
      firstName: "Test",
      lastName: "User",
      preferences: {
        language: "en",
        theme: "light",
      },
      settings: {
        timezone: "America/New_York",
      },
    },
    orgMetadata: {
      timezone: "America/Chicago",
      data_retention: 365,
    },
    accountMetadata: {
      industry: "Technology",
      template_id: "tech-startup",
    },
  }),
}));

// Mock the account templates
vi.mock("@/data/accountTemplates", () => ({
  getTemplateById: (id: string) => {
    if (id === "tech-startup") {
      return {
        id: "tech-startup",
        name: "Tech Startup",
        recommendedSettings: {
          timezone: "America/Los_Angeles",
          language: "en",
        },
        defaultSettings: {
          data_retention: 730,
        },
      };
    }
    return null;
  },
}));

describe("useSmartDefaults", () => {
  test("returns correct default value for user scope", () => {
    const { result } = renderHook(() => useSmartDefaults("user"));

    const defaultValue = result.current.getDefaultValue("timezone");

    expect(defaultValue.value).toBe("America/New_York");
    expect(defaultValue.inheritedFrom).toBe("user");
    expect(defaultValue.source).toBe("User preferences");
  });

  test("returns correct default value for account scope", () => {
    const { result } = renderHook(() => useSmartDefaults("account"));

    const defaultValue = result.current.getDefaultValue("industry");

    expect(defaultValue.value).toBe("Technology");
    expect(defaultValue.inheritedFrom).toBe("account");
    expect(defaultValue.source).toBe("Account settings");
  });

  test("returns template default when no direct value exists", () => {
    const { result } = renderHook(() => useSmartDefaults("account"));

    const defaultValue = result.current.getDefaultValue("data_retention");

    expect(defaultValue.value).toBe(365);
    expect(defaultValue.inheritedFrom).toBe("organization");
    expect(defaultValue.source).toBe("Organization settings");
  });

  test("returns inheritance chain correctly", () => {
    const { result } = renderHook(() => useSmartDefaults("user"));

    const chain = result.current.getInheritanceChain("timezone");

    expect(chain).toHaveLength(2);
    expect(chain[0].inheritedFrom).toBe("user");
    expect(chain[1].inheritedFrom).toBe("organization");
  });

  test("returns suggestions for known settings", () => {
    const { result } = renderHook(() => useSmartDefaults("account"));

    const suggestions = result.current.getSuggestions("timezone");

    expect(suggestions).toContain("America/New_York");
    expect(suggestions).toContain("America/Los_Angeles");
    expect(suggestions).toContain("Europe/London");
  });

  test("returns recommendation with template-based logic", () => {
    const { result } = renderHook(() => useSmartDefaults("account"));

    const recommendation = result.current.getRecommendation("timezone");

    expect(recommendation).toEqual({
      value: "America/Chicago",
      reason: "Matches your organization's timezone",
    });
  });

  test("returns fallback value when no defaults exist", () => {
    const { result } = renderHook(() => useSmartDefaults("account"));

    const defaultValue = result.current.getDefaultValue(
      "unknown_setting",
      "fallback",
    );

    expect(defaultValue.value).toBe("fallback");
    expect(defaultValue.inheritedFrom).toBe("system");
    expect(defaultValue.source).toBe("System default");
  });
});
