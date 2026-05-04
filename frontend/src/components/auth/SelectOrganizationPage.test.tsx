import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import SelectOrganizationPage from "./SelectOrganizationPage";

const mockUseAuth = vi.fn();
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/pages/OrganizationSelection", () => ({
  default: () => <div>ORG_SELECTION_SENTINEL</div>,
}));

vi.mock("@/lib/firebase", () => ({
  auth: { currentUser: null },
  authInitialized: true,
  authBypassEnabled: false,
}));

const renderSelectOrganizationPage = () =>
  render(
    <MemoryRouter initialEntries={["/select-organization"]}>
      <Routes>
        <Route path="/auth/signin" element={<div>SIGNIN_SENTINEL</div>} />
        <Route path="/" element={<div>HOME_SENTINEL</div>} />
        <Route
          path="/select-organization"
          element={<SelectOrganizationPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

describe("SelectOrganizationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders loading spinner when isAuthLoading is true", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isAuthLoading: true,
      hasSelectedWorkspace: false,
    });

    renderSelectOrganizationPage();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(
      screen.queryByText("ORG_SELECTION_SENTINEL"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("SIGNIN_SENTINEL")).not.toBeInTheDocument();
  });

  test("redirects unauthenticated user to /auth/signin", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isAuthLoading: false,
      hasSelectedWorkspace: false,
    });

    renderSelectOrganizationPage();

    expect(screen.getByText("SIGNIN_SENTINEL")).toBeInTheDocument();
    expect(
      screen.queryByText("ORG_SELECTION_SENTINEL"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("HOME_SENTINEL")).not.toBeInTheDocument();
  });

  test("redirects authenticated user who already has a workspace to /", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isAuthLoading: false,
      hasSelectedWorkspace: true,
    });

    renderSelectOrganizationPage();

    expect(screen.getByText("HOME_SENTINEL")).toBeInTheDocument();
    expect(
      screen.queryByText("ORG_SELECTION_SENTINEL"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("SIGNIN_SENTINEL")).not.toBeInTheDocument();
  });

  test("renders OrganizationSelection for authenticated user with no workspace", () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isAuthLoading: false,
      hasSelectedWorkspace: false,
    });

    renderSelectOrganizationPage();

    expect(screen.getByText("ORG_SELECTION_SENTINEL")).toBeInTheDocument();
    expect(screen.queryByText("SIGNIN_SENTINEL")).not.toBeInTheDocument();
    expect(screen.queryByText("HOME_SENTINEL")).not.toBeInTheDocument();
  });
});
