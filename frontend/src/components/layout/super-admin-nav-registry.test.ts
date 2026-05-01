import { describe, test, expect, beforeEach, vi } from "vitest";
import {
  SUPER_ADMIN_NAV,
  _getNavSnapshot,
  _navSubscribe,
  registerSuperAdminNavRow,
  resetSuperAdminNavForTesting,
  type NavRowId,
} from "./super-admin-nav-registry";

const id = (value: string) => value as NavRowId;

describe("super-admin-nav-registry", () => {
  beforeEach(() => {
    resetSuperAdminNavForTesting();
  });

  describe("registerSuperAdminNavRow — validation", () => {
    test("rejects rows with paths that do not start with a slash", () => {
      registerSuperAdminNavRow({
        id: id("no-slash"),
        label: "No Slash",
        path: "admin/feature-flags",
        order: 10,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(0);
    });

    test("rejects rows with javascript: URIs", () => {
      registerSuperAdminNavRow({
        id: id("xss"),
        label: "XSS Attempt",
        path: "javascript:alert(1)",
        order: 10,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(0);
    });

    test("rejects rows with disallowed characters in the path", () => {
      registerSuperAdminNavRow({
        id: id("bad-chars"),
        label: "Bad Chars",
        path: "/admin/feature flags",
        order: 10,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(0);
    });

    test("accepts rows with allowed characters: alphanumerics, slash, underscore, hyphen", () => {
      registerSuperAdminNavRow({
        id: id("ok"),
        label: "OK",
        path: "/admin/feature_flags-v2",
        order: 10,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(1);
      expect(SUPER_ADMIN_NAV[0].path).toBe("/admin/feature_flags-v2");
    });

    test("deduplicates rows with the same id (first wins)", () => {
      registerSuperAdminNavRow({
        id: id("feature-flags"),
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: id("feature-flags"),
        label: "Feature Flags Duplicate",
        path: "/admin/other-path",
        order: 99,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(1);
      expect(SUPER_ADMIN_NAV[0].label).toBe("Feature Flags");
      expect(SUPER_ADMIN_NAV[0].path).toBe("/admin/feature-flags");
    });
  });

  describe("registerSuperAdminNavRow — storage semantics", () => {
    test("appends rows in registration order (no implicit sort)", () => {
      registerSuperAdminNavRow({
        id: id("third"),
        label: "Third",
        path: "/admin/third",
        order: 30,
      });
      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: id("second"),
        label: "Second",
        path: "/admin/second",
        order: 20,
      });

      expect(SUPER_ADMIN_NAV.map((r) => r.id)).toEqual([
        "third",
        "first",
        "second",
      ]);
    });

    test("preserves rows with isVisible: false (no implicit filter)", () => {
      registerSuperAdminNavRow({
        id: id("hidden"),
        label: "Hidden",
        path: "/admin/hidden",
        order: 10,
        isVisible: false,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(1);
      expect(SUPER_ADMIN_NAV[0].isVisible).toBe(false);
    });

    test("preserves all fields including optional icon and isVisible", () => {
      const icon = () => null;
      registerSuperAdminNavRow({
        id: id("full"),
        label: "Full",
        path: "/admin/full",
        order: 42,
        icon,
        isVisible: true,
      });

      expect(SUPER_ADMIN_NAV[0]).toEqual({
        id: "full",
        label: "Full",
        path: "/admin/full",
        order: 42,
        icon,
        isVisible: true,
      });
    });
  });

  describe("standard consumer pattern (filter visible, sort by order)", () => {
    test("sort by order ascending produces ascending output", () => {
      registerSuperAdminNavRow({
        id: id("row-30"),
        label: "Row 30",
        path: "/admin/30",
        order: 30,
      });
      registerSuperAdminNavRow({
        id: id("row-10"),
        label: "Row 10",
        path: "/admin/10",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: id("row-20"),
        label: "Row 20",
        path: "/admin/20",
        order: 20,
      });

      const sorted = [...SUPER_ADMIN_NAV].sort((a, b) => a.order - b.order);

      expect(sorted.map((r) => r.id)).toEqual(["row-10", "row-20", "row-30"]);
    });

    test("filter on isVisible !== false drops only explicitly hidden rows", () => {
      registerSuperAdminNavRow({
        id: id("explicit-visible"),
        label: "Explicit Visible",
        path: "/admin/explicit-visible",
        order: 10,
        isVisible: true,
      });
      registerSuperAdminNavRow({
        id: id("default-visible"),
        label: "Default Visible",
        path: "/admin/default-visible",
        order: 20,
      });
      registerSuperAdminNavRow({
        id: id("hidden"),
        label: "Hidden",
        path: "/admin/hidden",
        order: 30,
        isVisible: false,
      });

      const visible = SUPER_ADMIN_NAV.filter((r) => r.isVisible !== false);

      expect(visible.map((r) => r.id)).toEqual([
        "explicit-visible",
        "default-visible",
      ]);
    });

    test("combined filter+sort produces the visible rows in ascending order", () => {
      registerSuperAdminNavRow({
        id: id("hidden-low"),
        label: "Hidden Low",
        path: "/admin/hidden-low",
        order: 5,
        isVisible: false,
      });
      registerSuperAdminNavRow({
        id: id("visible-high"),
        label: "Visible High",
        path: "/admin/visible-high",
        order: 30,
      });
      registerSuperAdminNavRow({
        id: id("visible-low"),
        label: "Visible Low",
        path: "/admin/visible-low",
        order: 10,
      });

      const result = SUPER_ADMIN_NAV.filter((r) => r.isVisible !== false).sort(
        (a, b) => a.order - b.order,
      );

      expect(result.map((r) => r.id)).toEqual(["visible-low", "visible-high"]);
    });
  });

  describe("store subscription / notify semantics", () => {
    test("_getNavSnapshot starts at 0 and increments on each successful registration", () => {
      expect(_getNavSnapshot()).toBe(0);

      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });
      expect(_getNavSnapshot()).toBe(1);

      registerSuperAdminNavRow({
        id: id("second"),
        label: "Second",
        path: "/admin/second",
        order: 20,
      });
      expect(_getNavSnapshot()).toBe(2);
    });

    test("rejected registrations do not advance the snapshot", () => {
      registerSuperAdminNavRow({
        id: id("good"),
        label: "Good",
        path: "/admin/good",
        order: 10,
      });
      const before = _getNavSnapshot();

      registerSuperAdminNavRow({
        id: id("good"),
        label: "Duplicate",
        path: "/admin/good",
        order: 99,
      });
      registerSuperAdminNavRow({
        id: id("invalid"),
        label: "Invalid",
        path: "javascript:alert(1)",
        order: 10,
      });

      expect(_getNavSnapshot()).toBe(before);
    });

    test("_navSubscribe calls the listener after each successful registration", () => {
      const listener = vi.fn();
      _navSubscribe(listener);

      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: id("second"),
        label: "Second",
        path: "/admin/second",
        order: 20,
      });

      expect(listener).toHaveBeenCalledTimes(2);
    });

    test("_navSubscribe does not call the listener on rejected registrations", () => {
      const listener = vi.fn();
      _navSubscribe(listener);

      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: id("first"),
        label: "Duplicate",
        path: "/admin/first",
        order: 99,
      });
      registerSuperAdminNavRow({
        id: id("invalid"),
        label: "Invalid",
        path: "not-a-valid-path",
        order: 10,
      });

      expect(listener).toHaveBeenCalledTimes(1);
    });

    test("the unsubscribe function returned by _navSubscribe stops further notifications", () => {
      const listener = vi.fn();
      const unsubscribe = _navSubscribe(listener);

      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });
      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();

      registerSuperAdminNavRow({
        id: id("second"),
        label: "Second",
        path: "/admin/second",
        order: 20,
      });
      expect(listener).toHaveBeenCalledTimes(1);
    });

    test("multiple subscribers each receive notifications", () => {
      const a = vi.fn();
      const b = vi.fn();
      _navSubscribe(a);
      _navSubscribe(b);

      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });

      expect(a).toHaveBeenCalledTimes(1);
      expect(b).toHaveBeenCalledTimes(1);
    });

    test("resetSuperAdminNavForTesting clears the array, snapshot, and listeners", () => {
      const listener = vi.fn();
      _navSubscribe(listener);
      registerSuperAdminNavRow({
        id: id("first"),
        label: "First",
        path: "/admin/first",
        order: 10,
      });
      expect(SUPER_ADMIN_NAV).toHaveLength(1);
      expect(_getNavSnapshot()).toBe(1);
      expect(listener).toHaveBeenCalledTimes(1);

      resetSuperAdminNavForTesting();

      expect(SUPER_ADMIN_NAV).toHaveLength(0);
      expect(_getNavSnapshot()).toBe(0);

      registerSuperAdminNavRow({
        id: id("after-reset"),
        label: "After Reset",
        path: "/admin/after-reset",
        order: 10,
      });

      // Listener was cleared by reset, so a post-reset registration must not call it.
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });
});
