import * as React from "react";
import { cn } from "@/lib/utils";
import { Loader2, CheckCircle2, Circle } from "lucide-react";
import { Progress } from "@/components/ui/progress";

export interface ProgressStep {
  name: string;
  status: "pending" | "processing" | "completed";
}

export interface ProgressInfo {
  percentage: number;
  currentStep: number;
  totalSteps: number;
  steps?: ProgressStep[];
}

interface LoadingOverlayProps {
  isLoading: boolean;
  message?: string;
  subMessage?: string;
  progress?: ProgressInfo;
  className?: string;
  variant?: "fullscreen" | "local";
}

export const LoadingOverlay = React.forwardRef<
  HTMLDivElement,
  LoadingOverlayProps
>(
  (
    {
      isLoading,
      message = "Processing...",
      subMessage,
      progress,
      className,
      variant = "local",
    },
    ref,
  ) => {
    if (!isLoading) return null;

    const getStepIcon = (status: string) => {
      switch (status) {
        case "completed":
          return <CheckCircle2 className="h-4 w-4 text-green-500" />;
        case "processing":
          return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
        default:
          return <Circle className="h-4 w-4 text-muted-foreground" />;
      }
    };

    return (
      <div
        ref={ref}
        className={cn(
          "absolute inset-0 z-50 flex items-center justify-center",
          "bg-background/80 backdrop-blur-sm",
          variant === "fullscreen" && "fixed",
          className,
        )}
        aria-busy="true"
        aria-label={message}
      >
        <div
          className={cn(
            "flex flex-col items-center space-y-4 rounded-lg bg-card p-6 shadow-lg",
            progress && "min-w-[400px]",
          )}
        >
          <Loader2 className="h-8 w-8 animate-spin text-primary" />

          <div className="text-center w-full">
            <p className="text-sm font-medium">{message}</p>
            {subMessage && (
              <p className="mt-1 text-xs text-muted-foreground">{subMessage}</p>
            )}
          </div>

          {progress && (
            <div className="w-full space-y-3">
              <Progress value={progress.percentage} className="w-full h-2" />
              <p className="text-xs text-center text-muted-foreground">
                Step {progress.currentStep} of {progress.totalSteps}
              </p>

              {progress.steps && (
                <div className="space-y-2 text-left">
                  {progress.steps.map((step, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 text-xs"
                    >
                      {getStepIcon(step.status)}
                      <span
                        className={cn(
                          step.status === "completed" &&
                            "text-muted-foreground",
                          step.status === "processing" && "font-medium",
                        )}
                      >
                        {step.name}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  },
);

LoadingOverlay.displayName = "LoadingOverlay";
