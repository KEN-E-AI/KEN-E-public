import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertTriangle,
  Save,
  RotateCcw,
  Clock,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface UnsavedChangesIndicatorProps {
  hasUnsavedChanges: boolean;
  isLoading?: boolean;
  lastSaved?: string;
  onSave?: () => void;
  onReset?: () => void;
  saveDisabled?: boolean;
  variant?: "badge" | "alert" | "card" | "inline";
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const UnsavedChangesIndicator = ({
  hasUnsavedChanges,
  isLoading = false,
  lastSaved,
  onSave,
  onReset,
  saveDisabled = false,
  variant = "badge",
  size = "md",
  className,
}: UnsavedChangesIndicatorProps) => {
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

  const buttonSizes = {
    sm: "h-7 px-2 text-xs",
    md: "h-8 px-3 text-sm",
    lg: "h-9 px-4 text-base",
  };

  const getStatusIcon = () => {
    if (isLoading)
      return (
        <Clock
          className={cn(iconSizes[size], "text-brand-medium-blue animate-spin")}
        />
      );
    if (hasUnsavedChanges)
      return (
        <AlertTriangle
          className={cn(iconSizes[size], "text-brand-dark-blue")}
        />
      );
    return (
      <CheckCircle className={cn(iconSizes[size], "text-brand-dark-blue")} />
    );
  };

  const getStatusText = () => {
    if (isLoading) return "Saving...";
    if (hasUnsavedChanges) return "Unsaved changes";
    return "All changes saved";
  };

  const getStatusColor = () => {
    if (isLoading)
      return "bg-brand-light-blue/20 text-brand-dark-blue border-brand-light-blue/40";
    if (hasUnsavedChanges)
      return "bg-brand-yellow/20 text-brand-dark-blue border-brand-yellow/40";
    return "bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40";
  };

  if (variant === "badge") {
    return (
      <Badge
        className={cn(
          "flex items-center gap-1.5",
          getStatusColor(),
          sizeClasses[size],
          className,
        )}
      >
        {getStatusIcon()}
        {getStatusText()}
      </Badge>
    );
  }

  if (variant === "alert") {
    if (!hasUnsavedChanges && !isLoading) return null;

    return (
      <Alert
        className={cn("border-brand-yellow/40 bg-brand-yellow/20", className)}
      >
        <AlertTriangle className="h-4 w-4 text-brand-dark-blue" />
        <AlertDescription className="text-brand-dark-blue">
          <div className="flex items-center justify-between">
            <span>{getStatusText()}</span>
            <div className="flex items-center gap-2 ml-4">
              {onSave && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onSave}
                  disabled={saveDisabled || isLoading}
                  className="h-7 px-3 text-xs bg-brand-yellow/10 border-brand-yellow/60 text-brand-dark-blue hover:bg-brand-yellow/20"
                >
                  <Save className="h-3 w-3 mr-1" />
                  Save
                </Button>
              )}
              {onReset && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onReset}
                  disabled={isLoading}
                  className="h-7 px-3 text-xs bg-brand-yellow/10 border-brand-yellow/60 text-brand-dark-blue hover:bg-brand-yellow/20"
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  if (variant === "card") {
    return (
      <Card className={cn("w-full", className)}>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <div>
                <p className="font-medium">{getStatusText()}</p>
                {lastSaved && (
                  <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
                    Last saved: {lastSaved}
                  </p>
                )}
              </div>
            </div>

            {hasUnsavedChanges && (
              <div className="flex items-center gap-2">
                {onReset && (
                  <Button
                    variant="outline"
                    size={size}
                    onClick={onReset}
                    disabled={isLoading}
                    className={buttonSizes[size]}
                  >
                    <RotateCcw className={cn(iconSizes[size], "mr-2")} />
                    Reset
                  </Button>
                )}
                {onSave && (
                  <Button
                    variant="default"
                    size={size}
                    onClick={onSave}
                    disabled={saveDisabled || isLoading}
                    className={buttonSizes[size]}
                  >
                    <Save className={cn(iconSizes[size], "mr-2")} />
                    Save Changes
                  </Button>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Inline variant (default)
  return (
    <div className={cn("flex items-center justify-between", className)}>
      <div className="flex items-center gap-2">
        {getStatusIcon()}
        <span className={cn("font-medium", sizeClasses[size])}>
          {getStatusText()}
        </span>
        {lastSaved && (
          <span className="text-sm text-[var(--color-text-tertiary)]">
            • Last saved: {lastSaved}
          </span>
        )}
      </div>

      {hasUnsavedChanges && (
        <div className="flex items-center gap-2">
          {onReset && (
            <Button
              variant="outline"
              size={size}
              onClick={onReset}
              disabled={isLoading}
              className={buttonSizes[size]}
            >
              <RotateCcw className={cn(iconSizes[size], "mr-2")} />
              Reset
            </Button>
          )}
          {onSave && (
            <Button
              variant="default"
              size={size}
              onClick={onSave}
              disabled={saveDisabled || isLoading}
              className={buttonSizes[size]}
            >
              <Save className={cn(iconSizes[size], "mr-2")} />
              Save
            </Button>
          )}
        </div>
      )}
    </div>
  );
};

interface AutoSaveIndicatorProps {
  isAutoSaving: boolean;
  lastAutoSaved?: string;
  autoSaveEnabled?: boolean;
  onToggleAutoSave?: () => void;
  className?: string;
}

export const AutoSaveIndicator = ({
  isAutoSaving,
  lastAutoSaved,
  autoSaveEnabled = false,
  onToggleAutoSave,
  className,
}: AutoSaveIndicatorProps) => {
  return (
    <div className={cn("flex items-center gap-3 text-sm", className)}>
      <div className="flex items-center gap-2">
        {isAutoSaving ? (
          <Clock className="h-4 w-4 text-brand-medium-blue animate-spin" />
        ) : (
          <CheckCircle className="h-4 w-4 text-brand-dark-blue" />
        )}
        <span className="text-[var(--color-text-tertiary)]">
          {isAutoSaving ? "Auto-saving..." : "Auto-saved"}
        </span>
        {lastAutoSaved && (
          <span className="text-[var(--color-text-tertiary)]">
            {lastAutoSaved}
          </span>
        )}
      </div>

      {onToggleAutoSave && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleAutoSave}
          className="h-6 px-2 text-xs"
        >
          {autoSaveEnabled ? "Disable" : "Enable"} Auto-save
        </Button>
      )}
    </div>
  );
};

interface FormStateIndicatorProps {
  isDirty: boolean;
  isValid: boolean;
  isSubmitting: boolean;
  hasErrors: boolean;
  lastSaved?: string;
  onSave?: () => void;
  onReset?: () => void;
  className?: string;
}

export const FormStateIndicator = ({
  isDirty,
  isValid,
  isSubmitting,
  hasErrors,
  lastSaved,
  onSave,
  onReset,
  className,
}: FormStateIndicatorProps) => {
  const getFormStatus = () => {
    if (isSubmitting)
      return {
        icon: Clock,
        text: "Saving...",
        color: "text-brand-medium-blue",
      };
    if (hasErrors)
      return { icon: XCircle, text: "Has errors", color: "text-red-600" };
    if (isDirty)
      return {
        icon: AlertTriangle,
        text: "Unsaved changes",
        color: "text-brand-yellow",
      };
    return {
      icon: CheckCircle,
      text: "All changes saved",
      color: "text-brand-light-green",
    };
  };

  const { icon: Icon, text, color } = getFormStatus();

  return (
    <div
      className={cn(
        "flex items-center justify-between p-3 bg-[var(--color-bg-secondary)] rounded-lg",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", color)} />
        <span className="text-sm font-medium">{text}</span>
        {lastSaved && (
          <span className="text-xs text-[var(--color-text-tertiary)]">
            • Last saved: {lastSaved}
          </span>
        )}
      </div>

      {(isDirty || hasErrors) && (
        <div className="flex items-center gap-2">
          {onReset && (
            <Button
              variant="outline"
              size="sm"
              onClick={onReset}
              disabled={isSubmitting}
              className="h-7 px-3 text-xs"
            >
              <RotateCcw className="h-3 w-3 mr-1" />
              Reset
            </Button>
          )}
          {onSave && (
            <Button
              variant="default"
              size="sm"
              onClick={onSave}
              disabled={!isValid || isSubmitting}
              className="h-7 px-3 text-xs"
            >
              <Save className="h-3 w-3 mr-1" />
              Save
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
