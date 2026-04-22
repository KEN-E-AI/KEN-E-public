import { User, Settings, HelpCircle, LogOut, Moon, Sun } from 'lucide-react';
import { useTheme } from './ThemeProvider';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { cn } from './ui/utils';
import { Link } from 'react-router';

interface ProfileMenuProps {
  compact?: boolean;
}

export function ProfileMenu({ compact = false }: ProfileMenuProps) {
  const { theme, setTheme } = useTheme();
  
  // Mock user data - in real app, this would come from auth context
  const currentUser = {
    name: 'Sarah Chen',
    email: 'sarah@company.com',
    initials: 'SC',
  };

  const handleSignOut = () => {
    console.log('Sign out');
    // In real app, call auth.signOut()
  };

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            'rounded-full transition-all outline-none flex items-center justify-center shrink-0',
            'hover:ring-2 hover:ring-[var(--color-violet-500)] hover:ring-offset-2',
            'hover:ring-offset-background active:scale-95',
            compact ? 'size-8' : 'size-9'
          )}
          style={{
            transitionTimingFunction: 'var(--ease-bounce)',
            transitionDuration: 'var(--duration-fast)',
          }}
        >
          <div
            className={cn(
              'rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center text-white font-bold',
              compact ? 'size-8 text-xs' : 'size-9 text-sm'
            )}
          >
            {currentUser.initials}
          </div>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-[260px] rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-0 shadow-lg"
      >
        {/* User info header */}
        <div className="px-4 py-3 bg-[var(--color-surface-muted)]">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center text-white font-bold">
              {currentUser.initials}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className="text-[var(--text-body-md)] text-[var(--color-text-primary)] truncate"
                style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}
              >
                {currentUser.name}
              </p>
              <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] truncate">
                {currentUser.email}
              </p>
            </div>
          </div>
        </div>

        <DropdownMenuSeparator className="m-0" />

        {/* Menu items */}
        <div className="py-1.5">
          <DropdownMenuGroup>
            <DropdownMenuItem asChild>
              <Link
                to="/settings/user"
                className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
              >
                <Settings className="size-4" />
                <span className="text-[var(--text-body-sm)]">User Settings</span>
              </Link>
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={toggleTheme}
              className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
            >
              {theme === 'dark' ? (
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

            <DropdownMenuItem className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]">
              <HelpCircle className="size-4" />
              <span className="text-[var(--text-body-sm)]">Help & Docs</span>
            </DropdownMenuItem>
          </DropdownMenuGroup>

          <DropdownMenuSeparator />

          <DropdownMenuItem
            onClick={handleSignOut}
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