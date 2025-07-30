import * as React from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface LoadingOverlayProps {
  isLoading: boolean;
  message?: string;
  subMessage?: string;
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
      className,
      variant = "local",
    },
    ref,
  ) => {
    if (!isLoading) return null;

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
        <div className="flex flex-col items-center space-y-4 rounded-lg bg-card p-6 shadow-lg">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <div className="text-center">
            <p className="text-sm font-medium">{message}</p>
            {subMessage && (
              <p className="mt-1 text-xs text-muted-foreground">{subMessage}</p>
            )}
          </div>
        </div>
      </div>
    );
  },
);

LoadingOverlay.displayName = "LoadingOverlay";
