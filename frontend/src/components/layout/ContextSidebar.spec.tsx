import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { ContextSidebar } from "./ContextSidebar";
import { AuthContext } from "@/contexts/AuthContext";
import type { NotificationCategory } from "@/types/notification.types";
import api from "@/lib/api";

// Mock notifications with different categories
const mockNotifications = [
  {
    id: "1",
    account_id: "acc_123",
    category: "Data Quality Alert" as NotificationCategory,
    description: "Data quality issue detected",
    status: "unread",
    created_at: new Date().toISOString(),
    data: { title: "Alert: Data Quality" },
  },
  {
    id: "2",
    account_id: "acc_123",
    category: "News & Press" as NotificationCategory,
    description: "New press release available",
    status: "read",
    created_at: new Date().toISOString(),
    data: { title: "Press Release" },
  },
  {
    id: "3",
    account_id: "acc_123",
    category: "KPI Performance" as NotificationCategory,
    description: "KPI threshold exceeded",
    status: "unread",
    created_at: new Date().toISOString(),
    data: { title: "KPI Alert" },
  },
];

const mockAuthContextValue = {
  user: { id: "user_123", permissions: { organizations: {} } },
  notifications: mockNotifications,
  setNotifications: vi.fn(),
  orgMetadata: {},
  accountMetadata: {},
  selectedOrgAccount: null,
  setSelectedOrgAccount: vi.fn(),
  setCurrentOrganization: vi.fn(),
};

const renderWithProviders = (ui: React.ReactElement, initialRoute = "/") => {
  window.history.pushState({}, "", initialRoute);
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={mockAuthContextValue as any}>
        {ui}
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

// Mock api
vi.mock("@/lib/api", () => ({
  default: {
    put: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

describe("ContextSidebar", () => {
  const defaultProps = {
    isCollapsed: false,
    onToggleCollapse: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("shows notifications on home page", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/");
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  test("displays correct icons for notification categories", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/");

    // Check that notifications are rendered with proper category-based icons
    // Data Quality Alert should have AlertTriangle icon
    expect(screen.getByText("Alert: Data Quality")).toBeInTheDocument();
    expect(screen.getByText("Data quality issue detected")).toBeInTheDocument();

    // News & Press should have Newspaper icon
    expect(screen.getByText("Press Release")).toBeInTheDocument();
    expect(screen.getByText("New press release available")).toBeInTheDocument();

    // KPI Performance should have TrendingUp icon
    expect(screen.getByText("KPI Alert")).toBeInTheDocument();
    expect(screen.getByText("KPI threshold exceeded")).toBeInTheDocument();
  });

  test("shows unread notifications with green background", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/");

    // Find unread notification containers by their background color class
    const unreadNotifications = screen.getAllByText(
      /Alert: Data Quality|KPI Alert/,
    );
    unreadNotifications.forEach((notification) => {
      // Navigate up to the notification container, then find the icon container
      const notificationContainer = notification.closest(
        '[class*="flex items-start gap-3"]',
      );
      const iconContainer = notificationContainer?.querySelector(
        '[class*="rounded-full"]',
      );
      expect(iconContainer).toHaveClass("bg-[#B8E2AF]");
    });
  });

  test("shows read notifications with gray background", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/");

    // Find read notification by its title
    const readNotification = screen.getByText("Press Release");
    // Navigate up to the notification container, then find the icon container
    const notificationContainer = readNotification.closest(
      '[class*="flex items-start gap-3"]',
    );
    const iconContainer = notificationContainer?.querySelector(
      '[class*="rounded-full"]',
    );
    expect(iconContainer).toHaveClass("bg-gray-100");
  });

  test("shows Performance menu on performance page", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/performance");
    expect(screen.getByText("Performance")).toBeInTheDocument();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Channel Performance")).toBeInTheDocument();
  });

  test("shows Knowledge Base menu on knowledge page", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/knowledge");
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText("Products")).toBeInTheDocument();
    expect(screen.getByText("Metrics")).toBeInTheDocument();
    expect(screen.getByText("Activities")).toBeInTheDocument();
  });

  test("highlights active menu item", () => {
    renderWithProviders(
      <ContextSidebar {...defaultProps} />,
      "/knowledge/metrics",
    );
    const metricsButton = screen.getByRole("button", { name: "Metrics" });
    expect(metricsButton).toHaveClass(
      "bg-brand-light-blue/20",
      "text-brand-medium-blue",
    );
  });

  test("navigates when clicking menu items", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/settings");

    await user.click(screen.getByText("Organization"));
    expect(window.location.pathname).toBe("/settings/organization");
  });

  test("toggles collapsed state", async () => {
    const onToggleCollapse = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <ContextSidebar {...defaultProps} onToggleCollapse={onToggleCollapse} />,
      "/",
    );

    await user.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(onToggleCollapse).toHaveBeenCalledTimes(1);
  });
});
