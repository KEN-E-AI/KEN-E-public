import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Link, Clock, Settings } from "lucide-react";
import {
  PRODUCT_INTEGRATIONS,
  INTEGRATION_CATEGORIES,
} from "@/data/productIntegrations";
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
  const handleIntegrationToggle = (integrationId: string, checked: boolean) => {
    if (checked) {
      onChange([...value, integrationId]);
    } else {
      onChange(value.filter((id) => id !== integrationId));
    }
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

                  return (
                    <Card
                      key={integration.id}
                      className={`p-3 transition-all ${
                        !isAvailable
                          ? "opacity-60"
                          : isSelected
                            ? "border-brand-medium-blue bg-brand-light-blue/10"
                            : "hover:border-dashboard-gray-300"
                      } ${compact ? "text-sm" : ""}`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-2 flex-1">
                          <div
                            className={`bg-brand-light-blue/20 rounded flex items-center justify-center flex-shrink-0 ${
                              compact ? "w-8 h-8" : "w-10 h-10"
                            }`}
                          >
                            <Icon
                              className={`text-brand-medium-blue ${
                                compact ? "h-4 w-4" : "h-5 w-5"
                              }`}
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h5
                                className={`font-medium text-dashboard-gray-800 ${
                                  compact ? "text-sm" : ""
                                }`}
                              >
                                {integration.name}
                              </h5>
                              {isEnabled && isSelected && (
                                <Badge
                                  variant="default"
                                  className="text-xs bg-green-100 text-green-800"
                                >
                                  Enabled
                                </Badge>
                              )}
                            </div>
                            <p
                              className={`text-dashboard-gray-600 mb-1 ${
                                compact ? "text-xs" : "text-sm"
                              }`}
                            >
                              {integration.description}
                            </p>
                            {integration.features && !compact && (
                              <div className="text-xs text-dashboard-gray-500">
                                <span className="font-medium">Features:</span>{" "}
                                {integration.features.slice(0, 2).join(", ")}
                                {integration.features.length > 2 && "..."}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {!isAvailable ? (
                            <Badge
                              variant="outline"
                              className="text-xs bg-orange-100 text-orange-800"
                            >
                              <Clock className="h-3 w-3 mr-1" />
                              Coming Soon
                            </Badge>
                          ) : (
                            <>
                              {isSelected && onConfigure && (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onConfigure(integration.id);
                                      }}
                                      className="h-8 w-8 p-0"
                                    >
                                      <Settings className="h-4 w-4 text-dashboard-gray-600" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>Configure {integration.name}</p>
                                  </TooltipContent>
                                </Tooltip>
                              )}
                              <Switch
                                checked={isSelected}
                                onCheckedChange={(checked) =>
                                  handleIntegrationToggle(
                                    integration.id,
                                    checked,
                                  )
                                }
                                onClick={(e) => e.stopPropagation()}
                              />
                            </>
                          )}
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ),
        )}

        {/* Selected integrations summary */}
        {value.length > 0 && (
          <Card className="bg-brand-light-blue/5 border-brand-light-blue/20 p-3">
            <h5
              className={`font-medium text-dashboard-gray-800 mb-2 ${
                compact ? "text-sm" : ""
              }`}
            >
              Selected Integrations ({value.length})
            </h5>
            <div className="flex flex-wrap gap-1">
              {value.map((integrationId) => {
                const integration = PRODUCT_INTEGRATIONS.find(
                  (i) => i.id === integrationId,
                );
                const isEnabled = isIntegrationEnabled(integrationId);

                return (
                  <Badge
                    key={integrationId}
                    variant={isEnabled ? "default" : "secondary"}
                    className={`text-xs ${
                      isEnabled ? "bg-green-100 text-green-800" : ""
                    }`}
                  >
                    {integration?.name || integrationId}
                    {isEnabled && " ✓"}
                  </Badge>
                );
              })}
            </div>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
};
