import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  AlertTriangle,
} from "lucide-react";
import { WizardStep1BasicInfo } from "./wizard/WizardStep1BasicInfo";
import { WizardStep2MarketingChannelsImproved } from "./wizard/WizardStep2MarketingChannelsImproved";
import { WizardStep3ProductIntegrationsImproved } from "./wizard/WizardStep3ProductIntegrationsImproved";
import { WizardStep5ConfirmImproved } from "./wizard/WizardStep5ConfirmImproved";
import { ValidationSummary } from "@/components/ui/ValidationSummary";
import {
  templateService,
  type IndustryTemplate,
} from "@/services/templateService";
import { validateAccountCreation } from "./validation/accountValidation";
import { validateCrossStepConsistency } from "@/lib/validation/crossStepValidation";
import { validateMarketingChannelsWithBudget } from "@/lib/validation/marketingChannelValidation";
import { validateProductIntegrations } from "@/lib/validation/productIntegrationValidation";
import { ErrorBoundary } from "./ErrorBoundary";
import type { ValidationResult } from "@/types/validation";

export interface AccountCreationData {
  // Step 1: Basic Information
  account_name: string;
  description: string;
  industry: string;
  websites: string[];
  estimated_annual_ad_budget: number | null;
  business_strategy_documents: File[];

  // Step 2: Template Selection (will be auto-selected based on industry)
  template_id: string;

  // Step 2: Marketing Channels
  marketing_channels: string[];

  // Step 3: Product Integrations
  product_integrations: string[];

  // Configuration fields (from step 1 and template)
  timezone: string;
  data_region: string;
  region: string[];
  objectives: string[];
  kpis: string[];
}

interface AccountCreationWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (data: AccountCreationData) => void;
}

export const AccountCreationWizard = ({
  isOpen,
  onClose,
  onComplete,
}: AccountCreationWizardProps) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadedTemplate, setLoadedTemplate] = useState<IndustryTemplate | null>(
    null,
  );
  const [validationErrors, setValidationErrors] = useState<
    Array<{ field: string; message: string }>
  >([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [formData, setFormData] = useState<AccountCreationData>({
    account_name: "",
    description: "",
    industry: "",
    websites: [""],
    estimated_annual_ad_budget: null,
    business_strategy_documents: [],
    template_id: "",
    marketing_channels: [],
    product_integrations: [],
    objectives: [],
    kpis: [],
    timezone: "America/New_York",
    data_region: "US",
    region: ["US"],
  });

  const totalSteps = 4; // Removed objectives/KPIs step
  const progress = (currentStep / totalSteps) * 100;

  const handleNext = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = async () => {
    setIsSubmitting(true);
    setValidationErrors([]);
    setSubmitError(null);

    try {
      // Validate all form data before submission
      const validation = validateAccountCreation(formData);

      if (!validation.success) {
        setValidationErrors(validation.errors || []);
        setIsSubmitting(false);
        return;
      }

      // Call the completion function with validated data
      await onComplete(validation.data);
      onClose();
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "An unexpected error occurred",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  // Get validation results for all steps
  const getStepValidations = () => {
    const step2Validation = validateMarketingChannelsWithBudget(
      formData.marketing_channels,
      formData.estimated_annual_ad_budget,
    );
    const step3Validation = validateProductIntegrations(
      formData.product_integrations,
    );
    const crossStepValidation = validateCrossStepConsistency(formData);

    return [
      {
        step: "Basic Information",
        stepNumber: 1,
        result: {
          isValid:
            formData.account_name.trim() !== "" &&
            formData.industry !== "" &&
            formData.template_id !== "" &&
            // Either websites OR business documents required
            (formData.websites.some((w) => w.trim() !== "") ||
              formData.business_strategy_documents.length > 0) &&
            formData.region.length > 0 &&
            formData.data_region !== "" &&
            formData.timezone !== "",
          errors: [],
          warnings: [],
        },
        isRequired: true,
      },
      {
        step: "Marketing Channels",
        stepNumber: 2,
        result: step2Validation,
        isRequired: true,
      },
      {
        step: "Product Integrations",
        stepNumber: 3,
        result: step3Validation,
        isRequired: false, // Optional step
      },
      {
        step: "Overall Consistency",
        stepNumber: 5,
        result: crossStepValidation,
        isRequired: false,
      },
    ];
  };

  const stepValidations = getStepValidations();

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return (
          formData.account_name.trim() !== "" &&
          formData.industry !== "" &&
          formData.template_id !== "" &&
          // Either websites OR business documents required
          (formData.websites.some((w) => w.trim() !== "") ||
            formData.business_strategy_documents.length > 0) &&
          formData.region.length > 0 &&
          formData.data_region !== "" &&
          formData.timezone !== ""
        );
      case 2:
        // Allow proceeding if no critical errors
        const marketingValidation = stepValidations.find(
          (v) => v.stepNumber === 2,
        );
        return marketingValidation ? marketingValidation.result.isValid : false;
      case 3:
        return true; // Product integrations are optional
      case 4:
        // Final step - check all validations
        const hasBlockingErrors = stepValidations.some(
          (v) => !v.result.isValid && v.isRequired !== false,
        );
        return !hasBlockingErrors;
      default:
        return false;
    }
  };

  if (!isOpen) return null;

  return (
    <ErrorBoundary>
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto">
          <div className="p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-dashboard-gray-900">
                  Create New Account
                </h2>
                <p className="text-dashboard-gray-600 mt-1">
                  Step {currentStep} of {totalSteps}
                </p>
              </div>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
            </div>

            {/* Progress Bar */}
            <div className="mb-8">
              <Progress value={progress} className="w-full" />
              <div className="flex justify-between mt-2 text-sm text-dashboard-gray-600">
                <span
                  className={currentStep >= 1 ? "text-brand-medium-blue" : ""}
                >
                  Basic Info
                </span>
                <span
                  className={currentStep >= 2 ? "text-brand-medium-blue" : ""}
                >
                  Channels
                </span>
                <span
                  className={currentStep >= 3 ? "text-brand-medium-blue" : ""}
                >
                  Integrations
                </span>
                <span
                  className={currentStep >= 4 ? "text-brand-medium-blue" : ""}
                >
                  Confirm
                </span>
              </div>
            </div>

            {/* Step Content */}
            <div className="min-h-[400px]">
              {currentStep === 1 && (
                <WizardStep1BasicInfo
                  formData={formData}
                  setFormData={setFormData}
                  onTemplateLoad={setLoadedTemplate}
                />
              )}

              {currentStep === 2 && (
                <WizardStep2MarketingChannelsImproved
                  formData={formData}
                  setFormData={setFormData}
                  selectedTemplate={loadedTemplate}
                />
              )}

              {currentStep === 3 && (
                <WizardStep3ProductIntegrationsImproved
                  formData={formData}
                  setFormData={setFormData}
                  selectedTemplate={loadedTemplate}
                />
              )}

              {currentStep === 4 && (
                <div className="space-y-6">
                  <WizardStep5ConfirmImproved
                    formData={formData}
                    selectedTemplate={loadedTemplate}
                  />

                  {/* Validation Summary */}
                  <ValidationSummary
                    validations={stepValidations}
                    canProceed={canProceed()}
                    onFixIssues={(stepNumber) => setCurrentStep(stepNumber)}
                  />
                </div>
              )}
            </div>

            {/* Error Display */}
            {(submitError || validationErrors.length > 0) && (
              <Alert variant="destructive" className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {submitError || (
                    <>
                      Please fix the validation errors in the following fields:{" "}
                      <strong>
                        {validationErrors
                          .map((error) => {
                            // Convert field names to more readable format
                            const fieldName = error.field
                              .replace(/_/g, " ")
                              .replace(/\b\w/g, (l) => l.toUpperCase());
                            return fieldName;
                          })
                          .join(", ")}
                      </strong>
                    </>
                  )}
                </AlertDescription>
              </Alert>
            )}

            {/* Navigation */}
            <div className="flex justify-between mt-8">
              <Button
                variant="outline"
                onClick={handlePrevious}
                disabled={currentStep === 1 || isSubmitting}
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Previous
              </Button>

              {currentStep < totalSteps ? (
                <Button
                  onClick={handleNext}
                  disabled={!canProceed() || isSubmitting}
                >
                  Next
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              ) : (
                <Button
                  onClick={handleComplete}
                  disabled={!canProceed() || isSubmitting}
                >
                  <CheckCircle className="h-4 w-4 mr-2" />
                  {isSubmitting ? "Creating Account..." : "Create Account"}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
};
