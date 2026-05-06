import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { BarChart3, Search, Check } from "lucide-react";
import {
  MARKETING_CHANNELS_WITH_DESCRIPTIONS,
  type MarketingChannelInfo,
} from "@/data/marketingChannelsWithDescriptions";
import { ValidationAlert } from "@/components/ui/ValidationAlert";
import { validateMarketingChannelsWithBudget } from "@/lib/validation/marketingChannelValidation";
import type { AccountCreationData } from "../AccountCreationWizard";
import type { IndustryTemplate } from "@/services/templateService";
import type { ValidationMessage } from "@/types/validation";

interface WizardStep2MarketingChannelsImprovedProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
  selectedTemplate?: IndustryTemplate | null;
  showValidation?: boolean;
}

export const WizardStep2MarketingChannelsImproved = ({
  formData,
  setFormData,
  selectedTemplate,
  showValidation = true,
}: WizardStep2MarketingChannelsImprovedProps) => {
  const [searchTerm, setSearchTerm] = useState("");

  const handleChannelToggle = (channelName: string, checked: boolean) => {
    if (checked) {
      if (!formData.marketing_channels.includes(channelName)) {
        setFormData({
          ...formData,
          marketing_channels: [...formData.marketing_channels, channelName],
        });
      }
    } else {
      setFormData({
        ...formData,
        marketing_channels: formData.marketing_channels.filter(
          (c) => c !== channelName,
        ),
      });
    }
  };

  // Filter channels based on search term
  const filteredChannels = useMemo(() => {
    let channels: MarketingChannelInfo[] = MARKETING_CHANNELS_WITH_DESCRIPTIONS;

    if (searchTerm) {
      channels = channels.filter(
        (channel) =>
          channel.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          channel.description.toLowerCase().includes(searchTerm.toLowerCase()),
      );
    }

    return channels;
  }, [searchTerm]);

  // Validate current selections
  const validationResult = validateMarketingChannelsWithBudget(
    formData.marketing_channels,
    formData.estimated_annual_ad_budget,
  );

  // Convert validation result to UI messages
  const validationMessages: ValidationMessage[] = [
    ...validationResult.errors.map((error) => ({
      severity: "error" as const,
      message: error,
      field: "marketing_channels",
    })),
    ...validationResult.warnings.map((warning) => ({
      severity: "warning" as const,
      message: warning,
      field: "marketing_channels",
    })),
  ];

  return (
    <Card className="w-full max-w-5xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-brand-medium-blue" />
          Marketing Channels
        </CardTitle>
        <p className="text-sm text-[var(--color-text-tertiary)]">
          Select the marketing channels you currently use or plan to use.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Validation Messages */}
        {showValidation && validationMessages.length > 0 && (
          <ValidationAlert messages={validationMessages} />
        )}

        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-disabled)]" />
          <Input
            type="text"
            placeholder="Search marketing channels..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Channel List */}
        <div className="space-y-2 max-h-[500px] overflow-y-auto pr-2">
          {filteredChannels.length === 0 ? (
            <div className="text-center py-8 text-[var(--color-text-tertiary)]">
              No channels found matching your search.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredChannels.map((channel) => {
                const isSelected = formData.marketing_channels.includes(
                  channel.name,
                );

                return (
                  <div
                    key={channel.id}
                    className={`flex items-start space-x-3 p-3 rounded-lg border transition-all ${
                      isSelected
                        ? "border-brand-medium-blue bg-brand-light-blue/5"
                        : "border-[var(--color-border-default)] hover:border-[var(--color-border-default)] hover:bg-[var(--color-bg-secondary)]"
                    }`}
                  >
                    <Checkbox
                      id={`channel-${channel.id}`}
                      checked={isSelected}
                      onCheckedChange={(checked) =>
                        handleChannelToggle(channel.name, checked as boolean)
                      }
                      className="mt-0.5"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <Label
                            htmlFor={`channel-${channel.id}`}
                            className="text-sm font-medium text-[var(--color-text-secondary)] cursor-pointer"
                          >
                            {channel.name}
                          </Label>
                          <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                            {channel.description}
                          </p>
                        </div>
                        {isSelected && (
                          <Check className="h-4 w-4 text-brand-medium-blue ml-2 flex-shrink-0" />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected count indicator */}
        {formData.marketing_channels.length > 0 && (
          <div className="text-sm text-[var(--color-text-tertiary)] text-center">
            {formData.marketing_channels.length} channel
            {formData.marketing_channels.length !== 1 ? "s" : ""} selected
          </div>
        )}
      </CardContent>
    </Card>
  );
};
