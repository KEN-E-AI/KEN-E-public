import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { ContextSidebar } from "./ContextSidebar";
import { AuthProvider } from "@/contexts/AuthContext";

const renderWithProviders = (ui: React.ReactElement, initialRoute = "/") => {
  window.history.pushState({}, "", initialRoute);
  return render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>,
  );
};

describe("ContextSidebar", () => {
  const defaultProps = {
    isCollapsed: false,
    onToggleCollapse: vi.fn(),
  };

  test("shows notifications on home page", () => {
    renderWithProviders(<ContextSidebar {...defaultProps} />, "/");
    expect(screen.getByText("Notifications")).toBeInTheDocument();
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

    await user.click(screen.getByText("Account"));
    expect(window.location.pathname).toBe("/settings/account");
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
