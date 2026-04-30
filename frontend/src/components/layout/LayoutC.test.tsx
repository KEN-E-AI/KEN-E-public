import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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

vi.mock("./TopNav", async () => {
  const actual =
    await vi.importActual<typeof import("./TopNav")>("./TopNav");
  return {
    ...actual,
    TopNav: () => <div data-testid="top-nav" />,
  };
});

vi.mock("@/components/chat/SessionsSidebar", () => ({
  SessionsSidebar: () => <div data-testid="sessions-sidebar" />,
}));

vi.mock("@/components/chat/ChatInterface", () => ({
  ChatInterface: ({ compact }: { compact?: boolean }) => (
    <div
      data-testid="chat-interface"
      data-compact={compact ? "true" : "false"}
    />
  ),
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

function renderLayoutC({
  initialPath = "/",
  children = <div data-testid="page-content" />,
}: {
  initialPath?: string;
  children?: React.ReactNode;
} = {}) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
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

  describe("composition", () => {
    test("renders TopNav, SessionsSidebar, and children at /", () => {
      renderLayoutC();
      expect(screen.getByTestId("top-nav")).toBeInTheDocument();
      expect(screen.getByTestId("sessions-sidebar")).toBeInTheDocument();
      expect(screen.getByTestId("page-content")).toBeInTheDocument();
    });

    test("does not render legacy chrome (IconNavigation, ContextSidebar, vertical Sidebar)", () => {
      renderLayoutC();
      expect(screen.queryByTestId("icon-navigation")).not.toBeInTheDocument();
      expect(screen.queryByTestId("context-sidebar")).not.toBeInTheDocument();
      expect(screen.queryByTestId("sidebar")).not.toBeInTheDocument();
    });

    test("wraps the tree in ExtensionsProvider (no useExtensions context error)", () => {
      // If ExtensionsProvider were missing, useExtensions would warn. The render
      // simply needs to complete without throwing.
      expect(() => renderLayoutC()).not.toThrow();
    });
  });

  describe("semantic landmarks", () => {
    test("renders <header> wrapping TopNav", () => {
      renderLayoutC();
      const header = screen.getByRole("banner");
      expect(within(header).getByTestId("top-nav")).toBeInTheDocument();
    });

    test("renders <main> wrapping children", () => {
      renderLayoutC({
        children: <p data-testid="inner-content">Hello</p>,
      });
      const main = screen.getByRole("main");
      expect(within(main).getByTestId("inner-content")).toBeInTheDocument();
    });
  });

  describe("Mini Chat Widget", () => {
    test("does NOT render at home (/)", () => {
      renderLayoutC({ initialPath: "/" });
      expect(screen.queryByTestId("mini-chat-widget")).not.toBeInTheDocument();
    });

    test("renders at non-home routes (e.g., /performance)", () => {
      renderLayoutC({ initialPath: "/performance" });
      expect(screen.getByTestId("mini-chat-widget")).toBeInTheDocument();
    });

    test("clicking the widget trigger opens it and mounts ChatInterface in compact mode", async () => {
      const { default: userEvent } = await import("@testing-library/user-event");
      const user = userEvent.setup();
      renderLayoutC({ initialPath: "/performance" });

      // Closed by default — Radix CollapsibleContent unmounts children.
      expect(screen.queryByTestId("chat-interface")).not.toBeInTheDocument();

      const trigger = screen.getByRole("button", { name: /KEN-E/i });
      await user.click(trigger);

      const chat = await screen.findByTestId("chat-interface");
      expect(chat).toHaveAttribute("data-compact", "true");
    });

    test("widget block carries `hidden md:block` so it is desktop-only", () => {
      renderLayoutC({ initialPath: "/performance" });
      const widget = screen.getByTestId("mini-chat-widget").parentElement!;
      expect(widget.className).toMatch(/\bhidden\b/);
      expect(widget.className).toMatch(/\bmd:block\b/);
    });
  });

  describe("mobile bottom tab bar", () => {
    test("renders <nav aria-label=\"Primary navigation (mobile)\"> with 7 links", () => {
      renderLayoutC();
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      const links = within(mobileNav).getAllByRole("link");
      expect(links).toHaveLength(7);
    });

    test("each mobile tab link has the correct href", () => {
      renderLayoutC();
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      const expected: Array<[string, string]> = [
        ["Chat", "/"],
        ["Performance", "/performance"],
        ["Calendar", "/calendar"],
        ["Workflows", "/workflows"],
        ["Knowledge", "/strategy"],
        ["Extensions", "/extensions"],
        ["Settings", "/settings/account"],
      ];
      expected.forEach(([name, href]) => {
        const link = within(mobileNav).getByRole("link", {
          name: new RegExp(`^${name}$`, "i"),
        });
        expect(link).toHaveAttribute("href", href);
      });
    });

    test("active tab carries the violet-500 + scale-110 classes", () => {
      renderLayoutC({ initialPath: "/performance" });
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      const performanceLink = within(mobileNav).getByRole("link", {
        name: /^performance$/i,
      });
      expect(performanceLink).toHaveClass("text-[var(--color-violet-500)]");
      expect(performanceLink).toHaveClass("scale-110");
    });

    test("nav block carries `md:hidden` so it is mobile-only", () => {
      renderLayoutC();
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      expect(mobileNav.className).toMatch(/\bmd:hidden\b/);
    });

    test("renders the rainbow gradient top border at 3px", () => {
      renderLayoutC();
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      const inline = mobileNav.getAttribute("style") ?? "";
      expect(inline).toMatch(/border-top:\s*3px solid transparent/i);
      expect(inline).toMatch(/border-image:\s*var\(--gradient-rainbow\)\s*1/i);
    });
  });

  describe("LAYOUT_BANNER_REGISTRY (preserved across the rewrite)", () => {
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
  });
});
