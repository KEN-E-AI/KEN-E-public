import React from "react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import {
  CheckCircle,
  AlertCircle,
  Clock,
  AlertTriangle,
  Info,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type ConfigurationStatus =
  | "complete"
  | "warning"
  | "incomplete"
  | "error"
  | "pending";

interface ConfigurationStatusBadgeProps {
  status: ConfigurationStatus;
  completedSteps: number;
  totalSteps: number;
  requiredSteps?: number;
  lastUpdated?: string;
  showDetails?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const ConfigurationStatusBadge = ({
  status,
  completedSteps,
  totalSteps,
  requiredSteps = totalSteps,
  lastUpdated,
  showDetails = false,
  size = "md",
  className,
}: ConfigurationStatusBadgeProps) => {
  const getStatusConfig = () => {
    switch (status) {
      case "complete":
        return {
          icon: CheckCircle,
          label: "Complete",
          color: "bg-green-50 text-green-700 border-green-200",
          iconColor: "text-green-600",
        };
      case "warning":
        return {
          icon: AlertTriangle,
          label: "Needs Attention",
          color: "bg-yellow-50 text-yellow-700 border-yellow-200",
          iconColor: "text-yellow-600",
        };
      case "incomplete":
        return {
          icon: Clock,
          label: "In Progress",
          color: "bg-blue-50 text-blue-700 border-blue-200",
          iconColor: "text-blue-600",
        };
      case "error":
        return {
          icon: XCircle,
          label: "Error",
          color: "bg-red-50 text-red-700 border-red-200",
          iconColor: "text-red-600",
        };
      case "pending":
        return {
          icon: Info,
          label: "Pending",
          color: "bg-gray-50 text-gray-700 border-gray-200",
          iconColor: "text-gray-600",
        };
      default:
        return {
          icon: Clock,
          label: "Unknown",
          color: "bg-gray-50 text-gray-700 border-gray-200",
          iconColor: "text-gray-600",
        };
    }
  };

  const { icon: Icon, label, color, iconColor } = getStatusConfig();
  const progress = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;
  const requiredProgress =
    totalSteps > 0
      ? (Math.min(completedSteps, requiredSteps) / requiredSteps) * 100
      : 0;

  const sizeClasses = {
    sm: "text-xs px-2 py-1",
    md: "text-sm px-2.5 py-1.5",
    lg: "text-base px-3 py-2",
  };

  const iconSizes = {
    sm: "h-3 w-3",
    md: "h-4 w-4",
    lg: "h-5 w-5",
  };

  if (showDetails) {
    return (
      <Card className={cn("w-full", className)}>
        <CardContent className="pt-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Badge
                className={cn(
                  "flex items-center gap-1.5",
                  color,
                  sizeClasses[size],
                )}
              >
                <Icon className={cn(iconSizes[size], iconColor)} />
                {label}
              </Badge>
              <span className="text-sm text-gray-600">
                {completedSteps}/{totalSteps} steps
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Overall Progress</span>
                <span className="font-medium">{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} className="h-2" />

              {requiredSteps < totalSteps && (
                <>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Required Steps</span>
                    <span className="font-medium">
                      {Math.round(requiredProgress)}%
                    </span>
                  </div>
                  <Progress
                    value={requiredProgress}
                    className="h-2 bg-orange-100"
                  >
                    <div
                      className="h-full bg-orange-500 transition-all duration-300"
                      style={{ width: `${requiredProgress}%` }}
                    />
                  </Progress>
                </>
              )}
            </div>

            {lastUpdated && (
              <p className="text-xs text-gray-500">
                Last updated: {lastUpdated}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Badge
      className={cn(
        "flex items-center gap-1.5",
        color,
        sizeClasses[size],
        className,
      )}
    >
      <Icon className={cn(iconSizes[size], iconColor)} />
      {label}
      {(size === "md" || size === "lg") && (
        <span className="ml-1 opacity-75">
          {completedSteps}/{totalSteps}
        </span>
      )}
    </Badge>
  );
};

interface ConfigurationOverviewProps {
  sections: Array<{
    id: string;
    title: string;
    status: ConfigurationStatus;
    completedSteps: number;
    totalSteps: number;
    requiredSteps?: number;
    lastUpdated?: string;
    description?: string;
  }>;
  className?: string;
}

export const ConfigurationOverview = ({
  sections,
  className,
}: ConfigurationOverviewProps) => {
  const totalCompleted = sections.reduce(
    (sum, section) => sum + section.completedSteps,
    0,
  );
  const totalSteps = sections.reduce(
    (sum, section) => sum + section.totalSteps,
    0,
  );
  const totalRequired = sections.reduce(
    (sum, section) => sum + (section.requiredSteps || section.totalSteps),
    0,
  );
  const totalRequiredCompleted = sections.reduce(
    (sum, section) =>
      sum +
      Math.min(
        section.completedSteps,
        section.requiredSteps || section.totalSteps,
      ),
    0,
  );

  const overallProgress =
    totalSteps > 0 ? (totalCompleted / totalSteps) * 100 : 0;
  const requiredProgress =
    totalRequired > 0 ? (totalRequiredCompleted / totalRequired) * 100 : 0;

  const getOverallStatus = (): ConfigurationStatus => {
    const hasErrors = sections.some((section) => section.status === "error");
    const hasWarnings = sections.some(
      (section) => section.status === "warning",
    );
    const allComplete = sections.every(
      (section) => section.status === "complete",
    );

    if (hasErrors) return "error";
    if (allComplete) return "complete";
    if (hasWarnings) return "warning";
    return "incomplete";
  };

  return (
    <div className={cn("space-y-4", className)}>
      <Card>
        <CardContent className="pt-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium">Configuration Overview</h3>
              <ConfigurationStatusBadge
                status={getOverallStatus()}
                completedSteps={totalCompleted}
                totalSteps={totalSteps}
                requiredSteps={totalRequired}
                size="md"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Overall Progress</span>
                  <span className="font-medium">
                    {Math.round(overallProgress)}%
                  </span>
                </div>
                <Progress value={overallProgress} className="h-2" />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Required Steps</span>
                  <span className="font-medium">
                    {Math.round(requiredProgress)}%
                  </span>
                </div>
                <Progress
                  value={requiredProgress}
                  className="h-2 bg-orange-100"
                >
                  <div
                    className="h-full bg-orange-500 transition-all duration-300"
                    style={{ width: `${requiredProgress}%` }}
                  />
                </Progress>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3">
        {sections.map((section) => (
          <div
            key={section.id}
            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
          >
            <div>
              <h4 className="font-medium text-gray-900">{section.title}</h4>
              {section.description && (
                <p className="text-sm text-gray-600 mt-1">
                  {section.description}
                </p>
              )}
            </div>
            <ConfigurationStatusBadge
              status={section.status}
              completedSteps={section.completedSteps}
              totalSteps={section.totalSteps}
              requiredSteps={section.requiredSteps}
              lastUpdated={section.lastUpdated}
              size="sm"
            />
          </div>
        ))}
      </div>
    </div>
  );
};
