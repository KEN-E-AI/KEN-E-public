import { Settings, LogOut } from "lucide-react";
import { Link } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

type ProfileMenuProps = {
  compact?: boolean;
};

export function ProfileMenu({ compact = false }: ProfileMenuProps) {
  const { user, logout } = useAuth();

  const first = user?.firstName?.[0] ?? "";
  const last = user?.lastName?.[0] ?? "";
  const initials = (first + last).toUpperCase() || "U";

  const fullName = user
    ? `${user.firstName} ${user.lastName}`.trim() || user.email
    : "";

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
          </DropdownMenuGroup>

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
