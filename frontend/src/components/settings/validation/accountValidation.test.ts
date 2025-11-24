import { describe, test, expect } from "vitest";
import { validateAccountCreation, accountCreationSchema } from "./accountValidation";

describe("validateAccountCreation", () => {
  test("validates account creation with dry_run=true", () => {
    const data = {
      account_name: "Test Account",
      industry: "Technology",
      websites: ["https://example.com"],
      estimated_annual_ad_budget: null,
      business_strategy_documents: [],
      template_id: "tech_template",
      marketing_channels: ["Search Engine Marketing"],
      product_integrations: [],
      enabled_strategies: ["business_strategy"],
      override_product_categories: [],
      objectives: ["Objective 1"],
      kpis: ["KPI 1"],
      timezone: "America/New_York",
      data_region: "US",
      region: ["US"],
      dry_run: true,
    };

    const result = validateAccountCreation(data);

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.data?.dry_run).toBe(true);
  });

  test("validates account creation with dry_run=false", () => {
    const data = {
      account_name: "Test Account",
      industry: "Technology",
      websites: ["https://example.com"],
      estimated_annual_ad_budget: null,
      business_strategy_documents: [],
      template_id: "tech_template",
      marketing_channels: ["Search Engine Marketing"],
      product_integrations: [],
      enabled_strategies: ["business_strategy"],
      override_product_categories: [],
      objectives: ["Objective 1"],
      kpis: ["KPI 1"],
      timezone: "America/New_York",
      data_region: "US",
      region: ["US"],
      dry_run: false,
    };

    const result = validateAccountCreation(data);

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.data?.dry_run).toBe(false);
  });

  test("defaults dry_run to false when not provided", () => {
    const data = {
      account_name: "Test Account",
      industry: "Technology",
      websites: ["https://example.com"],
      estimated_annual_ad_budget: null,
      business_strategy_documents: [],
      template_id: "tech_template",
      marketing_channels: ["Search Engine Marketing"],
      product_integrations: [],
      enabled_strategies: ["business_strategy"],
      override_product_categories: [],
      objectives: ["Objective 1"],
      kpis: ["KPI 1"],
      timezone: "America/New_York",
      data_region: "US",
      region: ["US"],
    };

    const result = validateAccountCreation(data);

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.data?.dry_run).toBe(false);
  });

  test("preserves dry_run through validation without stripping it", () => {
    const dataWithDryRun = {
      account_name: "Test Account",
      industry: "Technology",
      websites: ["https://example.com"],
      estimated_annual_ad_budget: null,
      business_strategy_documents: [],
      template_id: "tech_template",
      marketing_channels: ["Search Engine Marketing"],
      product_integrations: [],
      enabled_strategies: ["business_strategy"],
      override_product_categories: [],
      objectives: ["Objective 1"],
      kpis: ["KPI 1"],
      timezone: "America/New_York",
      data_region: "US",
      region: ["US"],
      dry_run: true,
    };

    const result = validateAccountCreation(dataWithDryRun);

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.data).toHaveProperty("dry_run");
    expect(result.data?.dry_run).toBe(true);
  });

  test("schema enforces dry_run as boolean type", () => {
    const dataWithInvalidDryRun = {
      account_name: "Test Account",
      industry: "Technology",
      websites: ["https://example.com"],
      estimated_annual_ad_budget: null,
      business_strategy_documents: [],
      template_id: "tech_template",
      marketing_channels: ["Search Engine Marketing"],
      product_integrations: [],
      enabled_strategies: ["business_strategy"],
      override_product_categories: [],
      objectives: ["Objective 1"],
      kpis: ["KPI 1"],
      timezone: "America/New_York",
      data_region: "US",
      region: ["US"],
      dry_run: "invalid" as any,
    };

    const result = validateAccountCreation(dataWithInvalidDryRun);

    expect(result.success).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors?.some((e) => e.field === "dry_run")).toBe(true);
  });
});
