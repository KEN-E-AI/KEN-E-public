import {
  migrateDataRegionValue,
  needsDataRegionMigration,
  getDataRegionDisplayName,
} from "./dataRegionMigration";

describe("migrateDataRegionValue", () => {
  test("migrates United States to US", () => {
    expect(migrateDataRegionValue("United States")).toBe("US");
  });

  test("migrates Europe to EU", () => {
    expect(migrateDataRegionValue("Europe")).toBe("EU");
  });

  test("keeps US as US", () => {
    expect(migrateDataRegionValue("US")).toBe("US");
  });

  test("keeps EU as EU", () => {
    expect(migrateDataRegionValue("EU")).toBe("EU");
  });

  test("defaults undefined to US", () => {
    expect(migrateDataRegionValue(undefined)).toBe("US");
  });

  test("defaults null to US", () => {
    expect(migrateDataRegionValue(null)).toBe("US");
  });

  test("defaults empty string to US", () => {
    expect(migrateDataRegionValue("")).toBe("US");
  });

  test("defaults unknown values to US with warning", () => {
    const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(migrateDataRegionValue("Unknown Region")).toBe("US");
    expect(consoleSpy).toHaveBeenCalledWith(
      'Unknown data region value "Unknown Region" - defaulting to "US"',
    );

    consoleSpy.mockRestore();
  });
});

describe("needsDataRegionMigration", () => {
  test("returns true for United States", () => {
    expect(needsDataRegionMigration("United States")).toBe(true);
  });

  test("returns true for Europe", () => {
    expect(needsDataRegionMigration("Europe")).toBe(true);
  });

  test("returns false for US", () => {
    expect(needsDataRegionMigration("US")).toBe(false);
  });

  test("returns false for EU", () => {
    expect(needsDataRegionMigration("EU")).toBe(false);
  });

  test("returns true for undefined", () => {
    expect(needsDataRegionMigration(undefined)).toBe(true);
  });

  test("returns true for null", () => {
    expect(needsDataRegionMigration(null)).toBe(true);
  });

  test("returns false for unknown values", () => {
    expect(needsDataRegionMigration("Unknown")).toBe(false);
  });
});

describe("getDataRegionDisplayName", () => {
  test("returns United States for US", () => {
    expect(getDataRegionDisplayName("US")).toBe("United States");
  });

  test("returns Europe for EU", () => {
    expect(getDataRegionDisplayName("EU")).toBe("Europe");
  });

  test("returns the original value for unknown regions", () => {
    expect(getDataRegionDisplayName("Unknown")).toBe("Unknown");
  });
});
