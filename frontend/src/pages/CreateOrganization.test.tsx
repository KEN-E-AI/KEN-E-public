import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { CreateOrganization } from "./CreateOrganization";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

const mockCreateOrganization = vi.fn();
vi.mock("@/data/organizationApi", () => ({
  createOrganization: (...args: unknown[]) => mockCreateOrganization(...args),
}));

vi.mock("@/data/subscriptionPlansApi", () => ({
  getDefaultPlan: vi.fn().mockResolvedValue({
    plan_name: "Free Plan",
    plan_description: "Basic features for getting started",
    price: 0,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      features: ["Basic Reports", "1 User"],
      max_reports: 10,
      max_users: 1,
    },
  }),
}));

// Mock api client for Firestore permission write
vi.mock("@/lib/api", () => ({
  default: { put: vi.fn().mockResolvedValue({ data: {} }) },
}));

// Mock branding components
vi.mock("@/components/branding/Logo", () => ({
  Logo: () => <div data-testid="logo">Logo</div>,
}));

const mockCompleteWorkspaceSelection = vi.fn();
const mockSetCurrentOrganization = vi.fn();
const mockSetSelectedOrgAccount = vi.fn();
const mockUpdateUser = vi.fn();
const mockSetOrgMetadata = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "user-123",
      uid: "user-123",
      permissions: { organizations: {} },
    },
    updateUser: mockUpdateUser,
    completeWorkspaceSelection: mockCompleteWorkspaceSelection,
    setCurrentOrganization: mockSetCurrentOrganization,
    setSelectedOrgAccount: mockSetSelectedOrgAccount,
    orgMetadata: {},
    setOrgMetadata: mockSetOrgMetadata,
  }),
}));

function renderPage() {
  return render(
    <BrowserRouter>
      <CreateOrganization />
    </BrowserRouter>,
  );
}

describe("CreateOrganization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders form with organization name field and submit button", () => {
    renderPage();
    expect(
      screen.getByRole("textbox", { name: /organization name/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create organization/i }),
    ).toBeInTheDocument();
  });

  test("shows agency toggle that reveals child org field when enabled", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(
      screen.queryByLabelText(/child organizations/i),
    ).not.toBeInTheDocument();

    const agencyToggle = screen.getByRole("switch", {
      name: /this is an agency/i,
    });
    await user.click(agencyToggle);

    expect(screen.getByLabelText(/child organizations/i)).toBeInTheDocument();
  });

  test("shows validation toast when submitting without organization name", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Missing required fields",
          variant: "destructive",
        }),
      );
    });
    expect(mockCreateOrganization).not.toHaveBeenCalled();
  });

  test("success path: calls createOrganization and navigates to settings", async () => {
    const newOrg = {
      organization_id: "org-new-123",
      organization_name: "Acme Corp",
      plan: "Free Plan",
      accounts: [],
    };
    mockCreateOrganization.mockResolvedValue(newOrg);

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockCreateOrganization).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(mockCompleteWorkspaceSelection).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/settings/organization");
    });

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Organization created successfully!",
      }),
    );
  });
});
