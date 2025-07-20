import { useNavigate, useLocation } from "react-router-dom";
import { useMemo } from "react";
import React from "react";

export interface SettingsNavigationItem {
  id: string;
  title: string;
  description: string;
  route: string;
  icon: React.ComponentType<{ className?: string }>;
  enabled: boolean;
  requiresWorkspace: boolean;
}

export interface SettingsNavigation {
  currentRoute: string;
  currentSection: "settings" | "organization" | "account" | "user";
  navigationItems: SettingsNavigationItem[];
  navigateToSettings: () => void;
  navigateToOrganization: () => void;
  navigateToAccount: (accountId?: string) => void;
  navigateToUser: () => void;
  isCurrentRoute: (route: string) => boolean;
}

/**
 * Custom hook for managing settings navigation
 * Provides navigation helpers and current route information
 */
export const useSettingsNavigation = (): SettingsNavigation => {
  const navigate = useNavigate();
  const location = useLocation();

  const currentRoute = location.pathname;

  const currentSection = useMemo(() => {
    if (currentRoute === "/settings") return "settings";
    if (
      currentRoute.startsWith("/settings/organization") ||
      currentRoute === "/organization-settings"
    )
      return "organization";
    if (
      currentRoute.startsWith("/settings/user") ||
      currentRoute === "/user-settings"
    )
      return "user";
    return "settings";
  }, [currentRoute]);

  const navigationItems: SettingsNavigationItem[] = useMemo(() => {
    return [
      {
        id: "organization",
        title: "Organization Settings",
        description:
          "Manage organization profile, subscription, billing, and team settings",
        route: "/settings/organization",
        icon: ({ className = "" }) =>
          React.createElement(
            "svg",
            {
              className,
              fill: "none",
              viewBox: "0 0 24 24",
              stroke: "currentColor",
            },
            React.createElement("path", {
              strokeLinecap: "round",
              strokeLinejoin: "round",
              strokeWidth: 2,
              d: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 8v-2a1 1 0 011-1h1a1 1 0 011 1v2M7 7h.01M7 11h.01",
            }),
          ),
        enabled: true,
        requiresWorkspace: true,
      },
      {
        id: "user",
        title: "User Settings",
        description:
          "Manage your personal profile, notifications, and preferences",
        route: "/settings/user",
        icon: ({ className = "" }) =>
          React.createElement(
            "svg",
            {
              className,
              fill: "none",
              viewBox: "0 0 24 24",
              stroke: "currentColor",
            },
            React.createElement("path", {
              strokeLinecap: "round",
              strokeLinejoin: "round",
              strokeWidth: 2,
              d: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
            }),
          ),
        enabled: true,
        requiresWorkspace: false,
      },
    ];
  }, []);

  const navigateToSettings = () => {
    navigate("/settings");
  };

  const navigateToOrganization = () => {
    navigate("/settings/organization");
  };

  const navigateToAccount = (accountId?: string) => {
    if (accountId) {
      navigate(`/settings/account/${accountId}`);
    } else {
      navigate("/settings/account");
    }
  };

  const navigateToUser = () => {
    navigate("/settings/user");
  };

  const isCurrentRoute = (route: string) => {
    return currentRoute === route;
  };

  return {
    currentRoute,
    currentSection,
    navigationItems,
    navigateToSettings,
    navigateToOrganization,
    navigateToAccount,
    navigateToUser,
    isCurrentRoute,
  };
};

export default useSettingsNavigation;
