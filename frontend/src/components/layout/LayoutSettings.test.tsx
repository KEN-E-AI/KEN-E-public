import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LayoutSettings } from "./LayoutSettings";
import type { SettingsNavRow, SettingsNavRowId } from "./LayoutSettings";

vi.mock("./ProfileMenu", () => ({
  ProfileMenu: ({ compact }: { compact?: boolean }) => (
    <div data-testid="profile-menu" data-compact={compact}>
      ProfileMenu
    </div>
  ),
}));

const seedRows: SettingsNavRow[] = [
  {
    id: "organization" as SettingsNavRowId,
    label: "Organization",
    path: "/settings/organization",
    order: 10,
  },
  {
    id: "account" as SettingsNavRowId,
    label: "Account",
    path: "/settings/account",
    order: 20,
  },
  {
    id: "user" as SettingsNavRowId,
    label: "User",
    path: "/settings/user",
    order: 30,
  },
];

function renderLayoutSettings({
  subNavItems = seedRows,
  initialPath = "/settings/organization",
  children,
}: {
  subNavItems?: SettingsNavRow[];
  initialPath?: string;
  children?: React.ReactNode;
} = {}) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <LayoutSettings subNavItems={subNavItems}>
        {children ?? <div>Page content</div>}
      </LayoutSettings>
    </MemoryRouter>,
  );
}

describe("LayoutSettings", () => {
  describe("Semantic landmarks", () => {
    test("renders header landmark", () => {
      renderLayoutSettings();
      expect(screen.getByRole("banner")).toBeInTheDocument();
    });

    test("renders navigation landmark with correct label", () => {
      renderLayoutSettings();
      expect(
        screen.getByRole("navigation", { name: "Settings sections" }),
      ).toBeInTheDocument();
    });

    test("renders complementary (aside) landmark", () => {
      renderLayoutSettings();
      expect(screen.getByRole("complementary")).toBeInTheDocument();
    });

    test("renders main landmark", () => {
      renderLayoutSettings();
      expect(screen.getByRole("main")).toBeInTheDocument();
    });
  });

  describe("Header content", () => {
    test("renders KEN-E logo", () => {
      renderLayoutSettings();
      expect(screen.getByRole("img", { name: /KEN-E/i })).toBeInTheDocument();
    });

    test("renders Back to App links (mobile icon + desktop text)", () => {
      renderLayoutSettings();
      const backLinks = screen.getAllByRole("link", { name: /back to app/i });
      // Mobile (aria-label) + desktop (text span) — both rendered, CSS hides each at appropriate breakpoint
      expect(backLinks).toHaveLength(2);
    });

    test("Back to App links point to /", () => {
      renderLayoutSettings();
      const backLinks = screen.getAllByRole("link", { name: /back to app/i });
      backLinks.forEach((link) => expect(link).toHaveAttribute("href", "/"));
    });

    test("Back to App links use primary text color for WCAG AA contrast", () => {
      renderLayoutSettings();
      const backLinks = screen.getAllByRole("link", { name: /back to app/i });
      // ghost variant defaults to --color-text-tertiary (#94a3b8, 2.47:1 against bg)
      // both buttons must explicitly override to --color-text-primary (#1e293b, ~12:1)
      backLinks.forEach((link) => {
        expect(link).toHaveClass("text-[var(--color-text-primary)]");
      });
    });

    test("renders ProfileMenu with compact prop", () => {
      renderLayoutSettings();
      const profileMenu = screen.getByTestId("profile-menu");
      expect(profileMenu).toBeInTheDocument();
      expect(profileMenu).toHaveAttribute("data-compact", "true");
    });

    test("renders Organization Settings breadcrumb at /settings/organization", () => {
      renderLayoutSettings({ initialPath: "/settings/organization" });
      expect(
        screen.getByRole("heading", { name: "Organization Settings" }),
      ).toBeInTheDocument();
    });

    test("renders User Settings breadcrumb at /settings/user", () => {
      renderLayoutSettings({ initialPath: "/settings/user" });
      expect(
        screen.getByRole("heading", { name: "User Settings" }),
      ).toBeInTheDocument();
    });

    test("renders Account Settings breadcrumb at /settings/account/abc", () => {
      renderLayoutSettings({ initialPath: "/settings/account/abc" });
      expect(
        screen.getByRole("heading", { name: "Account Settings" }),
      ).toBeInTheDocument();
    });

    test("renders Settings breadcrumb as fallback for unknown routes", () => {
      renderLayoutSettings({ initialPath: "/settings/unknown" });
      expect(
        screen.getByRole("heading", { name: "Settings" }),
      ).toBeInTheDocument();
    });

    test("does not match breadcrumb on substring — /settings/user-prefs is not User Settings", () => {
      renderLayoutSettings({ initialPath: "/settings/user-prefs" });
      expect(
        screen.getByRole("heading", { name: "Settings" }),
      ).toBeInTheDocument();
    });
  });

  describe("Sub-nav rows", () => {
    test("renders all visible rows", () => {
      renderLayoutSettings();
      expect(
        screen.getByRole("link", { name: "Organization" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Account" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "User" })).toBeInTheDocument();
    });

    test("excludes rows with isVisible: false", () => {
      const rows: SettingsNavRow[] = [
        ...seedRows,
        {
          id: "hidden" as SettingsNavRowId,
          label: "Hidden Tab",
          path: "/settings/hidden",
          order: 40,
          isVisible: false,
        },
      ];
      renderLayoutSettings({ subNavItems: rows });
      expect(
        screen.queryByRole("link", { name: "Hidden Tab" }),
      ).not.toBeInTheDocument();
    });

    test("includes rows with isVisible: true", () => {
      const rows: SettingsNavRow[] = [
        {
          id: "visible" as SettingsNavRowId,
          label: "Visible Tab",
          path: "/settings/visible",
          order: 10,
          isVisible: true,
        },
      ];
      renderLayoutSettings({ subNavItems: rows });
      expect(
        screen.getByRole("link", { name: "Visible Tab" }),
      ).toBeInTheDocument();
    });

    test("renders rows sorted by order ascending", () => {
      const outOfOrder: SettingsNavRow[] = [
        {
          id: "user" as SettingsNavRowId,
          label: "User",
          path: "/settings/user",
          order: 30,
        },
        {
          id: "organization" as SettingsNavRowId,
          label: "Organization",
          path: "/settings/organization",
          order: 10,
        },
        {
          id: "account" as SettingsNavRowId,
          label: "Account",
          path: "/settings/account",
          order: 20,
        },
      ];
      renderLayoutSettings({ subNavItems: outOfOrder });
      const links = screen.getAllByRole("link", {
        name: /^(Organization|Account|User)$/i,
      });
      expect(links[0]).toHaveTextContent("Organization");
      expect(links[1]).toHaveTextContent("Account");
      expect(links[2]).toHaveTextContent("User");
    });

    test("renders empty nav when subNavItems is empty", () => {
      renderLayoutSettings({ subNavItems: [] });
      expect(
        screen.getByRole("navigation", { name: "Settings sections" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: /organization|account|user/i }),
      ).not.toBeInTheDocument();
    });

    test("excludes rows with unsafe (non-relative) paths", () => {
      const rows: SettingsNavRow[] = [
        {
          id: "safe" as SettingsNavRowId,
          label: "Safe Link",
          path: "/settings/safe",
          order: 10,
        },
        {
          id: "unsafe" as SettingsNavRowId,
          label: "Unsafe Link",
          path: "javascript:alert(1)" as unknown as string,
          order: 20,
        },
      ];
      renderLayoutSettings({ subNavItems: rows });
      expect(
        screen.getByRole("link", { name: "Safe Link" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "Unsafe Link" }),
      ).not.toBeInTheDocument();
    });

    test("excludes rows with /__dev__ paths", () => {
      const rows: SettingsNavRow[] = [
        {
          id: "safe" as SettingsNavRowId,
          label: "Safe Link",
          path: "/settings/safe",
          order: 10,
        },
        {
          id: "dev-route" as SettingsNavRowId,
          label: "Dev Route",
          path: "/__dev__/something",
          order: 20,
        },
      ];
      renderLayoutSettings({ subNavItems: rows });
      expect(
        screen.getByRole("link", { name: "Safe Link" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "Dev Route" }),
      ).not.toBeInTheDocument();
    });

    test("excludes rows with bare / path", () => {
      const rows: SettingsNavRow[] = [
        {
          id: "safe" as SettingsNavRowId,
          label: "Safe Link",
          path: "/settings/safe",
          order: 10,
        },
        {
          id: "home" as SettingsNavRowId,
          label: "Home Route",
          path: "/",
          order: 20,
        },
      ];
      renderLayoutSettings({ subNavItems: rows });
      expect(
        screen.getByRole("link", { name: "Safe Link" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "Home Route" }),
      ).not.toBeInTheDocument();
    });

    test("excludes rows with dot-segment traversal paths", () => {
      const rows: SettingsNavRow[] = [
        {
          id: "safe" as SettingsNavRowId,
          label: "Safe Link",
          path: "/settings/safe",
          order: 10,
        },
        {
          id: "traversal" as SettingsNavRowId,
          label: "Traversal Link",
          path: "/settings/../admin",
          order: 20,
        },
      ];
      renderLayoutSettings({ subNavItems: rows });
      expect(
        screen.getByRole("link", { name: "Safe Link" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "Traversal Link" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("Active row highlighting", () => {
    test("marks the exact matching row with aria-current=page", () => {
      renderLayoutSettings({ initialPath: "/settings/organization" });
      const orgLink = screen.getByRole("link", { name: "Organization" });
      expect(orgLink).toHaveAttribute("aria-current", "page");
    });

    test("does not mark non-matching rows with aria-current", () => {
      renderLayoutSettings({ initialPath: "/settings/organization" });
      const userLink = screen.getByRole("link", { name: "User" });
      expect(userLink).not.toHaveAttribute("aria-current");
    });

    test("marks a row with aria-current when pathname starts with row.path + /", () => {
      renderLayoutSettings({ initialPath: "/settings/account/abc-123" });
      const accountLink = screen.getByRole("link", { name: "Account" });
      expect(accountLink).toHaveAttribute("aria-current", "page");
    });

    test("applies active class to the active row", () => {
      renderLayoutSettings({ initialPath: "/settings/organization" });
      const orgLink = screen.getByRole("link", { name: "Organization" });
      expect(orgLink).toHaveClass("bg-[var(--color-violet-100)]");
    });

    test("does not apply active class to inactive rows", () => {
      renderLayoutSettings({ initialPath: "/settings/organization" });
      const accountLink = screen.getByRole("link", { name: "Account" });
      expect(accountLink).not.toHaveClass("bg-[var(--color-violet-100)]");
    });
  });

  describe("Content area", () => {
    test("renders children inside main", () => {
      renderLayoutSettings({ children: <div>Settings Page Content</div> });
      expect(screen.getByText("Settings Page Content")).toBeInTheDocument();
    });

    test("children appear inside the main landmark", () => {
      renderLayoutSettings({ children: <p>Inner Content</p> });
      const main = screen.getByRole("main");
      expect(main).toContainElement(screen.getByText("Inner Content"));
    });
  });

  describe("Responsive class structure", () => {
    test("body uses flex-col and md:flex-row for responsive layout", () => {
      const { container } = renderLayoutSettings();
      const body = container.querySelector(".flex-col.md\\:flex-row");
      expect(body).toBeInTheDocument();
    });

    test("aside includes md:flex-col and md:w-48 utility classes", () => {
      const { container } = renderLayoutSettings();
      const aside = container.querySelector("aside");
      expect(aside).toHaveClass("md:flex-col");
      expect(aside).toHaveClass("md:w-48");
    });

    test("aside mobile horizontal-scroll and xl:w-56 rail-widening classes present", () => {
      const { container } = renderLayoutSettings();
      const aside = container.querySelector("aside");
      expect(aside).toHaveClass("flex-row");
      expect(aside).toHaveClass("overflow-x-auto");
      expect(aside).toHaveClass("xl:w-56");
    });

    test("mobile back-button carries md:hidden", () => {
      const { container } = renderLayoutSettings();
      const mobileBackBtn = container.querySelector(
        '[aria-label="Back to App"]',
      );
      expect(mobileBackBtn).toHaveClass("md:hidden");
    });

    test("desktop Back to App button carries hidden md:flex", () => {
      renderLayoutSettings();
      const allBackLinks = screen.getAllByRole("link", {
        name: /back to app/i,
      });
      const desktopLink = allBackLinks.find(
        (el) =>
          el.classList.contains("hidden") && el.classList.contains("md:flex"),
      );
      expect(desktopLink).toBeDefined();
      expect(desktopLink).toHaveClass("hidden");
      expect(desktopLink).toHaveClass("md:flex");
    });
  });
});
