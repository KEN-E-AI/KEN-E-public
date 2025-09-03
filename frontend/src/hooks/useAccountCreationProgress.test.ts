import { renderHook, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import api from "@/lib/api";
import { useAccountCreationProgress } from "./useAccountCreationProgress";

// Mock api
vi.mock("@/lib/api");

describe("useAccountCreationProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("returns idle state when no accountId is provided", () => {
    const { result } = renderHook(() => useAccountCreationProgress(null));
    expect(result.current).toEqual({
      status: "idle",
      message: "",
    });
  });

  test("fetches status when accountId is provided", async () => {
    const mockStatus = {
      status: "processing",
      message: "Creating account...\n\nConducting research on your business to configure your account. This may take 15-20 minutes.",
    };

    (api.get as any).mockResolvedValue({ data: mockStatus });

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    await waitFor(() => {
      expect(result.current).toEqual({
        status: "processing",
        message: mockStatus.message,
      });
    });

    expect(api.get).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test123/creation-status",
    );
  });

  test("polls for status updates every 30 seconds", async () => {
    const mockStatus1 = {
      status: "processing",
      message: "Creating account...",
    };

    const mockStatus2 = {
      status: "processing",
      message: "Still processing...",
    };

    (api.get as any)
      .mockResolvedValueOnce({ data: mockStatus1 })
      .mockResolvedValueOnce({ data: mockStatus2 });

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    // Initial fetch
    await waitFor(() => {
      expect(result.current.message).toBe("Creating account...");
    });

    // Advance timer by 30 seconds to trigger next poll
    vi.advanceTimersByTime(30000);

    await waitFor(() => {
      expect(result.current.message).toBe("Still processing...");
    });

    expect(api.get).toHaveBeenCalledTimes(2);
  });

  test("stops polling when status is completed", async () => {
    const mockStatus = {
      status: "completed",
      message: "Account setup complete",
    };

    (api.get as any).mockResolvedValue({ data: mockStatus });

    renderHook(() => useAccountCreationProgress("acc_test123"));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledTimes(1);
    });

    // Advance timer - should not trigger more calls
    vi.advanceTimersByTime(30000);

    // Wait a bit to ensure no additional calls
    await new Promise(resolve => setTimeout(resolve, 100));

    expect(api.get).toHaveBeenCalledTimes(1); // Still only 1 call
  });

  test("stops polling when status is failed", async () => {
    const mockStatus = {
      status: "failed",
      message: "Account setup failed. Please try again.",
    };

    (api.get as any).mockResolvedValue({ data: mockStatus });

    renderHook(() => useAccountCreationProgress("acc_test123"));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledTimes(1);
    });

    // Advance timer - should not trigger more calls
    vi.advanceTimersByTime(30000);

    // Wait a bit to ensure no additional calls
    await new Promise(resolve => setTimeout(resolve, 100));

    expect(api.get).toHaveBeenCalledTimes(1); // Still only 1 call
  });

  test("continues polling on error without updating UI", async () => {
    const mockStatus = {
      status: "processing",
      message: "Creating account...",
    };

    (api.get as any)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce({ data: mockStatus });

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    // First call fails
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        "[useAccountCreationProgress] Failed to check status:",
        expect.any(Error),
      );
    });

    // Status should remain idle after error
    expect(result.current.status).toBe("idle");

    // Advance timer for next poll (30 seconds)
    vi.advanceTimersByTime(30000);

    // Second call succeeds
    await waitFor(() => {
      expect(result.current.status).toBe("processing");
    });

    expect(api.get).toHaveBeenCalledTimes(2);
    consoleSpy.mockRestore();
  });

  test("shows timeout message after 30 minutes", async () => {
    const mockStatus = {
      status: "processing",
      message: "Creating account...",
    };

    (api.get as any).mockResolvedValue({ data: mockStatus });

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    // Initial fetch
    await waitFor(() => {
      expect(result.current.status).toBe("processing");
    });

    // Advance timer by 30 minutes + 1 second
    vi.advanceTimersByTime(30 * 60 * 1000 + 1000);

    await waitFor(() => {
      expect(result.current.status).toBe("failed");
      expect(result.current.message).toContain("taking longer than expected");
    });
  });

  test("cleans up interval on unmount", () => {
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");

    (api.get as any).mockResolvedValue({
      data: {
        status: "processing",
        message: "Creating account...",
      },
    });

    const { unmount } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });

  test("resets state when accountId changes to null", async () => {
    const mockStatus = {
      status: "processing",
      message: "Creating account...",
    };

    (api.get as any).mockResolvedValue({ data: mockStatus });

    const { result, rerender } = renderHook(
      ({ accountId }) => useAccountCreationProgress(accountId),
      {
        initialProps: { accountId: "acc_test123" as string | null },
      },
    );

    await waitFor(() => {
      expect(result.current.status).toBe("processing");
    });

    // Change accountId to null
    rerender({ accountId: null });

    expect(result.current).toEqual({
      status: "idle",
      message: "",
    });
  });

  test("starts new polling when accountId changes", async () => {
    const mockStatus1 = {
      status: "processing",
      message: "Creating first account...",
    };

    const mockStatus2 = {
      status: "processing",
      message: "Creating second account...",
    };

    (api.get as any)
      .mockResolvedValueOnce({ data: mockStatus1 })
      .mockResolvedValueOnce({ data: mockStatus2 });

    const { result, rerender } = renderHook(
      ({ accountId }) => useAccountCreationProgress(accountId),
      {
        initialProps: { accountId: "acc_first" as string | null },
      },
    );

    await waitFor(() => {
      expect(result.current.message).toBe("Creating first account...");
    });

    // Change to a different accountId
    rerender({ accountId: "acc_second" });

    await waitFor(() => {
      expect(result.current.message).toBe("Creating second account...");
    });

    expect(api.get).toHaveBeenCalledWith("/api/v1/accounts/acc_first/creation-status");
    expect(api.get).toHaveBeenCalledWith("/api/v1/accounts/acc_second/creation-status");
  });
});