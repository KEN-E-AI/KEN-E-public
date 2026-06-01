// NOTE: Class-contract lock only — runtime breakpoint behaviour is not verified by JSDOM.
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
import { LAST_SESSION_KEY, BOOT_UID_KEY } from "@/hooks/useActiveChatSession";

// TopNav is mocked here to keep this file focused on LayoutC composition.
// The TopNav <nav aria-label="Primary navigation"> landmark and its mobile
// drawer counterpart are exercised in TopNav.test.tsx — including landmark
// presence, drawer behaviour, and ARIA state. If you need to verify the
// real-TopNav-inside-LayoutC composition, mount LayoutC without this mock
// (be aware TopNav pulls in AccountSwitcher / NotificationBell / ProfileMenu
// — each requires its own context).
vi.mock("./TopNav", async () => {
  const actual = await vi.importActual<typeof import("./TopNav")>("./TopNav");
  return {
    ...actual,
    TopNav: () => <div data-testid="top-nav" />,
  };
});

// ChatInterface mock now exposes session-wiring props so the widget tests can
// assert that the right sessionId / callbacks are forwarded. The compact prop
// is still surfaced via data-compact for the existing compact-mode assertions.
vi.mock("@/components/chat/ChatInterface", () => ({
  ChatInterface: ({
    compact,
    sessionId,
    onCreateSession,
    onSessionStarted,
  }: {
    compact?: boolean;
    sessionId?: string;
    onCreateSession?: () => Promise<string | null>;
    onSessionStarted?: (id: string) => void;
  }) => (
    <div
      data-testid="chat-interface"
      data-compact={compact ? "true" : "false"}
      data-session-id={sessionId ?? ""}
      data-has-create-session={onCreateSession ? "true" : "false"}
      data-has-session-started={onSessionStarted ? "true" : "false"}
    />
  ),
}));

// Feature flags — default to flag OFF so existing tests are unaffected.
// Individual test cases in the "Cross-surface widget session wiring" suite
// override this to flag ON via vi.mocked(useFeatureFlag).mockReturnValue(...).
vi.mock("@/contexts/FeatureFlagsContext", () => ({
  useFeatureFlag: vi.fn().mockReturnValue({
    enabled: false,
    reason: "default" as const,
    isLoading: false,
  }),
}));

// chatApi — stub createChatConversation for the lazy-create path.
vi.mock("@/lib/chatApi", async (orig) => {
  const actual = await orig<typeof import("@/lib/chatApi")>();
  return { ...actual, createChatConversation: vi.fn() };
});

import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import { createChatConversation } from "@/lib/chatApi";

const mockUseFeatureFlag = vi.mocked(useFeatureFlag);
const mockCreateChatConversation = vi.mocked(createChatConversation);

// Deterministic in-memory storage (mirrors the Chat.spec.tsx helper).
function memoryStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => void store.clear(),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  };
}

function installMemoryStorage() {
  vi.stubGlobal("localStorage", memoryStorage());
  vi.stubGlobal("sessionStorage", memoryStorage());
}

const mockAuthContext = (
  overrides?: Partial<AuthContextType>,
): Partial<AuthContextType> => ({
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
  ...overrides,
});

function renderLayoutC({
  initialPath = "/",
  children = <div data-testid="page-content" />,
  authOverrides,
}: {
  initialPath?: string;
  children?: React.ReactNode;
  authOverrides?: Partial<AuthContextType>;
} = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthContext.Provider
          value={mockAuthContext(authOverrides) as AuthContextType}
        >
          <Routes>
            <Route element={<LayoutC />}>
              <Route path="*" element={children} />
            </Route>
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LayoutC", () => {
  beforeEach(() => {
    resetLayoutBannersForTesting();
  });

  describe("composition", () => {
    test("renders TopNav and children at /", () => {
      renderLayoutC();
      expect(screen.getByTestId("top-nav")).toBeInTheDocument();
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

    test("renders mobile <nav aria-label='Primary navigation (mobile)'>", () => {
      renderLayoutC();
      expect(
        screen.getByRole("navigation", {
          name: /Primary navigation \(mobile\)/i,
        }),
      ).toBeInTheDocument();
    });

    test("layout shell does not inject extra <h1> — page h1 count stays at one", () => {
      // The layout must not duplicate page-provided headings.
      // If a page supplies one <h1>, the rendered tree must have exactly one.
      renderLayoutC({ children: <h1>Page title</h1> });
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    });
  });

  describe("content-area max-width (isFullWidth allowlist)", () => {
    // Allowlisted routes opt out of `max-w-screen-2xl` to avoid horizontally
    // clipping wide tables on large monitors. Expressed as a route allowlist.
    const fullWidthRoutes: Array<[string, string]> = [
      ["/knowledge", "Knowledge index"],
      ["/knowledge/strategy", "Knowledge sub-route"],
      ["/knowledge/products", "Products under /knowledge"],
      ["/knowledge/insights", "Insights under /knowledge"],
      ["/knowledge/competitors", "Competitors under /knowledge"],
      ["/measurement-plan", "Marketing Strategies (Index)"],
      ["/strategy", "pre-existing"],
      ["/workflows/automations", "pre-existing"],
      ["/performance/dashboards/foo", "pre-existing"],
    ];

    fullWidthRoutes.forEach(([path, label]) => {
      test(`${path} renders full-bleed (${label})`, () => {
        renderLayoutC({ initialPath: path });
        const content = screen.getByTestId("layout-content");
        expect(content).toHaveAttribute("data-full-width", "true");
        expect(content.className).not.toMatch(/\bmax-w-screen-2xl\b/);
      });
    });

    const constrainedRoutes: Array<[string, string]> = [
      ["/", "Home"],
      ["/performance", "Performance (top-level, not /dashboards/)"],
      ["/reports", "Reports"],
      ["/settings/user", "User settings"],
      ["/campaigns", "Campaigns"],
    ];

    constrainedRoutes.forEach(([path, label]) => {
      test(`${path} keeps the max-w-screen-2xl constraint (${label})`, () => {
        renderLayoutC({ initialPath: path });
        const content = screen.getByTestId("layout-content");
        expect(content).toHaveAttribute("data-full-width", "false");
        expect(content.className).toMatch(/\bmax-w-screen-2xl\b/);
      });
    });
  });

  describe("Mini Chat Widget", () => {
    test("does NOT render at home (/chat)", () => {
      renderLayoutC({ initialPath: "/chat" });
      expect(screen.queryByTestId("mini-chat-widget")).not.toBeInTheDocument();
    });

    test("renders at non-home routes (e.g., /performance)", () => {
      renderLayoutC({ initialPath: "/performance" });
      expect(screen.getByTestId("mini-chat-widget")).toBeInTheDocument();
    });

    test("clicking the widget trigger opens it and mounts ChatInterface in compact mode", async () => {
      const { default: userEvent } = await import(
        "@testing-library/user-event"
      );
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
    test('renders <nav aria-label="Primary navigation (mobile)"> with 7 links', () => {
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
        ["Chat", "/chat"],
        ["Performance", "/performance"],
        ["Calendar", "/calendar"],
        ["Workflows", "/workflows/agents"],
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

    test("Workflows mobile tab is active on a /workflows/* sub-path other than the direct href", () => {
      renderLayoutC({ initialPath: "/workflows/automations" });
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      const workflowsLink = within(mobileNav).getByRole("link", {
        name: /^workflows$/i,
      });
      expect(workflowsLink).toHaveClass("text-[var(--color-violet-500)]");
      expect(workflowsLink).toHaveClass("scale-110");
    });

    test("inactive tab uses the secondary-text class (WCAG AA contrast)", () => {
      // Mirror of TopNav's desktop-pill assertion. text-tertiary would fail
      // WCAG AA contrast on this surface (and used to — axe flagged 9 light /
      // 7 dark violations across the two nav surfaces before the fix).
      renderLayoutC({ initialPath: "/performance" });
      const mobileNav = screen.getByRole("navigation", {
        name: /Primary navigation \(mobile\)/i,
      });
      const chatLink = within(mobileNav).getByRole("link", {
        name: /^chat$/i,
      });
      expect(chatLink).toHaveClass("text-[var(--color-text-secondary)]");
      expect(chatLink).not.toHaveClass("text-[var(--color-text-tertiary)]");
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
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("dup-banner"),
      );
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

// ─── Cross-surface widget session wiring (CH-61) ─────────────────────────────

describe("LayoutC — cross-surface widget session wiring (CH-61)", () => {
  const TEST_UID = "test-user";
  const ACCOUNT_ID = "acct_1";

  beforeEach(() => {
    resetLayoutBannersForTesting();
    installMemoryStorage();
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default" as const,
      isLoading: false,
    });
    mockCreateChatConversation.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default" as const,
      isLoading: false,
    });
  });

  // Opens the widget on a non-/chat route and returns the ChatInterface element.
  async function openWidget(opts?: {
    authOverrides?: Partial<AuthContextType>;
  }) {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderLayoutC({
      initialPath: "/performance",
      authOverrides: opts?.authOverrides ?? {
        selectedOrgAccount: {
          accountId: ACCOUNT_ID as any,
          orgId: "org_1" as any,
          role: "member" as any,
        } as any,
      },
    });
    const trigger = screen.getByRole("button", { name: /KEN-E/i });
    await user.click(trigger);
    return await screen.findByTestId("chat-interface");
  }

  test("(a) flag-on, no stored session → widget mounts with sessionId='' and onCreateSession wired", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    // No LAST_SESSION_KEY or BOOT_UID_KEY set — getActiveSessionId returns null.
    const chatEl = await openWidget();
    expect(chatEl).toHaveAttribute("data-session-id", "");
    expect(chatEl).toHaveAttribute("data-has-create-session", "true");
    expect(chatEl).toHaveAttribute("data-has-session-started", "true");
  });

  test("(b) flag-on, stored session + matching boot uid → widget mounts with that session id", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    localStorage.setItem(
      LAST_SESSION_KEY,
      JSON.stringify({ id: "active_session_42", accountId: ACCOUNT_ID }),
    );
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);
    const chatEl = await openWidget();
    expect(chatEl).toHaveAttribute("data-session-id", "active_session_42");
    expect(chatEl).toHaveAttribute("data-has-create-session", "true");
    expect(chatEl).toHaveAttribute("data-has-session-started", "true");
  });

  test("(b2) flag-on, marker written AFTER mount → opening widget re-reads storage and resolves session", async () => {
    // This is the exact regression the PO caught: LayoutC stays mounted across SPA
    // navigation; the user chats on /chat (setActiveSessionId fires), then navigates
    // to /performance and opens the widget. The stale useMemo must NOT return undefined.
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();

    renderLayoutC({
      initialPath: "/performance",
      authOverrides: {
        selectedOrgAccount: {
          accountId: ACCOUNT_ID as any,
          orgId: "org_1" as any,
          role: "member" as any,
        } as any,
      },
    });

    // Storage is empty at this point — memo computed undefined on initial render.
    expect(screen.queryByTestId("chat-interface")).not.toBeInTheDocument();

    // Simulate /chat page writing the resume marker AFTER LayoutC mounted
    // (the SPA-navigation scenario the PO identified).
    localStorage.setItem(
      LAST_SESSION_KEY,
      JSON.stringify({ id: "late_session_99", accountId: ACCOUNT_ID }),
    );
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);

    // Open the widget — miniChatOpen flips to true, triggering the memo re-read.
    const trigger = screen.getByRole("button", { name: /KEN-E/i });
    await user.click(trigger);

    const chatEl = await screen.findByTestId("chat-interface");
    // The widget must now carry the session that was written after mount.
    expect(chatEl).toHaveAttribute("data-session-id", "late_session_99");
  });

  test("(c) flag-off → widget mounts with no session props regardless of stored keys", async () => {
    // Flag stays OFF (default in beforeEach).
    localStorage.setItem(LAST_SESSION_KEY, "should_not_be_used");
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);
    const chatEl = await openWidget();
    // sessionId should be empty (undefined coerced to "") and no callbacks wired.
    expect(chatEl).toHaveAttribute("data-session-id", "");
    expect(chatEl).toHaveAttribute("data-has-create-session", "false");
    expect(chatEl).toHaveAttribute("data-has-session-started", "false");
  });

  test("(d) {!isHome} guard still hides the widget on /chat", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    renderLayoutC({ initialPath: "/chat" });
    expect(screen.queryByTestId("mini-chat-widget")).not.toBeInTheDocument();
  });

  test("flag-on, boot uid mismatch (different user) → widget mounts with no session id", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    localStorage.setItem(LAST_SESSION_KEY, "other_users_session");
    sessionStorage.setItem(BOOT_UID_KEY, "different-user-id");
    const chatEl = await openWidget();
    expect(chatEl).toHaveAttribute("data-session-id", "");
  });

  test("flag-on, account switch: widget does NOT resume a different account's session", async () => {
    // Regression guard: acct_2 must not be able to read acct_1's stored session.
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    // Store a session for acct_1 using the new account-scoped JSON format.
    localStorage.setItem(
      LAST_SESSION_KEY,
      JSON.stringify({ id: "sess_for_acct1", accountId: "acct_1" }),
    );
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);
    // Render widget for acct_2 — must NOT see acct_1's session.
    const chatEl = await openWidget({
      authOverrides: {
        selectedOrgAccount: {
          accountId: "acct_2" as any,
          orgId: "org_1" as any,
          role: "member" as any,
        } as any,
      },
    });
    expect(chatEl).toHaveAttribute("data-session-id", "");
  });

  test("(TC-1c regression) flag-on, session written after mount → widget open picks it up", async () => {
    // Regression for TC-1c: LayoutC never remounts on SPA navigation, so the
    // useMemo deps [chatV2Enabled, user?.id] alone would never re-read storage
    // when /chat writes the session marker after mount. miniChatOpen must be in
    // the memo deps so opening the widget triggers a fresh getActiveSessionId call.
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    // No session in storage before render.
    const { default: userEvent } = await import("@testing-library/user-event");
    const ue = userEvent.setup();
    renderLayoutC({
      initialPath: "/performance",
      authOverrides: {
        selectedOrgAccount: {
          accountId: ACCOUNT_ID as any,
          orgId: "org_1" as any,
          role: "member" as any,
        } as any,
      },
    });

    // Write session marker after mount — simulates /chat page creating a session
    // while the user is on a different page with LayoutC already mounted.
    localStorage.setItem(LAST_SESSION_KEY, "post_mount_session");
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);

    // Open the widget — this is the trigger that must cause widgetSessionId to
    // re-read storage (via miniChatOpen entering the memo deps).
    const trigger = screen.getByRole("button", { name: /KEN-E/i });
    await ue.click(trigger);

    const chatEl = await screen.findByTestId("chat-interface");
    expect(chatEl).toHaveAttribute("data-session-id", "post_mount_session");
    expect(chatEl).toHaveAttribute("data-has-create-session", "true");
    expect(chatEl).toHaveAttribute("data-has-session-started", "true");
  });

  test("widget remains in compact mode regardless of flag state", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "rollout" as const,
      isLoading: false,
    });
    localStorage.setItem(LAST_SESSION_KEY, "active_session");
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);
    const chatEl = await openWidget();
    expect(chatEl).toHaveAttribute("data-compact", "true");
  });
});
