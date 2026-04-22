import { Outlet, useLocation, Link } from 'react-router';
import { Logo } from '../components/Logo';
import { ProfileMenu } from '../components/ProfileMenu';
import { ChevronLeft } from 'lucide-react';
import { Button } from '../components/ui/button';

export function LayoutSettings() {
  const location = useLocation();

  // Determine the breadcrumb based on the current path
  const getBreadcrumb = () => {
    if (location.pathname.includes('/settings/organization')) {
      return 'Organization Settings';
    } else if (location.pathname.includes('/settings/user')) {
      return 'User Settings';
    } else if (location.pathname.includes('/settings/account')) {
      return 'Account Settings';
    }
    return 'Settings';
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Top Navigation Bar */}
      <div 
        className="bg-background relative"
        style={{
          borderBottom: '4px solid transparent',
          borderImage: 'var(--gradient-rainbow) 1',
        }}
      >
        <div className="flex items-center h-16 px-4 md:px-6">
          {/* Left: Logo + Back Button + Breadcrumb */}
          <div className="flex items-center gap-2 md:gap-4 flex-1 min-w-0">
            {/* Mobile: Back button icon only */}
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="md:hidden p-2 shrink-0"
            >
              <Link to="/">
                <ChevronLeft className="size-5" />
              </Link>
            </Button>

            <Logo variant="icon" size="sm" />
            
            <div className="h-8 w-px bg-[var(--color-border-default)] shrink-0 hidden md:block" />
            
            {/* Desktop: Back button with text */}
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="gap-2 hidden md:flex"
            >
              <Link to="/">
                <ChevronLeft className="size-4" />
                <span>Back to App</span>
              </Link>
            </Button>

            <div className="h-8 w-px bg-[var(--color-border-default)] shrink-0 hidden md:block" />

            <div className="min-w-0">
              <h1 
                className="text-[var(--text-body-md)] md:text-[var(--text-body-lg)] text-[var(--color-text-primary)] truncate"
                style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}
              >
                {getBreadcrumb()}
              </h1>
            </div>
          </div>

          {/* Right: Profile Menu */}
          <div className="flex items-center gap-2 shrink-0">
            <ProfileMenu compact />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}