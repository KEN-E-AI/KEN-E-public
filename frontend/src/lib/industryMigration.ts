/**
 * Maps legacy industry values to new standardized industry values
 */

const INDUSTRY_MIGRATION_MAP: Record<string, string> = {
  // Direct mappings from old simple values
  Technology: "Enterprise Software and SaaS [B2B]",
  Healthcare: "Health Care and Social Assistance",
  Finance: "Finance and Insurance",
  Education: "Educational Services",
  Retail: "Retail Trade [B2C]",
  Manufacturing: "Manufacturing",
  Services: "Professional, Scientific, and Technical Services [B2B]",
  "Professional Services":
    "Professional, Scientific, and Technical Services [B2B]",

  // From account templates
  Software: "Enterprise Software and SaaS [B2B]",
  "Healthcare Services": "Health Care and Social Assistance",
  Automotive: "Retail Trade [B2C]",
  "Real Estate": "Real Estate and Rental and Leasing",
  Entertainment: "Arts, Entertainment, and Recreation",
  "Food & Beverage": "Hospitality, Accommodation and Food Services",
  "Non-Profit": "Nonprofit Organizations and NGOs",

  // Keep these as-is since they're already in the new format
  Other: "Other",
};

/**
 * Migrates an old industry value to the new standardized format
 * @param oldIndustry - The legacy industry value
 * @returns The migrated industry value, or the original if no mapping exists
 */
export function migrateIndustryValue(
  oldIndustry: string | undefined | null,
): string {
  if (!oldIndustry) {
    return "Other";
  }

  // Check if it needs migration
  const migratedValue = INDUSTRY_MIGRATION_MAP[oldIndustry];
  if (migratedValue) {
    return migratedValue;
  }

  // If the value is already in the new format (contains brackets or specific keywords), keep it
  if (
    oldIndustry.includes("[") ||
    oldIndustry.includes("and") ||
    oldIndustry === "Utilities" ||
    oldIndustry === "Construction" ||
    oldIndustry === "Transportation and Warehousing" ||
    oldIndustry === "Public Administration" ||
    oldIndustry === "Media and Publishing" ||
    oldIndustry.includes("Higher Educational") ||
    oldIndustry.includes("except Public Administration")
  ) {
    return oldIndustry;
  }

  // Default to "Other" for unrecognized values
  console.warn(
    `Unknown industry value "${oldIndustry}" - defaulting to "Other"`,
  );
  return "Other";
}

/**
 * Checks if an industry value needs migration
 * @param industry - The industry value to check
 * @returns True if the value needs migration
 */
export function needsIndustryMigration(
  industry: string | undefined | null,
): boolean {
  if (!industry) {
    return true;
  }

  return !!INDUSTRY_MIGRATION_MAP[industry];
}

/**
 * Gets a shorter display name for long industry values
 * @param industry - The full industry name
 * @returns A shorter display-friendly version
 */
export function getIndustryDisplayName(industry: string): string {
  // Remove bracketed suffixes for display
  const withoutBrackets = industry.replace(/\s*\[.*?\]\s*$/, "");

  // Special cases for very long names
  const displayNameMap: Record<string, string> = {
    "Agriculture, Forestry, Fishing and Hunting":
      "Agriculture & Natural Resources",
    "Professional, Scientific, and Technical Services": "Professional Services",
    "Hospitality, Accommodation and Food Services": "Hospitality & Food",
    "Pharmaceuticals and Biotechnology": "Pharma & Biotech",
    "Other Services (except Public Administration)": "Other Services",
    "Nonprofit Organizations and NGOs": "Nonprofit & NGOs",
  };

  return displayNameMap[withoutBrackets] || withoutBrackets;
}
