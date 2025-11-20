import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  AlertTriangle,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { WizardStep1BasicInfo } from "./wizard/WizardStep1BasicInfo";
import { WizardStep2MarketingChannelsImproved } from "./wizard/WizardStep2MarketingChannelsImproved";
import { WizardStep3ProductIntegrationsImproved } from "./wizard/WizardStep3ProductIntegrationsImproved";
import { WizardStep4StrategySelection } from "./wizard/WizardStep4StrategySelection";
import { WizardStep5ConfirmImproved } from "./wizard/WizardStep5ConfirmImproved";
import {
  templateService,
  type IndustryTemplate,
} from "@/services/templateService";
import { validateAccountCreation } from "./validation/accountValidation";
import { validateCrossStepConsistency } from "@/lib/validation/crossStepValidation";
import { validateMarketingChannelsWithBudget } from "@/lib/validation/marketingChannelValidation";
import { validateProductIntegrations } from "@/lib/validation/productIntegrationValidation";
import { ErrorBoundary } from "./ErrorBoundary";

export interface AccountCreationData {
  // Step 1: Basic Information
  account_name: string;
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

  // Step 4: Strategy Selection (admin only)
  enabled_strategies: string[];
  override_product_categories: string[];

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
  const { isSuperAdmin } = useAuth();
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
    industry: "",
    websites: [""],
    estimated_annual_ad_budget: null,
    business_strategy_documents: [],
    template_id: "",
    marketing_channels: [],
    product_integrations: [],
    enabled_strategies: [
      "business_strategy",
      "competitive_strategy",
      "marketing_strategy",
      "brand_guidelines",
    ],
    override_product_categories: [],
    objectives: [],
    kpis: [],
    timezone: "America/New_York",
    data_region: "US",
    region: ["US"],
  });

  const STRATEGY_STEP = 4;
  const CONFIRMATION_STEP = 5;

  const totalSteps = isSuperAdmin ? 5 : 4; // Hide strategy selection step for non-super-admins

  // For non-super-admins, map step 5 to display as step 4
  const displayStep =
    !isSuperAdmin && currentStep === CONFIRMATION_STEP ? 4 : currentStep;
  const progress = (displayStep / totalSteps) * 100;

  // Reset wizard state when modal opens
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(1);
      setFormData({
        account_name: "",
        industry: "",
        websites: [""],
        estimated_annual_ad_budget: null,
        business_strategy_documents: [],
        template_id: "",
        marketing_channels: [],
        product_integrations: [],
        enabled_strategies: [
          "business_strategy",
          "competitive_strategy",
          "marketing_strategy",
          "brand_guidelines",
        ],
        override_product_categories: [],
        objectives: [],
        kpis: [],
        timezone: "America/New_York",
        data_region: "US",
        region: ["US"],
      });
      setValidationErrors([]);
      setSubmitError(null);
      setIsSubmitting(false);
      setLoadedTemplate(null);
      setSelectedCategory("All");
    }
  }, [isOpen]);

  const handleNext = () => {
    let nextStep = currentStep + 1;

    // Skip strategy selection step for non-super-admins
    if (!isSuperAdmin && nextStep === STRATEGY_STEP) {
      nextStep = CONFIRMATION_STEP;
    }

    const maxStep = CONFIRMATION_STEP;
    if (nextStep <= maxStep) {
      setCurrentStep(nextStep);
    }
  };

  const handlePrevious = () => {
    let prevStep = currentStep - 1;

    // Skip strategy selection step when going back if not super admin
    if (!isSuperAdmin && prevStep === STRATEGY_STEP) {
      prevStep = 3;
    }

    if (prevStep >= 1) {
      setCurrentStep(prevStep);
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
        // Strategy selection step (super-admin only)
        if (isSuperAdmin) {
          const hasStrategy = formData.enabled_strategies.length > 0;
          // If marketing without business, require product categories
          const needsCategories =
            formData.enabled_strategies.includes("marketing_strategy") &&
            !formData.enabled_strategies.includes("business_strategy");
          const hasCategories = formData.override_product_categories.length > 0;
          return hasStrategy && (!needsCategories || hasCategories);
        }
        // Non-admins should never reach this step
        return false;
      case 5:
        // Confirmation step - validate everything
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
                  Step {displayStep} of {totalSteps}
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
                  className={displayStep >= 1 ? "text-brand-medium-blue" : ""}
                >
                  Basic Info
                </span>
                <span
                  className={displayStep >= 2 ? "text-brand-medium-blue" : ""}
                >
                  Channels
                </span>
                <span
                  className={displayStep >= 3 ? "text-brand-medium-blue" : ""}
                >
                  Integrations
                </span>
                <span
                  className={displayStep >= 4 ? "text-brand-medium-blue" : ""}
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

              {currentStep === STRATEGY_STEP && isSuperAdmin && (
                <WizardStep4StrategySelection
                  enabled_strategies={formData.enabled_strategies}
                  override_product_categories={
                    formData.override_product_categories
                  }
                  onUpdate={(data) => setFormData({ ...formData, ...data })}
                />
              )}

              {currentStep === CONFIRMATION_STEP && (
                <WizardStep5ConfirmImproved
                  formData={formData}
                  selectedTemplate={loadedTemplate}
                />
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
