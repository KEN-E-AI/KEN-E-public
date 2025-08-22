import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Link, Clock, Settings, CheckCircle } from "lucide-react";
import {
  PRODUCT_INTEGRATIONS,
  INTEGRATION_CATEGORIES,
} from "@/data/productIntegrationsWithLogos";
import { ValidationAlert } from "@/components/ui/ValidationAlert";
import {
  validateProductIntegrations,
  suggestComplementaryIntegrations,
} from "@/lib/validation/productIntegrationValidation";
import type { AccountCreationData } from "../AccountCreationWizard";
import type { IndustryTemplate } from "@/services/templateService";
import type { ValidationMessage } from "@/types/validation";

interface WizardStep3ProductIntegrationsImprovedProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
  selectedTemplate?: IndustryTemplate | null;
  showValidation?: boolean;
}

export const WizardStep3ProductIntegrationsImproved = ({
  formData,
  setFormData,
  selectedTemplate,
  showValidation = true,
}: WizardStep3ProductIntegrationsImprovedProps) => {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null);
  const [enabledIntegrations, setEnabledIntegrations] = useState<Set<string>>(new Set());

  const handleIntegrationClick = (integrationId: string) => {
    const integration = PRODUCT_INTEGRATIONS.find(
      (int) => int.id === integrationId,
    );
    if (integration?.status === "available" && !enabledIntegrations.has(integrationId)) {
      setSelectedIntegration(integrationId);
    }
  };

  const handleEnableIntegration = () => {
    if (selectedIntegration) {
      setEnabledIntegrations(prev => new Set(prev).add(selectedIntegration));
      if (!formData.product_integrations.includes(selectedIntegration)) {
        setFormData({
          ...formData,
          product_integrations: [
            ...formData.product_integrations,
            selectedIntegration,
          ],
        });
      }
      setSelectedIntegration(null);
    }
  };

  const handleImageError = (integrationId: string) => {
    setImageErrors((prev) => new Set(prev).add(integrationId));
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
    // Add top suggestion as info message
    ...suggestions.slice(0, 1).map((suggestionId) => {
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
    <Card className="w-full max-w-5xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link className="h-5 w-5 text-brand-medium-blue" />
          Product Integrations
        </CardTitle>
        <p className="text-sm text-dashboard-gray-600">
          Choose which marketing tools you'd like to connect with KEN-E.
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
              <h3 className="font-medium mb-3 text-dashboard-gray-800">
                {
                  INTEGRATION_CATEGORIES[
                    category as keyof typeof INTEGRATION_CATEGORIES
                  ]
                }
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {integrations.map((integration) => {
                  const Icon = integration.icon;
                  const isAvailable = integration.status === "available";
                  const isEnabled = enabledIntegrations.has(integration.id);
                  const hasImageError = imageErrors.has(integration.id);

                  return (
                    <Card
                      key={integration.id}
                      className={`p-3 transition-all ${
                        !isAvailable
                          ? "opacity-60 cursor-not-allowed"
                          : isEnabled
                            ? "border-green-500 bg-green-50"
                            : "hover:border-dashboard-gray-300"
                      }`}
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
                              <h4 className="font-medium text-sm text-dashboard-gray-800">
                                {integration.name}
                              </h4>
                            </div>

                            {/* Action buttons/badges */}
                            {isAvailable ? (
                              isEnabled ? (
                                <Badge
                                  variant="outline"
                                  className="text-xs bg-green-50 text-green-700 border-green-200 ml-2"
                                >
                                  <CheckCircle className="h-3 w-3 mr-1" />
                                  Enabled
                                </Badge>
                              ) : (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="ml-2 p-1 h-auto"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleIntegrationClick(integration.id);
                                  }}
                                >
                                  <Settings className="h-4 w-4" />
                                </Button>
                              )
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
        <Dialog open={!!selectedIntegration} onOpenChange={(open) => !open && setSelectedIntegration(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>
                Setup {PRODUCT_INTEGRATIONS.find(i => i.id === selectedIntegration)?.name}
              </DialogTitle>
              <DialogDescription>
                Follow these instructions to enable this integration:
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-3">
                <h4 className="font-medium text-sm">Integration Steps:</h4>
                <ol className="list-decimal list-inside space-y-2 text-sm text-dashboard-gray-600">
                  <li>Navigate to your {PRODUCT_INTEGRATIONS.find(i => i.id === selectedIntegration)?.name} account settings</li>
                  <li>Generate an API key or access token</li>
                  <li>Copy the API credentials</li>
                  <li>Return here and paste the credentials</li>
                  <li>Test the connection to verify setup</li>
                </ol>
              </div>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm text-blue-800">
                  <strong>Note:</strong> You can complete this setup after creating your account. The integration will be marked as pending until configured.
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
              <Button onClick={handleEnableIntegration}>
                Mark as Enabled
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
};
