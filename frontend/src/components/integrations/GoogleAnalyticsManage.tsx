import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  Settings,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import api from "@/lib/api";
import { GoogleAnalyticsSetup } from "./GoogleAnalyticsSetup";

interface GoogleAnalyticsManageProps {
  accountId: string;
  isOpen: boolean;
  onClose: () => void;
  onUpdate?: () => void;
}

export const GoogleAnalyticsManage = ({
  accountId,
  isOpen,
  onClose,
  onUpdate,
}: GoogleAnalyticsManageProps) => {
  const [status, setStatus] = useState<{
    configured: boolean;
    lastTested?: string;
    configuredAt?: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showUpdateDialog, setShowUpdateDialog] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const { toast } = useToast();

  // Fetch status when dialog opens
  useState(() => {
    if (isOpen) {
      fetchStatus();
    }
  });

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const response = await api.get(
        `/api/integrations/${accountId}/google-analytics/status`,
      );
      setStatus({
        configured: response.data.status === "configured",
        lastTested: response.data.last_tested_at,
        configuredAt: response.data.configured_at,
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: "Failed to fetch integration status",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const response = await api.post(
        `/api/integrations/${accountId}/google-analytics/test`,
        {
          integration_type: "google_analytics",
        },
      );

      setTestResult({
        success: response.data.success,
        message: response.data.message,
      });

      if (response.data.success) {
        fetchStatus(); // Refresh status to update last tested time
      }
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.response?.data?.detail || "Connection test failed",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleDelete = async () => {
    setIsLoading(true);
    try {
      await api.delete(`/api/integrations/${accountId}/google-analytics`);

      toast({
        title: "Success",
        description: "Google Analytics integration removed successfully",
      });

      onUpdate?.();
      setShowDeleteDialog(false);
      onClose();
    } catch (error: any) {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to remove integration",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  };

  if (showUpdateDialog) {
    return (
      <GoogleAnalyticsSetup
        accountId={accountId}
        isOpen={showUpdateDialog}
        onClose={() => {
          setShowUpdateDialog(false);
          fetchStatus();
        }}
        onSuccess={() => {
          onUpdate?.();
          fetchStatus();
        }}
      />
    );
  }

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Manage Google Analytics Integration</DialogTitle>
            <DialogDescription>
              View and manage your Google Analytics connection
            </DialogDescription>
          </DialogHeader>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-dashboard-gray-500" />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Status</span>
                  <Badge
                    variant={status?.configured ? "default" : "secondary"}
                    className={
                      status?.configured
                        ? "bg-green-100 text-green-800"
                        : "bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)]"
                    }
                  >
                    {status?.configured ? "Configured" : "Not Configured"}
                  </Badge>
                </div>

                {status?.configured && (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-dashboard-gray-600">
                        Configured At
                      </span>
                      <span className="text-sm">
                        {formatDate(status.configuredAt)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-dashboard-gray-600">
                        Last Tested
                      </span>
                      <span className="text-sm">
                        {formatDate(status.lastTested)}
                      </span>
                    </div>
                  </>
                )}
              </div>

              {testResult && (
                <Alert
                  variant={testResult.success ? "default" : "destructive"}
                  className={testResult.success ? "border-green-500" : ""}
                >
                  {testResult.success ? (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  <AlertTitle>
                    {testResult.success
                      ? "Connection Active"
                      : "Connection Failed"}
                  </AlertTitle>
                  <AlertDescription>{testResult.message}</AlertDescription>
                </Alert>
              )}

              {status?.configured && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={handleTestConnection}
                    disabled={isTesting}
                    className="flex-1"
                  >
                    {isTesting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Test Connection
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setShowUpdateDialog(true)}
                    className="flex-1"
                  >
                    <Settings className="mr-2 h-4 w-4" />
                    Update Credentials
                  </Button>
                </div>
              )}

              {!status?.configured && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Not Configured</AlertTitle>
                  <AlertDescription>
                    Google Analytics integration is not set up for this account.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          <DialogFooter>
            {status?.configured && (
              <Button
                variant="destructive"
                onClick={() => setShowDeleteDialog(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Remove Integration
              </Button>
            )}
            {!status?.configured && (
              <Button onClick={() => setShowUpdateDialog(true)}>
                Configure Integration
              </Button>
            )}
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove Google Analytics Integration?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the stored credentials for Google
              Analytics. You'll need to reconfigure the integration to use it
              again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
            >
              Remove Integration
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
