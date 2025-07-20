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
import {
  ACCOUNT_TEMPLATES,
  type AccountTemplate,
} from "@/data/accountTemplates";
import { WizardStep1BasicInfo } from "./wizard/WizardStep1BasicInfo";
import { WizardStep2TemplateSelection } from "./wizard/WizardStep2TemplateSelection";
import { WizardStep3Configuration } from "./wizard/WizardStep3Configuration";
import { WizardStep4Settings } from "./wizard/WizardStep4Settings";
import { validateAccountCreation } from "./validation/accountValidation";
import { ErrorBoundary } from "./ErrorBoundary";

export interface AccountCreationData {
  // Step 1: Basic Information
  account_name: string;
  description: string;
  industry: string;
  location: string;
  website: string;

  // Step 2: Template Selection
  template_id: string;

  // Step 3: Configuration
  objectives: string[];
  channels: string[];
  kpis: string[];
  timezone: string;

  // Step 4: Settings
  auto_sync: boolean;
  performance_alerts: boolean;
  budget_alerts: boolean;
  data_retention: number;
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
  const [validationErrors, setValidationErrors] = useState<
    Array<{ field: string; message: string }>
  >([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [formData, setFormData] = useState<AccountCreationData>({
    account_name: "",
    description: "",
    industry: "",
    location: "",
    website: "",
    template_id: "",
    objectives: [],
    channels: [],
    kpis: [],
    timezone: "America/New_York",
    auto_sync: true,
    performance_alerts: true,
    budget_alerts: true,
    data_retention: 365,
  });

  const totalSteps = 4;
  const progress = (currentStep / totalSteps) * 100;

  const selectedTemplate = formData.template_id
    ? ACCOUNT_TEMPLATES[formData.template_id]
    : null;

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

  const handleTemplateSelect = (template: AccountTemplate) => {
    setFormData({
      ...formData,
      template_id: template.id,
      industry: template.recommendedSettings.industry,
      timezone: template.recommendedSettings.timezone,
      objectives: template.defaultObjectives,
      channels: template.defaultChannels,
      kpis: template.defaultKPIs,
    });
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

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return formData.account_name.trim() !== "" && formData.industry !== "";
      case 2:
        return formData.template_id !== "";
      case 3:
        return formData.objectives.length > 0 && formData.channels.length > 0;
      case 4:
        return true;
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
                  Template
                </span>
                <span
                  className={currentStep >= 3 ? "text-brand-medium-blue" : ""}
                >
                  Configuration
                </span>
                <span
                  className={currentStep >= 4 ? "text-brand-medium-blue" : ""}
                >
                  Settings
                </span>
              </div>
            </div>

            {/* Step Content */}
            <div className="min-h-[400px]">
              {currentStep === 1 && (
                <WizardStep1BasicInfo
                  formData={formData}
                  setFormData={setFormData}
                />
              )}

              {currentStep === 2 && (
                <WizardStep2TemplateSelection
                  formData={formData}
                  selectedCategory={selectedCategory}
                  setSelectedCategory={setSelectedCategory}
                  onTemplateSelect={handleTemplateSelect}
                />
              )}

              {currentStep === 3 && selectedTemplate && (
                <WizardStep3Configuration
                  formData={formData}
                  setFormData={setFormData}
                  selectedTemplate={selectedTemplate}
                />
              )}

              {currentStep === 4 && (
                <WizardStep4Settings
                  formData={formData}
                  setFormData={setFormData}
                  selectedTemplate={selectedTemplate}
                />
              )}
            </div>

            {/* Error Display */}
            {(submitError || validationErrors.length > 0) && (
              <Alert variant="destructive" className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {submitError ||
                    "Please fix the validation errors before continuing."}
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
