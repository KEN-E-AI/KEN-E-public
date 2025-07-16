import { Settings, ChevronRight, AlertTriangle } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

interface AdvancedSettingsAccordionProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
  warningText?: string;
  defaultOpen?: boolean;
  className?: string;
}

export const AdvancedSettingsAccordion = ({
  children,
  title = "Advanced Settings",
  description = "These settings are for advanced users and can affect system behavior.",
  warningText,
  defaultOpen = false,
  className,
}: AdvancedSettingsAccordionProps) => {
  return (
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
          <div className="flex items-center gap-3 w-full">
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
        </AccordionTrigger>
        <AccordionContent className="px-4 pb-4">
          <div className="space-y-4">
            {description && (
              <p className="text-sm text-gray-600 mb-3">{description}</p>
            )}

            {warningText && (
              <Alert className="border-yellow-200 bg-yellow-50">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <AlertDescription className="text-yellow-800">
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
}

export const ProgressiveDisclosure = ({
  basicSettings,
  advancedSettings,
  advancedTitle = "Advanced Settings",
  advancedDescription = "Additional configuration options for power users.",
  advancedWarning,
  className,
}: ProgressiveDisclosureProps) => {
  return (
    <div className={className}>
      {/* Basic Settings */}
      <div className="space-y-6 mb-6">{basicSettings}</div>

      {/* Advanced Settings */}
      <AdvancedSettingsAccordion
        title={advancedTitle}
        description={advancedDescription}
        warningText={advancedWarning}
      >
        <div className="space-y-6">{advancedSettings}</div>
      </AdvancedSettingsAccordion>
    </div>
  );
};
