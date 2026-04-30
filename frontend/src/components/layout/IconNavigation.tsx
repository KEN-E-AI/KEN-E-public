import {
  Home,
  BarChart3,
  Settings,
  Megaphone,
  FileText,
  Glasses,
  BookOpen,
  User,
  ThumbsUp,
  Radiation,
} from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";

interface NavigationItem {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  route: string;
}

export function IconNavigation() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isSuperAdmin } = useAuth();

  const navigationItems: NavigationItem[] = [
    { id: "home", icon: Home, label: "Home", route: "/" },
    {
      id: "performance",
      icon: BarChart3,
      label: "Performance",
      route: "/performance",
    },
    {
      id: "recommendations",
      icon: ThumbsUp,
      label: "Recommendations",
      route: "/recommendations",
    },
    {
      id: "campaigns",
      icon: Megaphone,
      label: "Campaigns",
      route: "/campaigns",
    },
    {
      id: "reports",
      icon: FileText,
      label: "Reports",
      route: "/reports",
    },
    {
      id: "simulations",
      icon: Glasses,
      label: "Simulations",
      route: "/simulations",
    },
    {
      id: "knowledge",
      icon: BookOpen,
      label: "Knowledge Base",
      route: "/knowledge",
    },
  ];

  const isActive = (route: string) => {
    if (route === "/") {
      return location.pathname === "/";
    }
    return location.pathname.startsWith(route);
  };

  return (
    <div
      data-testid="icon-navigation"
      className="w-14 bg-brand-charcoal h-screen flex flex-col fixed left-0 top-0 z-40"
    >
      {/* Logo/Brand */}
      <div className="h-16 flex items-center justify-center border-b border-gray-700 bg-brand-medium-blue">
        <img
          src="/KEN-E Logo E Small Charcoal.png"
          alt="KEN-E Logo"
          className="w-8 h-8 object-contain"
        />
      </div>

      {/* Navigation Icons */}
      <div className="flex-1 py-4">
        <div className="space-y-1">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.route);

            return (
              <div key={item.id} className="relative group">
                <button
                  onClick={() => navigate(item.route)}
                  className={cn(
                    "w-full h-12 flex items-center justify-center transition-colors",
                    active
                      ? "bg-brand-medium-blue text-white"
                      : "text-gray-400 hover:text-white hover:bg-brand-medium-blue/20",
                  )}
                  aria-label={item.label}
                >
                  <Icon className="w-5 h-5" />
                </button>

                {/* Tooltip */}
                <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 px-2 py-1 bg-brand-dark-blue text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 border border-gray-700">
                  {item.label}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Icons - Admin Settings (super admin only), Settings and User */}
      <div className="space-y-1 p-2 border-t border-gray-700">
        {/* Admin Settings Icon - Super Admin Only */}
        {isSuperAdmin && (
          <div className="relative group">
            <button
              onClick={() => navigate("/settings/admin")}
              className={cn(
                "w-full h-12 flex items-center justify-center transition-colors rounded",
                isActive("/settings/admin")
                  ? "bg-brand-medium-blue text-white"
                  : "text-gray-400 hover:text-red-400 hover:bg-brand-medium-blue/20",
              )}
              aria-label="Admin Settings"
            >
              <Radiation className="w-5 h-5 text-red-400" />
            </button>

            {/* Tooltip */}
            <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 px-2 py-1 bg-brand-dark-blue text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 border border-gray-700">
              Admin Settings
            </div>
          </div>
        )}

        {/* Settings Icon */}
        <div className="relative group">
          <button
            onClick={() => navigate("/settings")}
            className={cn(
              "w-full h-12 flex items-center justify-center transition-colors rounded",
              location.pathname === "/settings/organization"
                ? "bg-brand-medium-blue text-white"
                : "text-gray-400 hover:text-white hover:bg-brand-medium-blue/20",
            )}
            aria-label="Orgs & Accounts"
          >
            <Settings className="w-5 h-5" />
          </button>

          {/* Tooltip */}
          <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 px-2 py-1 bg-brand-dark-blue text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 border border-gray-700">
            Orgs & Accounts
          </div>
        </div>

        {/* User Icon */}
        <div className="relative group">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "w-full h-12 flex items-center justify-center transition-colors rounded",
                  location.pathname === "/settings/user"
                    ? "bg-brand-medium-blue text-white"
                    : "text-gray-400 hover:text-white hover:bg-brand-medium-blue/20",
                )}
                aria-label="User menu"
              >
                <User className="w-5 h-5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" side="right" className="w-48">
              <DropdownMenuLabel>{user?.firstName || "User"}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  navigate("/settings/user");
                }}
              >
                <Settings className="h-4 w-4" />
                <span>Your Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer text-brand-red"
                onClick={() => {
                  logout();
                }}
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                <span>Sign Out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Tooltip */}
          <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 px-2 py-1 bg-brand-dark-blue text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 border border-gray-700">
            Your Settings
          </div>
        </div>
      </div>
    </div>
  );
}
