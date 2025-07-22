import { useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Menu,
  Home,
  BarChart3,
  Target,
  Search,
  BookOpen,
  Settings,
  Building,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import { useLocation, useNavigate } from "react-router-dom";
import { iconMap } from "@/lib/iconMap";

interface SubMenuItem {
  id: string;
  label: string;
  route: string;
}

interface MenuSection {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: SubMenuItem[];
}

const menuConfigurations: Record<string, MenuSection> = {
  "/performance": {
    title: "Performance",
    icon: BarChart3,
    items: [
      { id: "overview", label: "Overview", route: "/performance" },
      {
        id: "channel",
        label: "Channel Performance",
        route: "/performance/channels",
      },
    ],
  },
  "/big-bets": {
    title: "Big Bets",
    icon: Target,
    items: [
      { id: "overview", label: "Overview", route: "/big-bets" },
      { id: "bet1", label: "Big Bet 1", route: "/big-bets/1" },
      { id: "bet2", label: "Big Bet 2", route: "/big-bets/2" },
    ],
  },
  "/exploration": {
    title: "Data Exploration",
    icon: Search,
    items: [
      { id: "charts", label: "Charts", route: "/exploration/charts" },
      {
        id: "dashboards",
        label: "Dashboards",
        route: "/exploration/dashboards",
      },
      { id: "catalog", label: "Data Catalog", route: "/exploration/catalog" },
    ],
  },
  "/knowledge": {
    title: "Knowledge Base",
    icon: BookOpen,
    items: [
      { id: "products", label: "Products", route: "/knowledge/products" },
      { id: "metrics", label: "Metrics", route: "/knowledge/metrics" },
      { id: "activities", label: "Activities", route: "/knowledge/activities" },
      { id: "insights", label: "Insights", route: "/knowledge/insights" },
      {
        id: "strategy",
        label: "Measurement Strategy",
        route: "/knowledge/strategy",
      },
      { id: "account", label: "Account Overview", route: "/knowledge/account" },
      { id: "customers", label: "Customers", route: "/knowledge/customers" },
      {
        id: "competitors",
        label: "Competitors",
        route: "/knowledge/competitors",
      },
    ],
  },
  "/settings": {
    title: "Settings",
    icon: Settings,
    items: [
      {
        id: "organization",
        label: "Organization",
        route: "/settings/organization",
      },
      { id: "user", label: "User", route: "/settings/user" },
    ],
  },
};

interface ContextSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const ContextSidebar: React.FC<ContextSidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
}) => {
  const {
    notifications,
    user,
    orgMetadata,
    accountMetadata,
    selectedOrgAccount,
    setSelectedOrgAccount,
    setCurrentOrganization,
  } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Determine which menu to show based on current route
  const getActiveMenu = () => {
    const path = location.pathname;

    // Check each menu configuration to see if the current path starts with it
    for (const [menuPath, config] of Object.entries(menuConfigurations)) {
      if (path.startsWith(menuPath)) {
        return { path: menuPath, config };
      }
    }

    // Default to home/notifications
    return null;
  };

  const activeMenu = getActiveMenu();
  const isHomePage = location.pathname === "/";

  // Organization dropdown logic
  const accessibleOrgIds = Object.keys(user?.permissions?.organizations || {});

  const combinedOptions: Array<{
    value: string;
    label: string;
    orgName: string;
    orgId: string;
    accountId: string;
  }> = accessibleOrgIds
    .flatMap((orgId) => {
      const organization = orgMetadata[orgId];
      if (!organization) return [];

      const orgAccounts = organization.accounts || [];

      if (!organization.agency) {
        return orgAccounts.map((account: any) => ({
          value: JSON.stringify({ orgId, accountId: account.account_id }),
          label: account.account_name,
          orgName: organization.organization_name,
          orgId,
          accountId: account.account_id,
        }));
      }

      if (organization.agency && organization.child_organizations) {
        return organization.child_organizations.flatMap(
          (childOrgId: string) => {
            const childOrg = orgMetadata[childOrgId];
            if (!childOrg) return [];

            const childAccounts = childOrg.accounts || [];
            return childAccounts.map((account: any) => ({
              value: JSON.stringify({
                orgId: childOrgId,
                accountId: account.account_id,
              }),
              label: account.account_name,
              orgName: childOrg.organization_name,
              orgId: childOrgId,
              accountId: account.account_id,
            }));
          },
        );
      }

      return [];
    })
    .filter(Boolean);

  const currentValue = selectedOrgAccount
    ? JSON.stringify({
        orgId: selectedOrgAccount.orgId,
        accountId: selectedOrgAccount.accountId,
      })
    : "";

  const handleOrgAccountChange = (value: string) => {
    if (value === "all-orgs-accounts") {
      navigate("/organization-selection");
      return;
    }

    let parsed: { orgId: string; accountId: string };
    try {
      parsed = JSON.parse(value);
    } catch (err) {
      console.warn("⚠️ Failed to parse selection JSON:", value);
      return;
    }

    const { orgId, accountId } = parsed;
    const account = accountMetadata[accountId];
    const organization = orgMetadata[orgId];

    if (!account || !organization) {
      console.warn("⚠️ Invalid selection — no matching org/account.", {
        orgId,
        accountId,
      });
      return;
    }

    const selection: SelectedOrgAccount = {
      orgId,
      accountId,
      metadata: {
        organization_name: organization.organization_name,
        account_name: account.account_name,
        industry: account.industry,
        status: account.status,
        timezone: account.timezone,
        plan: organization.plan,
      },
    };

    setSelectedOrgAccount(selection);
    setCurrentOrganization(orgId);
  };

  return (
    <div
      className={cn(
        "fixed top-0 left-14 h-full bg-white border-r border-dashboard-gray-200 z-30 transition-all duration-300 flex flex-col",
        isCollapsed ? "w-16" : "w-80 md:w-80",
      )}
    >
      {/* Header */}
      {isCollapsed ? (
        <div className="h-12 flex items-center justify-center border-b border-dashboard-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-8 w-8 p-0"
            aria-label="Toggle sidebar"
          >
            <Menu className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="h-12 flex items-center justify-between px-4 border-b border-dashboard-gray-200">
          <h2 className="text-lg font-semibold text-dashboard-gray-900">
            {isHomePage ? "Notifications" : activeMenu?.config.title || "Menu"}
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-8 w-8 p-0"
            aria-label="Toggle sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Content - grows to fill available space */}
      {!isCollapsed && (
        <div className="flex-1 overflow-y-auto pb-20">
          {" "}
          {/* Add padding bottom for org dropdown */}
          {isHomePage ? (
            // Notifications content for home page
            <div className="pr-4 pl-0 py-4">
              <div className="rounded-r-lg overflow-hidden border border-[#E2E8F0]">
                {notifications && notifications.length > 0 ? (
                  notifications.map((notification, index) => {
                    const iconName = notification.data.icon;
                    const IconComponent = iconMap[iconName] || Home;
                    return (
                      <div
                        key={notification.id}
                        className={cn(
                          "flex items-start gap-3 p-4 hover:bg-gray-50 transition-colors cursor-pointer",
                          index !== notifications.length - 1 && "border-b",
                        )}
                      >
                      <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                        <IconComponent className="w-5 h-5 text-gray-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">
                          {notification.data.title}
                        </p>
                        <p className="text-sm text-gray-500 mt-1">
                          {notification.data.description}
                        </p>
                        <p className="text-xs text-gray-400 mt-2">
                          {new Date(notification.timestamp).toLocaleString()}
                        </p>
                      </div>
                      {notification.data.badge && (
                        <Badge variant="secondary" className="flex-shrink-0">
                          {notification.data.badge}
                        </Badge>
                      )}
                    </div>
                  );
                })
                ) : (
                  <div className="p-4 text-gray-500 text-center">
                    No notifications
                  </div>
                )}
              </div>
            </div>
          ) : activeMenu ? (
            // Sub-menu content for other pages
            <div className="py-2">
              {activeMenu.config.items.map((item) => {
                const isActive = location.pathname === item.route;
                return (
                  <button
                    key={item.id}
                    onClick={() => navigate(item.route)}
                    className={cn(
                      "w-full text-left px-4 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-brand-light-blue/20 text-brand-medium-blue border-r-2 border-brand-medium-blue"
                        : "text-gray-700 hover:bg-gray-50 hover:text-gray-900",
                    )}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          ) : (
            // Empty state
            <div className="p-4 text-center text-gray-500 text-sm">
              No menu items available
            </div>
          )}
        </div>
      )}

      {/* Organization dropdown - fixed at bottom */}
      {!isCollapsed && combinedOptions.length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4">
          <Select value={currentValue} onValueChange={handleOrgAccountChange}>
            <SelectTrigger className="w-full h-auto py-2 text-sm">
              <SelectValue placeholder="Select Organization & Account">
                {currentValue &&
                  (() => {
                    const selected = combinedOptions.find(
                      (opt) => opt.value === currentValue,
                    );
                    if (selected) {
                      return (
                        <div className="flex items-start gap-2 text-left">
                          <Building className="h-4 w-4 mt-0.5 flex-shrink-0" />
                          <div>
                            <div className="font-bold">{selected.orgName}</div>
                            <div className="text-xs text-gray-600">
                              {selected.label}
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  })()}
              </SelectValue>
            </SelectTrigger>
            <SelectContent align="start" className="max-w-[300px]">
              {combinedOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  <div className="flex items-start gap-2">
                    <Building className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    <div>
                      <div className="font-bold">{option.orgName}</div>
                      <div className="text-xs text-gray-600">
                        {option.label}
                      </div>
                    </div>
                  </div>
                </SelectItem>
              ))}
              <SelectItem
                key="all-orgs-accounts"
                value="all-orgs-accounts"
                className="border-t border-gray-200 mt-1 pt-2"
              >
                <div className="flex items-center gap-2">
                  <Building className="h-4 w-4" />
                  <div className="truncate">All Orgs and Accounts</div>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
};
