import React from "react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Asterisk, Info, AlertCircle } from "lucide-react";
import { ScopeBadge } from "../guidance/ScopeBadge";
import { cn } from "@/lib/utils";

interface RequiredIndicatorProps {
  required: boolean;
  scope?: "organization" | "account" | "user" | "template" | "system";
  size?: "sm" | "md" | "lg";
  variant?: "asterisk" | "badge" | "subtle";
  label?: string;
  tooltip?: string;
  className?: string;
}

export const RequiredIndicator = ({
  required,
  scope,
  size = "md",
  variant = "asterisk",
  label,
  tooltip,
  className,
}: RequiredIndicatorProps) => {
  const sizeClasses = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-base",
  };

  const iconSizes = {
    sm: "h-3 w-3",
    md: "h-4 w-4",
    lg: "h-5 w-5",
  };

  const renderIndicator = () => {
    if (!required) {
      if (variant === "badge") {
        return (
          <Badge
            variant="outline"
            className={cn("text-[var(--color-text-tertiary)] border-[var(--color-border-default)]", sizeClasses[size])}
          >
            Optional
          </Badge>
        );
      }
      return null;
    }

    switch (variant) {
      case "asterisk":
        return (
          <span
            className={cn(
              "text-red-500 font-medium",
              sizeClasses[size],
              className,
            )}
          >
            *
          </span>
        );

      case "badge":
        return (
          <Badge
            variant="outline"
            className={cn(
              "text-red-600 border-red-300 bg-red-50",
              sizeClasses[size],
            )}
          >
            <Asterisk className={cn(iconSizes[size], "mr-1")} />
            {label || "Required"}
          </Badge>
        );

      case "subtle":
        return (
          <div className={cn("flex items-center gap-1", className)}>
            <AlertCircle className={cn(iconSizes[size], "text-red-500")} />
            <span className={cn("text-red-600", sizeClasses[size])}>
              {label || "Required"}
            </span>
          </div>
        );

      default:
        return (
          <span
            className={cn(
              "text-red-500 font-medium",
              sizeClasses[size],
              className,
            )}
          >
            *
          </span>
        );
    }
  };

  const content = (
    <div className="flex items-center gap-2">
      {renderIndicator()}
      {scope && <ScopeBadge scope={scope} size={size === "lg" ? "md" : "sm"} />}
    </div>
  );

  if (tooltip) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{content}</TooltipTrigger>
          <TooltipContent>
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return content;
};

interface FieldRequiredIndicatorProps {
  required: boolean;
  fieldName: string;
  scope?: "organization" | "account" | "user" | "template" | "system";
  className?: string;
}

export const FieldRequiredIndicator = ({
  required,
  fieldName,
  scope,
  className,
}: FieldRequiredIndicatorProps) => {
  const tooltip = required
    ? `${fieldName} is required for ${scope || "this"} configuration`
    : `${fieldName} is optional for ${scope || "this"} configuration`;

  return (
    <RequiredIndicator
      required={required}
      scope={scope}
      size="sm"
      variant="asterisk"
      tooltip={tooltip}
      className={className}
    />
  );
};

interface RequiredFieldsOverviewProps {
  fields: Array<{
    name: string;
    required: boolean;
    completed: boolean;
    scope?: "organization" | "account" | "user" | "template" | "system";
  }>;
  className?: string;
}

export const RequiredFieldsOverview = ({
  fields,
  className,
}: RequiredFieldsOverviewProps) => {
  const requiredFields = fields.filter((field) => field.required);
  const completedRequired = requiredFields.filter((field) => field.completed);
  const optionalFields = fields.filter((field) => !field.required);
  const completedOptional = optionalFields.filter((field) => field.completed);

  const requiredProgress =
    requiredFields.length > 0
      ? (completedRequired.length / requiredFields.length) * 100
      : 100;

  const optionalProgress =
    optionalFields.length > 0
      ? (completedOptional.length / optionalFields.length) * 100
      : 0;

  return (
    <div className={cn("space-y-4", className)}>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RequiredIndicator required={true} variant="subtle" size="sm" />
              <span className="text-sm font-medium">Required Fields</span>
            </div>
            <span className="text-sm text-[var(--color-text-tertiary)]">
              {completedRequired.length}/{requiredFields.length}
            </span>
          </div>
          <div className="w-full bg-red-100 rounded-full h-2">
            <div
              className="bg-red-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${requiredProgress}%` }}
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-[var(--color-text-tertiary)]" />
              <span className="text-sm font-medium">Optional Fields</span>
            </div>
            <span className="text-sm text-[var(--color-text-tertiary)]">
              {completedOptional.length}/{optionalFields.length}
            </span>
          </div>
          <div className="w-full bg-[var(--color-bg-elevated)] rounded-full h-2">
            <div
              className="bg-[var(--color-border-strong)] h-2 rounded-full transition-all duration-300"
              style={{ width: `${optionalProgress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-medium text-[var(--color-text-primary)]">Field Status</h4>
        <div className="grid gap-2">
          {fields.map((field) => (
            <div
              key={field.name}
              className="flex items-center justify-between p-2 bg-[var(--color-bg-secondary)] rounded"
            >
              <div className="flex items-center gap-2">
                <RequiredIndicator
                  required={field.required}
                  scope={field.scope}
                  size="sm"
                  variant="asterisk"
                />
                <span className="text-sm">{field.name}</span>
              </div>
              <div className="flex items-center gap-2">
                {field.scope && <ScopeBadge scope={field.scope} size="sm" />}
                <Badge
                  variant={field.completed ? "default" : "outline"}
                  className={cn(
                    "text-xs",
                    field.completed
                      ? "bg-brand-light-green/30 text-brand-dark-blue border-brand-light-green/40"
                      : "bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-[var(--color-border-default)]",
                  )}
                >
                  {field.completed ? "Completed" : "Pending"}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
