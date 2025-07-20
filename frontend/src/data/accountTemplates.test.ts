import { describe, test, expect } from "vitest";
import {
  ACCOUNT_TEMPLATES,
  TEMPLATE_CATEGORIES,
  getTemplatesByCategory,
  getTemplateById,
  type AccountTemplate,
} from "./accountTemplates";

describe("Account Templates", () => {
  test("ACCOUNT_TEMPLATES contains expected templates", () => {
    expect(ACCOUNT_TEMPLATES).toBeDefined();
    expect(Object.keys(ACCOUNT_TEMPLATES)).toContain("e-commerce");
    expect(Object.keys(ACCOUNT_TEMPLATES)).toContain("saas");
    expect(Object.keys(ACCOUNT_TEMPLATES)).toContain("healthcare");
    expect(Object.keys(ACCOUNT_TEMPLATES)).toContain("education");
  });

  test("each template has required properties", () => {
    Object.values(ACCOUNT_TEMPLATES).forEach((template: AccountTemplate) => {
      expect(template).toHaveProperty("id");
      expect(template).toHaveProperty("name");
      expect(template).toHaveProperty("description");
      expect(template).toHaveProperty("icon");
      expect(template).toHaveProperty("category");
      expect(template).toHaveProperty("defaultObjectives");
      expect(template).toHaveProperty("defaultChannels");
      expect(template).toHaveProperty("defaultKPIs");
      expect(template).toHaveProperty("recommendedSettings");

      // Check that arrays are not empty
      expect(template.defaultObjectives.length).toBeGreaterThan(0);
      expect(template.defaultChannels.length).toBeGreaterThan(0);
      expect(template.defaultKPIs.length).toBeGreaterThan(0);

      // Check recommendedSettings structure
      expect(template.recommendedSettings).toHaveProperty("timezone");
      expect(template.recommendedSettings).toHaveProperty("data_region");
      expect(template.recommendedSettings).toHaveProperty("industry");
    });
  });

  test("TEMPLATE_CATEGORIES contains expected categories", () => {
    expect(TEMPLATE_CATEGORIES).toContain("All");
    expect(TEMPLATE_CATEGORIES).toContain("Technology");
    expect(TEMPLATE_CATEGORIES).toContain("Healthcare");
    expect(TEMPLATE_CATEGORIES).toContain("Education");
    expect(TEMPLATE_CATEGORIES).toContain("Retail");
  });

  test("getTemplatesByCategory returns all templates for 'All' category", () => {
    const allTemplates = getTemplatesByCategory("All");
    expect(allTemplates).toHaveLength(Object.keys(ACCOUNT_TEMPLATES).length);
    expect(allTemplates).toEqual(Object.values(ACCOUNT_TEMPLATES));
  });

  test("getTemplatesByCategory filters templates by category", () => {
    const technologyTemplates = getTemplatesByCategory("Technology");
    expect(technologyTemplates.length).toBeGreaterThan(0);

    technologyTemplates.forEach((template) => {
      expect(template.category).toBe("Technology");
    });
  });

  test("getTemplatesByCategory returns empty array for non-existent category", () => {
    const nonExistentTemplates = getTemplatesByCategory("NonExistent");
    expect(nonExistentTemplates).toHaveLength(0);
  });

  test("getTemplateById returns correct template", () => {
    const saasTemplate = getTemplateById("saas");
    expect(saasTemplate).toBeDefined();
    expect(saasTemplate?.id).toBe("saas");
    expect(saasTemplate?.name).toBe("SaaS");
    expect(saasTemplate?.category).toBe("Technology");
  });

  test("getTemplateById returns undefined for non-existent id", () => {
    const nonExistentTemplate = getTemplateById("non-existent");
    expect(nonExistentTemplate).toBeUndefined();
  });

  test("e-commerce template has correct properties", () => {
    const ecommerceTemplate = ACCOUNT_TEMPLATES["e-commerce"];
    expect(ecommerceTemplate.name).toBe("E-Commerce");
    expect(ecommerceTemplate.category).toBe("Retail");
    expect(ecommerceTemplate.defaultObjectives).toContain(
      "Drive website traffic",
    );
    expect(ecommerceTemplate.defaultChannels).toContain(
      "Search Engine Marketing",
    );
    expect(ecommerceTemplate.defaultKPIs).toContain("Conversion Rate");
    expect(ecommerceTemplate.recommendedSettings.industry).toBe("Retail");
  });

  test("saas template has correct properties", () => {
    const saasTemplate = ACCOUNT_TEMPLATES["saas"];
    expect(saasTemplate.name).toBe("SaaS");
    expect(saasTemplate.category).toBe("Technology");
    expect(saasTemplate.defaultObjectives).toContain(
      "Generate qualified leads",
    );
    expect(saasTemplate.defaultChannels).toContain("Content Marketing");
    expect(saasTemplate.defaultKPIs).toContain("Monthly Recurring Revenue");
    expect(saasTemplate.recommendedSettings.industry).toBe("Software");
  });

  test("healthcare template has correct properties", () => {
    const healthcareTemplate = ACCOUNT_TEMPLATES["healthcare"];
    expect(healthcareTemplate.name).toBe("Healthcare");
    expect(healthcareTemplate.category).toBe("Healthcare");
    expect(healthcareTemplate.defaultObjectives).toContain(
      "Attract new patients",
    );
    expect(healthcareTemplate.defaultChannels).toContain("Local Advertising");
    expect(healthcareTemplate.defaultKPIs).toContain(
      "Patient Acquisition Cost",
    );
    expect(healthcareTemplate.recommendedSettings.industry).toBe(
      "Healthcare Services",
    );
  });

  test("all templates have unique ids", () => {
    const ids = Object.keys(ACCOUNT_TEMPLATES);
    const uniqueIds = [...new Set(ids)];
    expect(ids).toHaveLength(uniqueIds.length);
  });

  test("all templates have valid timezones", () => {
    const validTimezones = [
      "America/New_York",
      "America/Chicago",
      "America/Denver",
      "America/Los_Angeles",
      "America/Detroit",
      "Europe/London",
      "Europe/Paris",
      "Asia/Tokyo",
      "Australia/Sydney",
    ];

    Object.values(ACCOUNT_TEMPLATES).forEach((template) => {
      expect(validTimezones).toContain(template.recommendedSettings.timezone);
    });
  });

  test("template categories match template assignments", () => {
    const categoriesFromTemplates = new Set(
      Object.values(ACCOUNT_TEMPLATES).map((t) => t.category),
    );

    // All categories except "All" should be present in templates
    const expectedCategories = TEMPLATE_CATEGORIES.filter((c) => c !== "All");
    expectedCategories.forEach((category) => {
      expect(categoriesFromTemplates).toContain(category);
    });
  });

  test("templates have reasonable number of objectives, channels, and KPIs", () => {
    Object.values(ACCOUNT_TEMPLATES).forEach((template) => {
      expect(template.defaultObjectives.length).toBeGreaterThanOrEqual(3);
      expect(template.defaultObjectives.length).toBeLessThanOrEqual(6);

      expect(template.defaultChannels.length).toBeGreaterThanOrEqual(3);
      expect(template.defaultChannels.length).toBeLessThanOrEqual(8);

      expect(template.defaultKPIs.length).toBeGreaterThanOrEqual(3);
      expect(template.defaultKPIs.length).toBeLessThanOrEqual(8);
    });
  });
});
