import { useState } from "react";
import { AlertCircle, ExternalLink } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import axios from "axios";
import { auth } from "@/lib/firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface ReauthPromptProps {
  service: string;
}

export function ReauthPrompt({ service }: ReauthPromptProps) {
  const { selectedOrgAccount } = useAuth();
  const [isConnecting, setIsConnecting] = useState(false);

  const handleReconnect = async () => {
    const accountId = selectedOrgAccount?.accountId;
    if (!accountId) return;

    setIsConnecting(true);
    try {
      const user = auth.currentUser;
      const token = user ? await user.getIdToken() : null;
      const response = await axios.get(
        `${API_BASE_URL}/api/oauth/authorize/${service}?account_id=${accountId}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      window.location.href = response.data.auth_url;
    } catch {
      setIsConnecting(false);
    }
  };

  const serviceName =
    service === "google-analytics" ? "Google Analytics" : service;

  return (
    <Alert variant="destructive" className="mt-2 max-w-xs lg:max-w-md">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="flex items-center justify-between gap-2">
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
      </AlertDescription>
    </Alert>
  );
}
