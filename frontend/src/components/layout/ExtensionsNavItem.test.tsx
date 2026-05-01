import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Puzzle, LayoutDashboard, Search } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  ExtensionsContext,
  type ExtensionsContextValue,
  type ExtensionDefinition,
} from "@/contexts/ExtensionsContext";
import { ExtensionsNavItem } from "./ExtensionsNavItem";

const ITEM = { name: "Extensions", href: "/extensions", icon: Puzzle };

function makeExtension(
  overrides: Partial<ExtensionDefinition> & { id: string; slug: string },
): ExtensionDefinition {
  return {
    name: overrides.name ?? overrides.id,
    description: "",
    longDescription: "",
    icon: LayoutDashboard,
    category: "Test",
    color: "var(--color-blue-500)",
    shadow: "var(--shadow-color-blue)",
    rotation: "",
    configSteps: [],
    source: "official",
    ...overrides,
  };
}

function makeContextValue(
  extensions: ExtensionDefinition[],
): ExtensionsContextValue {
  return {
    activeExtensions: new Map(),
    isActive: () => false,
    activateExtension: () => {},
    deactivateExtension: () => {},
    getActiveExtensionDefinitions: () => extensions,
  };
}

function renderWith({
  extensions = [] as ExtensionDefinition[],
  isActive = false,
} = {}) {
  return render(
    <MemoryRouter>
      <TooltipProvider>
        <ExtensionsContext.Provider value={makeContextValue(extensions)}>
          <ExtensionsNavItem item={ITEM} isActive={isActive} />
        </ExtensionsContext.Provider>
      </TooltipProvider>
    </MemoryRouter>,
  );
}

describe("ExtensionsNavItem", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders the link with the item name", () => {
    renderWith();
    expect(screen.getByRole("link", { name: /extensions/i })).toHaveAttribute(
      "href",
      "/extensions",
    );
  });

  test("does not render the hover panel until hovered", () => {
    renderWith();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  test("hovering the wrapper opens the panel", () => {
    const ext1 = makeExtension({
      id: "dashboard-creator",
      slug: "dashboard-creator",
      name: "Dashboard Creator",
      icon: LayoutDashboard,
    });
    const ext2 = makeExtension({
      id: "seo-optimizer",
      slug: "seo-optimizer",
      name: "SEO Optimizer",
      icon: Search,
    });
    renderWith({ extensions: [ext1, ext2] });

    fireEvent.mouseEnter(
      screen.getByRole("link", { name: /extensions/i }).parentElement!,
    );

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /dashboard creator/i }),
    ).toHaveAttribute("href", "/extensions/dashboard-creator");
    expect(
      screen.getByRole("menuitem", { name: /seo optimizer/i }),
    ).toHaveAttribute("href", "/extensions/seo-optimizer");
    expect(
      screen.getByRole("menuitem", { name: /browse all extensions/i }),
    ).toBeInTheDocument();
  });

  test("mouse-leave keeps the panel open until the 150ms timer elapses", () => {
    renderWith();
    const wrapper = screen.getByRole("link", {
      name: /extensions/i,
    }).parentElement!;

    fireEvent.mouseEnter(wrapper);
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.mouseLeave(wrapper);

    // Just before the threshold: panel is still open.
    act(() => {
      vi.advanceTimersByTime(149);
    });
    expect(screen.getByRole("menu")).toBeInTheDocument();

    // At the threshold: panel closes.
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  test("re-entering before the timer fires cancels the close", () => {
    renderWith();
    const wrapper = screen.getByRole("link", {
      name: /extensions/i,
    }).parentElement!;

    fireEvent.mouseEnter(wrapper);
    fireEvent.mouseLeave(wrapper);

    act(() => {
      vi.advanceTimersByTime(100);
    });

    fireEvent.mouseEnter(wrapper);

    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Panel still open because the close timer was cancelled by re-enter.
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  test("with no active extensions, the panel shows only the Browse-all link (no divider)", () => {
    renderWith();
    fireEvent.mouseEnter(
      screen.getByRole("link", { name: /extensions/i }).parentElement!,
    );

    const menuItems = screen.getAllByRole("menuitem");
    expect(menuItems).toHaveLength(1);
    expect(menuItems[0]).toHaveTextContent(/browse all extensions/i);
  });

  test("clears the pending hover-close timer on unmount (no leaked setTimeout)", () => {
    const { unmount } = renderWith();
    const wrapper = screen.getByRole("link", {
      name: /extensions/i,
    }).parentElement!;

    fireEvent.mouseEnter(wrapper);
    fireEvent.mouseLeave(wrapper);

    // The 150ms close-delay timer is now pending.
    const pendingDuringMount = vi.getTimerCount();
    expect(pendingDuringMount).toBeGreaterThan(0);

    // Unmount before the timer fires — the routine case where the user clicks a
    // different nav link mid-hover and ExtensionsNavItem leaves the tree.
    unmount();

    // The cleanup effect must have cleared the timer; the pending count drops.
    expect(vi.getTimerCount()).toBeLessThan(pendingDuringMount);
  });
});
