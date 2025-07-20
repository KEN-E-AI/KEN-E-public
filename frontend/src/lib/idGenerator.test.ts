import { describe, test, expect } from "vitest";
import {
  generateId,
  generateOrganizationId,
  generateMetricId,
  generateActivityId,
  generateIntuitionId,
  generateLogId,
  generateAccountId,
  isValidId,
} from "./idGenerator";

describe("idGenerator", () => {
  describe("generateId", () => {
    test("should generate timestamp-based ID without prefix", () => {
      const id = generateId();
      expect(id).toMatch(/^\d{13}_\d+$/);
    });

    test("should generate ID with prefix", () => {
      const id = generateId("test-");
      expect(id).toMatch(/^test-\d{13}_\d+$/);
    });

    test("should generate unique IDs", () => {
      const id1 = generateId();
      const id2 = generateId();
      expect(id1).not.toBe(id2);
    });
  });

  describe("generateOrganizationId", () => {
    test("should generate ID with org_ prefix", () => {
      const id = generateOrganizationId();
      expect(id).toMatch(/^org_\d{13}_\d+$/);
    });

    test("should generate unique organization IDs", () => {
      const id1 = generateOrganizationId();
      const id2 = generateOrganizationId();
      expect(id1).not.toBe(id2);
    });
  });

  describe("generateMetricId", () => {
    test("should generate ID with metric- prefix", () => {
      const id = generateMetricId();
      expect(id).toMatch(/^metric-\d{13}_\d+$/);
    });

    test("should match existing pattern from MetricsPage.tsx", () => {
      const id = generateMetricId();
      expect(id).toMatch(/^metric-\d{13}_\d+$/);
    });
  });

  describe("generateActivityId", () => {
    test("should generate ID with activity- prefix", () => {
      const id = generateActivityId();
      expect(id).toMatch(/^activity-\d{13}_\d+$/);
    });
  });

  describe("generateIntuitionId", () => {
    test("should generate ID with i prefix", () => {
      const id = generateIntuitionId();
      expect(id).toMatch(/^i\d{13}_\d+$/);
    });

    test("should match existing pattern from ActivitiesPage.tsx", () => {
      const id = generateIntuitionId();
      expect(id).toMatch(/^i\d{13}_\d+$/);
    });
  });

  describe("generateLogId", () => {
    test("should generate ID with l prefix", () => {
      const id = generateLogId();
      expect(id).toMatch(/^l\d{13}_\d+$/);
    });

    test("should match existing pattern from ActivitiesPage.tsx", () => {
      const id = generateLogId();
      expect(id).toMatch(/^l\d{13}_\d+$/);
    });
  });

  describe("generateAccountId", () => {
    test("should generate ID with acc_ prefix", () => {
      const id = generateAccountId();
      expect(id).toMatch(/^acc_\d{13}_\d+$/);
    });
  });

  describe("isValidId", () => {
    test("should validate IDs without prefix requirement", () => {
      const validId = "test123";
      expect(isValidId(validId)).toBe(true);
    });

    test("should validate IDs with expected prefix", () => {
      const validId = "org_1705123456789";
      expect(isValidId(validId, "org_")).toBe(true);
    });

    test("should reject IDs with wrong prefix", () => {
      const invalidId = "metric-1705123456789";
      expect(isValidId(invalidId, "org_")).toBe(false);
    });

    test("should reject IDs that are too short", () => {
      const shortId = "abc";
      expect(isValidId(shortId)).toBe(false);
    });

    test("should reject IDs with invalid characters", () => {
      const invalidId = "test@#$%";
      expect(isValidId(invalidId)).toBe(false);
    });

    test("should accept valid characters (letters, numbers, underscore, hyphen)", () => {
      const validId = "test_123-abc";
      expect(isValidId(validId)).toBe(true);
    });
  });

  describe("uniqueness", () => {
    test("should generate 100 unique organization IDs", () => {
      const ids = new Set();
      for (let i = 0; i < 100; i++) {
        ids.add(generateOrganizationId());
      }
      expect(ids.size).toBe(100);
    });

    test("should generate unique IDs even when called rapidly", async () => {
      const promises = Array.from({ length: 50 }, () =>
        Promise.resolve(generateOrganizationId()),
      );
      const ids = await Promise.all(promises);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(50);
    });
  });
});
