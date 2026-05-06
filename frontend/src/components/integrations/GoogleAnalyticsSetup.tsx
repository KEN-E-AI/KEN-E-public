import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCircle, CheckCircle, Loader2, Upload } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import api from "@/lib/api";

interface GoogleAnalyticsSetupProps {
  accountId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const GoogleAnalyticsSetup = ({
  accountId,
  isOpen,
  onClose,
  onSuccess,
}: GoogleAnalyticsSetupProps) => {
  const [credentials, setCredentials] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const { toast } = useToast();

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        setCredentials(content);
        setTestResult(null);
      };
      reader.readAsText(file);
    }
  };

  const validateCredentials = () => {
    try {
      const parsed = JSON.parse(credentials);
      if (
        !parsed.type ||
        !parsed.project_id ||
        !parsed.private_key ||
        !parsed.client_email
      ) {
        throw new Error("Invalid service account JSON structure");
      }
      return parsed;
    } catch (error) {
      toast({
        title: "Invalid Credentials",
        description:
          "Please provide valid Google Analytics service account JSON",
        variant: "destructive",
      });
      return null;
    }
  };

  const handleTestConnection = async () => {
    const parsedCredentials = validateCredentials();
    if (!parsedCredentials) return;

    setIsTesting(true);
    setTestResult(null);

    try {
      const response = await api.post(
        `/api/integrations/${accountId}/google-analytics/test`,
        {
          integration_type: "google_analytics",
          credentials: parsedCredentials,
        },
      );

      setTestResult({
        success: response.data.success,
        message: response.data.message,
      });
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.response?.data?.detail || "Connection test failed",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveCredentials = async () => {
    const parsedCredentials = validateCredentials();
    if (!parsedCredentials) return;

    setIsLoading(true);

    try {
      await api.post(`/api/integrations/${accountId}/google-analytics`, {
        integration_type: "google_analytics",
        credentials: parsedCredentials,
      });

      toast({
        title: "Success",
        description: "Google Analytics credentials saved successfully",
      });

      onSuccess?.();
      onClose();
    } catch (error: any) {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to save credentials",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setCredentials("");
    setTestResult(null);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Setup Google Analytics Integration</DialogTitle>
          <DialogDescription>
            Connect your Google Analytics account to start importing data
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Prerequisites</AlertTitle>
            <AlertDescription>
              You need a Google Analytics service account with the following
              permissions:
              <ul className="list-disc list-inside mt-2">
                <li>Google Analytics Data API enabled</li>
                <li>Viewer or higher access to your GA4 properties</li>
                <li>Service account JSON key file</li>
              </ul>
            </AlertDescription>
          </Alert>

          <Tabs defaultValue="paste" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="paste">Paste JSON</TabsTrigger>
              <TabsTrigger value="upload">Upload File</TabsTrigger>
            </TabsList>

            <TabsContent value="paste">
              <div className="space-y-2">
                <Label htmlFor="credentials">Service Account JSON</Label>
                <Textarea
                  id="credentials"
                  placeholder='Paste your service account JSON here (starts with {"type": "service_account"...})'
                  value={credentials}
                  onChange={(e) => {
                    setCredentials(e.target.value);
                    setTestResult(null);
                  }}
                  className="min-h-[200px] font-mono text-xs"
                />
              </div>
            </TabsContent>

            <TabsContent value="upload">
              <div className="space-y-2">
                <Label htmlFor="file-upload">Service Account JSON File</Label>
                <div className="flex items-center gap-4">
                  <Input
                    id="file-upload"
                    type="file"
                    accept=".json"
                    onChange={handleFileUpload}
                    className="flex-1"
                  />
                  <Upload className="h-5 w-5 text-[var(--color-text-tertiary)]" />
                </div>
                {credentials && (
                  <p className="text-sm text-green-600">
                    ✓ File loaded successfully
                  </p>
                )}
              </div>
            </TabsContent>
          </Tabs>

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
                  ? "Connection Successful"
                  : "Connection Failed"}
              </AlertTitle>
              <AlertDescription>{testResult.message}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={handleTestConnection}
            disabled={!credentials || isTesting}
          >
            {isTesting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Testing...
              </>
            ) : (
              "Test Connection"
            )}
          </Button>
          <Button
            onClick={handleSaveCredentials}
            disabled={!credentials || !testResult?.success || isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Credentials"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
