import { renderHook, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import axios from "axios";
import { useAccountCreationProgress } from "./useAccountCreationProgress";

// Mock axios
vi.mock("axios");

describe("useAccountCreationProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("returns null when no accountId is provided", () => {
    const { result } = renderHook(() => useAccountCreationProgress(null));
    expect(result.current).toBeNull();
  });

  test("fetches progress when accountId is provided", async () => {
    const mockProgress = {
      status: "processing",
      percentage: 60,
      current_step: 3,
      total_steps: 5,
      message: "Generating strategy...",
      steps: [
        { name: "Creating account", status: "completed" },
        { name: "Setting up database", status: "completed" },
        { name: "Generating strategy", status: "processing" },
        { name: "Syncing activities", status: "pending" },
        { name: "Finalizing setup", status: "pending" },
      ],
    };

    (axios.get as any).mockResolvedValue({ data: mockProgress });

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    await waitFor(() => {
      expect(result.current).toEqual({
        percentage: 60,
        currentStep: 3,
        totalSteps: 5,
        steps: mockProgress.steps,
      });
    });

    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/accounts/acc_test123/creation-status"),
      expect.any(Object),
    );
  });

  test("polls for progress updates", async () => {
    const mockProgress1 = {
      status: "processing",
      percentage: 20,
      current_step: 1,
      total_steps: 5,
      message: "Creating account...",
      steps: [{ name: "Creating account", status: "processing" }],
    };

    const mockProgress2 = {
      status: "processing",
      percentage: 40,
      current_step: 2,
      total_steps: 5,
      message: "Setting up database...",
      steps: [{ name: "Setting up database", status: "processing" }],
    };

    (axios.get as any)
      .mockResolvedValueOnce({ data: mockProgress1 })
      .mockResolvedValueOnce({ data: mockProgress2 });

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    // Initial fetch
    await waitFor(() => {
      expect(result.current?.percentage).toBe(20);
    });

    // Advance timer to trigger next poll
    vi.advanceTimersByTime(1000);

    await waitFor(() => {
      expect(result.current?.percentage).toBe(40);
    });

    expect(axios.get).toHaveBeenCalledTimes(2);
  });

  test("stops polling when status is completed", async () => {
    const mockProgress = {
      status: "completed",
      percentage: 100,
      current_step: 5,
      total_steps: 5,
      message: "Account creation completed",
      steps: [
        { name: "Creating account", status: "completed" },
        { name: "Setting up database", status: "completed" },
        { name: "Generating strategy", status: "completed" },
        { name: "Syncing activities", status: "completed" },
        { name: "Finalizing setup", status: "completed" },
      ],
    };

    (axios.get as any).mockResolvedValue({ data: mockProgress });

    renderHook(() => useAccountCreationProgress("acc_test123"));

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledTimes(1);
    });

    // Advance timer - should not trigger more calls
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledTimes(1); // Still only 1 call
    });
  });

  test("stops polling when status is failed", async () => {
    const mockProgress = {
      status: "failed",
      percentage: 60,
      current_step: 3,
      total_steps: 5,
      message: "Account creation failed",
      steps: [],
    };

    (axios.get as any).mockResolvedValue({ data: mockProgress });

    renderHook(() => useAccountCreationProgress("acc_test123"));

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledTimes(1);
    });

    // Advance timer - should not trigger more calls
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledTimes(1); // Still only 1 call
    });
  });

  test("continues polling on error", async () => {
    (axios.get as any)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce({
        data: {
          status: "processing",
          percentage: 40,
          current_step: 2,
          total_steps: 5,
          message: "Processing...",
          steps: [],
        },
      });

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { result } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    // First call fails
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to fetch account creation progress:",
        expect.any(Error),
      );
    });

    // Advance timer for next poll
    vi.advanceTimersByTime(1000);

    // Second call succeeds
    await waitFor(() => {
      expect(result.current?.percentage).toBe(40);
    });

    expect(axios.get).toHaveBeenCalledTimes(2);
    consoleSpy.mockRestore();
  });

  test("includes auth token when available", async () => {
    const mockToken = "test-auth-token";
    Storage.prototype.getItem = vi.fn(() => mockToken);

    (axios.get as any).mockResolvedValue({
      data: {
        status: "processing",
        percentage: 50,
        current_step: 3,
        total_steps: 5,
        message: "Processing...",
        steps: [],
      },
    });

    renderHook(() => useAccountCreationProgress("acc_test123"));

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: { Authorization: `Bearer ${mockToken}` },
        }),
      );
    });
  });

  test("works without auth token", async () => {
    Storage.prototype.getItem = vi.fn(() => null);

    (axios.get as any).mockResolvedValue({
      data: {
        status: "processing",
        percentage: 50,
        current_step: 3,
        total_steps: 5,
        message: "Processing...",
        steps: [],
      },
    });

    renderHook(() => useAccountCreationProgress("acc_test123"));

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: {},
        }),
      );
    });
  });

  test("cleans up interval on unmount", () => {
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");

    (axios.get as any).mockResolvedValue({
      data: {
        status: "processing",
        percentage: 50,
        current_step: 3,
        total_steps: 5,
        message: "Processing...",
        steps: [],
      },
    });

    const { unmount } = renderHook(() =>
      useAccountCreationProgress("acc_test123"),
    );

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
