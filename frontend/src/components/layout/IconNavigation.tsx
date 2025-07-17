import {
  Home,
  BarChart3,
  Settings,
  Target,
  Search,
  BookOpen,
  User,
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
  const { logout } = useAuth();

  const navigationItems: NavigationItem[] = [
    { id: "home", icon: Home, label: "Home", route: "/" },
    {
      id: "performance",
      icon: BarChart3,
      label: "Performance",
      route: "/performance",
    },
    { id: "big-bets", icon: Target, label: "Big Bets", route: "/big-bets" },
    {
      id: "exploration",
      icon: Search,
      label: "Data Exploration",
      route: "/exploration",
    },
    {
      id: "knowledge",
      icon: BookOpen,
      label: "Knowledge Base",
      route: "/knowledge",
    },
    { id: "settings", icon: Settings, label: "Settings", route: "/settings" },
  ];

  const isActive = (route: string) => {
    if (route === "/") {
      return location.pathname === "/";
    }
    return location.pathname.startsWith(route);
  };

  return (
    <div className="w-14 bg-brand-dark-blue h-screen flex flex-col fixed left-0 top-0 z-40">
      {/* Logo/Brand */}
      <div className="h-14 flex items-center justify-center border-b border-gray-700">
        <div className="w-8 h-8 bg-brand-medium-blue rounded flex items-center justify-center">
          <span className="text-white text-xs font-bold">K</span>
        </div>
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

      {/* User Icon - Fixed at bottom */}
      <div className="p-2 border-t border-gray-700">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="w-full h-12 flex items-center justify-center text-gray-400 hover:text-white hover:bg-brand-medium-blue/20 transition-colors rounded"
              aria-label="User menu"
            >
              <User className="w-5 h-5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="right" className="w-48">
            <DropdownMenuLabel>Your Name</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="flex items-center gap-2 cursor-pointer"
              onClick={() => {
                console.log("Invite Users");
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
                  d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"
                />
              </svg>
              <span>Invite Users</span>
            </DropdownMenuItem>
            <DropdownMenuItem
              className="flex items-center gap-2 cursor-pointer"
              onClick={() => {
                navigate("/settings");
              }}
            >
              <Settings className="h-4 w-4" />
              <span>Settings</span>
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
      </div>
    </div>
  );
}
