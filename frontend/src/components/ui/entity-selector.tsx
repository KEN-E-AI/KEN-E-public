import { useAuth } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Building2, User, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface EntitySelectorProps {
  className?: string;
  onSelectionChange?: (selection: SelectedOrgAccount) => void;
  showUserContext?: boolean;
  organizationOnly?: boolean;
}

export const EntitySelector = ({
  className = "",
  onSelectionChange,
  showUserContext = false,
  organizationOnly = false,
}: EntitySelectorProps) => {
  const navigate = useNavigate();
  const {
    user,
    selectedOrgAccount,
    setCurrentOrganization,
    setSelectedOrgAccount,
    orgMetadata,
    accountMetadata,
  } = useAuth();

  // Get organizations the user has access to
  const accessibleOrgIds = Object.keys(user?.permissions?.organizations || {});

  // Build options based on mode
  const combinedOptions = organizationOnly
    ? accessibleOrgIds
        .map((orgId) => {
          const organization = orgMetadata[orgId];
          if (!organization) return null;

          return {
            value: JSON.stringify({ orgId, accountId: "" }),
            label: organization.organization_name,
            orgId,
            accountId: "",
            metadata: {
              organization_name: organization.organization_name,
              account_name: "",
              industry: "",
              status: "Active",
              timezone: "",
              plan: organization.plan,
            },
          };
        })
        .filter(Boolean)
    : accessibleOrgIds
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
        accountId: organizationOnly ? "" : selectedOrgAccount.accountId,
      })
    : "";

  const handleValueChange = (value: string) => {
    if (value === "all-orgs-accounts") {
      navigate("/select-organization");
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
    const organization = orgMetadata[orgId];

    if (!organization) {
      console.warn("⚠️ Invalid selection — no matching org.", {
        orgId,
        accountId,
      });
      return;
    }

    if (organizationOnly) {
      // For organization-only mode, just set the organization
      setCurrentOrganization(orgId);

      // Find the first account in the organization, or create a selection without an account
      const firstAccount = organization.accounts?.[0];
      const selection: SelectedOrgAccount = {
        orgId,
        accountId: firstAccount?.account_id || "",
        metadata: {
          organization_name: organization.organization_name,
          account_name: firstAccount?.account_name || "",
          industry: firstAccount?.industry || "",
          status: firstAccount?.status || "Active",
          timezone: firstAccount?.timezone || "",
          plan: organization.plan,
        },
      };
      setSelectedOrgAccount(selection);

      if (onSelectionChange) {
        onSelectionChange(selection);
      }
    } else {
      // Original logic for org/account selection
      const account = accountMetadata[accountId];

      if (!account) {
        console.warn("⚠️ Invalid selection — no matching account.", {
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

      if (onSelectionChange) {
        onSelectionChange(selection);
      }
    }
  };

  const currentOrgName =
    selectedOrgAccount?.metadata?.organization_name || "Select Organization";
  const currentAccountName =
    selectedOrgAccount?.metadata?.account_name || "Select Account";
  const currentUserName =
    user?.firstName && user?.lastName
      ? `${user.firstName} ${user.lastName}`
      : user?.email || "User";

  return (
    <Select value={currentValue} onValueChange={handleValueChange}>
      <SelectTrigger className={`h-auto p-3 ${className}`}>
        <SelectValue>
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-[var(--color-text-tertiary)]" />
            <div className="flex flex-col items-start">
              {organizationOnly ? (
                <div className="text-sm font-medium text-[var(--color-text-primary)]">
                  <span className="truncate">{currentOrgName}</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm font-medium text-[var(--color-text-primary)]">
                  <span className="truncate">{currentOrgName}</span>
                  <ChevronRight className="h-3 w-3 text-[var(--color-text-disabled)]" />
                  <span className="truncate">{currentAccountName}</span>
                </div>
              )}
              {showUserContext && (
                <div className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)] mt-1">
                  <User className="h-3 w-3" />
                  <span className="truncate">{currentUserName}</span>
                </div>
              )}
            </div>
          </div>
        </SelectValue>
      </SelectTrigger>
      <SelectContent align="start" className="max-w-[400px]">
        {combinedOptions.map((option, index) => (
          <SelectItem
            key={`${option.orgId}-${option.accountId}-${index}`}
            value={option.value}
          >
            <div className="flex items-center gap-2 py-1">
              <Building2 className="h-3 w-3 text-[var(--color-text-tertiary)]" />
              <div className="flex flex-col">
                <div className="font-medium text-sm">
                  {option.metadata.organization_name}
                </div>
                {!organizationOnly && (
                  <div className="text-xs text-[var(--color-text-tertiary)]">
                    {option.metadata.account_name}
                  </div>
                )}
              </div>
            </div>
          </SelectItem>
        ))}
        {!organizationOnly && (
          <SelectItem
            key="all-orgs-accounts"
            value="all-orgs-accounts"
            className="border-t border-[var(--color-border-default)] mt-1 pt-2"
          >
            <div className="flex items-center gap-2">
              <Building2 className="h-3 w-3 text-[var(--color-text-tertiary)]" />
              <div className="truncate">All Organizations & Accounts</div>
            </div>
          </SelectItem>
        )}
      </SelectContent>
    </Select>
  );
};
