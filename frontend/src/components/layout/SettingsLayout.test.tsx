import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import SettingsLayout from "./SettingsLayout";

// Mock the AuthContext
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    selectedOrgAccount: {
      orgId: "test-org",
      accountId: "test-account",
      metadata: {
        organization_name: "Test Organization",
        account_name: "Test Account",
      },
    },
  }),
}));

// Mock the context-breadcrumb component
vi.mock("@/components/ui/context-breadcrumb", () => ({
  ContextBreadcrumb: ({ currentPage }: { currentPage: string }) => (
    <div data-testid="context-breadcrumb">Breadcrumb for {currentPage}</div>
  ),
}));

// Mock the entity-selector component
vi.mock("@/components/ui/entity-selector", () => ({
  EntitySelector: ({ className }: { className?: string }) => (
    <div data-testid="entity-selector" className={className}>
      Entity Selector
    </div>
  ),
}));

// Mock the Layout component
vi.mock("./Layout", () => ({
  default: ({
    children,
    pageTitle,
  }: {
    children: React.ReactNode;
    pageTitle: string;
  }) => (
    <div data-testid="layout" data-page-title={pageTitle}>
      {children}
    </div>
  ),
}));

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
};

describe("SettingsLayout", () => {
  test("renders with basic props", () => {
    renderWithRouter(
      <SettingsLayout pageTitle="Test Settings" currentPage="settings">
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.getByTestId("layout")).toBeInTheDocument();
    expect(screen.getByTestId("layout")).toHaveAttribute(
      "data-page-title",
      "Test Settings",
    );
    expect(screen.getByText("Test content")).toBeInTheDocument();
  });

  test("shows breadcrumb with correct current page", () => {
    renderWithRouter(
      <SettingsLayout pageTitle="Test Settings" currentPage="organization">
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.getByTestId("context-breadcrumb")).toHaveTextContent(
      "Breadcrumb for organization",
    );
  });

  test("shows entity selector when showEntitySelector is true and not settings page", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="organization"
        showEntitySelector={true}
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.getByTestId("entity-selector")).toBeInTheDocument();
  });

  test("hides entity selector when showEntitySelector is false", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="organization"
        showEntitySelector={false}
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.queryByTestId("entity-selector")).not.toBeInTheDocument();
  });

  test("hides entity selector on settings page", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="settings"
        showEntitySelector={true}
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.queryByTestId("entity-selector")).not.toBeInTheDocument();
  });

  test("shows back button when showBackButton is true and not settings page", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="organization"
        showBackButton={true}
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.getByText("Back to Settings")).toBeInTheDocument();
  });

  test("hides back button when showBackButton is false", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="organization"
        showBackButton={false}
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.queryByText("Back to Settings")).not.toBeInTheDocument();
  });

  test("hides back button on settings page", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="settings"
        showBackButton={true}
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    expect(screen.queryByText("Back to Settings")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    renderWithRouter(
      <SettingsLayout
        pageTitle="Test Settings"
        currentPage="settings"
        className="custom-class"
      >
        <div>Test content</div>
      </SettingsLayout>,
    );

    const container = screen
      .getByTestId("layout")
      .querySelector(".custom-class");
    expect(container).toBeInTheDocument();
  });
});
