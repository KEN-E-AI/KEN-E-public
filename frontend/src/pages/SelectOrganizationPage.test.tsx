import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import SelectOrganizationPage, {
  PLACEHOLDER_ORGS,
  PLACEHOLDER_ACCOUNTS,
} from "./SelectOrganizationPage";

// --- module mocks ---

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...original,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/data/organizationApi", () => ({
  getOrganizations: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
  },
}));

// --- helpers ---

import { useAuth } from "@/contexts/AuthContext";
import { getOrganizations } from "@/data/organizationApi";
import api from "@/lib/api";

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;
const mockGetOrganizations = getOrganizations as ReturnType<typeof vi.fn>;
const mockApiGet = (api as { get: ReturnType<typeof vi.fn> }).get;

function buildAuthUser(
  overrides: Partial<{
    isSuperAdmin: boolean;
    id: string;
    isAuthenticated: boolean;
    isAuthLoading: boolean;
    hasSelectedWorkspace: boolean;
  }> = {},
) {
  return {
    user: { id: "user-123", email: "user@example.com" },
    isSuperAdmin: overrides.isSuperAdmin ?? false,
    isAuthenticated: overrides.isAuthenticated ?? true,
    isAuthLoading: overrides.isAuthLoading ?? false,
    hasSelectedWorkspace: overrides.hasSelectedWorkspace ?? false,
    ...overrides,
  };
}

function makeAxiosOrgResponse(orgs: Record<string, string>) {
  return {
    data: {
      data: {
        permissions: {
          organizations: orgs,
        },
      },
    },
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <SelectOrganizationPage />
    </MemoryRouter>,
  );
}

// --- tests ---

describe("SelectOrganizationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("loading state", () => {
    it("shows a loading spinner while user data is being fetched", () => {
      mockUseAuth.mockReturnValue(buildAuthUser());
      // Axios never resolves — keeps the component in loading state
      mockApiGet.mockReturnValue(new Promise(() => {}));

      renderPage();

      expect(screen.queryByText("Organizations")).not.toBeInTheDocument();
      expect(screen.queryByText("Accounts")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /continue/i }),
      ).not.toBeInTheDocument();
      // Loading spinner indicator is visible
      expect(screen.getByText(/loading your workspace/i)).toBeInTheDocument();
    });
  });

  describe("zero-orgs redirect", () => {
    it("redirects to /create-organization when non-super-admin has no org permissions", async () => {
      mockUseAuth.mockReturnValue(buildAuthUser({ isSuperAdmin: false }));
      mockApiGet.mockResolvedValue(makeAxiosOrgResponse({}));

      renderPage();

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/create-organization", {
          replace: true,
        });
      });
    });

    it("does not render selector cards while user data is still loading (no-flash guarantee)", () => {
      mockUseAuth.mockReturnValue(buildAuthUser({ isSuperAdmin: false }));
      // Axios never resolves — component stays in loading state
      mockApiGet.mockReturnValue(new Promise(() => {}));

      renderPage();

      // While loading, neither card title should be visible
      expect(screen.queryByText("Organizations")).not.toBeInTheDocument();
      expect(screen.queryByText("Accounts")).not.toBeInTheDocument();
    });

    it("does not redirect when non-super-admin has at least one org", async () => {
      mockUseAuth.mockReturnValue(buildAuthUser({ isSuperAdmin: false }));
      mockApiGet.mockResolvedValue(
        makeAxiosOrgResponse({ "org-abc": "member" }),
      );

      renderPage();

      await waitFor(() => {
        expect(screen.getByText("Organizations")).toBeInTheDocument();
      });

      expect(mockNavigate).not.toHaveBeenCalledWith(
        "/create-organization",
        expect.anything(),
      );
    });

    it("does not redirect when user is super-admin even with empty Firestore permissions", async () => {
      mockUseAuth.mockReturnValue(buildAuthUser({ isSuperAdmin: true }));
      // Super-admin path calls getOrganizations(), not axios.get
      mockGetOrganizations.mockResolvedValue([
        { organization_id: "org-super-1" },
      ]);

      renderPage();

      await waitFor(() => {
        expect(screen.getByText("Organizations")).toBeInTheDocument();
      });

      expect(mockNavigate).not.toHaveBeenCalledWith(
        "/create-organization",
        expect.anything(),
      );
      expect(mockApiGet).not.toHaveBeenCalled();
    });
  });

  describe("loaded state (with orgs)", () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue(buildAuthUser({ isSuperAdmin: false }));
      mockApiGet.mockResolvedValue(
        makeAxiosOrgResponse({ "org-abc": "member" }),
      );
    });

    it("renders the page heading", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /choose a workspace/i }),
        ).toBeInTheDocument();
      });
    });

    it("renders both Organizations and Accounts card titles", async () => {
      renderPage();
      await waitFor(() => {
        expect(screen.getByText("Organizations")).toBeInTheDocument();
        expect(screen.getByText("Accounts")).toBeInTheDocument();
      });
    });

    it("renders the Continue button as disabled by default", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /continue/i }),
        ).toBeDisabled();
      });
    });

    it("enables Continue button after selecting an org and account", async () => {
      const user = userEvent.setup();
      renderPage();

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /continue/i }),
        ).toBeDisabled();
      });

      const orgRows = screen.getAllByRole("button", {
        name: new RegExp(PLACEHOLDER_ORGS[0].name, "i"),
      });
      await user.click(orgRows[0]);

      const accountRows = screen.getAllByRole("button", {
        name: new RegExp(PLACEHOLDER_ACCOUNTS[0].name, "i"),
      });
      await user.click(accountRows[0]);

      expect(screen.getByRole("button", { name: /continue/i })).toBeEnabled();
    });

    it("renders the Contact Support mailto link", async () => {
      renderPage();
      await waitFor(() => {
        const link = screen.getByRole("link", { name: /contact support/i });
        expect(link).toHaveAttribute("href", "mailto:support@ken-e.com");
      });
    });

    it("does not render a BackgroundEffects component inside the page", async () => {
      renderPage();
      await waitFor(() => {
        expect(screen.getByText("Organizations")).toBeInTheDocument();
      });
      expect(screen.queryAllByTestId("bg-blobs").length).toBe(0);
      expect(screen.queryAllByTestId("bg-static").length).toBe(0);
    });
  });
});
