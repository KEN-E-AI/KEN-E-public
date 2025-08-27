/**
 * UI component for displaying account consistency issues and recovery suggestions
 */

import React from "react";
import { AlertCircle, AlertTriangle, Info, RefreshCw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { ConsistencyCheck, ConsistencyIssue } from "@/lib/consistency";
import {
  getRecoverySuggestions,
  requiresImmediateAttention,
} from "@/lib/consistency";
import { cn } from "@/lib/utils";

interface ConsistencyAlertProps {
  consistencyCheck: ConsistencyCheck;
  onRefresh?: () => void;
  onViewDetails?: (accountId: string) => void;
  className?: string;
}

export function ConsistencyAlert({
  consistencyCheck,
  onRefresh,
  onViewDetails,
  className,
}: ConsistencyAlertProps) {
  if (consistencyCheck.isConsistent) {
    return (
      <Alert className={cn("border-green-200 bg-green-50", className)}>
        <Info className="h-4 w-4 text-green-600" />
        <AlertTitle className="text-green-800">
          All accounts are consistent
        </AlertTitle>
        <AlertDescription className="text-green-700">
          All {consistencyCheck.totalAccounts} accounts have been verified for
          data integrity. Last checked:{" "}
          {new Date(consistencyCheck.lastChecked).toLocaleTimeString()}
        </AlertDescription>
      </Alert>
    );
  }

  const criticalIssues = consistencyCheck.inconsistencies.filter(
    (i) => i.severity === "critical",
  );
  const errorIssues = consistencyCheck.inconsistencies.filter(
    (i) => i.severity === "error",
  );
  const warningIssues = consistencyCheck.inconsistencies.filter(
    (i) => i.severity === "warning",
  );

  const needsAttention = requiresImmediateAttention(
    consistencyCheck.inconsistencies,
  );

  return (
    <div className={cn("space-y-4", className)}>
      {/* Summary Alert */}
      <Alert variant={needsAttention ? "destructive" : "default"}>
        {needsAttention ? (
          <AlertCircle className="h-4 w-4" />
        ) : (
          <AlertTriangle className="h-4 w-4" />
        )}
        <AlertTitle>
          {needsAttention ? "Critical" : "Minor"} account consistency issues
          detected
        </AlertTitle>
        <AlertDescription className="space-y-2">
          <p>
            Found {consistencyCheck.inconsistencies.length} issue(s) across{" "}
            {consistencyCheck.totalAccounts} accounts.
          </p>
          <div className="flex items-center gap-2">
            {criticalIssues.length > 0 && (
              <Badge variant="destructive">
                {criticalIssues.length} Critical
              </Badge>
            )}
            {errorIssues.length > 0 && (
              <Badge variant="secondary">{errorIssues.length} Errors</Badge>
            )}
            {warningIssues.length > 0 && (
              <Badge variant="outline">{warningIssues.length} Warnings</Badge>
            )}
            {onRefresh && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRefresh}
                className="ml-auto"
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                Recheck
              </Button>
            )}
          </div>
        </AlertDescription>
      </Alert>

      {/* Issue Details */}
      {consistencyCheck.inconsistencies.map((issue, index) => (
        <ConsistencyIssueCard
          key={`${issue.accountId}-${index}`}
          issue={issue}
          onViewAccount={onViewDetails}
        />
      ))}
    </div>
  );
}

interface ConsistencyIssueCardProps {
  issue: ConsistencyIssue;
  onViewAccount?: (accountId: string) => void;
}

function ConsistencyIssueCard({
  issue,
  onViewAccount,
}: ConsistencyIssueCardProps) {
  const suggestions = getRecoverySuggestions(issue);

  const getSeverityIcon = (severity: ConsistencyIssue["severity"]) => {
    switch (severity) {
      case "critical":
        return <AlertCircle className="h-4 w-4 text-red-600" />;
      case "error":
        return <AlertTriangle className="h-4 w-4 text-orange-600" />;
      case "warning":
        return <Info className="h-4 w-4 text-yellow-600" />;
    }
  };

  const getSeverityColor = (severity: ConsistencyIssue["severity"]) => {
    switch (severity) {
      case "critical":
        return "border-red-200 bg-red-50";
      case "error":
        return "border-orange-200 bg-orange-50";
      case "warning":
        return "border-yellow-200 bg-yellow-50";
    }
  };

  return (
    <Card className={cn("border-l-4", getSeverityColor(issue.severity))}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {getSeverityIcon(issue.severity)}
            <div>
              <CardTitle className="text-sm font-medium">
                {issue.accountName || `Account ${issue.accountId.slice(0, 8)}`}
              </CardTitle>
              <CardDescription className="text-xs">
                {issue.type.replace("_", " ")} • {issue.severity}
              </CardDescription>
            </div>
          </div>
          {onViewAccount && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewAccount(issue.accountId)}
            >
              View Account
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-sm text-muted-foreground mb-3">{issue.issue}</p>

        {suggestions.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">
              Suggested actions:
            </p>
            <ul className="text-xs text-muted-foreground space-y-1">
              {suggestions.map((suggestion, index) => (
                <li key={index} className="flex items-start gap-2">
                  <span className="text-blue-600 mt-0.5">•</span>
                  <span>{suggestion}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export { ConsistencyIssueCard };
