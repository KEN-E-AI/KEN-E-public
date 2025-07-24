import { describe, it, expect } from "vitest";
import {
  toAccountId,
  toOrganizationId,
  toMetricId,
  toActivityId,
  toActivityLogId,
  toUserId,
  tryAccountId,
  tryOrganizationId,
  isAccountId,
  isOrganizationId,
  isMetricId,
  isActivityId,
  isActivityLogId,
  isUserId,
} from "./branded-types";

describe("Branded Types", () => {
  describe("Type Guards", () => {
    it("correctly identifies account IDs", () => {
      expect(isAccountId("acc_123")).toBe(true);
      expect(isAccountId("acc_")).toBe(true); // Current impl allows this
      expect(isAccountId("org_123")).toBe(false);
      expect(isAccountId("123")).toBe(false);
      expect(isAccountId("")).toBe(false);
    });

    it("correctly identifies organization IDs", () => {
      expect(isOrganizationId("org_123")).toBe(true);
      expect(isOrganizationId("acc_123")).toBe(false);
      expect(isOrganizationId("123")).toBe(false);
      expect(isOrganizationId("")).toBe(false);
    });

    it("correctly identifies metric IDs", () => {
      expect(isMetricId("metric_123")).toBe(true);
      expect(isMetricId("acc_123")).toBe(false);
      expect(isMetricId("123")).toBe(false);
    });

    it("correctly identifies activity IDs", () => {
      expect(isActivityId("activity_123")).toBe(true);
      expect(isActivityId("acc_123")).toBe(false);
      expect(isActivityId("123")).toBe(false);
    });

    it("correctly identifies activity log IDs", () => {
      expect(isActivityLogId("activitylog_123")).toBe(true);
      expect(isActivityLogId("activity_123")).toBe(false);
      expect(isActivityLogId("123")).toBe(false);
    });

    it("correctly identifies user IDs", () => {
      expect(isUserId("any_non_empty_string")).toBe(true);
      expect(isUserId("firebase_uid_123")).toBe(true);
      expect(isUserId("")).toBe(false);
    });
  });

  describe("Safe Casting Functions", () => {
    it("successfully casts valid account IDs", () => {
      const id = "acc_123";
      const accountId = toAccountId(id);
      expect(accountId).toBe(id);
    });

    it("throws on invalid account ID", () => {
      expect(() => toAccountId("org_123")).toThrow(
        "Invalid account ID format: org_123",
      );
      expect(() => toAccountId("123")).toThrow(
        "Invalid account ID format: 123",
      );
    });

    it("successfully casts valid organization IDs", () => {
      const id = "org_123";
      const orgId = toOrganizationId(id);
      expect(orgId).toBe(id);
    });

    it("throws on invalid organization ID", () => {
      expect(() => toOrganizationId("acc_123")).toThrow(
        "Invalid organization ID format: acc_123",
      );
    });

    it("successfully casts valid metric IDs", () => {
      const id = "metric_123";
      const metricId = toMetricId(id);
      expect(metricId).toBe(id);
    });

    it("successfully casts valid activity IDs", () => {
      const id = "activity_123";
      const activityId = toActivityId(id);
      expect(activityId).toBe(id);
    });

    it("successfully casts valid activity log IDs", () => {
      const id = "activitylog_123";
      const activityLogId = toActivityLogId(id);
      expect(activityLogId).toBe(id);
    });

    it("successfully casts valid user IDs", () => {
      const id = "firebase_uid_123";
      const userId = toUserId(id);
      expect(userId).toBe(id);
    });
  });

  describe("Optional Casting Functions", () => {
    it("returns branded type for valid IDs", () => {
      expect(tryAccountId("acc_123")).toBe("acc_123");
      expect(tryOrganizationId("org_123")).toBe("org_123");
    });

    it("returns undefined for invalid IDs", () => {
      expect(tryAccountId("org_123")).toBeUndefined();
      expect(tryAccountId("123")).toBeUndefined();
      expect(tryOrganizationId("acc_123")).toBeUndefined();
      expect(tryOrganizationId("123")).toBeUndefined();
    });
  });

  describe("Type Safety", () => {
    it("prevents mixing different ID types at compile time", () => {
      // This test demonstrates the compile-time safety
      // In actual usage, TypeScript would prevent these assignments
      const accountId = toAccountId("acc_123");
      const orgId = toOrganizationId("org_123");

      // These would be compile errors in actual TypeScript code:
      // const wrongAssignment: OrganizationId = accountId; // Error!
      // const wrongParam = (id: AccountId) => {}; wrongParam(orgId); // Error!

      // Runtime values are still strings
      expect(typeof accountId).toBe("string");
      expect(typeof orgId).toBe("string");
    });
  });

  describe("Edge Cases", () => {
    it("handles very long strings", () => {
      const longId = "acc_" + "x".repeat(1000);
      expect(isAccountId(longId)).toBe(true);
      expect(() => toAccountId(longId)).not.toThrow();

      const veryLongInvalidId = "x".repeat(10000);
      expect(isAccountId(veryLongInvalidId)).toBe(false);
    });

    it("handles special characters in IDs", () => {
      // Valid IDs with numbers and underscores
      expect(isAccountId("acc_123_456")).toBe(true);
      expect(isOrganizationId("org_test_123")).toBe(true);
      expect(isMetricId("metric_abc_123")).toBe(true);

      // Invalid IDs with special characters
      expect(isAccountId("acc_123!@#")).toBe(false);
      expect(isAccountId("acc_123-456")).toBe(false);
      expect(isAccountId("acc_123 456")).toBe(false);
      expect(isAccountId("acc_123.456")).toBe(false);
      expect(isAccountId("acc_123/456")).toBe(false);
    });

    it("handles unicode characters", () => {
      expect(isAccountId("acc_123_émoji")).toBe(false);
      expect(isAccountId("acc_123_中文")).toBe(false);
      expect(isAccountId("acc_123_🚀")).toBe(false);
      expect(isOrganizationId("org_123_émoji")).toBe(false);
    });

    it("handles null and undefined inputs for type guards", () => {
      // @ts-expect-error - Testing runtime behavior with invalid input
      expect(isAccountId(null)).toBe(false);
      // @ts-expect-error - Testing runtime behavior with invalid input
      expect(isAccountId(undefined)).toBe(false);
      // @ts-expect-error - Testing runtime behavior with invalid input
      expect(isOrganizationId(null)).toBe(false);
      // @ts-expect-error - Testing runtime behavior with invalid input
      expect(isOrganizationId(undefined)).toBe(false);
    });

    it("handles empty strings", () => {
      expect(isAccountId("")).toBe(false);
      expect(isOrganizationId("")).toBe(false);
      expect(isMetricId("")).toBe(false);
      expect(isActivityId("")).toBe(false);
      expect(isActivityLogId("")).toBe(false);
      expect(isUserId("")).toBe(false);
    });

    it("handles strings with only prefix", () => {
      expect(isAccountId("acc_")).toBe(true); // Current impl allows this
      expect(isOrganizationId("org_")).toBe(true); // Current impl allows this
      expect(isMetricId("metric_")).toBe(true); // Current impl allows this
      expect(isActivityId("activity_")).toBe(true); // Current impl allows this
      expect(isActivityLogId("activitylog_")).toBe(true); // Current impl allows this
    });

    it("handles case sensitivity", () => {
      expect(isAccountId("ACC_123")).toBe(false);
      expect(isAccountId("Acc_123")).toBe(false);
      expect(isOrganizationId("ORG_123")).toBe(false);
      expect(isOrganizationId("Org_123")).toBe(false);
    });

    it("handles whitespace", () => {
      expect(isAccountId(" acc_123")).toBe(false);
      expect(isAccountId("acc_123 ")).toBe(false);
      expect(isAccountId(" acc_123 ")).toBe(false);
      expect(isAccountId("acc_ 123")).toBe(false);
      expect(isAccountId("acc_\t123")).toBe(false);
      expect(isAccountId("acc_\n123")).toBe(false);
    });

    it("handles numeric-only IDs after prefix", () => {
      expect(isAccountId("acc_123")).toBe(true);
      expect(isAccountId("acc_000")).toBe(true);
      expect(isAccountId("acc_999999999")).toBe(true);
      expect(isOrganizationId("org_123")).toBe(true);
      expect(isMetricId("metric_123")).toBe(true);
    });

    it("handles mixed alphanumeric IDs after prefix", () => {
      expect(isAccountId("acc_abc123")).toBe(true);
      expect(isAccountId("acc_123abc")).toBe(true);
      expect(isAccountId("acc_a1b2c3")).toBe(true);
      expect(isOrganizationId("org_test123")).toBe(true);
      expect(isMetricId("metric_abc123xyz")).toBe(true);
    });

    it("try functions handle edge cases gracefully", () => {
      expect(tryAccountId("")).toBeUndefined();
      // @ts-expect-error - Testing runtime behavior
      expect(tryAccountId(null)).toBeUndefined();
      // @ts-expect-error - Testing runtime behavior
      expect(tryAccountId(undefined)).toBeUndefined();
      expect(tryAccountId("acc_123!@#")).toBeUndefined();
      expect(tryAccountId("ACC_123")).toBeUndefined();

      expect(tryOrganizationId("")).toBeUndefined();
      // @ts-expect-error - Testing runtime behavior
      expect(tryOrganizationId(null)).toBeUndefined();
      expect(tryOrganizationId("org_123 456")).toBeUndefined();
    });
  });
});
