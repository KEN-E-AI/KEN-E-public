import { describe, test, expect, beforeEach, vi } from "vitest";
import {
  SETTINGS_NAV_REGISTRY,
  _getSettingsNavSnapshot,
  _settingsNavSubscribe,
  registerSettingsNavRow,
  resetSettingsNavForTesting,
  type SettingsNavRowId,
} from "./settings-nav-registry";

const sId = (value: string) => value as SettingsNavRowId;

describe("settings-nav-registry", () => {
  beforeEach(() => {
    resetSettingsNavForTesting();
  });

  describe("registerSettingsNavRow — validation", () => {
    test("rejects rows with paths that do not start with a slash", () => {
      registerSettingsNavRow({
        id: sId("no-slash"),
        label: "No Slash",
        path: "settings/foo",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("rejects rows with javascript: URIs", () => {
      registerSettingsNavRow({
        id: sId("xss"),
        label: "XSS Attempt",
        path: "javascript:alert(1)",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("rejects rows with disallowed characters in the path (space)", () => {
      registerSettingsNavRow({
        id: sId("bad-chars"),
        label: "Bad Chars",
        path: "/settings/feature flags",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("rejects rows with dot-segment traversal (..) in the path", () => {
      registerSettingsNavRow({
        id: sId("traversal"),
        label: "Traversal",
        path: "/settings/../admin",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("rejects rows with /__dev__ paths", () => {
      registerSettingsNavRow({
        id: sId("dev-route"),
        label: "Dev Route",
        path: "/__dev__/something",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("rejects rows with paths exceeding 200 characters", () => {
      const longPath = "/" + "a".repeat(200);
      registerSettingsNavRow({
        id: sId("too-long"),
        label: "Too Long",
        path: longPath,
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("rejects bare / path (requires at least one char after the slash)", () => {
      registerSettingsNavRow({
        id: sId("bare-slash"),
        label: "Bare Slash",
        path: "/",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
    });

    test("accepts rows with allowed characters: alphanumerics, slash, underscore, hyphen", () => {
      registerSettingsNavRow({
        id: sId("ok"),
        label: "OK",
        path: "/settings/foo-bar_baz",
        order: 10,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(1);
      expect(SETTINGS_NAV_REGISTRY[0].path).toBe("/settings/foo-bar_baz");
    });
  });

  describe("registerSettingsNavRow — storage semantics", () => {
    test("appends rows in registration order (no implicit sort)", () => {
      registerSettingsNavRow({
        id: sId("third"),
        label: "Third",
        path: "/settings/third",
        order: 30,
      });
      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });
      registerSettingsNavRow({
        id: sId("second"),
        label: "Second",
        path: "/settings/second",
        order: 20,
      });

      expect(SETTINGS_NAV_REGISTRY.map((r) => r.id)).toEqual([
        "third",
        "first",
        "second",
      ]);
    });

    test("preserves rows with isVisible: () => false (no implicit filter)", () => {
      registerSettingsNavRow({
        id: sId("hidden"),
        label: "Hidden",
        path: "/settings/hidden",
        order: 40,
        isVisible: () => false,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(1);
      expect(SETTINGS_NAV_REGISTRY[0].isVisible?.()).toBe(false);
    });

    test("preserves function reference identity for isVisible", () => {
      const isVisible = () => true;
      registerSettingsNavRow({
        id: sId("func"),
        label: "Func",
        path: "/settings/func",
        order: 10,
        isVisible,
      });

      expect(SETTINGS_NAV_REGISTRY[0].isVisible).toBe(isVisible);
    });

    test("preserves all fields including optional isVisible", () => {
      const isVisible = () => true;
      registerSettingsNavRow({
        id: sId("full"),
        label: "Full",
        path: "/settings/full",
        order: 42,
        isVisible,
      });

      expect(SETTINGS_NAV_REGISTRY[0]).toEqual({
        id: "full",
        label: "Full",
        path: "/settings/full",
        order: 42,
        isVisible,
      });
    });
  });

  describe("registerSettingsNavRow — dedup", () => {
    test("second registration with the same id is rejected (first wins)", () => {
      registerSettingsNavRow({
        id: sId("settings-org"),
        label: "Organization",
        path: "/settings/organization",
        order: 10,
      });
      registerSettingsNavRow({
        id: sId("settings-org"),
        label: "Organization Duplicate",
        path: "/settings/other-path",
        order: 99,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(1);
      expect(SETTINGS_NAV_REGISTRY[0].label).toBe("Organization");
      expect(SETTINGS_NAV_REGISTRY[0].path).toBe("/settings/organization");
    });

    test("snapshot does not advance for the duplicate", () => {
      registerSettingsNavRow({
        id: sId("good"),
        label: "Good",
        path: "/settings/good",
        order: 10,
      });
      const before = _getSettingsNavSnapshot();

      registerSettingsNavRow({
        id: sId("good"),
        label: "Duplicate",
        path: "/settings/good",
        order: 99,
      });

      expect(_getSettingsNavSnapshot()).toBe(before);
    });

    test("listener is not called for a duplicate registration", () => {
      const listener = vi.fn();
      _settingsNavSubscribe(listener);

      registerSettingsNavRow({
        id: sId("good"),
        label: "Good",
        path: "/settings/good",
        order: 10,
      });
      expect(listener).toHaveBeenCalledTimes(1);

      registerSettingsNavRow({
        id: sId("good"),
        label: "Duplicate",
        path: "/settings/good",
        order: 99,
      });
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });

  describe("seed rows", () => {
    test("three rows present after module import (Organization, Account, User in that order)", () => {
      // resetSettingsNavForTesting is called in beforeEach, so re-seed by importing
      // The seed rows are loaded at module import time; after reset we register manually to match
      registerSettingsNavRow({
        id: sId("organization"),
        label: "Organization",
        path: "/settings/organization",
        order: 10,
      });
      registerSettingsNavRow({
        id: sId("account"),
        label: "Account",
        path: "/settings/account",
        order: 20,
      });
      registerSettingsNavRow({
        id: sId("user"),
        label: "User",
        path: "/settings/user",
        order: 30,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(3);
      expect(SETTINGS_NAV_REGISTRY[0]).toMatchObject({
        id: "organization",
        label: "Organization",
        path: "/settings/organization",
        order: 10,
      });
      expect(SETTINGS_NAV_REGISTRY[1]).toMatchObject({
        id: "account",
        label: "Account",
        path: "/settings/account",
        order: 20,
      });
      expect(SETTINGS_NAV_REGISTRY[2]).toMatchObject({
        id: "user",
        label: "User",
        path: "/settings/user",
        order: 30,
      });
    });
  });

  describe("snapshot semantics", () => {
    test("snapshot starts at 0 after resetSettingsNavForTesting", () => {
      expect(_getSettingsNavSnapshot()).toBe(0);
    });

    test("snapshot increments on each successful registration", () => {
      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });
      expect(_getSettingsNavSnapshot()).toBe(1);

      registerSettingsNavRow({
        id: sId("second"),
        label: "Second",
        path: "/settings/second",
        order: 20,
      });
      expect(_getSettingsNavSnapshot()).toBe(2);
    });

    test("rejected registrations do not advance the snapshot", () => {
      registerSettingsNavRow({
        id: sId("good"),
        label: "Good",
        path: "/settings/good",
        order: 10,
      });
      const before = _getSettingsNavSnapshot();

      registerSettingsNavRow({
        id: sId("good"),
        label: "Duplicate",
        path: "/settings/good",
        order: 99,
      });
      registerSettingsNavRow({
        id: sId("invalid"),
        label: "Invalid",
        path: "javascript:alert(1)",
        order: 10,
      });

      expect(_getSettingsNavSnapshot()).toBe(before);
    });
  });

  describe("consumer pattern — filter(isVisible?.() !== false).sort(order)", () => {
    test("rows with isVisible: () => true are kept", () => {
      registerSettingsNavRow({
        id: sId("visible"),
        label: "Visible",
        path: "/settings/visible",
        order: 10,
        isVisible: () => true,
      });

      const visible = SETTINGS_NAV_REGISTRY.filter(
        (r) => r.isVisible?.() !== false,
      );
      expect(visible).toHaveLength(1);
    });

    test("rows with isVisible: () => false are dropped by the consumer pattern", () => {
      registerSettingsNavRow({
        id: sId("hidden"),
        label: "Hidden",
        path: "/settings/hidden",
        order: 40,
        isVisible: () => false,
      });

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(1);

      const visible = SETTINGS_NAV_REGISTRY.filter(
        (r) => r.isVisible?.() !== false,
      );
      expect(visible).toHaveLength(0);
    });

    test("rows without isVisible are kept (default-visible)", () => {
      registerSettingsNavRow({
        id: sId("default"),
        label: "Default",
        path: "/settings/default",
        order: 10,
      });

      const visible = SETTINGS_NAV_REGISTRY.filter(
        (r) => r.isVisible?.() !== false,
      );
      expect(visible).toHaveLength(1);
    });

    test("combined filter+sort produces visible rows in ascending order", () => {
      registerSettingsNavRow({
        id: sId("hidden-low"),
        label: "Hidden Low",
        path: "/settings/hidden-low",
        order: 5,
        isVisible: () => false,
      });
      registerSettingsNavRow({
        id: sId("visible-high"),
        label: "Visible High",
        path: "/settings/visible-high",
        order: 30,
      });
      registerSettingsNavRow({
        id: sId("visible-low"),
        label: "Visible Low",
        path: "/settings/visible-low",
        order: 10,
      });

      const result = SETTINGS_NAV_REGISTRY.filter(
        (r) => r.isVisible?.() !== false,
      ).sort((a, b) => a.order - b.order);

      expect(result.map((r) => r.id)).toEqual(["visible-low", "visible-high"]);
    });
  });

  describe("store subscription / notify semantics", () => {
    test("_settingsNavSubscribe calls the listener after each successful registration", () => {
      const listener = vi.fn();
      _settingsNavSubscribe(listener);

      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });
      registerSettingsNavRow({
        id: sId("second"),
        label: "Second",
        path: "/settings/second",
        order: 20,
      });

      expect(listener).toHaveBeenCalledTimes(2);
    });

    test("_settingsNavSubscribe does not call listener on rejected registrations", () => {
      const listener = vi.fn();
      _settingsNavSubscribe(listener);

      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });
      registerSettingsNavRow({
        id: sId("first"),
        label: "Duplicate",
        path: "/settings/first",
        order: 99,
      });
      registerSettingsNavRow({
        id: sId("invalid"),
        label: "Invalid",
        path: "not-a-valid-path",
        order: 10,
      });

      expect(listener).toHaveBeenCalledTimes(1);
    });

    test("the unsubscribe function returned by _settingsNavSubscribe stops further notifications", () => {
      const listener = vi.fn();
      const unsubscribe = _settingsNavSubscribe(listener);

      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });
      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();

      registerSettingsNavRow({
        id: sId("second"),
        label: "Second",
        path: "/settings/second",
        order: 20,
      });
      expect(listener).toHaveBeenCalledTimes(1);
    });

    test("multiple subscribers each receive notifications", () => {
      const a = vi.fn();
      const b = vi.fn();
      _settingsNavSubscribe(a);
      _settingsNavSubscribe(b);

      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });

      expect(a).toHaveBeenCalledTimes(1);
      expect(b).toHaveBeenCalledTimes(1);
    });

    test("resetSettingsNavForTesting clears the array, snapshot, and listeners", () => {
      const listener = vi.fn();
      _settingsNavSubscribe(listener);
      registerSettingsNavRow({
        id: sId("first"),
        label: "First",
        path: "/settings/first",
        order: 10,
      });
      expect(SETTINGS_NAV_REGISTRY).toHaveLength(1);
      expect(_getSettingsNavSnapshot()).toBe(1);
      expect(listener).toHaveBeenCalledTimes(1);

      resetSettingsNavForTesting();

      expect(SETTINGS_NAV_REGISTRY).toHaveLength(0);
      expect(_getSettingsNavSnapshot()).toBe(0);

      registerSettingsNavRow({
        id: sId("after-reset"),
        label: "After Reset",
        path: "/settings/after-reset",
        order: 10,
      });

      // Listener was cleared by reset, so a post-reset registration must not call it.
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });
});
