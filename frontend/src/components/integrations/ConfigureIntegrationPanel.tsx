import { useState } from "react";
import { Info, Loader2, Plug, RefreshCw, Settings, Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { IntegrationIcon } from "./IntegrationIcon";
import { GoogleAnalyticsPropertySelector } from "./GoogleAnalyticsPropertySelector";
import {
  useGoogleAnalyticsConnection,
  type GoogleAnalyticsConnectionState,
} from "./useGoogleAnalyticsConnection";

type DisplayStatus = "connected" | "disconnected" | "error";

type ConfigureIntegrationPanelProps = {
  /** The integration being configured (only Google Analytics is wired today). */
  integration: { name: string };
  accountId: string;
  onClose: () => void;
};

const statusConfig: Record<
  DisplayStatus,
  { label: string; dotClass: string; textClass: string; bgClass: string }
> = {
  connected: {
    label: "Connected",
    dotClass: "bg-[var(--color-success)]",
    textClass: "text-[var(--color-success-text)]",
    bgClass: "bg-[var(--color-success-bg)]",
  },
  disconnected: {
    label: "Not Connected",
    dotClass: "bg-[var(--color-error)]",
    textClass: "text-[var(--color-error-text)]",
    bgClass: "bg-[var(--color-error-bg)]",
  },
  error: {
    label: "Issue",
    dotClass: "bg-[var(--color-warning)]",
    textClass: "text-[var(--color-warning-text)]",
    bgClass: "bg-[var(--color-warning-bg)]",
  },
};

const toDisplayStatus = (
  state: GoogleAnalyticsConnectionState | undefined,
): DisplayStatus => {
  if (state === "configured") return "connected";
  if (state === "expired" || state === "error") return "error";
  return "disconnected";
};

/**
 * Side-panel body (rendered inside a Sheet) for configuring an account
 * integration, ported from the Figma export. The connection actions are wired
 * to the live Google Analytics OAuth flow; the per-user permissions section has
 * no backend yet and is rendered as a disabled "coming soon" placeholder.
 */
export function ConfigureIntegrationPanel({
  integration,
  accountId,
  onClose,
}: ConfigureIntegrationPanelProps) {
  const { toast } = useToast();
  const { status, isLoading, isConnecting, isBusy, connect, disconnect } =
    useGoogleAnalyticsConnection(accountId);
  const [showPropertySelector, setShowPropertySelector] = useState(false);

  const displayStatus = toDisplayStatus(status?.state);
  const badge = statusConfig[displayStatus];

  const handleConnect = async () => {
    try {
      await connect();
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to initiate Google OAuth";
      toast({
        title: "Connection Failed",
        description: detail,
        variant: "destructive",
      });
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnect();
      toast({
        title: "Disconnected",
        description: `${integration.name} disconnected successfully.`,
      });
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to disconnect";
      toast({
        title: "Error",
        description: detail,
        variant: "destructive",
      });
    }
  };

  if (showPropertySelector) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 p-4">
        <GoogleAnalyticsPropertySelector
          accountId={accountId}
          onComplete={() => setShowPropertySelector(false)}
          onSkip={() => setShowPropertySelector(false)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 pb-4 pr-12">
        <div>
          <div className="flex items-center gap-3 mb-3">
            <IntegrationIcon name={integration.name} />
            <h3 className="truncate">
              Configure {integration.name} Integration
            </h3>
          </div>
          <div
            className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full ${badge.bgClass}`}
          >
            <span className={`size-2 rounded-full ${badge.dotClass}`} />
            <span
              className={`text-xs ${badge.textClass}`}
              style={{ fontWeight: 600 }}
            >
              {isLoading ? "Checking…" : badge.label}
            </span>
          </div>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
        {/* Connection action */}
        {displayStatus === "disconnected" && (
          <div className="p-4 rounded-[var(--radius-md)] border-2 border-dashed border-[var(--color-border-default)] text-center">
            <p className="text-sm text-[var(--color-text-secondary)] mb-3">
              This integration is not yet connected.
            </p>
            <Button size="sm" onClick={handleConnect} disabled={isConnecting}>
              {isConnecting ? (
                <Loader2 className="size-3.5 mr-1.5 animate-spin" />
              ) : (
                <Plug className="size-3.5 mr-1.5" />
              )}
              Connect {integration.name}
            </Button>
          </div>
        )}

        {displayStatus === "error" && (
          <div className="p-4 rounded-[var(--radius-md)] bg-[var(--color-warning-bg)] border border-[var(--color-warning)]">
            <p className="text-sm text-[var(--color-warning-text)] mb-3">
              There was an issue with this integration. Please try reconnecting.
            </p>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleConnect}
              disabled={isConnecting}
            >
              {isConnecting ? (
                <Loader2 className="size-3.5 mr-1.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5 mr-1.5" />
              )}
              Reconnect {integration.name}
            </Button>
          </div>
        )}

        {displayStatus === "connected" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-[var(--radius-md)] bg-[var(--color-surface-muted)]">
              <div className="min-w-0">
                <p className="text-sm text-[var(--color-text-secondary)]">
                  This integration is active.
                </p>
                {status?.userEmail && (
                  <p className="text-xs text-[var(--color-text-tertiary)] truncate">
                    {status.userEmail}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDisconnect}
                disabled={isBusy}
                className="text-[var(--color-error)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-bg)]"
              >
                <Unplug className="size-3.5 mr-1.5" />
                Disconnect
              </Button>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setShowPropertySelector(true)}
            >
              <Settings className="size-3.5 mr-1.5" />
              Manage Properties
              {status?.propertyCount !== undefined &&
                status.propertyCount > 0 &&
                ` (${status.propertyCount})`}
            </Button>
          </div>
        )}

        {/* Credentials notice */}
        <div className="flex gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--color-info-bg)] border border-[var(--color-info)]">
          <Info className="size-4 text-[var(--color-info)] shrink-0 mt-0.5" />
          <p className="text-xs text-[var(--color-info-text)]">
            All users in this account will share the same credentials when
            accessing {integration.name}.
          </p>
        </div>

        <Separator />

        {/* Permissions section — backend support pending (per-account connection
            sharing in the Integrations PRD), so the controls are not yet shown. */}
        <div>
          <h4 className="mb-2">Permissions</h4>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Enabling this integration makes the{" "}
            <span style={{ fontWeight: 600 }}>
              {integration.name} Specialist
            </span>{" "}
            agent available to all users in the account.
          </p>
          <div className="p-3 rounded-[var(--radius-md)] bg-[var(--color-surface-muted)] text-sm text-[var(--color-text-tertiary)]">
            Per-user permission controls are coming soon.
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-2 p-4 border-t border-[var(--color-border-default)]">
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button size="sm" onClick={onClose}>
          Done
        </Button>
      </div>
    </div>
  );
}
