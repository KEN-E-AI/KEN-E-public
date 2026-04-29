import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  MessageSquare,
  TrendingUp,
  Calendar,
  Network,
  BookOpen,
  Puzzle,
  Settings,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import type { Brand } from "@/lib/branded-types";

export const SIDEBAR_WIDTH_EXPANDED = "md:w-64";
export const SIDEBAR_WIDTH_COLLAPSED = "md:w-16";

const navigation = [
  { name: "Chat", href: "/", icon: MessageSquare },
  { name: "Performance", href: "/performance", icon: TrendingUp },
  { name: "Calendar", href: "/calendar", icon: Calendar },
  { name: "Workflows", href: "/workflows", icon: Network },
  { name: "Knowledge", href: "/strategy", icon: BookOpen },
  { name: "Extensions", href: "/extensions", icon: Puzzle },
  { name: "Settings", href: "/settings/account", icon: Settings },
] as const;

type NavRowId = Brand<string, "NavRowId">;

export type SuperAdminNavRow = {
  id: NavRowId;
  label: string;
  path: string;
  order: number;
  icon?: React.ComponentType<{ className?: string }>;
  isVisible?: boolean;
};

export const SUPER_ADMIN_NAV: SuperAdminNavRow[] = [];

export function registerSuperAdminNavRow(row: SuperAdminNavRow): void {
  if (!/^\/[a-zA-Z0-9/_-]*$/.test(row.path)) {
    return;
  }
  if (!SUPER_ADMIN_NAV.some((r) => r.id === row.id)) {
    SUPER_ADMIN_NAV.push(row);
  }
}

export function Sidebar() {
  const location = useLocation();
  const { isSuperAdmin } = useAuth();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sidebarCollapsed") === "true",
  );

  useEffect(() => {
    const width = collapsed ? "4rem" : "16rem";
    document.documentElement.style.setProperty("--sidebar-width", width);
  }, [collapsed]);

  const handleToggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebarCollapsed", String(next));
  };

  const visibleAdminRows = SUPER_ADMIN_NAV.filter(
    (row) => row.isVisible !== false,
  ).sort((a, b) => a.order - b.order);

  const showAdminSection = isSuperAdmin && visibleAdminRows.length > 0;

  return (
    <aside
      className={cn(
        "hidden md:flex md:flex-col h-full border-r border-[var(--color-border-default)] transition-all duration-fast ease-default shrink-0",
        collapsed ? "md:w-16" : "md:w-64",
      )}
      style={{ backgroundColor: "var(--color-bg-primary)" }}
    >
      <div className="flex items-center justify-end px-2 py-3 border-b border-[var(--color-border-default)]">
        <button
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          onClick={handleToggle}
          className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-md)] text-[var(--color-text-tertiary)] hover:bg-accent hover:text-[var(--color-violet-500)] transition-colors duration-fast ease-bounce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)] focus-visible:ring-offset-2"
        >
          {collapsed ? (
            <ChevronRight className="size-4" aria-hidden="true" />
          ) : (
            <ChevronLeft className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>

      <nav
        aria-label="Primary navigation"
        className="flex-1 flex flex-col gap-1 p-2 overflow-y-auto"
      >
        <TooltipProvider>
          {navigation.map((item) => {
            const isActive =
              item.href === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.href);

            return (
              <Tooltip key={item.name}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.href}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 rounded-[var(--radius-md)] text-sm font-bold transition-all duration-fast ease-bounce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)] focus-visible:ring-offset-2",
                      collapsed && "justify-center px-2",
                      isActive
                        ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                        : "text-[var(--color-text-secondary)] hover:bg-accent hover:text-[var(--color-violet-500)]",
                    )}
                  >
                    <item.icon className="size-5 shrink-0" aria-hidden="true" />
                    {collapsed ? (
                      <span className="sr-only">{item.name}</span>
                    ) : (
                      <span>{item.name}</span>
                    )}
                  </Link>
                </TooltipTrigger>
                {collapsed && (
                  <TooltipContent side="right">{item.name}</TooltipContent>
                )}
              </Tooltip>
            );
          })}
        </TooltipProvider>
      </nav>

      {showAdminSection && (
        <div className="border-t border-[var(--color-border-default)] p-2">
          {!collapsed && (
            <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
              Admin
            </p>
          )}
          <TooltipProvider>
            {visibleAdminRows.map((row) => {
              const isActive = location.pathname.startsWith(row.path);
              const AdminIcon = row.icon ?? ShieldCheck;
              return (
                <Tooltip key={row.id}>
                  <TooltipTrigger asChild>
                    <Link
                      to={row.path}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-[var(--radius-md)] text-sm font-bold transition-all duration-fast ease-bounce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)] focus-visible:ring-offset-2",
                        collapsed && "justify-center px-2",
                        isActive
                          ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                          : "text-[var(--color-text-secondary)] hover:bg-accent hover:text-[var(--color-violet-500)]",
                      )}
                    >
                      <AdminIcon
                        className="size-5 shrink-0"
                        aria-hidden="true"
                      />
                      {collapsed ? (
                        <span className="sr-only">{row.label}</span>
                      ) : (
                        <span>{row.label}</span>
                      )}
                    </Link>
                  </TooltipTrigger>
                  {collapsed && (
                    <TooltipContent side="right">{row.label}</TooltipContent>
                  )}
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </div>
      )}
    </aside>
  );
}
