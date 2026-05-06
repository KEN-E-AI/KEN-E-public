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
        <p className="text-sm text-[var(--color-text-tertiary)] mt-2">
          Please review your account configuration before creating your account.
        </p>
      </CardHeader>
      <CardContent>
        {/* Account Summary */}
        <div className="p-6 bg-brand-light-blue/10 rounded-lg border border-brand-light-blue/20">
          <h4 className="text-lg font-semibold mb-4 text-[var(--color-text-primary)]">
            Account Summary
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="space-y-3">
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Account Name
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.account_name}
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Industry
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.industry}
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Template
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {selectedTemplate?.name || "Not loaded"}
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Websites
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.websites.filter((w) => w.trim() !== "").length}{" "}
                  configured
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Data Region
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.data_region}
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Timezone
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.timezone}
                </p>
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Marketing Channels
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.marketing_channels.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Product Integrations
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.product_integrations.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Objectives
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.objectives.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  KPIs
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.kpis.length} selected
                </p>
              </div>
              <div>
                <p className="font-medium text-[var(--color-text-secondary)]">
                  Customer Regions
                </p>
                <p className="text-[var(--color-text-tertiary)]">
                  {formData.region.length} selected
                </p>
              </div>
              {formData.estimated_annual_ad_budget && (
                <div>
                  <p className="font-medium text-[var(--color-text-secondary)]">
                    Annual Ad Budget
                  </p>
                  <p className="text-[var(--color-text-tertiary)]">
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
