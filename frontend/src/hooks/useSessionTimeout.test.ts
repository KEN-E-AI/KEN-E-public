import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSessionTimeout } from "./useSessionTimeout";

vi.mock("@/services/chatService", () => ({
  chatService: {
    recordActivity: vi
      .fn()
      .mockResolvedValue({ status: "ok", remaining_seconds: 1800 }),
  },
}));

describe("useSessionTimeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("initializes with no warning and not expired", () => {
    const { result } = renderHook(() =>
      useSessionTimeout({
        sessionId: "sess-1",
        warningMinutes: 25,
        timeoutMinutes: 30,
      }),
    );

    expect(result.current.isWarningShown).toBe(false);
    expect(result.current.isExpired).toBe(false);
    expect(result.current.remainingSeconds).toBe(1800);
  });

  test("warning fires after warningMinutes of inactivity", () => {
    const { result } = renderHook(() =>
      useSessionTimeout({
        sessionId: "sess-1",
        warningMinutes: 1,
        timeoutMinutes: 2,
      }),
    );

    // Advance past warning threshold (1 minute)
    act(() => {
      vi.advanceTimersByTime(61_000);
    });

    expect(result.current.isWarningShown).toBe(true);
    expect(result.current.isExpired).toBe(false);
  });

  test("timeout fires after timeoutMinutes of inactivity", () => {
    const onTimeout = vi.fn();
    const { result } = renderHook(() =>
      useSessionTimeout({
        sessionId: "sess-1",
        warningMinutes: 1,
        timeoutMinutes: 2,
        onTimeout,
      }),
    );

    // Advance past timeout threshold (2 minutes)
    act(() => {
      vi.advanceTimersByTime(121_000);
    });

    expect(result.current.isExpired).toBe(true);
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  test("extendSession resets timer and clears warnings", () => {
    const { result } = renderHook(() =>
      useSessionTimeout({
        sessionId: "sess-1",
        warningMinutes: 1,
        timeoutMinutes: 2,
      }),
    );

    // Trigger warning
    act(() => {
      vi.advanceTimersByTime(61_000);
    });
    expect(result.current.isWarningShown).toBe(true);

    // Extend session
    act(() => {
      result.current.extendSession();
    });

    expect(result.current.isWarningShown).toBe(false);
    expect(result.current.isExpired).toBe(false);
    expect(result.current.remainingSeconds).toBe(120);
  });

  test("disabled when sessionId is null", () => {
    const { result } = renderHook(() =>
      useSessionTimeout({
        sessionId: null,
        warningMinutes: 1,
        timeoutMinutes: 2,
      }),
    );

    act(() => {
      vi.advanceTimersByTime(300_000);
    });

    expect(result.current.isWarningShown).toBe(false);
    expect(result.current.isExpired).toBe(false);
  });

  test("disabled when enabled is false", () => {
    const { result } = renderHook(() =>
      useSessionTimeout({
        sessionId: "sess-1",
        enabled: false,
        warningMinutes: 1,
        timeoutMinutes: 2,
      }),
    );

    act(() => {
      vi.advanceTimersByTime(300_000);
    });

    expect(result.current.isWarningShown).toBe(false);
    expect(result.current.isExpired).toBe(false);
  });
});
