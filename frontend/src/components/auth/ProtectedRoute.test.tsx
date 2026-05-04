import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./ProtectedRoute";

// Minimal mock — ProtectedRoute only reads three fields
const mockUseAuth = vi.fn();
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Prevent Authentication from rendering its full form tree
vi.mock("@/pages/Authentication", () => ({
  default: () => <div>AUTH_PAGE_SENTINEL</div>,
}));

// Mock Firebase to avoid module initialisation errors
vi.mock("@/lib/firebase", () => ({
  auth: { currentUser: null },
  authInitialized: true,
  authBypassEnabled: false,
}));

const renderProtectedRoute = (initialEntry = "/") =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        {/* Sentinel for the redirect target */}
        <Route
          path="/select-organization"
          element={<div>SELECT_ORG_SENTINEL</div>}
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <div>PROTECTED_CONTENT</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders loading spinner when isAuthLoading is true", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isAuthLoading: true,
      hasSelectedWorkspace: false,
    });

    renderProtectedRoute();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED_CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByText("SELECT_ORG_SENTINEL")).not.toBeInTheDocument();
  });

  test("renders Authentication page when user is not authenticated", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isAuthLoading: false,
      hasSelectedWorkspace: false,
    });

    renderProtectedRoute();

    expect(screen.getByText("AUTH_PAGE_SENTINEL")).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED_CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByText("SELECT_ORG_SENTINEL")).not.toBeInTheDocument();
  });

  test("redirects to /select-organization when authenticated but no workspace selected", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isAuthLoading: false,
      hasSelectedWorkspace: false,
    });

    renderProtectedRoute();

    expect(screen.getByText("SELECT_ORG_SENTINEL")).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED_CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByText("AUTH_PAGE_SENTINEL")).not.toBeInTheDocument();
  });

  test("renders children when authenticated and workspace is selected", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isAuthLoading: false,
      hasSelectedWorkspace: true,
    });

    renderProtectedRoute();

    expect(screen.getByText("PROTECTED_CONTENT")).toBeInTheDocument();
    expect(screen.queryByText("SELECT_ORG_SENTINEL")).not.toBeInTheDocument();
    expect(screen.queryByText("AUTH_PAGE_SENTINEL")).not.toBeInTheDocument();
  });
});
