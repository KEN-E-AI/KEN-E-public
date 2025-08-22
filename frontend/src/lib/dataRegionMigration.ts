/**
 * Maps legacy data region values to new standardized data region values
 */

const DATA_REGION_MIGRATION_MAP: Record<string, string> = {
  // Legacy full names to abbreviations
  "United States": "US",
  Europe: "EU",

  // Keep these as-is since they're already in the new format
  US: "US",
  EU: "EU",
};

/**
 * Migrates an old data region value to the new standardized format
 * @param oldDataRegion - The legacy data region value
 * @returns The migrated data region value, or "US" as default
 */
export function migrateDataRegionValue(
  oldDataRegion: string | undefined | null,
): string {
  if (!oldDataRegion) {
    return "US";
  }

  // Check if it needs migration
  const migratedValue = DATA_REGION_MIGRATION_MAP[oldDataRegion];
  if (migratedValue) {
    return migratedValue;
  }

  // If the value is already in the new format, keep it
  if (oldDataRegion === "US" || oldDataRegion === "EU") {
    return oldDataRegion;
  }

  // Default to "US" for unrecognized values
  console.warn(
    `Unknown data region value "${oldDataRegion}" - defaulting to "US"`,
  );
  return "US";
}

/**
 * Checks if a data region value needs migration
 * @param dataRegion - The data region value to check
 * @returns True if the value needs migration
 */
export function needsDataRegionMigration(
  dataRegion: string | undefined | null,
): boolean {
  if (!dataRegion) {
    return true;
  }

  return (
    !!DATA_REGION_MIGRATION_MAP[dataRegion] &&
    DATA_REGION_MIGRATION_MAP[dataRegion] !== dataRegion
  );
}

/**
 * Gets the display name for a data region value
 * @param dataRegion - The data region abbreviation
 * @returns The full display name
 */
export function getDataRegionDisplayName(dataRegion: string): string {
  const displayNameMap: Record<string, string> = {
    US: "United States",
    EU: "Europe",
  };

  return displayNameMap[dataRegion] || dataRegion;
}
