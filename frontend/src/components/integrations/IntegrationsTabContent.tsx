import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon";
import { ConfigureIntegrationPanel } from "@/components/integrations/ConfigureIntegrationPanel";
import { useGoogleAnalyticsConnection } from "@/components/integrations/useGoogleAnalyticsConnection";

type IntegrationsTabContentProps = {
  accountId: string;
  productIntegrations: string[];
};

// Figma names the integration cards explicitly. Only Google Analytics has a
// backend OAuth flow today; Google Ads and Meta Ads are shown as "Coming soon".
const INTEGRATIONS: ReadonlyArray<{ name: string; enabled: boolean }> = [
  { name: "Google Analytics", enabled: true },
  { name: "Google Ads", enabled: false },
  { name: "Meta Ads", enabled: false },
];

export function IntegrationsTabContent({
  accountId,
  productIntegrations,
}: IntegrationsTabContentProps) {
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(
    null,
  );
  // GA connection status is the source of truth for the Google Analytics badge —
  // OAuth stores credentials separately from the account's product_integrations.
  const ga = useGoogleAnalyticsConnection(accountId);

  const isConnected = (name: string): boolean => {
    if (name === "Google Analytics") {
      return (
        ga.status?.state === "configured" || ga.status?.state === "expired"
      );
    }
    return productIntegrations.some(
      (p) => p.toLowerCase() === name.toLowerCase(),
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-1">Active Integrations</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Connect your marketing tools to enable AI-powered automation
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {INTEGRATIONS.map(({ name, enabled }) => {
            const connected = isConnected(name);
            return (
              <Card key={name} className={`p-4 ${enabled ? "" : "opacity-60"}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <IntegrationIcon name={name} className="size-10" />
                    <div>
                      <p className="font-medium">{name}</p>
                      {enabled ? (
                        <div
                          className={
                            connected
                              ? "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full mt-1 bg-[var(--color-success-bg)]"
                              : "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full mt-1 bg-[var(--color-error-bg)]"
                          }
                        >
                          <span
                            className={
                              connected
                                ? "size-1.5 rounded-full bg-[var(--color-success)]"
                                : "size-1.5 rounded-full bg-[var(--color-error)]"
                            }
                          />
                          <span
                            className={
                              connected
                                ? "text-xs font-semibold text-[var(--color-success-text)]"
                                : "text-xs font-semibold text-[var(--color-error-text)]"
                            }
                          >
                            {connected ? "Connected" : "Not Connected"}
                          </span>
                        </div>
                      ) : (
                        <Badge variant="outline" className="text-xs mt-1">
                          Coming soon
                        </Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!enabled}
                    onClick={() => enabled && setSelectedIntegration(name)}
                  >
                    Configure
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground mt-4">
          Connection status reflects this account&apos;s integrations. Connect
          or disconnect a tool from its Configure panel.
        </p>
      </div>

      <Sheet
        open={selectedIntegration !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedIntegration(null);
            void ga.refetch();
          }
        }}
      >
        <SheetContent className="sm:max-w-md p-0 gap-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Configure {selectedIntegration} integration</SheetTitle>
            <SheetDescription>
              Connect or disconnect this integration for your account.
            </SheetDescription>
          </SheetHeader>
          {selectedIntegration && (
            <ConfigureIntegrationPanel
              integration={{ name: selectedIntegration }}
              accountId={accountId}
              onClose={() => {
                setSelectedIntegration(null);
                void ga.refetch();
              }}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
