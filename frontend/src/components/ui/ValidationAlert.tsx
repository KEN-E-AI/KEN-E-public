import React from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, AlertCircle, Info, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ValidationMessage, ValidationSeverity } from "@/types/validation";

interface ValidationAlertProps {
  messages: ValidationMessage[];
  className?: string;
  showSeverityBadges?: boolean;
  maxMessages?: number;
}

const severityConfig = {
  error: {
    icon: AlertCircle,
    className: "border-red-500 text-red-700 bg-red-50",
    badgeVariant: "destructive" as const,
  },
  warning: {
    icon: AlertTriangle,
    className: "border-yellow-500 text-yellow-700 bg-yellow-50",
    badgeVariant: "secondary" as const,
  },
  info: {
    icon: Info,
    className: "border-blue-500 text-blue-700 bg-blue-50",
    badgeVariant: "outline" as const,
  },
} as const;

export const ValidationAlert: React.FC<ValidationAlertProps> = ({
  messages,
  className,
  showSeverityBadges = true,
  maxMessages = 5,
}) => {
  if (messages.length === 0) return null;

  // Group messages by severity
  const messagesBySeverity = messages.reduce(
    (acc, message) => {
      const severity = message.severity || "info";
      if (!acc[severity]) acc[severity] = [];
      acc[severity].push(message);
      return acc;
    },
    {} as Record<ValidationSeverity, ValidationMessage[]>,
  );

  // Order by severity (errors first, then warnings, then info)
  const orderedSeverities: ValidationSeverity[] = ["error", "warning", "info"];
  const displayMessages: ValidationMessage[] = [];

  orderedSeverities.forEach((severity) => {
    const severityMessages = messagesBySeverity[severity] || [];
    displayMessages.push(
      ...severityMessages.slice(0, maxMessages - displayMessages.length),
    );
  });

  const remainingCount = messages.length - displayMessages.length;

  return (
    <div className={cn("space-y-2", className)}>
      {orderedSeverities.map((severity) => {
        const severityMessages = messagesBySeverity[severity] || [];
        if (severityMessages.length === 0) return null;

        const config = severityConfig[severity];
        const Icon = config.icon;

        return (
          <Alert key={severity} className={cn(config.className, "text-sm")}>
            <Icon className="h-4 w-4" />
            <AlertDescription>
              <div className="space-y-1">
                {severityMessages
                  .slice(0, maxMessages)
                  .map((message, index) => (
                    <div key={index} className="flex items-start gap-2">
                      {showSeverityBadges && (
                        <Badge
                          variant={config.badgeVariant}
                          className="text-xs capitalize shrink-0"
                        >
                          {severity}
                        </Badge>
                      )}
                      <span className="text-sm">{message.message}</span>
                    </div>
                  ))}
              </div>
            </AlertDescription>
          </Alert>
        );
      })}

      {remainingCount > 0 && (
        <Alert className="border-gray-300 text-gray-600 bg-gray-50">
          <Info className="h-4 w-4" />
          <AlertDescription>
            <span className="text-sm">
              +{remainingCount} more validation message
              {remainingCount > 1 ? "s" : ""}
            </span>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};

// Simplified component for single severity
interface ValidationMessageListProps {
  messages: string[];
  severity: ValidationSeverity;
  title?: string;
  className?: string;
}

export const ValidationMessageList: React.FC<ValidationMessageListProps> = ({
  messages,
  severity,
  title,
  className,
}) => {
  if (messages.length === 0) return null;

  const config = severityConfig[severity];
  const Icon = config.icon;

  return (
    <Alert className={cn(config.className, className)}>
      <Icon className="h-4 w-4" />
      <AlertDescription>
        {title && <div className="font-medium mb-2">{title}</div>}
        <ul className="space-y-1 text-sm">
          {messages.map((message, index) => (
            <li key={index} className="flex items-start">
              <span className="mr-2">•</span>
              <span>{message}</span>
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
};

// Success message component
interface ValidationSuccessProps {
  message?: string;
  className?: string;
}

export const ValidationSuccess: React.FC<ValidationSuccessProps> = ({
  message = "All validations passed!",
  className,
}) => {
  return (
    <Alert
      className={cn("border-green-500 text-green-700 bg-green-50", className)}
    >
      <CheckCircle className="h-4 w-4" />
      <AlertDescription>
        <span className="text-sm font-medium">{message}</span>
      </AlertDescription>
    </Alert>
  );
};
