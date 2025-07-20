import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import ReCaptcha from "./ReCaptcha";

// Mock react-google-recaptcha
vi.mock("react-google-recaptcha", () => ({
  default: vi.fn(({ onChange, onExpired, onErrored }: any) => {
    // Store callbacks for testing
    (window as any).__recaptchaCallbacks = {
      onChange,
      onExpired,
      onErrored,
    };
    return <div data-testid="mock-recaptcha">Mock ReCAPTCHA</div>;
  }),
}));

// Mock axios
vi.mock("axios");

describe("ReCaptcha", () => {
  const mockOnVerify = vi.fn();
  const mockOnError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    // Clear environment variables
    import.meta.env.VITE_RECAPTCHA_SITE_KEY = "";
    import.meta.env.VITE_API_BASE_URL = "http://localhost:8000";
  });

  test("renders loading state initially", () => {
    render(<ReCaptcha onVerify={mockOnVerify} />);
    expect(screen.getByText("Loading security check...")).toBeInTheDocument();
  });

  test("uses environment variable for site key when available", async () => {
    import.meta.env.VITE_RECAPTCHA_SITE_KEY = "test-site-key";

    render(<ReCaptcha onVerify={mockOnVerify} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-recaptcha")).toBeInTheDocument();
    });

    // Should not call API when env var is available
    expect(axios.get).not.toHaveBeenCalled();
  });

  test("fetches site key from API when env var not available", async () => {
    const mockAxios = axios as any;
    mockAxios.get.mockResolvedValueOnce({
      data: { site_key: "api-site-key" },
    });

    render(<ReCaptcha onVerify={mockOnVerify} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-recaptcha")).toBeInTheDocument();
    });

    expect(axios.get).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/recaptcha-site-key",
    );
  });

  test("handles API error when fetching site key", async () => {
    const mockAxios = axios as any;
    mockAxios.get.mockRejectedValueOnce(new Error("Network error"));

    render(<ReCaptcha onVerify={mockOnVerify} onError={mockOnError} />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Security verification unavailable. Please contact support.",
        ),
      ).toBeInTheDocument();
    });

    expect(mockOnError).toHaveBeenCalledWith("Failed to load reCAPTCHA");
  });

  test("calls onVerify(true) on successful verification", async () => {
    import.meta.env.VITE_RECAPTCHA_SITE_KEY = "test-site-key";
    const mockAxios = axios as any;
    mockAxios.post.mockResolvedValueOnce({
      data: { success: true },
    });

    render(<ReCaptcha onVerify={mockOnVerify} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-recaptcha")).toBeInTheDocument();
    });

    // Simulate successful captcha completion
    const callbacks = (window as any).__recaptchaCallbacks;
    await callbacks.onChange("test-token");

    await waitFor(() => {
      expect(mockOnVerify).toHaveBeenCalledWith(true);
    });

    expect(axios.post).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/verify-recaptcha",
      { token: "test-token" },
    );
  });

  test("calls onVerify(false) on failed verification", async () => {
    import.meta.env.VITE_RECAPTCHA_SITE_KEY = "test-site-key";
    const mockAxios = axios as any;
    mockAxios.post.mockResolvedValueOnce({
      data: { success: false },
    });

    render(<ReCaptcha onVerify={mockOnVerify} onError={mockOnError} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-recaptcha")).toBeInTheDocument();
    });

    // Simulate captcha completion
    const callbacks = (window as any).__recaptchaCallbacks;
    await callbacks.onChange("test-token");

    await waitFor(() => {
      expect(mockOnVerify).toHaveBeenCalledWith(false);
    });

    expect(mockOnError).toHaveBeenCalledWith("reCAPTCHA verification failed");
  });

  test("handles captcha expiration", async () => {
    import.meta.env.VITE_RECAPTCHA_SITE_KEY = "test-site-key";

    render(<ReCaptcha onVerify={mockOnVerify} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-recaptcha")).toBeInTheDocument();
    });

    // Simulate captcha expiration
    const callbacks = (window as any).__recaptchaCallbacks;
    callbacks.onExpired();

    await waitFor(() => {
      expect(mockOnVerify).toHaveBeenCalledWith(false);
      expect(
        screen.getByText("reCAPTCHA expired. Please complete it again."),
      ).toBeInTheDocument();
    });
  });

  test("handles captcha error", async () => {
    import.meta.env.VITE_RECAPTCHA_SITE_KEY = "test-site-key";

    render(<ReCaptcha onVerify={mockOnVerify} onError={mockOnError} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-recaptcha")).toBeInTheDocument();
    });

    // Simulate captcha error
    const callbacks = (window as any).__recaptchaCallbacks;
    callbacks.onErrored();

    await waitFor(() => {
      expect(mockOnVerify).toHaveBeenCalledWith(false);
      expect(mockOnError).toHaveBeenCalledWith("reCAPTCHA error");
      expect(
        screen.getByText("reCAPTCHA error. Please refresh the page."),
      ).toBeInTheDocument();
    });
  });
});
