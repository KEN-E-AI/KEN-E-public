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
        <Clock className={cn(iconSizes[size], "text-blue-500 animate-spin")} />
      );
    if (hasUnsavedChanges)
      return (
        <AlertTriangle className={cn(iconSizes[size], "text-yellow-600")} />
      );
    return <CheckCircle className={cn(iconSizes[size], "text-green-600")} />;
  };

  const getStatusText = () => {
    if (isLoading) return "Saving...";
    if (hasUnsavedChanges) return "Unsaved changes";
    return "All changes saved";
  };

  const getStatusColor = () => {
    if (isLoading) return "bg-blue-50 text-blue-700 border-blue-200";
    if (hasUnsavedChanges)
      return "bg-yellow-50 text-yellow-700 border-yellow-200";
    return "bg-green-50 text-green-700 border-green-200";
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
      <Alert className={cn("border-yellow-200 bg-yellow-50", className)}>
        <AlertTriangle className="h-4 w-4 text-yellow-600" />
        <AlertDescription className="text-yellow-800">
          <div className="flex items-center justify-between">
            <span>{getStatusText()}</span>
            <div className="flex items-center gap-2 ml-4">
              {onSave && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onSave}
                  disabled={saveDisabled || isLoading}
                  className="h-7 px-3 text-xs bg-yellow-100 border-yellow-300 text-yellow-800 hover:bg-yellow-200"
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
                  className="h-7 px-3 text-xs bg-yellow-100 border-yellow-300 text-yellow-800 hover:bg-yellow-200"
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
                  <p className="text-sm text-gray-600 mt-1">
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
          <span className="text-sm text-gray-500">
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
          <Clock className="h-4 w-4 text-blue-500 animate-spin" />
        ) : (
          <CheckCircle className="h-4 w-4 text-green-500" />
        )}
        <span className="text-gray-600">
          {isAutoSaving ? "Auto-saving..." : "Auto-saved"}
        </span>
        {lastAutoSaved && (
          <span className="text-gray-500">{lastAutoSaved}</span>
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
      return { icon: Clock, text: "Saving...", color: "text-blue-600" };
    if (hasErrors)
      return { icon: XCircle, text: "Has errors", color: "text-red-600" };
    if (isDirty)
      return {
        icon: AlertTriangle,
        text: "Unsaved changes",
        color: "text-yellow-600",
      };
    return {
      icon: CheckCircle,
      text: "All changes saved",
      color: "text-green-600",
    };
  };

  const { icon: Icon, text, color } = getFormStatus();

  return (
    <div
      className={cn(
        "flex items-center justify-between p-3 bg-gray-50 rounded-lg",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", color)} />
        <span className="text-sm font-medium">{text}</span>
        {lastSaved && (
          <span className="text-xs text-gray-500">
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
