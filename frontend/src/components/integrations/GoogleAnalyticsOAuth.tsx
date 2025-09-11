import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { GoogleAnalyticsPropertySelector } from "./GoogleAnalyticsPropertySelector";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  AlertCircle,
  Loader2,
  Link,
  Unlink,
  RefreshCw,
  ExternalLink,
  Settings,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import api from "@/lib/api";

interface GoogleAnalyticsOAuthProps {
  accountId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  isAccountCreation?: boolean; // Flag to indicate this is during account creation
}

export const GoogleAnalyticsOAuth = ({
  accountId,
  isOpen,
  onClose,
  onSuccess,
  isAccountCreation = false,
}: GoogleAnalyticsOAuthProps) => {
  const [status, setStatus] = useState<{
    configured: boolean;
    expired?: boolean;
    userEmail?: string;
    propertyCount?: number;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [showDisconnectDialog, setShowDisconnectDialog] = useState(false);
  const [showPropertySelector, setShowPropertySelector] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen && !isAccountCreation) {
      // Only check status if not during account creation
      checkStatus();
    } else if (isOpen && isAccountCreation) {
      // During account creation, set default status
      setStatus({ configured: false });
      setIsLoading(false);
    }
    
    // Check if we just returned from OAuth and should show property selector
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('oauth_success') === 'google_analytics' && 
        urlParams.get('account') === accountId && 
        urlParams.get('select_properties') === 'true') {
      console.log('[GoogleAnalyticsOAuth] Detected OAuth callback, showing property selector');
      setShowPropertySelector(true);
      // Clear URL params
      const newUrl = window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [isOpen, isAccountCreation, accountId]);

  const checkStatus = async () => {
    setIsLoading(true);
    try {
      const response = await api.get(
        `/api/oauth/status/${accountId}/google-analytics`,
      );
      setStatus({
        configured: response.data.status === "configured",
        expired: response.data.status === "expired",
        userEmail: response.data.user_email,
        propertyCount: response.data.property_count,
      });
    } catch (error) {
      console.error("Failed to check status:", error);
      setStatus({ configured: false });
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    // During account creation, just mark as selected and inform user
    if (isAccountCreation) {
      toast({
        title: "Google Analytics Enabled",
        description:
          "You'll be redirected to connect your Google account after creating the account.",
      });
      if (onSuccess) {
        onSuccess();
      }
      return;
    }

    setIsConnecting(true);
    try {
      // Get authorization URL from backend
      const response = await api.get(
        `/api/oauth/authorize/google-analytics?account_id=${accountId}`,
      );

      // Redirect to Google OAuth
      window.location.href = response.data.auth_url;
    } catch (error: any) {
      toast({
        title: "Connection Failed",
        description:
          error.response?.data?.detail || "Failed to initiate Google OAuth",
        variant: "destructive",
      });
      setIsConnecting(false);
    }
  };

  const handleRefreshToken = async () => {
    setIsLoading(true);
    try {
      await api.post(`/api/oauth/refresh/${accountId}/google-analytics`);
      toast({
        title: "Success",
        description: "Access token refreshed successfully",
      });
      checkStatus();
    } catch (error: any) {
      toast({
        title: "Refresh Failed",
        description: error.response?.data?.detail || "Failed to refresh token",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setIsLoading(true);
    try {
      await api.delete(`/api/oauth/disconnect/${accountId}/google-analytics`);
      toast({
        title: "Success",
        description: "Google Analytics disconnected successfully",
      });
      setStatus({ configured: false });
      setShowDisconnectDialog(false);
      onSuccess?.();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to disconnect",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // If property selector should be shown, show it instead of the main dialog
  if (showPropertySelector) {
    return (
      <GoogleAnalyticsPropertySelector
        accountId={accountId}
        onComplete={(selectedProperties) => {
          console.log('[GoogleAnalyticsOAuth] Properties selected:', selectedProperties);
          setShowPropertySelector(false);
          toast({
            title: "Properties Selected",
            description: `Successfully selected ${selectedProperties.length} ${selectedProperties.length === 1 ? 'property' : 'properties'} for Google Analytics integration.`,
          });
          // Refresh status to show connected state
          checkStatus();
          onSuccess?.();
        }}
        onSkip={() => {
          console.log('[GoogleAnalyticsOAuth] Property selection skipped');
          setShowPropertySelector(false);
          checkStatus();
          onSuccess?.();
        }}
        isAccountCreation={isAccountCreation}
      />
    );
  }

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Google Analytics Integration</DialogTitle>
            <DialogDescription>
              {isAccountCreation
                ? "Enable Google Analytics for your new account"
                : "Connect your Google Analytics account to import data"}
            </DialogDescription>
          </DialogHeader>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-dashboard-gray-500" />
            </div>
          ) : (
            <div className="space-y-4">
              {status?.configured ? (
                <>
                  <Alert className="border-green-500">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <AlertTitle>Connected</AlertTitle>
                    <AlertDescription>
                      Your Google Analytics account is connected
                      {status.userEmail && ` (${status.userEmail})`}
                      {status.propertyCount !== undefined && status.propertyCount > 0 && (
                        <>
                          <br />
                          <span className="text-sm">
                            {status.propertyCount} {status.propertyCount === 1 ? 'property' : 'properties'} selected
                          </span>
                        </>
                      )}
                    </AlertDescription>
                  </Alert>

                  {status.expired && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>Token Expired</AlertTitle>
                      <AlertDescription>
                        Your access token has expired. Please refresh it to
                        continue using the integration.
                      </AlertDescription>
                    </Alert>
                  )}

                  <div className="flex gap-2">
                    {status.expired && (
                      <Button
                        onClick={handleRefreshToken}
                        disabled={isLoading}
                        className="flex-1"
                      >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Refresh Token
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      onClick={() => setShowPropertySelector(true)}
                      className="flex-1"
                    >
                      <Settings className="mr-2 h-4 w-4" />
                      Manage Properties
                      {status.propertyCount !== undefined && status.propertyCount > 0 && (
                        <Badge variant="secondary" className="ml-2">
                          {status.propertyCount}
                        </Badge>
                      )}
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => setShowDisconnectDialog(true)}
                      className="flex-1"
                    >
                      <Unlink className="mr-2 h-4 w-4" />
                      Disconnect
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>
                      {isAccountCreation ? "Ready to Connect" : "Not Connected"}
                    </AlertTitle>
                    <AlertDescription>
                      {isAccountCreation
                        ? "After clicking 'Create Account', you'll be redirected to Google to authorize access to your Analytics data."
                        : "Connect your Google account to enable Google Analytics data import for this account."}
                    </AlertDescription>
                  </Alert>

                  <div className="space-y-3">
                    <h4 className="text-sm font-medium">
                      What happens when you connect:
                    </h4>
                    <ul className="text-sm text-dashboard-gray-600 space-y-1">
                      <li className="flex items-start gap-2">
                        <span className="text-green-600 mt-0.5">✓</span>
                        You'll be redirected to Google to authorize access
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-600 mt-0.5">✓</span>
                        We'll only request read-only access to your GA data
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-600 mt-0.5">✓</span>
                        You can disconnect at any time
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-600 mt-0.5">✓</span>
                        Your credentials are encrypted and stored securely
                      </li>
                    </ul>
                  </div>

                  <Button
                    onClick={handleConnect}
                    disabled={isConnecting}
                    className="w-full"
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {isAccountCreation ? "Enabling..." : "Connecting..."}
                      </>
                    ) : (
                      <>
                        <Link className="mr-2 h-4 w-4" />
                        {isAccountCreation
                          ? "Enable Google Analytics"
                          : "Connect Google Analytics"}
                        {!isAccountCreation && (
                          <ExternalLink className="ml-2 h-3 w-3" />
                        )}
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={showDisconnectDialog}
        onOpenChange={setShowDisconnectDialog}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect Google Analytics?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove your Google Analytics connection. You'll need to
              reconnect to use the integration again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDisconnect}
              className="bg-red-600 hover:bg-red-700"
            >
              Disconnect
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
