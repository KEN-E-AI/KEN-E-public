import { ChevronsUpDown, Check, Building2, Settings } from "lucide-react";
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
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import type { OrganizationId, AccountId } from "@/lib/branded-types";

type AccountSwitcherProps = {
  compact?: boolean;
};

const AVATAR_COLORS = [
  "var(--color-violet-500)",
  "var(--color-blue-500)",
  "var(--color-teal-500)",
];

type OrgAvatarProps = {
  orgName: string;
  orgId: string;
  size?: "sm" | "md";
};

function OrgAvatar({ orgName, orgId, size = "sm" }: OrgAvatarProps) {
  const color = AVATAR_COLORS[orgId.charCodeAt(0) % AVATAR_COLORS.length];
  const dims = size === "sm" ? "size-6" : "size-8";
  const textSize = size === "sm" ? "text-[10px]" : "text-xs";
  return (
    <div
      className={cn(
        dims,
        "rounded-[var(--radius-sm)] flex items-center justify-center shrink-0",
      )}
      style={{ backgroundColor: color }}
    >
      <span className={cn(textSize, "text-white font-extrabold")}>
        {orgName.charAt(0)}
      </span>
    </div>
  );
}

export function AccountSwitcher({ compact = false }: AccountSwitcherProps) {
  const {
    selectedOrgAccount,
    orgMetadata,
    accountMetadata,
    setSelectedOrgAccount,
    setCurrentOrganization,
  } = useAuth();

  const accountsByOrg: Array<{
    orgId: string;
    orgName: string;
    accounts: Array<{ accountId: string; accountData: Record<string, any> }>;
  }> = Object.entries(orgMetadata).map(([orgId, orgData]) => ({
    orgId,
    orgName: orgData.organization_name ?? orgId,
    accounts: Object.entries(accountMetadata)
      .filter(([, acct]) => acct.organization_id === orgId)
      .map(([accountId, acct]) => ({ accountId, accountData: acct })),
  }));

  const handleSelect = (orgId: string, accountId: string) => {
    const org = orgMetadata[orgId] ?? {};
    const account = accountMetadata[accountId] ?? {};
    const selection: SelectedOrgAccount = {
      orgId: orgId as OrganizationId,
      accountId: accountId as AccountId,
      metadata: {
        organization_name: org.organization_name ?? "",
        account_name: account.account_name ?? "",
        industry: account.industry ?? "",
        status: account.status ?? "",
        timezone: account.timezone,
        plan: org.plan,
      },
    };
    setSelectedOrgAccount(selection);
    setCurrentOrganization(orgId as OrganizationId);
  };

  const triggerLabel =
    selectedOrgAccount != null
      ? `${selectedOrgAccount.metadata.organization_name} / ${selectedOrgAccount.metadata.account_name}`
      : "Select account";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "flex items-center gap-1.5 rounded-[var(--radius-md)] transition-all outline-none",
            "hover:bg-[var(--accent)] active:scale-[0.98]",
            "focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)]",
            compact ? "px-2 py-1.5" : "px-2.5 py-1.5",
          )}
          style={{
            transitionTimingFunction: "var(--ease-bounce)",
            transitionDuration: "var(--duration-fast)",
          }}
          aria-label={triggerLabel}
        >
          {selectedOrgAccount != null ? (
            <>
              <span
                className="text-[var(--color-text-tertiary)] truncate max-w-[100px]"
                style={{ fontSize: compact ? "12px" : "13px" }}
              >
                {selectedOrgAccount.metadata.organization_name}
              </span>
              <span className="text-[var(--color-text-disabled)]">/</span>
              <span
                className="text-[var(--color-text-primary)] truncate max-w-[120px]"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 700,
                  fontSize: compact ? "12px" : "13px",
                }}
              >
                {selectedOrgAccount.metadata.account_name}
              </span>
            </>
          ) : (
            <span
              className="text-[var(--color-text-disabled)]"
              style={{ fontSize: compact ? "12px" : "13px" }}
            >
              Select account
            </span>
          )}
          <ChevronsUpDown className="size-3 text-[var(--color-text-disabled)] shrink-0 ml-0.5" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="start"
        sideOffset={8}
        className="w-[280px] rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-0 shadow-lg"
      >
        {selectedOrgAccount != null && (
          <>
            <div className="px-4 py-3 bg-[var(--color-surface-muted)]">
              <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] uppercase tracking-wide font-bold">
                Current Account
              </p>
              <div className="flex items-center gap-2.5 mt-1.5">
                <OrgAvatar
                  orgName={selectedOrgAccount.metadata.organization_name}
                  orgId={String(selectedOrgAccount.orgId)}
                  size="md"
                />
                <div className="min-w-0">
                  <p
                    className="text-[var(--text-body-md)] text-[var(--color-text-primary)] truncate"
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 700,
                    }}
                  >
                    {selectedOrgAccount.metadata.account_name}
                  </p>
                  <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] truncate">
                    {selectedOrgAccount.metadata.organization_name}
                  </p>
                </div>
              </div>
            </div>
            <DropdownMenuSeparator className="m-0" />
          </>
        )}

        <div className="py-1.5 max-h-[300px] overflow-y-auto">
          {accountsByOrg.map(({ orgId, orgName, accounts }, orgIndex) => (
            <div key={orgId}>
              {orgIndex > 0 && <DropdownMenuSeparator />}
              <DropdownMenuLabel className="flex items-center gap-2 px-4 py-2 text-[var(--text-caption)] text-[var(--color-text-tertiary)] uppercase tracking-wide font-bold">
                <Building2 className="size-3" />
                {orgName}
              </DropdownMenuLabel>
              <DropdownMenuGroup>
                {accounts.map(({ accountId, accountData }) => {
                  const isActive = selectedOrgAccount?.accountId === accountId;
                  return (
                    <DropdownMenuItem
                      key={accountId}
                      onClick={() => handleSelect(orgId, accountId)}
                      className={cn(
                        "flex items-center gap-3 px-4 py-2.5 cursor-pointer rounded-none transition-colors",
                        isActive && "bg-[var(--color-violet-100)]",
                      )}
                    >
                      <OrgAvatar orgName={orgName} orgId={orgId} />
                      <div className="flex-1 min-w-0">
                        <p
                          className={cn(
                            "text-[var(--text-body-sm)] truncate",
                            isActive
                              ? "text-[var(--color-violet-500)]"
                              : "text-[var(--color-text-primary)]",
                          )}
                          style={{ fontWeight: isActive ? 700 : 500 }}
                        >
                          {accountData.account_name}
                        </p>
                        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] capitalize">
                          {accountData.industry}
                        </p>
                      </div>
                      {isActive && (
                        <Check className="size-4 text-[var(--color-violet-500)] shrink-0" />
                      )}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuGroup>
            </div>
          ))}
        </div>

        <DropdownMenuSeparator className="m-0" />

        <div className="py-1.5">
          <DropdownMenuItem asChild>
            <Link
              to="/settings/organization"
              className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
            >
              <Settings className="size-4" />
              <span className="text-[var(--text-body-sm)]">
                Organization Settings
              </span>
            </Link>
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
