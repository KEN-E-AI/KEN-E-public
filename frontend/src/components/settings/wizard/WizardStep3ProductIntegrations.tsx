import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Link, Clock } from "lucide-react";
import {
  PRODUCT_INTEGRATIONS,
  INTEGRATION_CATEGORIES,
} from "@/data/productIntegrations";
import { ValidationAlert } from "@/components/ui/ValidationAlert";
import {
  validateProductIntegrations,
  suggestComplementaryIntegrations,
} from "@/lib/validation/productIntegrationValidation";
import type { AccountCreationData } from "../AccountCreationWizard";
import type { IndustryTemplate } from "@/services/templateService";
import type { ValidationMessage } from "@/types/validation";

interface WizardStep3ProductIntegrationsProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
  selectedTemplate?: IndustryTemplate | null;
  showValidation?: boolean;
}

export const WizardStep3ProductIntegrations = ({
  formData,
  setFormData,
  selectedTemplate,
  showValidation = true,
}: WizardStep3ProductIntegrationsProps) => {
  const handleIntegrationToggle = (integrationId: string, checked: boolean) => {
    if (checked) {
      // Prevent duplicates and validate selection
      if (!formData.product_integrations.includes(integrationId)) {
        // Check if integration is available
        const integration = PRODUCT_INTEGRATIONS.find(
          (int) => int.id === integrationId,
        );
        if (integration?.status === "available") {
          setFormData({
            ...formData,
            product_integrations: [
              ...formData.product_integrations,
              integrationId,
            ],
          });
        }
      }
    } else {
      setFormData({
        ...formData,
        product_integrations: formData.product_integrations.filter(
          (id) => id !== integrationId,
        ),
      });
    }
  };

  const isIntegrationRecommended = (integrationId: string) => {
    return (
      selectedTemplate?.productIntegrations?.includes(integrationId) || false
    );
  };

  // Validate current selections
  const validationResult = validateProductIntegrations(
    formData.product_integrations,
  );

  // Get suggestions for complementary integrations
  const suggestions = suggestComplementaryIntegrations(
    formData.product_integrations,
  );

  // Convert validation result to UI messages
  const validationMessages: ValidationMessage[] = [
    ...validationResult.errors.map((error) => ({
      severity: "error" as const,
      message: error,
      field: "product_integrations",
    })),
    ...validationResult.warnings.map((warning) => ({
      severity: "warning" as const,
      message: warning,
      field: "product_integrations",
    })),
    // Add suggestions as info messages
    ...suggestions.slice(0, 2).map((suggestionId) => {
      const integration = PRODUCT_INTEGRATIONS.find(
        (int) => int.id === suggestionId,
      );
      return {
        severity: "info" as const,
        message: `Consider adding ${integration?.name || suggestionId} to complement your current selections.`,
        field: "product_integrations",
      };
    }),
  ];

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
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link className="h-5 w-5 text-brand-medium-blue" />
          Product Integrations
        </CardTitle>
        <p className="text-sm text-dashboard-gray-600">
          Choose which marketing tools you'd like to connect with KEN-E.
          {selectedTemplate && (
            <span className="text-brand-medium-blue font-medium">
              {" "}
              We've pre-selected integrations recommended for{" "}
              {selectedTemplate.industry}.
            </span>
          )}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Validation Messages */}
        {showValidation && validationMessages.length > 0 && (
          <ValidationAlert messages={validationMessages} />
        )}

        {/* Integration Categories */}
        {Object.entries(integrationsByCategory).map(
          ([category, integrations]) => (
            <div key={category}>
              <h3 className="font-medium mb-4 text-dashboard-gray-800">
                {
                  INTEGRATION_CATEGORIES[
                    category as keyof typeof INTEGRATION_CATEGORIES
                  ]
                }
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {integrations.map((integration) => {
                  const Icon = integration.icon;
                  const isAvailable = integration.status === "available";
                  const isSelected = formData.product_integrations.includes(
                    integration.id,
                  );
                  const isRecommended = isIntegrationRecommended(
                    integration.id,
                  );

                  return (
                    <Card
                      key={integration.id}
                      className={`p-4 transition-all ${
                        !isAvailable
                          ? "opacity-60 cursor-not-allowed"
                          : isSelected
                            ? "border-brand-medium-blue bg-brand-light-blue/10"
                            : "hover:border-dashboard-gray-300 cursor-pointer"
                      }`}
                      onClick={() =>
                        isAvailable &&
                        handleIntegrationToggle(integration.id, !isSelected)
                      }
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3 flex-1">
                          <div className="w-10 h-10 bg-brand-light-blue/20 rounded-lg flex items-center justify-center flex-shrink-0">
                            <Icon className="h-5 w-5 text-brand-medium-blue" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h4 className="font-medium text-dashboard-gray-800">
                                {integration.name}
                              </h4>
                              {isRecommended && (
                                <Badge variant="secondary" className="text-xs">
                                  Recommended
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-dashboard-gray-600 mb-2">
                              {integration.description}
                            </p>
                            {integration.features && (
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
        {formData.product_integrations.length > 0 && (
          <Card className="bg-brand-light-blue/5 border-brand-light-blue/20">
            <CardContent className="pt-4">
              <h4 className="font-medium text-sm text-dashboard-gray-800 mb-2">
                Selected Integrations ({formData.product_integrations.length})
              </h4>
              <div className="flex flex-wrap gap-2">
                {formData.product_integrations.map((integrationId) => {
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
        <Card className="bg-orange-50 border-orange-200">
          <CardContent className="pt-4">
            <div className="flex items-start gap-2">
              <Clock className="h-4 w-4 text-orange-600 mt-0.5" />
              <div>
                <h4 className="font-medium text-sm text-orange-800 mb-1">
                  More Integrations Coming Soon
                </h4>
                <p className="text-xs text-orange-700">
                  We're working on additional integrations with popular
                  marketing platforms. You can add more integrations after
                  setting up your account.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </CardContent>
    </Card>
  );
};
