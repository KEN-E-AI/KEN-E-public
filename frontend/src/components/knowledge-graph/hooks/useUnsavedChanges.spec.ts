import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useUnsavedChanges } from "./useUnsavedChanges";

describe("useUnsavedChanges", () => {
  it("should return false when not editing", () => {
    const originalData = { name: "Test", value: 123 };
    const formData = { name: "Modified", value: 456 };

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, false),
    );

    expect(result.current).toBe(false);
  });

  it("should return false when data matches original", () => {
    const originalData = { name: "Test", value: 123 };
    const formData = { name: "Test", value: 123 };

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, true),
    );

    expect(result.current).toBe(false);
  });

  it("should return true when data differs from original", () => {
    const originalData = { name: "Test", value: 123 };
    const formData = { name: "Modified", value: 123 };

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, true),
    );

    expect(result.current).toBe(true);
  });

  it("should handle nested object comparisons", () => {
    const originalData = {
      name: "Test",
      nested: { value: 123, flag: true },
    };
    const formData = {
      name: "Test",
      nested: { value: 456, flag: true },
    };

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, true),
    );

    expect(result.current).toBe(true);
  });

  it("should handle array comparisons", () => {
    const originalData = { items: ["a", "b", "c"] };
    const formData = { items: ["a", "b", "d"] };

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, true),
    );

    expect(result.current).toBe(true);
  });

  it("should handle null and undefined values", () => {
    const originalData = { name: null, value: undefined };
    const formData = { name: "Test", value: 123 };

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, true),
    );

    expect(result.current).toBe(true);
  });

  it("should handle empty objects", () => {
    const originalData = {};
    const formData = {};

    const { result } = renderHook(() =>
      useUnsavedChanges(originalData, formData, true),
    );

    expect(result.current).toBe(false);
  });
});
