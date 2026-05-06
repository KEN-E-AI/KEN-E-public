import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ValidationResult } from "@/types/validation";

interface ValidationSummaryProps {
  validations: {
    step: string;
    stepNumber: number;
    result: ValidationResult;
    isRequired?: boolean;
  }[];
  canProceed: boolean;
  onFixIssues?: (stepNumber: number) => void;
  className?: string;
  collapsible?: boolean;
}

export const ValidationSummary: React.FC<ValidationSummaryProps> = ({
  validations,
  canProceed,
  onFixIssues,
  className,
  collapsible = true,
}) => {
  const [expandedSteps, setExpandedSteps] = React.useState<Set<number>>(
    new Set(validations.map((v) => v.stepNumber)),
  );

  const toggleStep = (stepNumber: number) => {
    if (!collapsible) return;

    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepNumber)) {
      newExpanded.delete(stepNumber);
    } else {
      newExpanded.add(stepNumber);
    }
    setExpandedSteps(newExpanded);
  };

  const totalErrors = validations.reduce(
    (sum, validation) => sum + validation.result.errors.length,
    0,
  );
  const totalWarnings = validations.reduce(
    (sum, validation) => sum + validation.result.warnings.length,
    0,
  );

  const hasBlockingErrors = validations.some(
    (validation) =>
      !validation.result.isValid && validation.isRequired !== false,
  );

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center justify-between">
          <span className="text-lg">Validation Summary</span>
          <div className="flex items-center gap-2">
            {totalErrors > 0 && (
              <Badge variant="destructive" className="text-xs">
                {totalErrors} error{totalErrors > 1 ? "s" : ""}
              </Badge>
            )}
            {totalWarnings > 0 && (
              <Badge variant="secondary" className="text-xs">
                {totalWarnings} warning{totalWarnings > 1 ? "s" : ""}
              </Badge>
            )}
            {totalErrors === 0 && totalWarnings === 0 && (
              <Badge
                variant="outline"
                className="text-xs text-green-700 bg-green-50"
              >
                All Good!
              </Badge>
            )}
          </div>
        </CardTitle>

        {/* Overall status */}
        <div className="flex items-center gap-2 text-sm">
          {canProceed ? (
            <>
              <CheckCircle className="h-4 w-4 text-green-600" />
              <span className="text-green-700 font-medium">
                Ready to create account
              </span>
            </>
          ) : (
            <>
              <AlertCircle className="h-4 w-4 text-red-600" />
              <span className="text-red-700 font-medium">
                Issues need to be resolved before proceeding
              </span>
            </>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {validations.map((validation, index) => {
          const isExpanded = expandedSteps.has(validation.stepNumber);
          const hasIssues =
            validation.result.errors.length > 0 ||
            validation.result.warnings.length > 0;

          return (
            <div key={validation.stepNumber} className="space-y-2">
              {index > 0 && <Separator />}

              {/* Step header */}
              <div
                className={cn(
                  "flex items-center justify-between p-3 rounded-md transition-colors",
                  collapsible && hasIssues
                    ? "cursor-pointer hover:bg-[var(--color-bg-secondary)]"
                    : "",
                  !validation.result.isValid && validation.isRequired !== false
                    ? "bg-red-50 border border-red-200"
                    : hasIssues
                      ? "bg-yellow-50 border border-yellow-200"
                      : "bg-green-50 border border-green-200",
                )}
                onClick={() => hasIssues && toggleStep(validation.stepNumber)}
              >
                <div className="flex items-center gap-3">
                  {/* Status icon */}
                  {!validation.result.isValid ? (
                    <AlertCircle className="h-5 w-5 text-red-600" />
                  ) : validation.result.warnings.length > 0 ? (
                    <AlertTriangle className="h-5 w-5 text-yellow-600" />
                  ) : (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  )}

                  {/* Step info */}
                  <div>
                    <div className="font-medium text-sm">
                      Step {validation.stepNumber}: {validation.step}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[var(--color-text-tertiary)]">
                      {validation.result.errors.length > 0 && (
                        <span className="text-red-600">
                          {validation.result.errors.length} error
                          {validation.result.errors.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {validation.result.warnings.length > 0 && (
                        <span className="text-yellow-600">
                          {validation.result.warnings.length} warning
                          {validation.result.warnings.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {!hasIssues && (
                        <span className="text-green-600">Valid</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Fix button */}
                  {!validation.result.isValid && onFixIssues && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        onFixIssues(validation.stepNumber);
                      }}
                      className="text-xs"
                    >
                      Fix Issues
                    </Button>
                  )}

                  {/* Expand/collapse icon */}
                  {collapsible && hasIssues && (
                    <div className="p-1">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Step details */}
              {hasIssues && (isExpanded || !collapsible) && (
                <div className="pl-8 pr-3 space-y-3">
                  {/* Errors */}
                  {validation.result.errors.length > 0 && (
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-red-700 flex items-center gap-1">
                        <AlertCircle className="h-4 w-4" />
                        Errors (must be fixed):
                      </div>
                      <ul className="space-y-1">
                        {validation.result.errors.map((error, errorIndex) => (
                          <li key={errorIndex} className="text-sm text-red-600">
                            • {error}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Warnings */}
                  {validation.result.warnings.length > 0 && (
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-yellow-700 flex items-center gap-1">
                        <AlertTriangle className="h-4 w-4" />
                        Warnings (recommended to address):
                      </div>
                      <ul className="space-y-1">
                        {validation.result.warnings.map(
                          (warning, warningIndex) => (
                            <li
                              key={warningIndex}
                              className="text-sm text-yellow-600"
                            >
                              • {warning}
                            </li>
                          ),
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Footer actions */}
        {(totalErrors > 0 || totalWarnings > 0) && (
          <>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <div className="text-[var(--color-text-tertiary)]">
                {hasBlockingErrors
                  ? "Fix all errors to proceed"
                  : "You can proceed, but consider addressing warnings"}
              </div>
              {collapsible && (
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setExpandedSteps(
                        new Set(validations.map((v) => v.stepNumber)),
                      )
                    }
                    className="text-xs"
                  >
                    Expand All
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpandedSteps(new Set())}
                    className="text-xs"
                  >
                    Collapse All
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};
