import { Building, Users, User } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScopeBadge } from "./ScopeBadge";
import { ScopeHelpIcon } from "./ScopeTooltip";
import { cn } from "@/lib/utils";

interface SettingGroup {
  id: string;
  title: string;
  description?: string;
  scope: "organization" | "account" | "user";
  content: React.ReactNode;
  completionStatus?: "complete" | "incomplete" | "warning";
  completedSteps?: number;
  totalSteps?: number;
}

interface HierarchicalSettingsProps {
  settings: SettingGroup[];
  className?: string;
  showProgress?: boolean;
}

export const HierarchicalSettings = ({
  settings,
  className,
  showProgress = false,
}: HierarchicalSettingsProps) => {
  const getScopeStyles = (scope: string) => {
    switch (scope) {
      case "organization":
        return {
          border: "border-brand-light-blue/40",
          background: "bg-brand-light-blue/10",
          indent: "ml-0",
          connector: "border-l-brand-light-blue/60",
        };
      case "account":
        return {
          border: "border-brand-light-green/40",
          background: "bg-brand-light-green/10",
          indent: "ml-6",
          connector: "border-l-green-300",
        };
      case "user":
        return {
          border: "border-purple-200",
          background: "bg-purple-50/30",
          indent: "ml-12",
          connector: "border-l-purple-300",
        };
      default:
        return {
          border: "border-[var(--color-border-default)]",
          background: "bg-[var(--color-bg-secondary)]/30",
          indent: "ml-0",
          connector: "border-l-[var(--color-border-strong)]",
        };
    }
  };

  const getCompletionColor = (status: string) => {
    switch (status) {
      case "complete":
        return "text-brand-light-green";
      case "warning":
        return "text-brand-yellow";
      case "incomplete":
        return "text-red-600";
      default:
        return "text-[var(--color-text-tertiary)]";
    }
  };

  const getCompletionIcon = (status: string) => {
    switch (status) {
      case "complete":
        return "✅";
      case "warning":
        return "⚠️";
      case "incomplete":
        return "❌";
      default:
        return "⚪";
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      {settings.map((group, index) => {
        const styles = getScopeStyles(group.scope);
        const isNotFirst = index > 0;

        return (
          <div key={group.id} className="relative">
            {/* Connector line for hierarchy */}
            {isNotFirst && (
              <div
                className={cn(
                  "absolute left-3 -top-4 h-4 w-0.5 border-l-2 border-dashed",
                  styles.connector,
                )}
              />
            )}

            <Card
              className={cn(
                "transition-all duration-200 hover:shadow-md",
                styles.border,
                styles.background,
                styles.indent,
              )}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      {group.title}
                      <ScopeHelpIcon scope={group.scope} setting={group.id} />
                    </CardTitle>
                    <ScopeBadge scope={group.scope} size="sm" />
                  </div>

                  {showProgress && group.completionStatus && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm">
                        {getCompletionIcon(group.completionStatus)}
                      </span>
                      {group.completedSteps !== undefined &&
                        group.totalSteps !== undefined && (
                          <span
                            className={cn(
                              "text-sm font-medium",
                              getCompletionColor(group.completionStatus),
                            )}
                          >
                            {group.completedSteps}/{group.totalSteps}
                          </span>
                        )}
                    </div>
                  )}
                </div>

                {group.description && (
                  <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
                    {group.description}
                  </p>
                )}
              </CardHeader>

              <CardContent>{group.content}</CardContent>
            </Card>
          </div>
        );
      })}
    </div>
  );
};

interface SettingsSectionProps {
  title: string;
  description?: string;
  scope: "organization" | "account" | "user";
  children: React.ReactNode;
  className?: string;
}

export const SettingsSection = ({
  title,
  description,
  scope,
  children,
  className,
}: SettingsSectionProps) => {
  const styles = getScopeStyles(scope);

  return (
    <div className={cn("space-y-4", className)}>
      <div className={cn("border-l-4 pl-4", styles.connector)}>
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-lg font-semibold">{title}</h3>
          <ScopeBadge scope={scope} size="sm" />
        </div>
        {description && (
          <p className="text-sm text-[var(--color-text-tertiary)] mb-3">
            {description}
          </p>
        )}
      </div>

      {/* The second `getScopeStyles` below doesn't define `indent`; cast
          to read it (will be undefined at runtime, harmless to cn()). */}
      <div className={cn("space-y-4", (styles as { indent?: string }).indent)}>
        {children}
      </div>
    </div>
  );
};

const getScopeStyles = (scope: string) => {
  switch (scope) {
    case "organization":
      return {
        connector: "border-l-blue-400",
      };
    case "account":
      return {
        connector: "border-l-green-400",
      };
    case "user":
      return {
        connector: "border-l-purple-400",
      };
    default:
      return {
        connector: "border-l-[var(--color-border-strong)]",
      };
  }
};

interface ScopeNavigationProps {
  currentScope: "organization" | "account" | "user";
  onScopeChange: (scope: "organization" | "account" | "user") => void;
  className?: string;
}

export const ScopeNavigation = ({
  currentScope,
  onScopeChange,
  className,
}: ScopeNavigationProps) => {
  const scopes = [
    { id: "organization", label: "Organization", icon: Building },
    { id: "account", label: "Account", icon: Users },
    { id: "user", label: "User", icon: User },
  ] as const;

  return (
    <div
      className={cn(
        "flex space-x-1 bg-[var(--color-bg-elevated)] p-1 rounded-lg",
        className,
      )}
    >
      {scopes.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onScopeChange(id)}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            currentScope === id
              ? "bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] shadow-sm"
              : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)]",
          )}
        >
          <Icon className="h-4 w-4" />
          {label}
        </button>
      ))}
    </div>
  );
};
