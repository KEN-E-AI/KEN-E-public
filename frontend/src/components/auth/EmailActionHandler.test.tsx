import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import EmailActionHandler from "./EmailActionHandler";
import { applyActionCode, checkActionCode } from "firebase/auth";
import axios from "axios";

// Mock Firebase auth functions
vi.mock("firebase/auth", () => ({
  applyActionCode: vi.fn(),
  checkActionCode: vi.fn(),
  getAuth: vi.fn(() => ({})),
}));

// Mock the firebase lib
vi.mock("@/lib/firebase", () => ({
  auth: {},
}));

// Mock axios
vi.mock("axios");

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const renderWithRouter = (initialEntry: string) => {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/auth/action" element={<EmailActionHandler />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("EmailActionHandler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("shows error when oobCode is missing", async () => {
    renderWithRouter("/auth/action?mode=verifyEmail");

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Verification Failed" }),
      ).toBeInTheDocument();
      expect(screen.getByText(/Invalid verification link/)).toBeInTheDocument();
    });
  });

  test("shows error when mode is missing", async () => {
    renderWithRouter("/auth/action?oobCode=test123");

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Verification Failed" }),
      ).toBeInTheDocument();
      expect(screen.getByText(/Invalid verification link/)).toBeInTheDocument();
    });
  });

  test("shows error for unsupported modes", async () => {
    renderWithRouter("/auth/action?mode=resetPassword&oobCode=test123");

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Verification Failed" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/only handles email verification/),
      ).toBeInTheDocument();
    });
  });

  test("successfully verifies email", async () => {
    const mockCheckActionCode = vi.mocked(checkActionCode);
    const mockApplyActionCode = vi.mocked(applyActionCode);
    const mockAxiosPost = vi.mocked(axios.post);
    const mockAxiosPut = vi.mocked(axios.put);

    mockCheckActionCode.mockResolvedValue({
      data: { email: "test@example.com" },
    } as any);
    mockApplyActionCode.mockResolvedValue(undefined);

    // Mock the query response
    mockAxiosPost.mockResolvedValue({
      data: {
        documents: [
          {
            id: "user123",
            data: {
              profile: {
                email: "test@example.com",
                first_name: "Test",
                last_name: "User",
                email_verified: false,
              },
              permissions: {},
              preferences: {},
              metadata: {
                createdAt: "2024-01-01T00:00:00.000Z",
                lastUpdated: "2024-01-01T00:00:00.000Z",
              },
            },
          },
        ],
      },
    });

    // Mock the update response
    mockAxiosPut.mockResolvedValue({ data: { message: "Document updated" } });

    renderWithRouter("/auth/action?mode=verifyEmail&oobCode=validCode123");

    await waitFor(() => {
      expect(screen.getByText("Email Verified!")).toBeInTheDocument();
      expect(screen.getByText("Success!")).toBeInTheDocument();
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
      expect(
        screen.getByText(/has been successfully verified/),
      ).toBeInTheDocument();
    });

    expect(mockCheckActionCode).toHaveBeenCalledWith({}, "validCode123");
    expect(mockApplyActionCode).toHaveBeenCalledWith({}, "validCode123");

    // Verify the query was made
    expect(mockAxiosPost).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/firestore/documents/query"),
      expect.objectContaining({
        account_id: "system",
        collection: "users",
        field: "profile.email",
        operator: "==",
        value: "test@example.com",
      }),
    );

    // Verify the updates were made with the correct structure
    expect(mockAxiosPut).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/firestore/documents/users/user123"),
      {
        update: {
          field: "profile.email_verified",
          operator: "set",
          value: true,
        },
      },
    );

    expect(mockAxiosPut).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/firestore/documents/users/user123"),
      {
        update: {
          field: "metadata.lastUpdated",
          operator: "set",
          value: expect.any(String),
        },
      },
    );
  });

  test("handles expired action code error", async () => {
    const mockCheckActionCode = vi.mocked(checkActionCode);
    mockCheckActionCode.mockRejectedValue({
      code: "auth/expired-action-code",
    });

    renderWithRouter("/auth/action?mode=verifyEmail&oobCode=expiredCode");

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Verification Failed" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/verification link has expired/),
      ).toBeInTheDocument();
    });
  });

  test("handles invalid action code error", async () => {
    const mockCheckActionCode = vi.mocked(checkActionCode);
    mockCheckActionCode.mockRejectedValue({
      code: "auth/invalid-action-code",
    });

    renderWithRouter("/auth/action?mode=verifyEmail&oobCode=invalidCode");

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Verification Failed" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/verification link is invalid/),
      ).toBeInTheDocument();
    });
  });

  test("navigates to sign in when button is clicked", async () => {
    const user = userEvent.setup();
    renderWithRouter("/auth/action?mode=verifyEmail");

    await waitFor(() => {
      expect(screen.getByText("Go to Sign In")).toBeInTheDocument();
    });

    const signInButton = screen.getByText("Go to Sign In");
    await user.click(signInButton);

    expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
  });

  test("shows loading state initially", () => {
    renderWithRouter("/auth/action?mode=verifyEmail&oobCode=test123");

    expect(screen.getByText("Verifying your email...")).toBeInTheDocument();
  });

  test("shows warning when Firestore update fails", async () => {
    const mockCheckActionCode = vi.mocked(checkActionCode);
    const mockApplyActionCode = vi.mocked(applyActionCode);
    const mockAxiosPost = vi.mocked(axios.post);
    const mockAxiosPut = vi.mocked(axios.put);

    mockCheckActionCode.mockResolvedValue({
      data: { email: "test@example.com" },
    } as any);
    mockApplyActionCode.mockResolvedValue(undefined);

    // Mock the query response
    mockAxiosPost.mockResolvedValue({
      data: {
        documents: [
          {
            id: "user123",
            data: {
              profile: { email: "test@example.com" },
            },
          },
        ],
      },
    });

    // Mock the update to fail
    mockAxiosPut.mockRejectedValue(new Error("Update failed"));

    renderWithRouter("/auth/action?mode=verifyEmail&oobCode=validCode123");

    await waitFor(() => {
      expect(screen.getByText("Email Verified!")).toBeInTheDocument();
      expect(screen.getByText("Note")).toBeInTheDocument();
      expect(
        screen.getByText(
          /Your email has been verified, but we couldn't update your profile/,
        ),
      ).toBeInTheDocument();
    });
  });

  test("shows warning when user not found in Firestore", async () => {
    const mockCheckActionCode = vi.mocked(checkActionCode);
    const mockApplyActionCode = vi.mocked(applyActionCode);
    const mockAxiosPost = vi.mocked(axios.post);

    mockCheckActionCode.mockResolvedValue({
      data: { email: "test@example.com" },
    } as any);
    mockApplyActionCode.mockResolvedValue(undefined);

    // Mock the query response with no documents
    mockAxiosPost.mockResolvedValue({
      data: {
        documents: [],
      },
    });

    renderWithRouter("/auth/action?mode=verifyEmail&oobCode=validCode123");

    await waitFor(() => {
      expect(screen.getByText("Email Verified!")).toBeInTheDocument();
      expect(screen.getByText("Note")).toBeInTheDocument();
      expect(
        screen.getByText(
          /Your email has been verified, but we couldn't update your profile/,
        ),
      ).toBeInTheDocument();
    });
  });

  test("handles continueUrl parameter", async () => {
    const mockCheckActionCode = vi.mocked(checkActionCode);
    const mockApplyActionCode = vi.mocked(applyActionCode);
    const mockAxiosPost = vi.mocked(axios.post);
    const mockAxiosPut = vi.mocked(axios.put);

    mockCheckActionCode.mockResolvedValue({
      data: { email: "test@example.com" },
    } as any);
    mockApplyActionCode.mockResolvedValue(undefined);

    // Mock successful query and update
    mockAxiosPost.mockResolvedValue({
      data: {
        documents: [
          {
            id: "user123",
            data: {
              profile: { email: "test@example.com" },
            },
          },
        ],
      },
    });
    mockAxiosPut.mockResolvedValue({ data: { message: "Document updated" } });

    const continueUrl = "https://example.com/dashboard";
    renderWithRouter(
      `/auth/action?mode=verifyEmail&oobCode=validCode&continueUrl=${encodeURIComponent(
        continueUrl,
      )}`,
    );

    await waitFor(() => {
      expect(screen.getByText("Continue to example.com")).toBeInTheDocument();
    });
  });
});
