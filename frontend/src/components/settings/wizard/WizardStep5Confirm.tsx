import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle } from "lucide-react";
import { AccountCreationData } from "../AccountCreationWizard";
import { type IndustryTemplate } from "@/services/templateService";

interface WizardStep5ConfirmProps {
  formData: AccountCreationData;
  selectedTemplate: IndustryTemplate | null;
}

export const WizardStep5Confirm = ({
  formData,
  selectedTemplate,
}: WizardStep5ConfirmProps) => {
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
                  {formData.account_name}
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Industry</p>
                <p className="text-dashboard-gray-600">{formData.industry}</p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Template</p>
                <p className="text-dashboard-gray-600">
                  {selectedTemplate?.name || "Not loaded"}
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
                  Data Region
                </p>
                <p className="text-dashboard-gray-600">
                  {formData.data_region}
                </p>
              </div>
              <div>
                <p className="font-medium text-dashboard-gray-700">Timezone</p>
                <p className="text-dashboard-gray-600">{formData.timezone}</p>
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

        {/* Instructions */}
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
      </CardContent>
    </Card>
  );
};
