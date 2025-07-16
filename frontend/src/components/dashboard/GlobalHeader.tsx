import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import {
  User,
  Edit2,
  ChevronDown,
  Home,
  BarChart3,
  TrendingUp,
  Target,
  Search,
  BookOpen,
  Settings,
  Building,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface GlobalHeaderProps {
  pageTitle?: string;
  dateRange: { from: Date; to: Date };
  setDateRange: (range: { from: Date; to: Date }) => void;
  comparisonDateRange?: { from: Date; to: Date };
  setComparisonDateRange?: (range: { from: Date; to: Date }) => void;
  selectedOrgAccount: SelectedOrgAccount | null;
  setSelectedOrgAccount: (account: SelectedOrgAccount) => void;
}

const navigationMenuItems = [
  { id: "home", name: "Home", icon: Home },
  { id: "overview", name: "Performance", icon: BarChart3 },
  { id: "big-bets", name: "Big Bets", icon: Target },
  { id: "data-exploration", name: "Data Exploration", icon: Search },
  { id: "knowledge", name: "Knowledge Base", icon: BookOpen },
  { id: "settings", name: "Org Settings", icon: Settings },
];

const OrganizationAccountDropdown = ({
  selectedOrgAccount,
  setSelectedOrgAccount,
}: {
  selectedOrgAccount: SelectedOrgAccount | null;
  setSelectedOrgAccount: (account: SelectedOrgAccount) => void;
}) => {
  const navigate = useNavigate();
  const { setCurrentOrganization, user, orgMetadata, accountMetadata } =
    useAuth();

  // Get organizations the user has access to (instead of accounts)
  const accessibleOrgIds = Object.keys(user?.permissions?.organizations || {});

  // Build all accessible org/account combinations
  const combinedOptions = accessibleOrgIds
    .flatMap((orgId) => {
      const organization = orgMetadata[orgId];
      if (!organization) return [];

      // Get all accounts for this organization
      const orgAccounts = organization.accounts || [];

      // For regular organizations, return all accounts in the organization
      if (!organization.agency) {
        return orgAccounts.map((account: any) => ({
          value: JSON.stringify({ orgId, accountId: account.account_id }),
          label: `${organization.organization_name} - ${account.account_name}`,
          orgId,
          accountId: account.account_id,
          metadata: {
            organization_name: organization.organization_name,
            account_name: account.account_name,
            industry: account.industry || "Unknown",
            status: account.status || "Active",
            timezone: account.timezone,
            plan: organization.plan,
          },
        }));
      }

      // For agency organizations, get accounts from child organizations
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
              label: `${childOrg.organization_name} - ${account.account_name}`,
              orgId: childOrgId,
              accountId: account.account_id,
              metadata: {
                organization_name: childOrg.organization_name,
                account_name: account.account_name,
                industry: account.industry || "Unknown",
                status: account.status || "Active",
                timezone: account.timezone,
                plan: childOrg.plan,
              },
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

  const handleValueChange = (value: string) => {
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
    <Select value={currentValue} onValueChange={handleValueChange}>
      <SelectTrigger className="h-auto p-1 border-none shadow-none text-sm font-medium text-dashboard-gray-900 hover:bg-dashboard-gray-50 w-auto bg-transparent min-w-[200px]">
        <SelectValue placeholder="Select Organization & Account" />
      </SelectTrigger>
      <SelectContent align="start" className="max-w-[300px]">
        {combinedOptions.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            <div className="flex items-center gap-2">
              <Building className="h-3 w-3" />
              <div className="truncate">{option.label}</div>
            </div>
          </SelectItem>
        ))}
        <SelectItem
          key="all-orgs-accounts"
          value="all-orgs-accounts"
          className="border-t border-gray-200 mt-1 pt-2"
        >
          <div className="flex items-center gap-2">
            <Building className="h-3 w-3" />
            <div className="truncate">All Orgs and Accounts</div>
          </div>
        </SelectItem>
      </SelectContent>
    </Select>
  );
};

const GlobalHeader = ({
  pageTitle = "Measurement Strategy",
  dateRange,
  setDateRange,
  comparisonDateRange,
  setComparisonDateRange = () => {},
  selectedOrgAccount = null,
  setSelectedOrgAccount,
}: GlobalHeaderProps) => {
  const navigate = useNavigate();
  const {
    logout,
    setCurrentOrganization,
    setSelectedOrgAccount: setAuthOrgAccount,
  } = useAuth();
  const { accountMetadata } = useAuth();

  // Calculate appropriate width and margin based on sidebar state
  const getContainerClasses = () => {
    return "bg-white border border-dashboard-gray-200 rounded-lg px-6 py-4";
  };

  return (
    <div className={getContainerClasses()}>
      {/* Top Row - Navigation and User */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-semibold text-dashboard-gray-900">
            {pageTitle}
          </h1>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <OrganizationAccountDropdown
            selectedOrgAccount={selectedOrgAccount}
            setSelectedOrgAccount={(account) => {
              setSelectedOrgAccount(account);
              setAuthOrgAccount(account);
            }}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="p-2">
                <User className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Your Name</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  // Handle invite users
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
                  navigate("/user-settings");
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
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span>Your Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer text-red-600"
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
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="p-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <line
                    x1="4"
                    x2="20"
                    y1="12"
                    y2="12"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                  <line
                    x1="4"
                    x2="20"
                    y1="6"
                    y2="6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                  <line
                    x1="4"
                    x2="20"
                    y1="18"
                    y2="18"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                </svg>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {navigationMenuItems.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div key={item.id}>
                    <DropdownMenuItem
                      className="flex items-center gap-3 cursor-pointer"
                      onClick={() => {
                        // Handle navigation
                        if (item.id === "knowledge") {
                          navigate("/knowledge");
                        } else if (item.id === "home") {
                          navigate("/");
                        } else if (item.id === "overview") {
                          navigate("/performance");
                        } else if (item.id === "marketing-funnel") {
                          navigate("/measurement-strategy");
                        } else if (item.id === "big-bets") {
                          navigate("/big-bets");
                        } else if (item.id === "data-exploration") {
                          navigate("/exploration");
                        } else if (item.id === "settings") {
                          const selectedAccount =
                            selectedOrgAccount?.accountId &&
                            accountMetadata[selectedOrgAccount.accountId];

                          if (selectedAccount) {
                            setCurrentOrganization(selectedOrgAccount.orgId);
                          }

                          navigate("/account-settings");
                        } else {
                          console.log(`Navigate to ${item.name}`);
                        }
                      }}
                    >
                      <Icon className="h-4 w-4" />
                      <span>
                        {item.name === "Performance" ? (
                          <>
                            Performance
                            <br />
                          </>
                        ) : (
                          item.name
                        )}
                      </span>
                    </DropdownMenuItem>
                    {index === navigationMenuItems.length - 3 && (
                      <DropdownMenuSeparator />
                    )}
                  </div>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
};

export default GlobalHeader;
