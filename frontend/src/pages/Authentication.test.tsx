import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { signInWithPopup } from "firebase/auth";
import axios from "axios";
import Authentication from "./Authentication";
import { AuthContext } from "@/contexts/AuthContext";
import type { ReactNode } from "react";

// Mock Firebase auth
vi.mock("@/lib/firebase", () => ({
  auth: {},
  googleProvider: {},
}));

vi.mock("firebase/auth", () => ({
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
}));

// Mock axios
vi.mock("axios", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    isAxiosError: (error: any) => error.isAxiosError === true,
  },
}));
const mockedAxios = vi.mocked(axios);

// Mock ReCAPTCHA components
vi.mock("@/components/auth/ReCaptchaProvider", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: ({ onVerify }: { onVerify: () => void }) => {
    // Auto-verify for tests
    setTimeout(() => onVerify(), 0);
    return null;
  },
}));

describe("Authentication - Google Sign-In", () => {
  const mockLogin = vi.fn();
  const mockSetNotificationSettings = vi.fn();
  const mockSetSecuritySettings = vi.fn();
  const mockOnAuthenticated = vi.fn();

  const renderWithAuth = () => {
    const mockAuthValue = {
      user: null,
      login: mockLogin,
      signOut: vi.fn(),
      updateUser: vi.fn(),
      setNotificationSettings: mockSetNotificationSettings,
      setSecuritySettings: mockSetSecuritySettings,
      selectedOrganization: null,
      setSelectedOrganization: vi.fn(),
      selectedAccount: null,
      setSelectedAccount: vi.fn(),
    };

    return render(
      <AuthContext.Provider value={mockAuthValue}>
        <Authentication onAuthenticated={mockOnAuthenticated} />
      </AuthContext.Provider>,
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Setup default environment
    import.meta.env.VITE_API_BASE_URL = "http://localhost:8000";
  });

  test("renders Google sign-in button", () => {
    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    expect(googleButton).toBeInTheDocument();
    expect(googleButton).not.toBeDisabled();
  });

  test("successful Google sign-in for existing user", async () => {
    const user = userEvent.setup();
    const mockFirebaseUser = {
      uid: "test-uid",
      email: "test@example.com",
      displayName: "Test User",
    };

    const mockUserData = {
      profile: {
        email: "test@example.com",
        first_name: "Test",
        last_name: "User",
        job_title: "Developer",
      },
      permissions: { organizations: {}, accounts: {} },
      preferences: {},
    };

    // Mock successful Google sign-in
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: mockFirebaseUser,
    } as any);

    // Mock API calls for existing user
    mockedAxios.get.mockResolvedValueOnce({
      data: { data: mockUserData },
    });

    mockedAxios.post.mockResolvedValueOnce({
      data: { documents: [{ data: { emailNotifications: true } }] },
    });

    mockedAxios.post.mockResolvedValueOnce({
      data: { documents: [{ data: { twoFactorEnabled: false } }] },
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(signInWithPopup).toHaveBeenCalledWith(
        expect.anything(),
        expect.anything(),
      );
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        id: "test-uid",
        email: "test@example.com",
        firstName: "Test",
        lastName: "User",
        jobTitle: "Developer",
        permissions: { organizations: {}, accounts: {} },
        preferences: {},
      });
    });

    expect(mockSetNotificationSettings).toHaveBeenCalledWith({
      emailNotifications: true,
    });
    expect(mockSetSecuritySettings).toHaveBeenCalledWith({
      twoFactorEnabled: false,
    });
    expect(mockOnAuthenticated).toHaveBeenCalled();
  });

  test("successful Google sign-in for new user", async () => {
    const user = userEvent.setup();
    const mockFirebaseUser = {
      uid: "new-user-uid",
      email: "newuser@example.com",
      displayName: "New User",
    };

    // Mock successful Google sign-in
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: mockFirebaseUser,
    } as any);

    // Mock 404 for non-existent user
    mockedAxios.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });

    // Mock successful user creation
    mockedAxios.post.mockImplementation((url) => {
      if (url === "http://localhost:8000/api/v1/firestore/documents") {
        return Promise.resolve({ data: { success: true } });
      }
      // Return empty documents for notifications/security queries
      return Promise.resolve({ data: { documents: [] } });
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/firestore/documents",
        expect.objectContaining({
          account_id: "new-user-uid",
          collection: "users",
          document_id: "new-user-uid",
          data: expect.objectContaining({
            profile: expect.objectContaining({
              email: "newuser@example.com",
              first_name: "New",
              last_name: "User",
            }),
          }),
        }),
      );
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        id: "new-user-uid",
        email: "newuser@example.com",
        firstName: "New",
        lastName: "User",
        jobTitle: "",
        permissions: { organizations: {}, accounts: {} },
        preferences: {},
      });
    });

    expect(mockOnAuthenticated).toHaveBeenCalled();
  });

  test("handles Google sign-in cancellation", async () => {
    const user = userEvent.setup();

    // Mock user cancelling the popup
    vi.mocked(signInWithPopup).mockRejectedValueOnce({
      code: "auth/popup-closed-by-user",
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(
        screen.getByText("Sign-in cancelled. Please try again."),
      ).toBeInTheDocument();
    });

    expect(mockLogin).not.toHaveBeenCalled();
    expect(mockOnAuthenticated).not.toHaveBeenCalled();
  });

  test("handles popup blocked error", async () => {
    const user = userEvent.setup();

    // Mock popup blocked error
    vi.mocked(signInWithPopup).mockRejectedValueOnce({
      code: "auth/popup-blocked",
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(
        screen.getByText("Pop-up blocked. Please allow pop-ups for this site."),
      ).toBeInTheDocument();
    });

    expect(mockLogin).not.toHaveBeenCalled();
  });

  test("handles API server error", async () => {
    const user = userEvent.setup();
    const mockFirebaseUser = {
      uid: "test-uid",
      email: "test@example.com",
      displayName: "Test User",
    };

    // Mock successful Google sign-in
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: mockFirebaseUser,
    } as any);

    // Mock 500 server error
    mockedAxios.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 500 },
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(
        screen.getByText("Server error. Please try again later."),
      ).toBeInTheDocument();
    });

    expect(mockLogin).not.toHaveBeenCalled();
  });

  test("handles network error", async () => {
    const user = userEvent.setup();

    // Mock network error
    vi.mocked(signInWithPopup).mockRejectedValueOnce({
      code: "auth/network-request-failed",
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please check your connection."),
      ).toBeInTheDocument();
    });

    expect(mockLogin).not.toHaveBeenCalled();
  });

  test("disables Google button while loading", async () => {
    const user = userEvent.setup();

    // Mock a delayed response
    vi.mocked(signInWithPopup).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000)),
    );

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });

    expect(googleButton).not.toBeDisabled();

    await user.click(googleButton);

    // Button should be disabled while loading
    expect(googleButton).toBeDisabled();
  });

  test("handles single name users correctly", async () => {
    const user = userEvent.setup();
    const mockFirebaseUser = {
      uid: "single-name-uid",
      email: "prince@example.com",
      displayName: "Prince", // Single name
    };

    // Mock successful Google sign-in
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: mockFirebaseUser,
    } as any);

    // Mock 404 for non-existent user
    mockedAxios.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });

    // Mock successful user creation
    mockedAxios.post.mockImplementation((url) => {
      if (url === "http://localhost:8000/api/v1/firestore/documents") {
        return Promise.resolve({ data: { success: true } });
      }
      return Promise.resolve({ data: { documents: [] } });
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/firestore/documents",
        expect.objectContaining({
          data: expect.objectContaining({
            profile: expect.objectContaining({
              first_name: "Prince",
              last_name: "", // Empty last name for single name
            }),
          }),
        }),
      );
    });
  });

  test("handles users with no display name", async () => {
    const user = userEvent.setup();
    const mockFirebaseUser = {
      uid: "no-name-uid",
      email: "noname@example.com",
      displayName: null, // No display name
    };

    // Mock successful Google sign-in
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: mockFirebaseUser,
    } as any);

    // Mock 404 for non-existent user
    mockedAxios.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });

    // Mock successful user creation
    mockedAxios.post.mockImplementation((url) => {
      if (url === "http://localhost:8000/api/v1/firestore/documents") {
        return Promise.resolve({ data: { success: true } });
      }
      return Promise.resolve({ data: { documents: [] } });
    });

    renderWithAuth();

    const googleButton = screen.getByRole("button", { name: /google/i });
    await user.click(googleButton);

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/firestore/documents",
        expect.objectContaining({
          data: expect.objectContaining({
            profile: expect.objectContaining({
              first_name: "",
              last_name: "",
            }),
          }),
        }),
      );
    });
  });
});
