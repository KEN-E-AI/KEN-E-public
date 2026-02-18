import { useState } from "react";
import { AlertCircle, ExternalLink } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { apiClient } from "@/services/apiClient";

interface ReauthPromptProps {
  service: string;
}

export function ReauthPrompt({ service }: ReauthPromptProps) {
  const { selectedOrgAccount } = useAuth();
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleReconnect = async () => {
    const accountId = selectedOrgAccount?.accountId;
    if (!accountId) return;

    setIsConnecting(true);
    setError(null);
    try {
      const response = await apiClient.get(
        `/api/oauth/authorize/${service}?account_id=${accountId}`,
      );
      window.location.href = response.data.auth_url;
    } catch {
      setIsConnecting(false);
      setError("Failed to reconnect. Please try again.");
    }
  };

  const serviceName =
    service === "google-analytics" ? "Google Analytics" : service;

  return (
    <Alert variant="destructive" className="mt-2 max-w-xs lg:max-w-md">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <span>{serviceName} connection expired.</span>
          <Button
            size="sm"
            variant="outline"
            onClick={handleReconnect}
            disabled={isConnecting || !selectedOrgAccount?.accountId}
          >
            {isConnecting ? "Connecting..." : "Reconnect"}
            {!isConnecting && <ExternalLink className="ml-1 h-3 w-3" />}
          </Button>
        </div>
        {error && <span className="text-sm text-destructive">{error}</span>}
      </AlertDescription>
    </Alert>
  );
}
