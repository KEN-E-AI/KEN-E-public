import React, { Component, ErrorInfo, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, RefreshCw } from "lucide-react";
import { forceCleanLogout } from "@/utils/authRecovery";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);

    // Update state with error details
    this.setState({
      error,
      errorInfo,
    });

    // Check if this is an auth-related error
    const isAuthError =
      error.message?.includes("auth") ||
      error.message?.includes("organization") ||
      error.message?.includes("account") ||
      error.stack?.includes("AuthContext") ||
      error.stack?.includes("SelectOrganizationPage");

    if (isAuthError) {
      console.warn("Auth-related error detected, may require state cleanup");
    }
  }

  handleReset = () => {
    // Clear the error state
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });

    // Reload the page
    window.location.reload();
  };

  handleClearAndReset = async () => {
    try {
      // Clear localStorage
      localStorage.clear();

      // Force reload
      window.location.reload();
    } catch (error) {
      console.error("Failed to clear and reset:", error);
      // Try to reload anyway
      window.location.reload();
    }
  };

  handleFullReset = async () => {
    try {
      await forceCleanLogout();
    } catch (error) {
      console.error("Failed to perform full reset:", error);
      // Try basic clear and reload
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
              <p className="text-[var(--color-text-tertiary)]">
                {isProduction
                  ? "We encountered an unexpected error. This might be related to your account or organization data."
                  : "An error occurred in the application. This could be due to corrupted local data or deleted entities."}
              </p>

              {!isProduction && this.state.error && (
                <div className="bg-[var(--color-bg-elevated)] p-4 rounded-md space-y-2">
                  <p className="font-semibold text-sm">Error Details:</p>
                  <p className="text-sm text-[var(--color-text-secondary)] font-mono">
                    {this.state.error.message}
                  </p>
                  {this.state.errorInfo && (
                    <details className="text-xs text-[var(--color-text-tertiary)]">
                      <summary className="cursor-pointer hover:text-[var(--color-text-secondary)]">
                        Component Stack
                      </summary>
                      <pre className="mt-2 overflow-auto max-h-40">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </details>
                  )}
                </div>
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
                  Clear Cache & Reload
                </Button>

                <Button
                  onClick={this.handleFullReset}
                  variant="destructive"
                  className="flex items-center gap-2"
                >
                  Sign Out & Reset
                </Button>
              </div>

              <div className="text-sm text-[var(--color-text-tertiary)] mt-4">
                <p>If the problem persists after trying these options:</p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>Clear your browser's cookies and cache</li>
                  <li>Try using an incognito/private browser window</li>
                  <li>Contact support if you continue to experience issues</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
