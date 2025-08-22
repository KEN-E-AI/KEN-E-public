import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Clock, Settings, CheckCircle } from "lucide-react";
import {
  PRODUCT_INTEGRATIONS,
  INTEGRATION_CATEGORIES,
} from "@/data/productIntegrationsWithLogos";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ProductIntegrationsEditorProps {
  value: string[];
  onChange: (integrations: string[]) => void;
  enabledIntegrations?: string[]; // List of integrations that are currently enabled/configured
  onConfigure?: (integrationId: string) => void; // Callback when gear icon is clicked
  compact?: boolean;
}

export const ProductIntegrationsEditor = ({
  value,
  onChange,
  enabledIntegrations = [],
  onConfigure,
  compact = false,
}: ProductIntegrationsEditorProps) => {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(
    null,
  );

  const handleIntegrationClick = (integrationId: string) => {
    const integration = PRODUCT_INTEGRATIONS.find(
      (int) => int.id === integrationId,
    );
    if (integration?.status === "available") {
      setSelectedIntegration(integrationId);
    }
  };

  const handleToggleIntegration = () => {
    if (selectedIntegration) {
      const isCurrentlySelected = value.includes(selectedIntegration);

      if (isCurrentlySelected) {
        // Remove the integration
        onChange(value.filter((id) => id !== selectedIntegration));
      } else {
        // Add the integration
        onChange([...value, selectedIntegration]);
      }

      setSelectedIntegration(null);
    }
  };

  const handleImageError = (integrationId: string) => {
    setImageErrors((prev) => new Set(prev).add(integrationId));
  };

  const isIntegrationEnabled = (integrationId: string) => {
    return enabledIntegrations.includes(integrationId);
  };

  // Group integrations by category
  const integrationsByCategory = PRODUCT_INTEGRATIONS.reduce(
    (acc, integration) => {
      if (!acc[integration.category]) {
        acc[integration.category] = [];
      }
      acc[integration.category].push(integration);
      return acc;
    },
    {} as Record<string, typeof PRODUCT_INTEGRATIONS>,
  );

  return (
    <TooltipProvider>
      <div className="space-y-4">
        {/* Integration Categories */}
        {Object.entries(integrationsByCategory).map(
          ([category, integrations]) => (
            <div key={category}>
              <h4
                className={`font-medium mb-3 text-dashboard-gray-800 ${
                  compact ? "text-sm" : ""
                }`}
              >
                {
                  INTEGRATION_CATEGORIES[
                    category as keyof typeof INTEGRATION_CATEGORIES
                  ]
                }
              </h4>
              <div
                className={`grid gap-3 ${
                  compact ? "grid-cols-1" : "grid-cols-1 md:grid-cols-2"
                }`}
              >
                {integrations.map((integration) => {
                  const Icon = integration.icon;
                  const isAvailable = integration.status === "available";
                  const isSelected = value.includes(integration.id);
                  const isEnabled = isIntegrationEnabled(integration.id);
                  const hasImageError = imageErrors.has(integration.id);

                  return (
                    <Card
                      key={integration.id}
                      className={`p-3 transition-all cursor-pointer ${
                        !isAvailable
                          ? "opacity-60 cursor-not-allowed"
                          : isSelected
                            ? "border-green-500 bg-green-50"
                            : "hover:border-dashboard-gray-300"
                      } ${compact ? "text-sm" : ""}`}
                      onClick={() => {
                        if (isAvailable) {
                          handleIntegrationClick(integration.id);
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        {/* Logo or Icon */}
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                          {!hasImageError ? (
                            <img
                              src={integration.logo}
                              alt={`${integration.name} logo`}
                              className="w-8 h-8 object-contain"
                              onError={() => handleImageError(integration.id)}
                            />
                          ) : (
                            <div className="w-8 h-8 bg-brand-light-blue/20 rounded flex items-center justify-center">
                              <Icon className="h-4 w-4 text-brand-medium-blue" />
                            </div>
                          )}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between mb-1">
                            <div className="flex-1">
                              <h4
                                className={`font-medium text-dashboard-gray-800 ${
                                  compact ? "text-sm" : ""
                                }`}
                              >
                                {integration.name}
                              </h4>
                              {!compact && (
                                <p className="text-xs text-dashboard-gray-600 mt-1">
                                  {integration.description}
                                </p>
                              )}
                            </div>

                            {/* Action buttons/badges */}
                            {isAvailable ? (
                              <div className="flex items-center gap-1 ml-2">
                                {isSelected && (
                                  <Badge
                                    variant="outline"
                                    className="text-xs bg-green-50 text-green-700 border-green-200"
                                  >
                                    <CheckCircle className="h-3 w-3 mr-1" />
                                    {isEnabled ? "Enabled" : "Selected"}
                                  </Badge>
                                )}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="p-1 h-auto"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleIntegrationClick(integration.id);
                                  }}
                                >
                                  <Settings className="h-4 w-4" />
                                </Button>
                              </div>
                            ) : (
                              <Badge
                                variant="outline"
                                className="text-xs bg-orange-50 text-orange-700 border-orange-200 ml-2"
                              >
                                <Clock className="h-3 w-3 mr-1" />
                                Coming soon
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ),
        )}

        {/* Integration Setup Modal */}
        <Dialog
          open={!!selectedIntegration}
          onOpenChange={(open) => !open && setSelectedIntegration(null)}
        >
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>
                Setup{" "}
                {
                  PRODUCT_INTEGRATIONS.find((i) => i.id === selectedIntegration)
                    ?.name
                }
              </DialogTitle>
              <DialogDescription>
                Follow these instructions to enable this integration:
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-3">
                <h4 className="font-medium text-sm">Integration Steps:</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-dashboard-gray-600">
                  <li>
                    Navigate to your{" "}
                    {
                      PRODUCT_INTEGRATIONS.find(
                        (i) => i.id === selectedIntegration,
                      )?.name
                    }{" "}
                    account settings
                  </li>
                  <li>Generate an API key or access token</li>
                  <li>Copy the API credentials</li>
                  <li>Return here and paste the credentials</li>
                  <li>Test the connection to verify setup</li>
                </ol>
              </div>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm text-blue-800">
                  <strong>Note:</strong> You can complete this setup later. The
                  integration will be marked as pending until configured.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setSelectedIntegration(null)}
              >
                Cancel
              </Button>
              <Button onClick={handleToggleIntegration}>
                {value.includes(selectedIntegration || "")
                  ? "Remove Integration"
                  : "Add Integration"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
};
