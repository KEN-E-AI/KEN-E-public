import {
  describe,
  test,
  expect,
  vi,
  beforeEach,
  type MockedFunction,
} from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ProtectedRoute from "./ProtectedRoute";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext");

// Mock Firebase to avoid module initialisation errors
vi.mock("@/lib/firebase", () => ({
  auth: { currentUser: null },
  authInitialized: true,
  authBypassEnabled: false,
}));

const mockUseAuth = useAuth as MockedFunction<typeof useAuth>;

const makeAuthState = (overrides: Partial<ReturnType<typeof useAuth>> = {}) =>
  ({
    user: null,
    isAuthenticated: false,
    isAuthLoading: false,
    hasSelectedWorkspace: false,
    currentOrganizationId: null,
    selectedOrgAccount: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
    completeWorkspaceSelection: vi.fn(),
    resetWorkspaceSelection: vi.fn(),
    setCurrentOrganization: vi.fn(),
    setSelectedOrgAccount: vi.fn(),
    orgMetadata: {},
    accountMetadata: {},
    setOrgMetadata: vi.fn(),
    setAccountMetadata: vi.fn(),
    notifications: [],
    setNotifications: vi.fn(),
    refreshNotifications: vi.fn(),
    notificationSettings: [],
    securitySettings: [],
    setNotificationSettings: vi.fn(),
    setSecuritySettings: vi.fn(),
    isSuperAdmin: false,
    ...overrides,
  }) as ReturnType<typeof useAuth>;

// Sentinel component that surfaces its location for assertions
const SignInSentinel = () => {
  const location = useLocation();
  return (
    <div data-testid="sign-in-sentinel">
      SIGN IN
      {location.state?.from?.pathname && (
        <span data-testid="from-path">{location.state.from.pathname}</span>
      )}
    </div>
  );
};

const renderWithRouter = (initialPath = "/protected") => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/sign-in" element={<SignInSentinel />} />
        <Route
          path="/select-organization"
          element={<div data-testid="select-org-sentinel">SELECT_ORG</div>}
        />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <div>PROTECTED CONTENT</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
};

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("unauthenticated user is redirected to /sign-in", () => {
    mockUseAuth.mockReturnValue(makeAuthState({ isAuthenticated: false }));
    renderWithRouter();
    expect(screen.getByTestId("sign-in-sentinel")).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();
  });

  test("redirect to /sign-in carries the original location in state.from", () => {
    mockUseAuth.mockReturnValue(makeAuthState({ isAuthenticated: false }));
    renderWithRouter("/protected");
    expect(screen.getByTestId("from-path")).toHaveTextContent("/protected");
  });

  test("authenticated user with selected workspace renders children", () => {
    mockUseAuth.mockReturnValue(
      makeAuthState({ isAuthenticated: true, hasSelectedWorkspace: true }),
    );
    renderWithRouter();
    expect(screen.getByText("PROTECTED CONTENT")).toBeInTheDocument();
    expect(screen.queryByTestId("sign-in-sentinel")).not.toBeInTheDocument();
  });

  test("authenticated user without selected workspace redirects to /select-organization", () => {
    mockUseAuth.mockReturnValue(
      makeAuthState({ isAuthenticated: true, hasSelectedWorkspace: false }),
    );
    renderWithRouter();
    expect(screen.getByTestId("select-org-sentinel")).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sign-in-sentinel")).not.toBeInTheDocument();
  });

  test("shows loading spinner while auth state is loading", () => {
    mockUseAuth.mockReturnValue(makeAuthState({ isAuthLoading: true }));
    renderWithRouter();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sign-in-sentinel")).not.toBeInTheDocument();
  });
});
