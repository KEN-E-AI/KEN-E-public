import { Link, useLocation } from "react-router-dom";
import {
  MessageSquare,
  TrendingUp,
  Calendar,
  Network,
  BookOpen,
  Puzzle,
  Settings,
  type LucideIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
}

export const NAVIGATION: readonly NavItem[] = [
  { name: "Chat", href: "/", icon: MessageSquare },
  { name: "Performance", href: "/performance", icon: TrendingUp },
  { name: "Calendar", href: "/calendar", icon: Calendar },
  { name: "Workflows", href: "/workflows", icon: Network },
  { name: "Knowledge", href: "/strategy", icon: BookOpen },
  { name: "Extensions", href: "/extensions", icon: Puzzle },
  { name: "Settings", href: "/settings/account", icon: Settings },
] as const;

function isItemActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function TopNav() {
  const location = useLocation();

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
            className="flex items-center gap-1 lg:gap-2 flex-1"
          >
            <TooltipProvider>
              {NAVIGATION.map((item) => {
                const isActive = isItemActive(location.pathname, item.href);

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

          <div className="flex items-center gap-2">
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
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="shrink-0">
            <Logo variant="icon" size="sm" />
          </div>
          <div className="min-w-0">
            <AccountSwitcher compact />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <NotificationBell />
          <ProfileMenu />
        </div>
      </div>
    </>
  );
}
