import { Building, Users, User, LayoutTemplate } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ScopeBadgeProps {
  scope: "organization" | "account" | "user" | "template" | "system";
  inherited?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const ScopeBadge = ({
  scope,
  inherited = false,
  size = "md",
  className,
}: ScopeBadgeProps) => {
  const scopeConfig = {
    organization: {
      variant: "outline" as const,
      icon: Building,
      label: "Organization",
      color:
        "border-brand-light-blue/40 text-brand-dark-blue bg-brand-light-blue/20",
    },
    account: {
      variant: "secondary" as const,
      icon: Users,
      label: "Account",
      color:
        "border-brand-light-green/40 text-brand-dark-blue bg-brand-light-green/20",
    },
    user: {
      variant: "default" as const,
      icon: User,
      label: "User",
      color: "border-purple-200 text-purple-700 bg-purple-50",
    },
    template: {
      variant: "outline" as const,
      icon: LayoutTemplate,
      label: "Template",
      color: "border-orange-200 text-orange-700 bg-orange-50",
    },
    system: {
      variant: "outline" as const,
      icon: User,
      label: "System",
      color: "border-[var(--color-border-default)] text-[var(--color-text-secondary)] bg-[var(--color-bg-secondary)]",
    },
  };

  const config = scopeConfig[scope];
  const Icon = config.icon;

  const sizeClasses = {
    sm: "text-xs px-1.5 py-0.5",
    md: "text-xs px-2 py-1",
    lg: "text-sm px-2.5 py-1.5",
  };

  const iconSizes = {
    sm: "h-2.5 w-2.5",
    md: "h-3 w-3",
    lg: "h-3.5 w-3.5",
  };

  return (
    <Badge
      variant={config.variant}
      className={cn(
        "flex items-center gap-1 font-medium",
        config.color,
        sizeClasses[size],
        inherited && "opacity-75",
        className,
      )}
    >
      <Icon className={iconSizes[size]} />
      {config.label}
      {inherited && (
        <span className="text-xs opacity-75 ml-1">(inherited)</span>
      )}
    </Badge>
  );
};

interface ScopeIndicatorProps {
  scope: "organization" | "account" | "user" | "template" | "system";
  source?: string;
  inherited?: boolean;
  showTooltip?: boolean;
}

export const ScopeIndicator = ({
  scope,
  source,
  inherited = false,
  showTooltip = true,
}: ScopeIndicatorProps) => {
  const badge = <ScopeBadge scope={scope} inherited={inherited} size="sm" />;

  if (!showTooltip) {
    return badge;
  }

  return (
    <div
      className="flex items-center gap-1"
      title={source || `This setting is configured at the ${scope} level`}
    >
      {badge}
      {source && (
        <span className="text-xs text-[var(--color-text-tertiary)] hidden sm:inline">{source}</span>
      )}
    </div>
  );
};

interface InheritanceChainProps {
  chain: Array<{
    scope: "organization" | "account" | "user" | "template" | "system";
    value: any;
    source?: string;
  }>;
  currentScope: string;
  className?: string;
}

export const InheritanceChain = ({
  chain,
  currentScope,
  className,
}: InheritanceChainProps) => {
  if (chain.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-1", className)}>
      <span className="text-xs text-[var(--color-text-tertiary)] mr-1">Inheritance:</span>
      {chain.map((item, index) => (
        <div key={index} className="flex items-center">
          <ScopeIndicator
            scope={item.scope}
            source={item.source}
            inherited={item.scope !== currentScope}
            showTooltip={false}
          />
          {index < chain.length - 1 && (
            <span className="text-xs text-[var(--color-text-disabled)] mx-1">→</span>
          )}
        </div>
      ))}
    </div>
  );
};
