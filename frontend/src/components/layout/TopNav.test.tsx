import { describe, test, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ExtensionsProvider } from "@/contexts/ExtensionsContext";
import { TopNav } from "./TopNav";

vi.mock("./AccountSwitcher", () => ({
  AccountSwitcher: ({ compact }: { compact?: boolean }) => (
    <div
      data-testid="account-switcher"
      data-compact={compact ? "true" : "false"}
    />
  ),
}));
vi.mock("./NotificationBell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));
vi.mock("./ProfileMenu", () => ({
  ProfileMenu: () => <div data-testid="profile-menu" />,
}));

const EXPECTED_NAV = [
  { name: "Chat", href: "/" },
  { name: "Performance", href: "/performance" },
  { name: "Calendar", href: "/calendar" },
  { name: "Workflows", href: "/workflows" },
  { name: "Knowledge", href: "/strategy" },
  { name: "Extensions", href: "/extensions" },
  { name: "Settings", href: "/settings/account" },
] as const;

function renderTopNav(initialPath: string = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ExtensionsProvider>
        <TopNav />
      </ExtensionsProvider>
    </MemoryRouter>,
  );
}

describe("TopNav", () => {
  describe("desktop header", () => {
    test("renders a Primary navigation landmark with all 7 nav links", () => {
      renderTopNav();

      const nav = screen.getByRole("navigation", {
        name: "Primary navigation",
      });
      const links = within(nav).getAllByRole("link");
      expect(links).toHaveLength(7);
    });

    test("each nav link has the correct href", () => {
      renderTopNav();
      const nav = screen.getByRole("navigation", {
        name: "Primary navigation",
      });

      EXPECTED_NAV.forEach(({ name, href }) => {
        const link = within(nav).getByRole("link", {
          name: new RegExp(`^${name}$`, "i"),
        });
        expect(link).toHaveAttribute("href", href);
      });
    });

    test("active route's nav link has the violet-pill class", () => {
      renderTopNav("/performance");
      const nav = screen.getByRole("navigation", {
        name: "Primary navigation",
      });
      const performanceLink = within(nav).getByRole("link", {
        name: /^performance$/i,
      });
      expect(performanceLink).toHaveClass("bg-[var(--color-violet-500)]");
    });

    test("inactive nav link uses the secondary-text class (WCAG AA contrast)", () => {
      // text-secondary (#475569 light / #cbd5e1 dark) gives ≥7.5:1 against
      // the page background. The pre-fix tertiary-text (#94a3b8 / #64748b)
      // failed AA at 2.47:1 / 3.75:1 — see plan §10.3.
      renderTopNav("/performance");
      const nav = screen.getByRole("navigation", {
        name: "Primary navigation",
      });
      const chatLink = within(nav).getByRole("link", { name: /^chat$/i });
      expect(chatLink).toHaveClass("text-[var(--color-text-secondary)]");
      expect(chatLink).not.toHaveClass("text-[var(--color-text-tertiary)]");
      expect(chatLink).not.toHaveClass("bg-[var(--color-violet-500)]");
    });

    test("Chat is the active link at /", () => {
      renderTopNav("/");
      const nav = screen.getByRole("navigation", {
        name: "Primary navigation",
      });
      const chatLink = within(nav).getByRole("link", { name: /^chat$/i });
      expect(chatLink).toHaveClass("bg-[var(--color-violet-500)]");
    });

    test("Extensions slot renders the ExtensionsNavItem (hover panel hidden until hover)", () => {
      renderTopNav();
      const nav = screen.getByRole("navigation", {
        name: "Primary navigation",
      });
      const extensionsLink = within(nav).getByRole("link", {
        name: /^extensions$/i,
      });
      expect(extensionsLink).toHaveAttribute("href", "/extensions");
      // The hover panel (role="menu") should not be rendered until hover.
      expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    });

    test("renders the rainbow gradient bottom border at 4px", () => {
      renderTopNav();
      const desktop = screen.getByTestId("topnav-desktop");
      const inline = desktop.getAttribute("style") ?? "";
      expect(inline).toMatch(/border-bottom:\s*4px solid transparent/i);
      expect(inline).toMatch(/border-image:\s*var\(--gradient-rainbow\)\s*1/i);
    });

    test("does not render a standalone ThemeToggle (theme lives in ProfileMenu)", () => {
      renderTopNav();
      expect(
        screen.queryByRole("button", { name: /toggle theme/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId("theme-toggle")).not.toBeInTheDocument();
    });

    test("desktop block is hidden at mobile viewport via Tailwind responsive classes", () => {
      renderTopNav();
      // jsdom does not evaluate media queries; we assert the structural class
      // contract (`hidden md:block`) that drives visibility at runtime.
      const desktop = screen.getByTestId("topnav-desktop");
      expect(desktop).toHaveClass("hidden");
      expect(desktop).toHaveClass("md:block");
    });
  });

  describe("mobile compact header", () => {
    test("renders hamburger trigger + Logo + NotificationBell + ProfileMenu (AccountSwitcher moved to drawer)", () => {
      renderTopNav();
      const mobile = screen.getByTestId("topnav-mobile");

      // Hamburger trigger opens the nav drawer
      expect(
        within(mobile).getByRole("button", { name: "Open navigation menu" }),
      ).toBeInTheDocument();
      // NotificationBell and ProfileMenu remain in the header
      expect(
        within(mobile).getByTestId("notification-bell"),
      ).toBeInTheDocument();
      expect(within(mobile).getByTestId("profile-menu")).toBeInTheDocument();
      // AccountSwitcher is no longer inline in the mobile header (moved into the drawer)
      expect(
        within(mobile).queryByTestId("account-switcher"),
      ).not.toBeInTheDocument();
    });

    test("renders the rainbow gradient bottom border at 3px (vs 4px on desktop)", () => {
      renderTopNav();
      const mobile = screen.getByTestId("topnav-mobile");
      const inline = mobile.getAttribute("style") ?? "";
      expect(inline).toMatch(/border-bottom:\s*3px solid transparent/i);
      expect(inline).toMatch(/border-image:\s*var\(--gradient-rainbow\)\s*1/i);
    });

    test("mobile block is hidden at desktop viewport via Tailwind responsive class", () => {
      renderTopNav();
      const mobile = screen.getByTestId("topnav-mobile");
      expect(mobile).toHaveClass("md:hidden");
    });

    test("does not render the horizontal Primary navigation inside the mobile block", () => {
      renderTopNav();
      const mobile = screen.getByTestId("topnav-mobile");
      expect(
        within(mobile).queryByRole("navigation", {
          name: "Primary navigation",
        }),
      ).not.toBeInTheDocument();
    });

    test("renders a hamburger button (Open navigation menu) at mobile breakpoint", () => {
      renderTopNav();
      const trigger = screen.getByRole("button", {
        name: "Open navigation menu",
      });
      expect(trigger).toBeInTheDocument();
      expect(trigger).toHaveAttribute("data-testid", "mobile-nav-trigger");
    });
  });

  describe("mobile nav drawer", () => {
    test("hamburger click opens the drawer containing AccountSwitcher", async () => {
      const user = userEvent.setup();
      renderTopNav();

      const trigger = screen.getByRole("button", {
        name: "Open navigation menu",
      });
      await user.click(trigger);

      const drawer = screen.getByTestId("mobile-nav-drawer");
      expect(drawer).toBeInTheDocument();
      expect(
        within(drawer).getByTestId("account-switcher"),
      ).toBeInTheDocument();
    });

    test("drawer contains all 7 navigation links with correct hrefs", async () => {
      const user = userEvent.setup();
      renderTopNav();

      await user.click(
        screen.getByRole("button", { name: "Open navigation menu" }),
      );

      const drawer = screen.getByTestId("mobile-nav-drawer");
      const nav = within(drawer).getByRole("navigation", {
        name: "Primary navigation (mobile drawer)",
      });
      const links = within(nav).getAllByRole("link");
      expect(links).toHaveLength(7);

      EXPECTED_NAV.forEach(({ name, href }) => {
        const link = within(nav).getByRole("link", {
          name: new RegExp(`^${name}$`, "i"),
        });
        expect(link).toHaveAttribute("href", href);
      });
    });

    test("pressing Escape closes the drawer", async () => {
      const user = userEvent.setup();
      renderTopNav();

      await user.click(
        screen.getByRole("button", { name: "Open navigation menu" }),
      );
      expect(screen.getByTestId("mobile-nav-drawer")).toBeInTheDocument();

      await user.keyboard("{Escape}");
      expect(screen.queryByTestId("mobile-nav-drawer")).not.toBeInTheDocument();
    });
  });
});
