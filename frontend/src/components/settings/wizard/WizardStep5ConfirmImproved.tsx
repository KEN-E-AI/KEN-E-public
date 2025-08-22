import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle, AlertCircle, XCircle } from "lucide-react";
import { AccountCreationData } from "../AccountCreationWizard";
import { type IndustryTemplate } from "@/services/templateService";
import { validateAccountCreation } from "../validation/accountValidation";
import { validateCrossStepConsistency } from "@/lib/validation/crossStepValidation";
import { validateMarketingChannelsWithBudget } from "@/lib/validation/marketingChannelValidation";
import { validateProductIntegrations } from "@/lib/validation/productIntegrationValidation";

interface WizardStep5ConfirmImprovedProps {
  formData: AccountCreationData;
  selectedTemplate: IndustryTemplate | null;
}

export const WizardStep5ConfirmImproved = ({
  formData,
  selectedTemplate,
}: WizardStep5ConfirmImprovedProps) => {
  // Gather all validation issues
  const getValidationIssues = () => {
    const issues: string[] = [];

    // Step 1: Basic Information validation
    if (!formData.account_name.trim()) {
      issues.push("Account name is required");
    }
    if (!formData.industry) {
      issues.push("Industry selection is required");
    }
    if (!formData.template_id) {
      issues.push("Industry template is required");
    }
    if (
      !formData.websites.some((w) => w.trim() !== "") &&
      formData.business_strategy_documents.length === 0
    ) {
      issues.push("At least one website or business document is required");
    }
    if (formData.region.length === 0) {
      issues.push("At least one customer region must be selected");
    }
    if (!formData.data_region) {
      issues.push("Data storage region is required");
    }
    if (!formData.timezone) {
      issues.push("Timezone is required");
    }

    // Step 2: Marketing Channels validation
    const marketingValidation = validateMarketingChannelsWithBudget(
      formData.marketing_channels,
      formData.estimated_annual_ad_budget,
    );
    issues.push(...marketingValidation.errors);

    // Step 3: Product Integrations validation
    const integrationValidation = validateProductIntegrations(
      formData.product_integrations,
    );
    issues.push(...integrationValidation.errors);

    // Cross-step validation
    const crossStepValidation = validateCrossStepConsistency(formData);
    issues.push(...crossStepValidation.errors);

    // Overall account validation
    const accountValidation = validateAccountCreation(formData);
    if (!accountValidation.isValid) {
      issues.push(...accountValidation.errors);
    }

    return [...new Set(issues)]; // Remove duplicates
  };

  const validationIssues = getValidationIssues();
  const hasIssues = validationIssues.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CheckCircle className="h-5 w-5" />
          Confirm Account Details
        </CardTitle>
        <p className="text-sm text-dashboard-gray-600 mt-2">
          Please review your account configuration before creating your account.
        </p>
      </CardHeader>
      <CardContent>
        {/* Account Summary */}
        <div className="p-6 bg-brand-light-blue/10 rounded-lg border border-brand-light-blue/20">
          <h4 className="text-lg font-semibold mb-4 text-dashboard-gray-900">
            Account Summary
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="space-y-3">
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Account Name
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.account_name || "(Not set)"}
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Industry</p>
                <p className="text-dashboard-gray-600">
                  {formData.industry || "(Not set)"}
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Template</p>
                <p className="text-dashboard-gray-600">
                  {selectedTemplate?.industry || "Not loaded"}
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Websites</p>
                <p className="text-dashboard-gray-600">
                  {formData.websites.filter((w) => w.trim() !== "").length}{" "}
                  configured
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Business Documents
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.business_strategy_documents.length} uploaded
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Data Region
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.data_region || "(Not set)"}
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Timezone</p>
                <p className="text-dashboard-gray-600">
                  {formData.timezone || "(Not set)"}
                </p>
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Marketing Channels
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.marketing_channels.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Product Integrations
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.product_integrations.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Objectives
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.objectives.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">KPIs</p>
                <p className="text-dashboard-gray-600">
                  {formData.kpis.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">
                  Customer Regions
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.region.length} selected
                </p>
              </div>
              {formData.estimated_annual_ad_budget && (
                <div>
                  <p className="font-medium text-dashboard-gray-700">
                    Annual Ad Budget
                  </p>
                  <p className="text-dashboard-gray-600">
                    ${formData.estimated_annual_ad_budget.toLocaleString()} USD
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Status Box - Either Ready or Issues to Fix */}
        {hasIssues ? (
          <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-2">
              <XCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <h4 className="font-medium text-sm text-red-800 mb-2">
                  Issues Need to Be Resolved
                </h4>
                <p className="text-xs text-red-700 mb-3">
                  Please fix the following issues before creating your account:
                </p>
                <ul className="space-y-1 text-xs text-red-700">
                  {validationIssues.map((issue, index) => (
                    <li key={index} className="flex items-start gap-1">
                      <span className="text-red-500 mt-0.5">•</span>
                      <span>{issue}</span>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-red-700 mt-3 font-medium">
                  Click the "Previous" button to go back and fix these issues.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-start gap-2">
              <CheckCircle className="h-4 w-4 text-green-600 mt-0.5" />
              <div>
                <h4 className="font-medium text-sm text-green-800 mb-1">
                  Ready to Create Account
                </h4>
                <p className="text-xs text-green-700">
                  Click "Create Account" to set up your account with the
                  configuration above. You can modify most settings after your
                  account is created.
                </p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
