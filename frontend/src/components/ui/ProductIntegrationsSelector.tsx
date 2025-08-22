import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Link, Clock } from "lucide-react";
import {
  PRODUCT_INTEGRATIONS,
  INTEGRATION_CATEGORIES,
} from "@/data/productIntegrations";

interface ProductIntegrationsSelectorProps {
  value: string[];
  onChange: (integrations: string[]) => void;
  showRecommended?: boolean;
  recommendedIntegrations?: string[];
  compact?: boolean;
}

export const ProductIntegrationsSelector = ({
  value,
  onChange,
  showRecommended = false,
  recommendedIntegrations = [],
  compact = false,
}: ProductIntegrationsSelectorProps) => {
  const handleIntegrationToggle = (integrationId: string, checked: boolean) => {
    if (checked) {
      onChange([...value, integrationId]);
    } else {
      onChange(value.filter((id) => id !== integrationId));
    }
  };

  const isIntegrationRecommended = (integrationId: string) => {
    return recommendedIntegrations.includes(integrationId);
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
                const isRecommended =
                  showRecommended && isIntegrationRecommended(integration.id);

                return (
                  <Card
                    key={integration.id}
                    className={`p-3 transition-all cursor-pointer ${
                      !isAvailable
                        ? "opacity-60 cursor-not-allowed"
                        : isSelected
                          ? "border-brand-medium-blue bg-brand-light-blue/10"
                          : "hover:border-dashboard-gray-300"
                    } ${compact ? "text-sm" : ""}`}
                    onClick={() =>
                      isAvailable &&
                      handleIntegrationToggle(integration.id, !isSelected)
                    }
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
                            {isRecommended && (
                              <Badge variant="secondary" className="text-xs">
                                Recommended
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
                        <Badge
                          variant={isAvailable ? "default" : "outline"}
                          className={`text-xs ${
                            isAvailable
                              ? "bg-green-100 text-green-800"
                              : "bg-orange-100 text-orange-800"
                          }`}
                        >
                          {isAvailable ? (
                            "Available"
                          ) : (
                            <div className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              Coming Soon
                            </div>
                          )}
                        </Badge>
                        {isAvailable && (
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={(checked) =>
                              handleIntegrationToggle(
                                integration.id,
                                checked as boolean,
                              )
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
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
        <Card className="bg-brand-light-blue/5 border-brand-light-blue/20">
          <CardContent className="pt-3">
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
                const isRecommended = isIntegrationRecommended(integrationId);

                return (
                  <Badge
                    key={integrationId}
                    variant={isRecommended ? "default" : "secondary"}
                    className="text-xs"
                  >
                    {integration?.name || integrationId}
                  </Badge>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Coming soon notice */}
      {!compact && (
        <Card className="bg-orange-50 border-orange-200">
          <CardContent className="pt-3">
            <div className="flex items-start gap-2">
              <Clock className="h-4 w-4 text-orange-600 mt-0.5" />
              <div>
                <h5 className="font-medium text-sm text-orange-800 mb-1">
                  More Integrations Coming Soon
                </h5>
                <p className="text-xs text-orange-700">
                  We're working on additional integrations with popular
                  marketing platforms. You can add more integrations after
                  setting up your account.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
