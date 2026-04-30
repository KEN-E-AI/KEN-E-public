import { useSyncExternalStore } from "react";
import { Settings, LogOut, Sun, Moon, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/components/theme/ThemeProvider";
import {
  SUPER_ADMIN_NAV,
  _getNavSnapshot,
  _navSubscribe,
} from "./super-admin-nav-registry";

type ProfileMenuProps = {
  compact?: boolean;
};

export function ProfileMenu({ compact = false }: ProfileMenuProps) {
  const { user, logout, isSuperAdmin } = useAuth();
  const { mode, toggle: toggleTheme } = useTheme();

  // Re-render when a new SUPER_ADMIN_NAV row is registered.
  useSyncExternalStore(_navSubscribe, _getNavSnapshot, _getNavSnapshot);

  const first = user?.firstName?.[0] ?? "";
  const last = user?.lastName?.[0] ?? "";
  const initials = (first + last).toUpperCase() || "U";

  const fullName = user
    ? `${user.firstName} ${user.lastName}`.trim() || user.email
    : "";

  const visibleAdminRows = SUPER_ADMIN_NAV.filter(
    (row) => row.isVisible !== false,
  ).sort((a, b) => a.order - b.order);
  const showAdminSection = isSuperAdmin && visibleAdminRows.length > 0;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={`Profile menu for ${fullName || user?.email || "user"}`}
          className={cn(
            "rounded-full transition-all outline-none flex items-center justify-center shrink-0",
            "hover:ring-2 hover:ring-[var(--color-violet-500)] hover:ring-offset-2",
            "hover:ring-offset-background active:scale-95",
            "focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)] focus-visible:ring-offset-2",
            compact ? "size-8" : "size-9",
          )}
          style={{
            transitionTimingFunction: "var(--ease-bounce)",
            transitionDuration: "var(--duration-fast)",
          }}
        >
          <div
            className={cn(
              "rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center text-white font-bold",
              compact ? "size-8 text-xs" : "size-9 text-sm",
            )}
          >
            {initials}
          </div>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-[260px] rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-0 shadow-lg"
      >
        <div className="px-4 py-3 bg-[var(--color-surface-muted)]">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center text-white font-bold shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className="text-[var(--text-body-md)] text-[var(--color-text-primary)] truncate"
                style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
              >
                {fullName}
              </p>
              <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] truncate">
                {user?.email ?? ""}
              </p>
            </div>
          </div>
        </div>

        <DropdownMenuSeparator className="m-0" />

        <div className="py-1.5">
          <DropdownMenuGroup>
            <DropdownMenuItem asChild>
              <Link
                to="/settings/user"
                className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
              >
                <Settings className="size-4" />
                <span className="text-[var(--text-body-sm)]">
                  User Settings
                </span>
              </Link>
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={(event) => {
                event.preventDefault();
                toggleTheme();
              }}
              className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
            >
              {mode === "dark" ? (
                <>
                  <Sun className="size-4" />
                  <span className="text-[var(--text-body-sm)]">Light Mode</span>
                </>
              ) : (
                <>
                  <Moon className="size-4" />
                  <span className="text-[var(--text-body-sm)]">Dark Mode</span>
                </>
              )}
            </DropdownMenuItem>
          </DropdownMenuGroup>

          {showAdminSection && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="px-4 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
                Admin
              </DropdownMenuLabel>
              <DropdownMenuGroup>
                {visibleAdminRows.map((row) => {
                  const AdminIcon = row.icon ?? ShieldCheck;
                  return (
                    <DropdownMenuItem key={row.id} asChild>
                      <Link
                        to={row.path}
                        className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
                      >
                        <AdminIcon className="size-4" />
                        <span className="text-[var(--text-body-sm)]">
                          {row.label}
                        </span>
                      </Link>
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuGroup>
            </>
          )}

          <DropdownMenuSeparator />

          <DropdownMenuItem
            onClick={() => logout()}
            className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
          >
            <LogOut className="size-4" />
            <span className="text-[var(--text-body-sm)]">Sign Out</span>
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
