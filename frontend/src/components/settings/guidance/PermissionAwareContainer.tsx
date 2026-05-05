import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Lock, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface PermissionAwareContainerProps {
  requiredPermission: string;
  requiredRole?: "admin" | "member" | "viewer";
  scope?: "organization" | "account" | "user";
  fallbackContent?: React.ReactNode;
  showPermissionHint?: boolean;
  gracefulDegradation?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const PermissionAwareContainer = ({
  requiredPermission,
  requiredRole = "member",
  scope = "organization",
  fallbackContent,
  showPermissionHint = true,
  gracefulDegradation = false,
  children,
  className,
}: PermissionAwareContainerProps) => {
  const { user, selectedOrgAccount, isSuperAdmin } = useAuth();

  // Check if user has required permission
  const hasPermission = React.useMemo(() => {
    // Super admins always have permission
    if (isSuperAdmin) return true;

    if (!user || !selectedOrgAccount) return false;

    const orgId = selectedOrgAccount.orgId;
    const userRole = user.permissions?.organizations?.[orgId];

    if (!userRole) return false;

    // Role hierarchy: admin > member > viewer
    const roleHierarchy = {
      admin: 3,
      member: 2,
      viewer: 1,
    };

    const userRoleLevel =
      roleHierarchy[userRole as keyof typeof roleHierarchy] || 0;
    const requiredRoleLevel = roleHierarchy[requiredRole] || 0;

    return userRoleLevel >= requiredRoleLevel;
  }, [user, selectedOrgAccount, requiredRole, isSuperAdmin]);

  // If user has permission, render children normally
  if (hasPermission) {
    return <div className={className}>{children}</div>;
  }

  // If graceful degradation is enabled, show read-only version
  if (gracefulDegradation) {
    return (
      <div className={cn("relative", className)}>
        <div className="opacity-60 pointer-events-none select-none">
          {children}
        </div>
        <div className="absolute top-2 right-2">
          <Badge
            variant="outline"
            className="bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]"
          >
            <Lock className="h-3 w-3 mr-1" />
            Read-only
          </Badge>
        </div>
      </div>
    );
  }

  // Show fallback content if provided
  if (fallbackContent) {
    return <div className={className}>{fallbackContent}</div>;
  }

  // Show permission hint if enabled
  if (showPermissionHint) {
    return (
      <Alert
        className={cn("border-brand-yellow/40 bg-brand-yellow/20", className)}
      >
        <Info className="h-4 w-4 text-brand-dark-blue" />
        <AlertDescription className="text-brand-dark-blue">
          <div className="flex items-center justify-between">
            <span>
              You need <strong>{requiredRole}</strong> permissions to access
              this section.
            </span>
            <Badge
              variant="outline"
              className="ml-2 text-brand-yellow border-brand-yellow/60"
            >
              {scope} level
            </Badge>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  // Return nothing if no permission and no fallback
  return null;
};

interface PermissionCheckProps {
  requiredPermission: string;
  requiredRole?: "admin" | "member" | "viewer";
  scope?: "organization" | "account" | "user";
  children: (hasPermission: boolean) => React.ReactNode;
}

export const PermissionCheck = ({
  requiredPermission,
  requiredRole = "member",
  scope = "organization",
  children,
}: PermissionCheckProps) => {
  const { user, selectedOrgAccount, isSuperAdmin } = useAuth();

  const hasPermission = React.useMemo(() => {
    // Super admins always have permission
    if (isSuperAdmin) return true;

    if (!user || !selectedOrgAccount) return false;

    const orgId = selectedOrgAccount.orgId;
    const userRole = user.permissions?.organizations?.[orgId];

    if (!userRole) return false;

    const roleHierarchy = {
      admin: 3,
      member: 2,
      viewer: 1,
    };

    const userRoleLevel =
      roleHierarchy[userRole as keyof typeof roleHierarchy] || 0;
    const requiredRoleLevel = roleHierarchy[requiredRole] || 0;

    return userRoleLevel >= requiredRoleLevel;
  }, [user, selectedOrgAccount, requiredRole, isSuperAdmin]);

  return <>{children(hasPermission)}</>;
};

interface ConditionalPermissionProps {
  when: boolean;
  requiredPermission: string;
  requiredRole?: "admin" | "member" | "viewer";
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const ConditionalPermission = ({
  when,
  requiredPermission,
  requiredRole = "member",
  fallback,
  children,
}: ConditionalPermissionProps) => {
  if (!when) {
    return <>{children}</>;
  }

  return (
    <PermissionAwareContainer
      requiredPermission={requiredPermission}
      requiredRole={requiredRole}
      fallbackContent={fallback}
      showPermissionHint={true}
    >
      {children}
    </PermissionAwareContainer>
  );
};
