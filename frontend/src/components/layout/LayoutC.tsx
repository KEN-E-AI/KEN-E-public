import { useRef, useState, useSyncExternalStore } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { ChevronDown, MessageSquare } from "lucide-react";
import type { Brand } from "@/lib/branded-types";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ExtensionsProvider } from "@/contexts/ExtensionsContext";
import { SessionsSidebar } from "@/components/chat/SessionsSidebar";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { cn } from "@/lib/utils";
import { TopNav, NAVIGATION } from "./TopNav";

export type LayoutBannerId = Brand<string, "LayoutBannerId">;

export type LayoutBannerRow = {
  id: LayoutBannerId;
  order: number;
  component: React.ComponentType;
  isVisible?: boolean;
};

const _LAYOUT_BANNER_REGISTRY: LayoutBannerRow[] = [];
export const LAYOUT_BANNER_REGISTRY: ReadonlyArray<LayoutBannerRow> =
  _LAYOUT_BANNER_REGISTRY;

let _bannerVersion = 0;
const _bannerListeners = new Set<() => void>();

function _bannerSubscribe(listener: () => void): () => void {
  _bannerListeners.add(listener);
  return () => {
    _bannerListeners.delete(listener);
  };
}

function _getBannerSnapshot(): number {
  return _bannerVersion;
}

export function registerLayoutBanner(row: LayoutBannerRow): void {
  if (_LAYOUT_BANNER_REGISTRY.some((r) => r.id === row.id)) {
    if (import.meta.env.DEV) {
      console.warn(
        `[registerLayoutBanner] Rejected row "${row.id}": duplicate id`,
      );
    }
    return;
  }
  _LAYOUT_BANNER_REGISTRY.push(row);
  _bannerVersion += 1;
  _bannerListeners.forEach((listener) => listener());
}

export function unregisterLayoutBanner(id: LayoutBannerId): void {
  const index = _LAYOUT_BANNER_REGISTRY.findIndex((r) => r.id === id);
  if (index !== -1) {
    _LAYOUT_BANNER_REGISTRY.splice(index, 1);
    _bannerVersion += 1;
    _bannerListeners.forEach((listener) => listener());
  }
}

export function resetLayoutBannersForTesting(): void {
  if (!import.meta.env.DEV) return;
  _LAYOUT_BANNER_REGISTRY.length = 0;
  _bannerVersion = 0;
  _bannerListeners.clear();
}

const MINI_CHAT_DEFAULT_HEIGHT = 400;
const MINI_CHAT_MIN_HEIGHT = 200;

function isItemActive(
  pathname: string,
  href: string,
  matchPrefix?: string,
): boolean {
  const prefix = matchPrefix ?? href;
  return prefix === "/" ? pathname === "/" : pathname.startsWith(prefix);
}

export function LayoutC() {
  return (
    <ExtensionsProvider>
      <LayoutCInner />
    </ExtensionsProvider>
  );
}

function LayoutCInner() {
  const location = useLocation();
  const [miniChatOpen, setMiniChatOpen] = useState(false);
  const [miniChatHeight, setMiniChatHeight] = useState(
    MINI_CHAT_DEFAULT_HEIGHT,
  );
  const resizeStateRef = useRef<{
    startY: number;
    startHeight: number;
  } | null>(null);

  useSyncExternalStore(
    _bannerSubscribe,
    _getBannerSnapshot,
    _getBannerSnapshot,
  );

  const visibleBanners = LAYOUT_BANNER_REGISTRY.filter(
    (row) => row.isVisible !== false,
  ).sort((a, b) => a.order - b.order);

  const isHome = location.pathname === "/chat";
  // Routes that opt out of the max-w-screen-2xl content constraint and render
  // full-bleed. /knowledge/*, /measurement-plan, /strategy, /workflows/automations,
  // and /performance/dashboards/* host wide tables (MetricsConfiguration,
  // CompetitorsManagement, CustomerProfilesManagement, DashboardView) that would
  // horizontally clip on large monitors under the constrained width.
  const isFullWidth =
    location.pathname.startsWith("/strategy") ||
    location.pathname.startsWith("/workflows/automations") ||
    location.pathname.startsWith("/performance/dashboards/") ||
    location.pathname.startsWith("/knowledge") ||
    location.pathname.startsWith("/measurement-plan");

  const handleResizePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    resizeStateRef.current = {
      startY: e.clientY,
      startHeight: miniChatHeight,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handleResizePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeStateRef.current) return;
    const delta = resizeStateRef.current.startY - e.clientY;
    const max = Math.max(MINI_CHAT_MIN_HEIGHT, window.innerHeight - 200);
    const next = Math.min(
      max,
      Math.max(
        MINI_CHAT_MIN_HEIGHT,
        resizeStateRef.current.startHeight + delta,
      ),
    );
    setMiniChatHeight(next);
  };

  const handleResizePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeStateRef.current) return;
    resizeStateRef.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  return (
    <div className="flex flex-col h-screen bg-[var(--color-bg-primary)]">
      <header className="shrink-0">
        <TopNav />
      </header>

      {visibleBanners.length > 0 && (
        <div role="region" aria-label="System banners" className="shrink-0">
          {visibleBanners.map((row) => {
            const BannerComponent = row.component;
            return <BannerComponent key={row.id} />;
          })}
        </div>
      )}

      <div className="flex-1 overflow-hidden flex">
        {/* Sessions Sidebar — desktop only */}
        <aside
          aria-label="Chat sessions"
          className="hidden md:flex md:flex-col md:min-h-0 md:h-full"
        >
          <SessionsSidebar sessions={[]} />
        </aside>

        {/* Page content */}
        <main className="flex-1 min-h-0 overflow-hidden flex flex-col bg-[var(--color-bg-secondary)]">
          <div
            data-testid="layout-content"
            data-full-width={isFullWidth ? "true" : "false"}
            className={cn(
              isFullWidth ? "" : "max-w-screen-2xl",
              "w-full flex-1 min-h-0 flex flex-col bg-[var(--color-bg-primary)]",
            )}
            style={
              isFullWidth
                ? undefined
                : { borderRight: "2px dashed var(--color-border-default)" }
            }
          >
            <Outlet />
          </div>
        </main>
      </div>

      {/* Mini Chat Widget — non-home, desktop only */}
      {!isHome && (
        <Collapsible
          open={miniChatOpen}
          onOpenChange={setMiniChatOpen}
          className="hidden md:block"
        >
          <div
            data-testid="mini-chat-widget"
            className="bg-[var(--color-bg-primary)] relative"
            style={{
              borderTop: miniChatOpen
                ? "3px solid transparent"
                : "4px solid transparent",
              borderImage: "var(--gradient-rainbow) 1",
            }}
          >
            {miniChatOpen && (
              <div
                role="separator"
                aria-orientation="horizontal"
                aria-label="Resize chat panel"
                onPointerDown={handleResizePointerDown}
                onPointerMove={handleResizePointerMove}
                onPointerUp={handleResizePointerUp}
                onPointerCancel={handleResizePointerUp}
                className="absolute left-0 right-0 -top-1.5 h-3 z-20 cursor-ns-resize"
                style={{ touchAction: "none" }}
                title="Drag to resize"
              />
            )}
            <CollapsibleTrigger
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-[var(--color-accent)] transition-all rounded-none"
              style={{
                transitionTimingFunction: "var(--ease-default)",
                transitionDuration: "var(--duration-fast)",
              }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="size-10 rounded-[var(--radius-md)] bg-[var(--color-blue-500)] flex items-center justify-center -rotate-3"
                  style={{
                    boxShadow: "var(--shadow-color-blue)",
                  }}
                >
                  <MessageSquare className="size-5 text-[var(--color-text-inverse)]" />
                </div>
                <div className="text-left">
                  <p className="text-[var(--text-body-md)] font-bold">KEN-E</p>
                </div>
              </div>
              <ChevronDown
                className={cn(
                  "size-4 transition-transform text-[var(--color-text-tertiary)]",
                  miniChatOpen && "rotate-180",
                )}
              />
            </CollapsibleTrigger>

            <CollapsibleContent>
              <div
                className="relative flex flex-col"
                style={{
                  height: miniChatHeight,
                  borderTop: "2px dashed var(--color-border-default)",
                }}
              >
                <ChatInterface compact />
              </div>
            </CollapsibleContent>
          </div>
        </Collapsible>
      )}

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Primary navigation (mobile)"
        className="bg-[var(--color-bg-primary)] md:hidden relative"
        style={{
          borderTop: "3px solid transparent",
          borderImage: "var(--gradient-rainbow) 1",
        }}
      >
        <div className="grid grid-cols-7 h-16">
          {NAVIGATION.map((item) => {
            const isActive = isItemActive(
              location.pathname,
              item.href,
              item.matchPrefix,
            );
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 transition-all",
                  isActive
                    ? "text-[var(--color-violet-500)] scale-110"
                    : "text-[var(--color-text-secondary)]",
                )}
                style={{
                  transitionTimingFunction: "var(--ease-bounce)",
                  transitionDuration: "var(--duration-fast)",
                }}
              >
                <item.icon className="size-5" />
                <span className="text-[0.625rem] font-bold">{item.name}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
