import { describe, test, expect } from "vitest";
import {
  migrateIndustryValue,
  needsIndustryMigration,
  getIndustryDisplayName,
} from "./industryMigration";

describe("industryMigration", () => {
  describe("migrateIndustryValue", () => {
    test("migrates legacy simple industry values", () => {
      expect(migrateIndustryValue("Technology")).toBe(
        "Enterprise Software and SaaS [B2B]"
      );
      expect(migrateIndustryValue("Healthcare")).toBe(
        "Health Care and Social Assistance"
      );
      expect(migrateIndustryValue("Finance")).toBe("Finance and Insurance");
      expect(migrateIndustryValue("Education")).toBe("Educational Services");
      expect(migrateIndustryValue("Retail")).toBe("Retail Trade [B2C]");
      expect(migrateIndustryValue("Manufacturing")).toBe("Manufacturing");
      expect(migrateIndustryValue("Services")).toBe(
        "Professional, Scientific, and Technical Services [B2B]"
      );
    });

    test("migrates legacy template industry values", () => {
      expect(migrateIndustryValue("Software")).toBe(
        "Enterprise Software and SaaS [B2B]"
      );
      expect(migrateIndustryValue("Healthcare Services")).toBe(
        "Health Care and Social Assistance"
      );
      expect(migrateIndustryValue("Automotive")).toBe("Retail Trade [B2C]");
      expect(migrateIndustryValue("Real Estate")).toBe(
        "Real Estate and Rental and Leasing"
      );
      expect(migrateIndustryValue("Entertainment")).toBe(
        "Arts, Entertainment, and Recreation"
      );
      expect(migrateIndustryValue("Food & Beverage")).toBe(
        "Hospitality, Accommodation and Food Services"
      );
      expect(migrateIndustryValue("Non-Profit")).toBe(
        "Nonprofit Organizations and NGOs"
      );
    });

    test("returns 'Other' for null, undefined, or empty values", () => {
      expect(migrateIndustryValue(null)).toBe("Other");
      expect(migrateIndustryValue(undefined)).toBe("Other");
      expect(migrateIndustryValue("")).toBe("Other");
    });

    test("preserves values that are already in new format", () => {
      expect(migrateIndustryValue("Utilities")).toBe("Utilities");
      expect(migrateIndustryValue("Construction")).toBe("Construction");
      expect(migrateIndustryValue("Transportation and Warehousing")).toBe(
        "Transportation and Warehousing"
      );
      expect(migrateIndustryValue("Public Administration")).toBe(
        "Public Administration"
      );
      expect(migrateIndustryValue("Media and Publishing")).toBe(
        "Media and Publishing"
      );
      expect(migrateIndustryValue("Enterprise Software and SaaS [B2B]")).toBe(
        "Enterprise Software and SaaS [B2B]"
      );
    });

    test("returns 'Other' for unrecognized values with console warning", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      
      expect(migrateIndustryValue("Unknown Industry")).toBe("Other");
      expect(consoleSpy).toHaveBeenCalledWith(
        'Unknown industry value "Unknown Industry" - defaulting to "Other"'
      );
      
      consoleSpy.mockRestore();
    });

    test("preserves 'Other' value", () => {
      expect(migrateIndustryValue("Other")).toBe("Other");
    });
  });

  describe("needsIndustryMigration", () => {
    test("returns true for values that need migration", () => {
      expect(needsIndustryMigration("Technology")).toBe(true);
      expect(needsIndustryMigration("Healthcare")).toBe(true);
      expect(needsIndustryMigration("Software")).toBe(true);
      expect(needsIndustryMigration("Real Estate")).toBe(true);
      expect(needsIndustryMigration("Other")).toBe(true); // "Other" is in migration map
    });

    test("returns false for values already in new format", () => {
      expect(needsIndustryMigration("Utilities")).toBe(false);
      expect(needsIndustryMigration("Construction")).toBe(false);
      expect(needsIndustryMigration("Enterprise Software and SaaS [B2B]")).toBe(
        false
      );
      // Note: "Other" is in the migration map, so it returns true
      expect(needsIndustryMigration("Unknown New Industry")).toBe(false);
    });

    test("returns true for null, undefined, or empty values", () => {
      expect(needsIndustryMigration(null)).toBe(true);
      expect(needsIndustryMigration(undefined)).toBe(true);
      expect(needsIndustryMigration("")).toBe(true);
    });
  });

  describe("getIndustryDisplayName", () => {
    test("returns shortened display names for long industry values", () => {
      expect(
        getIndustryDisplayName("Agriculture, Forestry, Fishing and Hunting")
      ).toBe("Agriculture & Natural Resources");
      expect(
        getIndustryDisplayName(
          "Professional, Scientific, and Technical Services"
        )
      ).toBe("Professional Services");
      expect(
        getIndustryDisplayName("Hospitality, Accommodation and Food Services")
      ).toBe("Hospitality & Food");
      expect(
        getIndustryDisplayName("Pharmaceuticals and Biotechnology")
      ).toBe("Pharma & Biotech");
      expect(
        getIndustryDisplayName("Other Services (except Public Administration)")
      ).toBe("Other Services");
      expect(getIndustryDisplayName("Nonprofit Organizations and NGOs")).toBe(
        "Nonprofit & NGOs"
      );
    });

    test("removes bracketed suffixes from display names", () => {
      expect(getIndustryDisplayName("Enterprise Software and SaaS [B2B]")).toBe(
        "Enterprise Software and SaaS"
      );
      expect(getIndustryDisplayName("Retail Trade [B2C]")).toBe(
        "Retail Trade"
      );
      expect(getIndustryDisplayName("Consumer Goods and E-commerce [D2C]")).toBe(
        "Consumer Goods and E-commerce"
      );
    });

    test("returns original name without brackets if no mapping exists", () => {
      expect(getIndustryDisplayName("Manufacturing")).toBe("Manufacturing");
      expect(getIndustryDisplayName("Construction")).toBe("Construction");
      expect(getIndustryDisplayName("Utilities")).toBe("Utilities");
    });

    test("handles edge cases gracefully", () => {
      expect(getIndustryDisplayName("")).toBe("");
      expect(getIndustryDisplayName("   [B2B]   ")).toBe("");
    });
  });
});