import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, RefreshCw } from "lucide-react";
import { forceCleanLogout } from "@/utils/authRecovery";

type AppErrorBoundaryInnerProps = {
  children: ReactNode;
};

type AppErrorBoundaryInnerState = {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
};

class AppErrorBoundaryInner extends Component<
  AppErrorBoundaryInnerProps,
  AppErrorBoundaryInnerState
> {
  constructor(props: AppErrorBoundaryInnerProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): AppErrorBoundaryInnerState {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ error, errorInfo });
  }

  handleReset = () => {
    window.location.reload();
  };

  handleClearAndReset = async () => {
    try {
      localStorage.clear();
      window.location.reload();
    } catch {
      window.location.reload();
    }
  };

  handleFullReset = async () => {
    try {
      await forceCleanLogout();
    } catch {
      localStorage.clear();
      window.location.href = "/auth/signin";
    }
  };

  render() {
    if (this.state.hasError) {
      const isProduction = import.meta.env.VITE_ENVIRONMENT === "production";

      return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-secondary)] p-4">
          <Card className="max-w-2xl w-full">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-red-600">
                <AlertCircle className="h-6 w-6" />
                Something went wrong
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-[var(--color-text-secondary)]">
                {isProduction
                  ? "We encountered an unexpected error. This might be related to your account or organization data."
                  : "An error occurred in the application. This could be due to corrupted local data or deleted entities."}
              </p>

              {!isProduction && this.state.error && (
                <details className="bg-[var(--color-surface-muted)] p-4 rounded-[var(--radius-md)] text-sm text-[var(--color-text-secondary)]">
                  <summary className="cursor-pointer font-semibold">
                    Error Details
                  </summary>
                  <p className="mt-2 font-mono text-xs break-all">
                    {this.state.error.message}
                  </p>
                  {this.state.errorInfo && (
                    <pre className="mt-2 overflow-auto max-h-40 text-xs">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  )}
                </details>
              )}

              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={this.handleReset}
                  variant="default"
                  className="flex items-center gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  Try Again
                </Button>
                <Button
                  onClick={this.handleClearAndReset}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  Clear Cache &amp; Reload
                </Button>
                <Button
                  onClick={this.handleFullReset}
                  variant="destructive"
                  className="flex items-center gap-2"
                >
                  Sign Out &amp; Reset
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export function AppErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <AppErrorBoundaryInner key={location.pathname}>
      {children}
    </AppErrorBoundaryInner>
  );
}
