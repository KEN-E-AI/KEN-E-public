import type React from "react";
import { Outlet, useLocation, Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { ProfileMenu } from "./ProfileMenu";
import { Logo } from "@/components/branding/Logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Brand } from "@/lib/branded-types";

export type SettingsNavRowId = Brand<string, "SettingsNavRowId">;

export type SettingsNavRow = {
  id: SettingsNavRowId;
  label: string;
  path: string;
  order: number;
  isVisible?: boolean;
};

type LayoutSettingsProps = {
  subNavItems: SettingsNavRow[];
  children?: React.ReactNode;
};

const SAFE_PATH_RE = /^\/[a-zA-Z0-9/_-]+$/;
const SAFE_PATH_MAX_LEN = 200;

function isSafePath(path: string): boolean {
  // Block over-length paths, dot-segment traversal, and /__* dev-harness routes
  if (
    path.length > SAFE_PATH_MAX_LEN ||
    path.includes("..") ||
    path.startsWith("/__")
  )
    return false;
  return SAFE_PATH_RE.test(path);
}

function getBreadcrumb(pathname: string): string {
  if (
    pathname === "/settings/organization" ||
    pathname.startsWith("/settings/organization/")
  ) {
    return "Organization Settings";
  }
  if (pathname === "/settings/user" || pathname.startsWith("/settings/user/")) {
    return "User Settings";
  }
  if (
    pathname === "/settings/account" ||
    pathname.startsWith("/settings/account/")
  ) {
    return "Account Settings";
  }
  return "Settings";
}

export function LayoutSettings({ subNavItems, children }: LayoutSettingsProps) {
  const location = useLocation();

  const visibleRows = subNavItems
    .filter((row) => row.isVisible !== false && isSafePath(row.path))
    .sort((a, b) => a.order - b.order);

  return (
    <div className="flex flex-col h-screen bg-[var(--color-bg-primary)]">
      <header
        className="bg-[var(--color-bg-primary)] relative shrink-0"
        style={{
          borderBottom: "4px solid transparent",
          borderImage: "var(--gradient-rainbow) 1",
        }}
      >
        <div className="flex items-center h-16 px-4 md:px-6">
          <div className="flex items-center gap-2 md:gap-4 flex-1 min-w-0">
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="md:hidden p-2 shrink-0 text-[var(--color-text-primary)]"
            >
              <Link to="/" aria-label="Back to App">
                <ChevronLeft className="size-5" aria-hidden="true" />
              </Link>
            </Button>

            <Logo variant="icon" size="sm" />

            <div
              className="h-8 w-px shrink-0 hidden md:block"
              style={{ backgroundColor: "var(--color-border-default)" }}
            />

            <Button
              variant="ghost"
              size="sm"
              asChild
              className="gap-2 hidden md:flex text-[var(--color-text-primary)]"
            >
              <Link to="/">
                <ChevronLeft className="size-4" aria-hidden="true" />
                <span>Back to App</span>
              </Link>
            </Button>

            <div
              className="h-8 w-px shrink-0 hidden md:block"
              style={{ backgroundColor: "var(--color-border-default)" }}
            />

            <div className="min-w-0">
              <h1
                className="text-[var(--text-body-md)] md:text-[var(--text-body-lg)] text-[var(--color-text-primary)] truncate"
                style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
              >
                {getBreadcrumb(location.pathname)}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <ProfileMenu compact />
          </div>
        </div>
      </header>

      <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
        <aside
          className="flex flex-row overflow-x-auto md:flex-col md:w-48 xl:w-56 shrink-0 border-b md:border-b-0 md:border-r border-[var(--color-border-default)]"
          style={{ backgroundColor: "var(--color-bg-primary)" }}
        >
          <nav
            aria-label="Settings sections"
            className="flex flex-row md:flex-col gap-1 p-2"
          >
            {visibleRows.map((row) => {
              const isActive =
                location.pathname === row.path ||
                location.pathname.startsWith(`${row.path}/`);
              return (
                <Link
                  key={row.id}
                  to={row.path}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "flex items-center px-3 py-2 rounded-[var(--radius-md)] text-[var(--text-body-sm)] font-bold whitespace-nowrap transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)] focus-visible:ring-offset-2",
                    isActive
                      ? "bg-[var(--color-violet-100)] text-[var(--color-violet-500)] dark:bg-[var(--color-violet-500)]/10"
                      : "text-[var(--color-text-secondary)] hover:bg-accent hover:text-[var(--color-violet-500)]",
                  )}
                >
                  {row.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 overflow-auto">
          <div className="max-w-4xl mx-auto p-6">{children ?? <Outlet />}</div>
        </main>
      </div>
    </div>
  );
}
