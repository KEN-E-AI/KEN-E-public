import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import ReCaptchaV3 from "./ReCaptchaV3";

// Mock react-google-recaptcha-v3
vi.mock("react-google-recaptcha-v3", () => ({
  useGoogleReCaptcha: vi.fn(() => ({
    executeRecaptcha: vi.fn(async (action: string) => `test-token-${action}`),
  })),
}));

// Mock axios
vi.mock("axios");

describe("ReCaptchaV3", () => {
  const mockOnVerify = vi.fn();
  const mockOnError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    import.meta.env.VITE_API_BASE_URL = "http://localhost:8000";
  });

  test("automatically executes reCAPTCHA on mount", async () => {
    const mockAxios = axios as any;
    mockAxios.post.mockResolvedValueOnce({
      data: { success: true },
    });

    render(<ReCaptchaV3 onVerify={mockOnVerify} action="signin" />);

    // Should show verifying state initially
    expect(screen.getByText("Verifying security...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Security verified")).toBeInTheDocument();
    });

    expect(mockOnVerify).toHaveBeenCalledWith(true);
    expect(axios.post).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/verify-recaptcha",
      { token: "test-token-signin", action: "signin" },
    );
  });

  test("handles verification failure", async () => {
    const mockAxios = axios as any;
    mockAxios.post.mockResolvedValueOnce({
      data: { success: false },
    });

    render(
      <ReCaptchaV3
        onVerify={mockOnVerify}
        onError={mockOnError}
        action="signup"
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "Security verification failed. Please refresh and try again.",
        ),
      ).toBeInTheDocument();
    });

    expect(mockOnVerify).toHaveBeenCalledWith(false);
    expect(mockOnError).toHaveBeenCalledWith("Security verification failed");
  });

  test("handles network error", async () => {
    const mockAxios = axios as any;
    mockAxios.post.mockRejectedValueOnce(new Error("Network error"));

    render(
      <ReCaptchaV3
        onVerify={mockOnVerify}
        onError={mockOnError}
        action="signin"
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "Security verification error. Please refresh the page.",
        ),
      ).toBeInTheDocument();
    });

    expect(mockOnVerify).toHaveBeenCalledWith(false);
    expect(mockOnError).toHaveBeenCalledWith("Security verification error");
  });

  test("handles missing executeRecaptcha", async () => {
    // Mock useGoogleReCaptcha to return null executeRecaptcha
    const { useGoogleReCaptcha } = await import("react-google-recaptcha-v3");
    (useGoogleReCaptcha as any).mockReturnValueOnce({
      executeRecaptcha: null,
    });

    render(
      <ReCaptchaV3
        onVerify={mockOnVerify}
        onError={mockOnError}
        action="signin"
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("reCAPTCHA not available")).toBeInTheDocument();
    });

    expect(mockOnVerify).toHaveBeenCalledWith(false);
    expect(mockOnError).toHaveBeenCalledWith("reCAPTCHA not available");
  });

  test("shows correct status for each state", async () => {
    const mockAxios = axios as any;
    mockAxios.post.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve({ data: { success: true } }), 100),
        ),
    );

    const { rerender } = render(
      <ReCaptchaV3 onVerify={mockOnVerify} action="signin" />,
    );

    // Initially shows verifying
    expect(screen.getByText("Verifying security...")).toBeInTheDocument();

    // Wait for success
    await waitFor(() => {
      expect(screen.getByText("Security verified")).toBeInTheDocument();
    });

    // Check success icon is shown
    expect(screen.getByTestId("shield-check-icon")).toBeInTheDocument();
  });
});
