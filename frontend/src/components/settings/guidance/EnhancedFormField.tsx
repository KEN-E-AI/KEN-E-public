import React, { useState } from "react";
import { ChevronDown, ChevronUp, Lightbulb, Info } from "lucide-react";
import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
} from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScopeTooltip, ScopeHelpIcon } from "./ScopeTooltip";
import { ScopeIndicator, InheritanceChain } from "./ScopeBadge";
import { useSmartDefaults } from "./useSmartDefaults";

interface EnhancedFormFieldProps {
  name: string;
  label: string;
  helpText?: string;
  scope: "organization" | "account" | "user";
  showInheritance?: boolean;
  showRecommendations?: boolean;
  children: React.ReactNode;
  control: any;
  className?: string;
}

export const EnhancedFormField = ({
  name,
  label,
  helpText,
  scope,
  showInheritance = true,
  showRecommendations = true,
  children,
  control,
  className,
}: EnhancedFormFieldProps) => {
  const [showDetails, setShowDetails] = useState(false);
  const { getDefaultValue, getInheritanceChain, getRecommendation } =
    useSmartDefaults(scope);

  const defaultResult = getDefaultValue(name);
  const inheritanceChain = getInheritanceChain(name);
  const recommendation = getRecommendation(name);

  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem className={className}>
          <div className="flex items-center justify-between">
            <FormLabel className="flex items-center gap-2">
              {label}
              <ScopeHelpIcon scope={scope} setting={name} />
            </FormLabel>
            <div className="flex items-center gap-2">
              {showInheritance && defaultResult.inheritedFrom !== scope && (
                <ScopeIndicator
                  scope={defaultResult.inheritedFrom}
                  source={defaultResult.source}
                  inherited={true}
                />
              )}
              {(showInheritance && inheritanceChain.length > 1) ||
              recommendation ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDetails(!showDetails)}
                  className="h-6 px-2 text-xs"
                >
                  <Info className="h-3 w-3 mr-1" />
                  Details
                  {showDetails ? (
                    <ChevronUp className="h-3 w-3 ml-1" />
                  ) : (
                    <ChevronDown className="h-3 w-3 ml-1" />
                  )}
                </Button>
              ) : null}
            </div>
          </div>

          <FormControl>
            {React.cloneElement(children as React.ReactElement, { ...field })}
          </FormControl>

          {helpText && (
            <FormDescription className="text-sm text-[var(--color-text-tertiary)]">
              {helpText}
            </FormDescription>
          )}

          <Collapsible open={showDetails} onOpenChange={setShowDetails}>
            <CollapsibleContent className="space-y-3">
              {/* Recommendation */}
              {showRecommendations && recommendation && (
                <Alert className="border-orange-200 bg-orange-50">
                  <Lightbulb className="h-4 w-4 text-orange-600" />
                  <AlertDescription className="text-orange-800">
                    <strong>Recommendation:</strong> {recommendation.reason}
                    <div className="mt-1 text-sm font-mono bg-orange-100 px-2 py-1 rounded">
                      {String(recommendation.value)}
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              {/* Inheritance Chain */}
              {showInheritance && inheritanceChain.length > 1 && (
                <div className="border rounded-md p-3 bg-[var(--color-bg-secondary)]">
                  <div className="text-sm font-medium mb-2">
                    Setting Inheritance:
                  </div>
                  <InheritanceChain
                    // SmartDefaultResult's `inheritedFrom` aligns with
                    // InheritanceChain's `scope` field at runtime; their
                    // type shapes diverge cosmetically. Cast to bridge.
                    chain={
                      inheritanceChain as unknown as {
                        scope:
                          | "template"
                          | "user"
                          | "organization"
                          | "account"
                          | "system";
                        value: unknown;
                        source?: string;
                      }[]
                    }
                    currentScope={scope}
                    className="mb-2"
                  />
                  <div className="text-xs text-[var(--color-text-tertiary)]">
                    This setting inherits from {defaultResult.source}.
                    {defaultResult.canOverride &&
                      " You can override this value."}
                  </div>
                </div>
              )}

              {/* Current Value Info */}
              <div className="text-xs text-[var(--color-text-tertiary)] p-2 bg-[var(--color-bg-secondary)] rounded">
                <div className="flex items-center justify-between">
                  <span>Current value source:</span>
                  <ScopeIndicator
                    scope={defaultResult.inheritedFrom}
                    source={defaultResult.source}
                    showTooltip={false}
                  />
                </div>
                {defaultResult.value && (
                  <div className="mt-1 font-mono text-xs">
                    {String(defaultResult.value)}
                  </div>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>

          <FormMessage />
        </FormItem>
      )}
    />
  );
};

// Simplified version without advanced features
export const SimpleEnhancedFormField = ({
  name,
  label,
  helpText,
  scope,
  children,
  control,
  className,
}: Omit<EnhancedFormFieldProps, "showInheritance" | "showRecommendations">) => {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem className={className}>
          <FormLabel className="flex items-center gap-2">
            {label}
            <ScopeHelpIcon scope={scope} setting={name} />
          </FormLabel>
          <FormControl>
            {React.cloneElement(children as React.ReactElement, { ...field })}
          </FormControl>
          {helpText && (
            <FormDescription className="text-sm text-[var(--color-text-tertiary)]">
              {helpText}
            </FormDescription>
          )}
          <FormMessage />
        </FormItem>
      )}
    />
  );
};
