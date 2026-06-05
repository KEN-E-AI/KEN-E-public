import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";

/**
 * Connection state reported by the backend status endpoint.
 * Mirrors IntegrationStatus on the API (api/src/kene_api/models/integration_models.py).
 */
export type GoogleAnalyticsConnectionState =
  | "not_configured"
  | "configured"
  | "expired"
  | "error";

export type GoogleAnalyticsStatus = {
  state: GoogleAnalyticsConnectionState;
  userEmail?: string;
  propertyCount?: number;
};

export type UseGoogleAnalyticsConnection = {
  status: GoogleAnalyticsStatus | null;
  isLoading: boolean;
  isConnecting: boolean;
  isBusy: boolean;
  refetch: () => Promise<void>;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
};

/**
 * Encapsulates the four account-scoped Google Analytics OAuth calls shared by the
 * settings Configure panel and the account-creation wizard dialog. Actions throw
 * on failure so callers can surface their own toast copy.
 */
export function useGoogleAnalyticsConnection(
  accountId: string,
): UseGoogleAnalyticsConnection {
  const [status, setStatus] = useState<GoogleAnalyticsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  const refetch = useCallback(async () => {
    if (!accountId) return;
    setIsLoading(true);
    try {
      const response = await api.get(
        `/api/oauth/status/${accountId}/google-analytics`,
      );
      setStatus({
        state: response.data.status as GoogleAnalyticsConnectionState,
        userEmail: response.data.user_email,
        propertyCount: response.data.property_count,
      });
    } catch {
      // Treat an unreadable status as "not connected" rather than blocking the UI.
      setStatus({ state: "not_configured" });
    } finally {
      setIsLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const connect = useCallback(async () => {
    setIsConnecting(true);
    try {
      const response = await api.get(
        `/api/oauth/authorize/google-analytics?account_id=${accountId}`,
      );
      // Full-page redirect into Google's consent screen.
      window.location.href = response.data.auth_url;
    } catch (error) {
      setIsConnecting(false);
      throw error;
    }
  }, [accountId]);

  const disconnect = useCallback(async () => {
    setIsBusy(true);
    try {
      await api.delete(`/api/oauth/disconnect/${accountId}/google-analytics`);
      setStatus({ state: "not_configured" });
    } finally {
      setIsBusy(false);
    }
  }, [accountId]);

  const refresh = useCallback(async () => {
    setIsBusy(true);
    try {
      await api.post(`/api/oauth/refresh/${accountId}/google-analytics`);
      await refetch();
    } finally {
      setIsBusy(false);
    }
  }, [accountId, refetch]);

  return {
    status,
    isLoading,
    isConnecting,
    isBusy,
    refetch,
    connect,
    disconnect,
    refresh,
  };
}
