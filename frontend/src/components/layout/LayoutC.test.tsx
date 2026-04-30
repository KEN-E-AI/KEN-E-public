import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { AuthContextType } from "@/contexts/AuthContext";
import { AuthContext } from "@/contexts/AuthContext";
import type { UserId } from "@/lib/branded-types";
import {
  LayoutC,
  LAYOUT_BANNER_REGISTRY,
  registerLayoutBanner,
  unregisterLayoutBanner,
  resetLayoutBannersForTesting,
} from "./LayoutC";
import type { LayoutBannerId } from "./LayoutC";

vi.mock("./Sidebar", () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));
vi.mock("./TopNav", () => ({
  TopNav: () => <div data-testid="top-nav" />,
}));

const mockAuthContext = (): Partial<AuthContextType> => ({
  user: {
    id: "test-user" as UserId,
    email: "user@example.com",
    firstName: "Test",
    lastName: "User",
  },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  isSuperAdmin: false,
});

function renderLayoutC(
  children: React.ReactNode = <div data-testid="page-content" />,
) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={mockAuthContext() as AuthContextType}>
        <LayoutC>{children}</LayoutC>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("LayoutC", () => {
  beforeEach(() => {
    resetLayoutBannersForTesting();
  });

  test("renders Sidebar + TopNav + children", () => {
    renderLayoutC();
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("top-nav")).toBeInTheDocument();
    expect(screen.getByTestId("page-content")).toBeInTheDocument();
  });

  test("renders semantic landmarks", () => {
    renderLayoutC();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  test("children render inside main", () => {
    renderLayoutC(<p data-testid="inner-content">Hello</p>);
    const main = screen.getByRole("main");
    expect(main).toContainElement(screen.getByTestId("inner-content"));
  });

  test("banner slot renders nothing when registry empty", () => {
    renderLayoutC();
    expect(
      screen.queryByRole("region", { name: /system banners/i }),
    ).not.toBeInTheDocument();
  });

  test("banner slot renders one registered banner", () => {
    registerLayoutBanner({
      id: "test-banner" as LayoutBannerId,
      order: 10,
      component: () => <div data-testid="my-banner">Banner Content</div>,
    });
    renderLayoutC();
    const region = screen.getByRole("region", { name: /system banners/i });
    expect(region).toBeInTheDocument();
    expect(screen.getByTestId("my-banner")).toBeInTheDocument();
  });

  test("banner rows render in order ascending", () => {
    registerLayoutBanner({
      id: "banner-b" as LayoutBannerId,
      order: 20,
      component: () => <div data-testid="banner-20">Banner 20</div>,
    });
    registerLayoutBanner({
      id: "banner-a" as LayoutBannerId,
      order: 10,
      component: () => <div data-testid="banner-10">Banner 10</div>,
    });
    renderLayoutC();
    const banners = screen.getAllByTestId(/^banner-/);
    expect(banners[0]).toHaveAttribute("data-testid", "banner-10");
    expect(banners[1]).toHaveAttribute("data-testid", "banner-20");
  });

  test("banner rows with isVisible false are skipped", () => {
    registerLayoutBanner({
      id: "visible-banner" as LayoutBannerId,
      order: 10,
      component: () => <div data-testid="visible-banner">Visible</div>,
    });
    registerLayoutBanner({
      id: "hidden-banner" as LayoutBannerId,
      order: 20,
      isVisible: false,
      component: () => <div data-testid="hidden-banner">Hidden</div>,
    });
    renderLayoutC();
    expect(screen.getByTestId("visible-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("hidden-banner")).not.toBeInTheDocument();
  });

  test("duplicate id registration is rejected", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerLayoutBanner({
      id: "dup-banner" as LayoutBannerId,
      order: 10,
      component: () => <div />,
    });
    registerLayoutBanner({
      id: "dup-banner" as LayoutBannerId,
      order: 20,
      component: () => <div />,
    });
    expect(LAYOUT_BANNER_REGISTRY).toHaveLength(1);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("dup-banner"));
    warnSpy.mockRestore();
  });

  test("resetLayoutBannersForTesting clears the registry", () => {
    registerLayoutBanner({
      id: "to-clear" as LayoutBannerId,
      order: 10,
      component: () => <div />,
    });
    expect(LAYOUT_BANNER_REGISTRY).toHaveLength(1);
    resetLayoutBannersForTesting();
    expect(LAYOUT_BANNER_REGISTRY).toHaveLength(0);
  });

  test("unregisterLayoutBanner removes a banner", () => {
    const id = "removable" as LayoutBannerId;
    registerLayoutBanner({
      id,
      order: 10,
      component: () => <div data-testid="removable-banner">Removable</div>,
    });
    expect(LAYOUT_BANNER_REGISTRY).toHaveLength(1);
    unregisterLayoutBanner(id);
    expect(LAYOUT_BANNER_REGISTRY).toHaveLength(0);
  });

  test("legacy chrome (IconNavigation, ContextSidebar) is absent from LayoutC render tree", () => {
    // Regression guard: LayoutC must not introduce legacy chrome. The mocked Sidebar and
    // TopNav do not render IconNavigation or ContextSidebar — if either data-testid ever
    // appears in LayoutC's output it means legacy components leaked back in.
    renderLayoutC(<div data-testid="page-content" />);
    expect(screen.queryByTestId("icon-navigation")).not.toBeInTheDocument();
    expect(screen.queryByTestId("context-sidebar")).not.toBeInTheDocument();
  });
});
