import React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuGroup,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import {
  Building2,
  Users,
  User,
  ArrowRight,
  Plus,
  Settings,
  ChevronDown,
  ExternalLink,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { PermissionCheck } from "./PermissionAwareContainer";
import { cn } from "@/lib/utils";

export type ContextualActionType =
  | "switch_organization"
  | "create_organization"
  | "manage_organization"
  | "switch_account"
  | "create_account"
  | "manage_account"
  | "switch_user"
  | "manage_user"
  | "view_settings"
  | "custom";

interface ActionConfig {
  id: string;
  type: ContextualActionType;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  variant?:
    | "default"
    | "outline"
    | "secondary"
    | "destructive"
    | "ghost"
    | "link";
  size?: "sm" | "md" | "lg";
  route?: string;
  onClick?: () => void;
  requiredPermission?: string;
  requiredRole?: "admin" | "member" | "viewer";
  showInDropdown?: boolean;
  disabled?: boolean;
  external?: boolean;
  badge?: string;
  className?: string;
}

interface ContextualActionBarProps {
  context: "organization" | "account" | "user" | "settings";
  actions: ActionConfig[];
  primaryAction?: ActionConfig;
  dropdownLabel?: string;
  className?: string;
  onActionClick?: (action: ActionConfig) => void;
}

export const ContextualActionBar = ({
  context,
  actions,
  primaryAction,
  dropdownLabel = "More Actions",
  className,
  onActionClick,
}: ContextualActionBarProps) => {
  const navigate = useNavigate();
  const { selectedOrgAccount } = useAuth();

  const handleActionClick = (action: ActionConfig) => {
    if (onActionClick) {
      onActionClick(action);
    }

    if (action.onClick) {
      action.onClick();
      return;
    }

    if (action.route) {
      if (action.external) {
        window.open(action.route, "_blank");
      } else {
        navigate(action.route);
      }
    }
  };

  const renderActionButton = (action: ActionConfig, isDropdown = false) => {
    const IconComponent = action.icon;
    const buttonContent = (
      <>
        {IconComponent && <IconComponent className="h-4 w-4" />}
        {action.label}
        {action.badge && (
          <Badge variant="secondary" className="ml-2 text-xs">
            {action.badge}
          </Badge>
        )}
        {action.external && <ExternalLink className="h-3 w-3 ml-1" />}
      </>
    );

    if (isDropdown) {
      return (
        <DropdownMenuItem
          key={action.id}
          onClick={() => handleActionClick(action)}
          disabled={action.disabled}
          className={cn("flex items-center gap-2", action.className)}
        >
          {buttonContent}
        </DropdownMenuItem>
      );
    }

    return (
      <Button
        key={action.id}
        variant={action.variant || "outline"}
        size={action.size || "sm"}
        onClick={() => handleActionClick(action)}
        disabled={action.disabled}
        className={cn("flex items-center gap-2", action.className)}
      >
        {buttonContent}
      </Button>
    );
  };

  const renderActionWithPermission = (
    action: ActionConfig,
    isDropdown = false,
  ) => {
    if (action.requiredPermission || action.requiredRole) {
      return (
        <PermissionCheck
          key={action.id}
          requiredPermission={action.requiredPermission || ""}
          requiredRole={action.requiredRole || "member"}
        >
          {(hasPermission) => {
            if (!hasPermission) return null;
            return renderActionButton(action, isDropdown);
          }}
        </PermissionCheck>
      );
    }

    return renderActionButton(action, isDropdown);
  };

  const primaryActions = actions.filter((action) => !action.showInDropdown);
  const dropdownActions = actions.filter((action) => action.showInDropdown);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Primary Action */}
      {primaryAction && renderActionWithPermission(primaryAction)}

      {/* Primary Actions */}
      {primaryActions.map((action) => renderActionWithPermission(action))}

      {/* Dropdown Actions */}
      {dropdownActions.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              {dropdownLabel}
              <ChevronDown className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel>
              {context === "organization" && "Organization Actions"}
              {context === "account" && "Account Actions"}
              {context === "user" && "User Actions"}
              {context === "settings" && "Settings Actions"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              {dropdownActions.map((action) =>
                renderActionWithPermission(action, true),
              )}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
};

// Pre-configured action sets for common contexts
export const getOrganizationActions = (orgId?: string): ActionConfig[] => [
  {
    id: "switch_org",
    type: "switch_organization",
    label: "Switch Organization",
    icon: Building2,
    route: "/organization-selection",
    variant: "outline",
    showInDropdown: true,
  },
  {
    id: "create_org",
    type: "create_organization",
    label: "Create Organization",
    icon: Plus,
    route: "/create-organization",
    variant: "outline",
    showInDropdown: true,
    requiredRole: "admin",
  },
  {
    id: "manage_org",
    type: "manage_organization",
    label: "Manage Organization",
    icon: Settings,
    route: "/settings/organization",
    variant: "default",
    requiredRole: "admin",
  },
];

export const getAccountActions = (accountId?: string): ActionConfig[] => [
  {
    id: "switch_account",
    type: "switch_account",
    label: "Switch Account",
    icon: Users,
    route: "/organization-selection",
    variant: "outline",
  },
  {
    id: "create_account",
    type: "create_account",
    label: "Create Account",
    icon: Plus,
    route: "/settings/organization?openCreateAccount=true",
    variant: "default",
    requiredRole: "admin",
  },
  {
    id: "manage_account",
    type: "manage_account",
    label: "Manage Account",
    icon: Settings,
    route: accountId
      ? `/settings/account/${accountId}`
      : "/settings/organization",
    variant: "outline",
    showInDropdown: true,
    requiredRole: "member",
  },
];

export const getUserActions = (userId?: string): ActionConfig[] => [
  {
    id: "manage_user",
    type: "manage_user",
    label: "User Settings",
    icon: User,
    route: "/settings/user",
    variant: "outline",
  },
  {
    id: "view_profile",
    type: "custom",
    label: "View Profile",
    icon: User,
    route: userId ? `/profile/${userId}` : "/profile",
    variant: "outline",
    showInDropdown: true,
  },
];

interface QuickActionBarProps {
  context: "organization" | "account" | "user";
  className?: string;
  onActionClick?: (action: ActionConfig) => void;
}

export const QuickActionBar = ({
  context,
  className,
  onActionClick,
}: QuickActionBarProps) => {
  const { selectedOrgAccount } = useAuth();

  const getActionsForContext = () => {
    switch (context) {
      case "organization":
        return getOrganizationActions(selectedOrgAccount?.orgId);
      case "account":
        return getAccountActions(selectedOrgAccount?.accountId);
      case "user":
        return getUserActions();
      default:
        return [];
    }
  };

  const actions = getActionsForContext();

  return (
    <ContextualActionBar
      context={context}
      actions={actions}
      className={className}
      onActionClick={onActionClick}
    />
  );
};
