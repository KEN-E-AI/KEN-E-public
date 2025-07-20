import {
  Settings,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Clock,
  AlertCircle,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PermissionAwareContainer } from "./PermissionAwareContainer";

interface AdvancedSettingsAccordionProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
  warningText?: string;
  defaultOpen?: boolean;
  className?: string;
  requiredPermission?: string;
  requiredRole?: "admin" | "member" | "viewer";
  showCompletionStatus?: boolean;
  completedSteps?: number;
  totalSteps?: number;
}

export const AdvancedSettingsAccordion = ({
  children,
  title = "Advanced Settings",
  description = "These settings are for advanced users and can affect system behavior.",
  warningText,
  defaultOpen = false,
  className,
  requiredPermission,
  requiredRole = "member",
  showCompletionStatus = false,
  completedSteps = 0,
  totalSteps = 1,
}: AdvancedSettingsAccordionProps) => {
  const getCompletionStatus = () => {
    if (totalSteps === 0) return { status: "incomplete", progress: 0 };
    const progress = (completedSteps / totalSteps) * 100;

    if (progress === 100) return { status: "complete", progress };
    if (progress > 50) return { status: "warning", progress };
    return { status: "incomplete", progress };
  };

  const { status, progress } = getCompletionStatus();

  const getStatusIcon = () => {
    switch (status) {
      case "complete":
        return <CheckCircle className="h-3 w-3 text-brand-dark-blue" />;
      case "warning":
        return <AlertCircle className="h-3 w-3 text-brand-dark-blue" />;
      case "incomplete":
        return <Clock className="h-3 w-3 text-gray-600" />;
      default:
        return <Clock className="h-3 w-3 text-gray-600" />;
    }
  };

  const accordionContent = (
    <Accordion
      type="single"
      collapsible
      defaultValue={defaultOpen ? "advanced" : undefined}
      className={className}
    >
      <AccordionItem
        value="advanced"
        className="border border-orange-200 rounded-lg"
      >
        <AccordionTrigger className="px-4 py-3 hover:no-underline">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Settings className="h-4 w-4 text-orange-600" />
                <span className="font-medium">{title}</span>
              </div>
              <Badge
                variant="outline"
                className="text-orange-600 border-orange-300"
              >
                Advanced
              </Badge>
            </div>
            {showCompletionStatus && (
              <div className="flex items-center gap-2 mr-4">
                {getStatusIcon()}
                <span className="text-xs text-gray-600">
                  {completedSteps}/{totalSteps}
                </span>
              </div>
            )}
          </div>
        </AccordionTrigger>
        <AccordionContent className="px-4 pb-4">
          <div className="space-y-4">
            {description && (
              <p className="text-sm text-gray-600 mb-3">{description}</p>
            )}

            {showCompletionStatus && (
              <div className="space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-600">Configuration Progress</span>
                  <span className="text-gray-900 font-medium">
                    {Math.round(progress)}%
                  </span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>
            )}

            {warningText && (
              <Alert className="border-brand-yellow/40 bg-brand-yellow/20">
                <AlertTriangle className="h-4 w-4 text-brand-dark-blue" />
                <AlertDescription className="text-brand-dark-blue">
                  <strong>Warning:</strong> {warningText}
                </AlertDescription>
              </Alert>
            )}

            <div className="border-t pt-4">{children}</div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );

  // If permission is required, wrap with PermissionAwareContainer
  if (requiredPermission) {
    return (
      <PermissionAwareContainer
        requiredPermission={requiredPermission}
        requiredRole={requiredRole}
        gracefulDegradation={true}
      >
        {accordionContent}
      </PermissionAwareContainer>
    );
  }

  return accordionContent;
};

interface SettingsGroupProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export const SettingsGroup = ({
  title,
  description,
  children,
  className,
}: SettingsGroupProps) => {
  return (
    <div className={className}>
      <div className="mb-4">
        <h3 className="text-sm font-medium text-gray-900 mb-1">{title}</h3>
        {description && <p className="text-sm text-gray-600">{description}</p>}
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
};

interface ProgressiveDisclosureProps {
  basicSettings: React.ReactNode;
  advancedSettings: React.ReactNode;
  advancedTitle?: string;
  advancedDescription?: string;
  advancedWarning?: string;
  className?: string;
  requiredPermissionForAdvanced?: string;
  requiredRoleForAdvanced?: "admin" | "member" | "viewer";
  showCompletionStatus?: boolean;
  basicCompletedSteps?: number;
  basicTotalSteps?: number;
  advancedCompletedSteps?: number;
  advancedTotalSteps?: number;
}

export const ProgressiveDisclosure = ({
  basicSettings,
  advancedSettings,
  advancedTitle = "Advanced Settings",
  advancedDescription = "Additional configuration options for power users.",
  advancedWarning,
  className,
  requiredPermissionForAdvanced,
  requiredRoleForAdvanced = "member",
  showCompletionStatus = false,
  basicCompletedSteps = 0,
  basicTotalSteps = 1,
  advancedCompletedSteps = 0,
  advancedTotalSteps = 1,
}: ProgressiveDisclosureProps) => {
  const basicProgress =
    basicTotalSteps > 0 ? (basicCompletedSteps / basicTotalSteps) * 100 : 0;

  return (
    <div className={className}>
      {/* Basic Settings */}
      <div className="space-y-6 mb-6">
        {showCompletionStatus && (
          <div className="bg-gray-50 rounded-lg p-4 mb-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-900">
                Basic Configuration
              </h3>
              <span className="text-xs text-gray-600">
                {basicCompletedSteps}/{basicTotalSteps}
              </span>
            </div>
            <Progress value={basicProgress} className="h-2" />
          </div>
        )}
        {basicSettings}
      </div>

      {/* Advanced Settings */}
      <AdvancedSettingsAccordion
        title={advancedTitle}
        description={advancedDescription}
        warningText={advancedWarning}
        requiredPermission={requiredPermissionForAdvanced}
        requiredRole={requiredRoleForAdvanced}
        showCompletionStatus={showCompletionStatus}
        completedSteps={advancedCompletedSteps}
        totalSteps={advancedTotalSteps}
      >
        <div className="space-y-6">{advancedSettings}</div>
      </AdvancedSettingsAccordion>
    </div>
  );
};
