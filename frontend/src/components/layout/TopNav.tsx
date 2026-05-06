import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  MessageSquare,
  TrendingUp,
  Calendar,
  Network,
  BookOpen,
  Puzzle,
  Settings,
  Menu,
  type LucideIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Sheet,
  SheetContent,
  SheetClose,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Logo } from "@/components/branding/Logo";
import { AccountSwitcher } from "./AccountSwitcher";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";
import { ExtensionsNavItem } from "./ExtensionsNavItem";
import { cn } from "@/lib/utils";

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  /** When set, active-state matching uses this prefix instead of `href`. */
  matchPrefix?: string;
}

export const NAVIGATION: readonly NavItem[] = [
  { name: "Chat", href: "/chat", icon: MessageSquare },
  { name: "Performance", href: "/performance", icon: TrendingUp },
  { name: "Calendar", href: "/calendar", icon: Calendar },
  {
    name: "Workflows",
    href: "/workflows/agents",
    icon: Network,
    matchPrefix: "/workflows",
  },
  { name: "Knowledge", href: "/strategy", icon: BookOpen },
  { name: "Extensions", href: "/extensions", icon: Puzzle },
  { name: "Settings", href: "/settings/account", icon: Settings },
] as const;

function isItemActive(
  pathname: string,
  href: string,
  matchPrefix?: string,
): boolean {
  const prefix = matchPrefix ?? href;
  return prefix === "/" ? pathname === "/" : pathname.startsWith(prefix);
}

export function TopNav() {
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <>
      {/* Desktop Top Navigation Bar */}
      <div
        data-testid="topnav-desktop"
        className="bg-[var(--color-bg-primary)] hidden md:block relative"
        style={{
          borderBottom: "4px solid transparent",
          borderImage: "var(--gradient-rainbow) 1",
        }}
      >
        <div className="flex items-center h-16 px-6">
          <div className="flex items-center gap-2 shrink-0">
            <Logo variant="icon" size="sm" />
            <AccountSwitcher />
          </div>

          <div className="h-8 w-px bg-[var(--color-border-default)] mx-5 shrink-0" />

          <nav
            aria-label="Primary navigation"
            className="flex items-center gap-1 lg:gap-2 flex-1 min-w-0 overflow-hidden"
          >
            <TooltipProvider>
              {NAVIGATION.map((item) => {
                const isActive = isItemActive(
                  location.pathname,
                  item.href,
                  item.matchPrefix,
                );

                if (item.name === "Extensions") {
                  return (
                    <ExtensionsNavItem
                      key={item.name}
                      item={item}
                      isActive={isActive}
                    />
                  );
                }

                return (
                  <Tooltip key={item.name}>
                    <TooltipTrigger asChild>
                      <Link
                        to={item.href}
                        className={cn(
                          "flex items-center gap-2 p-2 lg:px-4 lg:py-2 rounded-[var(--radius-pill)] transition-all text-[var(--text-body-sm)] font-bold",
                          isActive
                            ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                            : "text-[var(--color-text-secondary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] hover:-translate-y-0.5",
                        )}
                        style={{
                          transitionTimingFunction: "var(--ease-bounce)",
                          transitionDuration: "var(--duration-fast)",
                        }}
                      >
                        <item.icon className="size-4" />
                        <span className="hidden lg:inline">{item.name}</span>
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent className="lg:hidden">
                      {item.name}
                    </TooltipContent>
                  </Tooltip>
                );
              })}
            </TooltipProvider>
          </nav>

          <div className="flex items-center gap-2 shrink-0 ml-2">
            <NotificationBell />
            <ProfileMenu />
          </div>
        </div>
      </div>

      {/* Mobile Compact Header */}
      <div
        data-testid="topnav-mobile"
        className="bg-[var(--color-bg-primary)] px-4 py-3 flex items-center justify-between md:hidden relative"
        style={{
          borderBottom: "3px solid transparent",
          borderImage: "var(--gradient-rainbow) 1",
        }}
      >
        <div className="flex items-center gap-2 shrink-0">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <button
                aria-label="Navigation menu"
                aria-expanded={drawerOpen}
                data-testid="mobile-nav-trigger"
                className="p-2 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent)] transition-colors"
              >
                <Menu className="size-5" aria-hidden="true" />
              </button>
            </SheetTrigger>

            {/* aria-describedby={undefined}: no SheetDescription present; suppresses Radix missing-description warning in JSDOM. */}
            <SheetContent
              side="left"
              className="p-0 w-72 flex flex-col"
              data-testid="mobile-nav-drawer"
              aria-describedby={undefined}
            >
              <SheetTitle className="sr-only">Navigation</SheetTitle>

              {/* pt-10 clears the built-in SheetContent close button (absolute right-4 top-4). */}
              <div className="pt-10 px-4 pb-4 border-b border-[var(--color-border-default)]">
                <AccountSwitcher />
              </div>

              <nav
                aria-label="Primary navigation (mobile drawer)"
                className="flex-1 overflow-y-auto py-2"
              >
                {/* Nested extensions list deferred until mobile-drawer spec ships. */}
                {NAVIGATION.map((item) => {
                  const isActive = isItemActive(
                    location.pathname,
                    item.href,
                    item.matchPrefix,
                  );
                  return (
                    <SheetClose asChild key={item.name}>
                      <Link
                        to={item.href}
                        className={cn(
                          "flex items-center gap-3 px-4 py-3 text-[var(--text-body-md)] font-bold transition-colors",
                          isActive
                            ? "bg-[var(--color-accent)] text-[var(--color-violet-500)]"
                            : "text-[var(--color-text-secondary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)]",
                        )}
                      >
                        <item.icon className="size-5 shrink-0" />
                        {item.name}
                      </Link>
                    </SheetClose>
                  );
                })}
              </nav>
            </SheetContent>
          </Sheet>

          <Logo variant="icon" size="sm" />
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <NotificationBell />
          <ProfileMenu />
        </div>
      </div>
    </>
  );
}
