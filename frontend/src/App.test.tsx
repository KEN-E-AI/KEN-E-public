import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LayoutSettings } from "@/components/layout/LayoutSettings";

// ProfileMenu is pulled in by LayoutSettings — stub it to avoid heavy auth dependencies
vi.mock("@/components/layout/ProfileMenu", () => ({
  ProfileMenu: () => <div data-testid="profile-menu">ProfileMenu</div>,
}));

function renderRoutes(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          {/* Canonical auth routes (UI-PRD-02) */}
          <Route
            path="/sign-in"
            element={<div data-testid="sign-in-page">Sign In</div>}
          />
          <Route
            path="/sign-up"
            element={<div data-testid="sign-up-page">Sign Up</div>}
          />

          {/* Top-level redirects — / and /settings */}
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route
            path="/settings"
            element={<Navigate to="/settings/organization" replace />}
          />

          {/* Backward-compat redirects */}
          <Route path="/login" element={<Navigate to="/sign-in" replace />} />
          <Route path="/signup" element={<Navigate to="/sign-up" replace />} />
          <Route
            path="/organization-settings"
            element={<Navigate to="/settings/organization" replace />}
          />
          <Route
            path="/account-settings"
            element={<Navigate to="/settings/organization" replace />}
          />
          <Route
            path="/user-settings"
            element={<Navigate to="/settings/user" replace />}
          />
          <Route
            path="/organization-selection"
            element={<Navigate to="/select-organization" replace />}
          />

          {/* Settings group — wrapped in LayoutSettings */}
          <Route element={<LayoutSettings />}>
            <Route
              path="/settings/organization"
              element={<div data-testid="settings-org-page">Org Settings</div>}
            />
            <Route
              path="/settings/account/:accountId"
              element={
                <div data-testid="settings-account-page">Account Settings</div>
              }
            />
            <Route
              path="/settings/user"
              element={
                <div data-testid="settings-user-page">User Settings</div>
              }
            />
          </Route>

          {/* Chat destination (target of the / redirect) */}
          <Route
            path="/chat"
            element={<div data-testid="chat-page">Chat</div>}
          />

          {/* Select-organization destination (target of the /organization-selection redirect) */}
          <Route
            path="/select-organization"
            element={
              <div data-testid="select-organization-page">
                Select Organization
              </div>
            }
          />

          {/* Admin routes remain under LayoutC (not LayoutSettings) */}
          <Route
            path="/settings/admin"
            element={<div data-testid="admin-page">Admin Settings</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App routing — top-level redirects", () => {
  test("/ redirects to /chat", () => {
    renderRoutes("/");
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });

  test("/settings redirects to /settings/organization", () => {
    renderRoutes("/settings");
    expect(screen.getByTestId("settings-org-page")).toBeInTheDocument();
  });
});

describe("App routing — backward-compat redirects", () => {
  test("/login redirects to /sign-in", () => {
    renderRoutes("/login");
    expect(screen.getByTestId("sign-in-page")).toBeInTheDocument();
  });

  test("/signup redirects to /sign-up", () => {
    renderRoutes("/signup");
    expect(screen.getByTestId("sign-up-page")).toBeInTheDocument();
  });

  test("/organization-settings redirects to /settings/organization", () => {
    renderRoutes("/organization-settings");
    expect(screen.getByTestId("settings-org-page")).toBeInTheDocument();
  });

  test("/account-settings redirects to /settings/organization", () => {
    renderRoutes("/account-settings");
    expect(screen.getByTestId("settings-org-page")).toBeInTheDocument();
  });

  test("/user-settings redirects to /settings/user", () => {
    renderRoutes("/user-settings");
    expect(screen.getByTestId("settings-user-page")).toBeInTheDocument();
  });

  test("/organization-selection redirects to /select-organization", () => {
    renderRoutes("/organization-selection");
    expect(screen.getByTestId("select-organization-page")).toBeInTheDocument();
  });
});

describe("App routing — canonical auth routes", () => {
  test("/sign-in mounts the authentication page", () => {
    renderRoutes("/sign-in");
    expect(screen.getByTestId("sign-in-page")).toBeInTheDocument();
  });

  test("/sign-up mounts the authentication page", () => {
    renderRoutes("/sign-up");
    expect(screen.getByTestId("sign-up-page")).toBeInTheDocument();
  });
});

describe("App routing — settings inside LayoutSettings", () => {
  test("/settings/organization renders inside LayoutSettings (sub-nav present)", () => {
    renderRoutes("/settings/organization");
    expect(
      screen.getByRole("navigation", { name: "Settings sections" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("settings-org-page")).toBeInTheDocument();
  });

  test("/settings/organization sub-nav has three rows: Organization, Account, User", () => {
    renderRoutes("/settings/organization");
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    expect(nav).toContainElement(
      screen.getByRole("link", { name: "Organization" }),
    );
    expect(nav).toContainElement(screen.getByRole("link", { name: "Account" }));
    expect(nav).toContainElement(screen.getByRole("link", { name: "User" }));
  });

  test("/settings/account/:accountId renders inside LayoutSettings", () => {
    renderRoutes("/settings/account/acct-123");
    expect(
      screen.getByRole("navigation", { name: "Settings sections" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("settings-account-page")).toBeInTheDocument();
  });

  test("/settings/user renders inside LayoutSettings", () => {
    renderRoutes("/settings/user");
    expect(
      screen.getByRole("navigation", { name: "Settings sections" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("settings-user-page")).toBeInTheDocument();
  });
});

describe("App routing — admin stays in LayoutC (not LayoutSettings)", () => {
  test("/settings/admin renders without LayoutSettings sub-nav", () => {
    renderRoutes("/settings/admin");
    // Admin page renders
    expect(screen.getByTestId("admin-page")).toBeInTheDocument();
    // LayoutSettings sub-nav is NOT present — admin stays inside LayoutC
    expect(
      screen.queryByRole("navigation", { name: "Settings sections" }),
    ).not.toBeInTheDocument();
  });
});
