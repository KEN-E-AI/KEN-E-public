import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import { EntitySelector } from "@/components/ui/entity-selector";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ContextualActionBar,
  getOrganizationActions,
  getAccountActions,
} from "../guidance/ContextualActionBar";
import { Building2, Users, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface EnhancedEntitySelectorProps {
  className?: string;
  onSelectionChange?: (selection: SelectedOrgAccount) => void;
  showUserContext?: boolean;
  showContextualActions?: boolean;
  availableActions?: ("switch" | "create" | "manage")[];
  layout?: "compact" | "card" | "inline";
  showCurrentContext?: boolean;
  onActionClick?: (action: any) => void;
}

export const EnhancedEntitySelector = ({
  className = "",
  onSelectionChange,
  showUserContext = false,
  showContextualActions = true,
  availableActions = ["switch", "create", "manage"],
  layout = "compact",
  showCurrentContext = true,
  onActionClick,
}: EnhancedEntitySelectorProps) => {
  const { selectedOrgAccount } = useAuth();

  const currentOrgName =
    selectedOrgAccount?.metadata?.organization_name || "Organization";
  const currentAccountName =
    selectedOrgAccount?.metadata?.account_name || "Account";

  const getFilteredActions = (baseActions: any[]) => {
    return baseActions.filter((action) => {
      if (availableActions.includes("switch") && action.type.includes("switch"))
        return true;
      if (availableActions.includes("create") && action.type.includes("create"))
        return true;
      if (availableActions.includes("manage") && action.type.includes("manage"))
        return true;
      return false;
    });
  };

  const organizationActions = getFilteredActions(
    getOrganizationActions(selectedOrgAccount?.orgId),
  );
  const accountActions = getFilteredActions(
    getAccountActions(selectedOrgAccount?.accountId),
  );

  if (layout === "card") {
    return (
      <Card className={cn("w-full", className)}>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="text-lg">Current Context</span>
            {showContextualActions && (
              <ContextualActionBar
                context="organization"
                actions={[...organizationActions, ...accountActions]}
                dropdownLabel="Actions"
                onActionClick={onActionClick}
              />
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <EntitySelector
              className="w-full"
              onSelectionChange={onSelectionChange}
              showUserContext={showUserContext}
            />

            {showCurrentContext && selectedOrgAccount && (
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-tertiary)] bg-[var(--color-bg-secondary)] p-3 rounded-lg">
                <Building2 className="h-4 w-4" />
                <span className="font-medium">Active Context:</span>
                <span>{currentOrgName}</span>
                <ArrowRight className="h-3 w-3 text-[var(--color-text-disabled)]" />
                <span>{currentAccountName}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (layout === "inline") {
    return (
      <div className={cn("flex items-center gap-4", className)}>
        <EntitySelector
          className="flex-1"
          onSelectionChange={onSelectionChange}
          showUserContext={showUserContext}
        />
        {showContextualActions && (
          <ContextualActionBar
            context="account"
            actions={[...organizationActions, ...accountActions]}
            dropdownLabel="Actions"
            onActionClick={onActionClick}
          />
        )}
      </div>
    );
  }

  // Compact layout (default)
  return (
    <div className={cn("space-y-3", className)}>
      <EntitySelector
        className="w-full"
        onSelectionChange={onSelectionChange}
        showUserContext={showUserContext}
      />

      {showContextualActions && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-tertiary)]">
            <Building2 className="h-3 w-3" />
            <span>{currentOrgName}</span>
            <ArrowRight className="h-3 w-3 text-[var(--color-text-disabled)]" />
            <span>{currentAccountName}</span>
          </div>
          <ContextualActionBar
            context="account"
            actions={[...organizationActions, ...accountActions]}
            dropdownLabel="Actions"
            onActionClick={onActionClick}
          />
        </div>
      )}
    </div>
  );
};

interface ContextSwitcherProps {
  className?: string;
  onSelectionChange?: (selection: SelectedOrgAccount) => void;
  showQuickActions?: boolean;
  showCurrentPath?: boolean;
}

export const ContextSwitcher = ({
  className,
  onSelectionChange,
  showQuickActions = true,
  showCurrentPath = true,
}: ContextSwitcherProps) => {
  const { selectedOrgAccount } = useAuth();

  const quickActions = [
    ...getOrganizationActions(selectedOrgAccount?.orgId).slice(0, 2),
    ...getAccountActions(selectedOrgAccount?.accountId).slice(0, 2),
  ];

  return (
    <div className={cn("bg-white border rounded-lg p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-[var(--color-text-primary)]">Context</h3>
        {showQuickActions && (
          <ContextualActionBar
            context="settings"
            actions={quickActions}
            dropdownLabel="Quick Actions"
          />
        )}
      </div>

      <EntitySelector
        className="w-full"
        onSelectionChange={onSelectionChange}
        showUserContext={false}
      />

      {showCurrentPath && selectedOrgAccount && (
        <div className="mt-3 pt-3 border-t">
          <div className="flex items-center text-xs text-[var(--color-text-tertiary)]">
            <Building2 className="h-3 w-3 mr-1" />
            <span>{selectedOrgAccount.metadata?.organization_name}</span>
            <ArrowRight className="h-3 w-3 mx-1" />
            <Users className="h-3 w-3 mr-1" />
            <span>{selectedOrgAccount.metadata?.account_name}</span>
          </div>
        </div>
      )}
    </div>
  );
};
