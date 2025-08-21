import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { BarChart3, TrendingUp } from "lucide-react";
import {
  MARKETING_CHANNELS,
  MARKETING_CHANNEL_CATEGORIES,
} from "@/data/marketingChannels";
import type { AccountCreationData } from "../AccountCreationWizard";
import type { IndustryTemplate } from "@/services/templateService";

interface WizardStep2MarketingChannelsProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
  selectedTemplate?: IndustryTemplate | null;
}

export const WizardStep2MarketingChannels = ({
  formData,
  setFormData,
  selectedTemplate,
}: WizardStep2MarketingChannelsProps) => {
  const handleChannelToggle = (channel: string, checked: boolean) => {
    if (checked) {
      setFormData({
        ...formData,
        marketing_channels: [...formData.marketing_channels, channel],
      });
    } else {
      setFormData({
        ...formData,
        marketing_channels: formData.marketing_channels.filter(
          (c) => c !== channel,
        ),
      });
    }
  };

  const isChannelRecommended = (channel: string) => {
    return selectedTemplate?.marketingChannels?.includes(channel) || false;
  };

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-brand-medium-blue" />
          Marketing Channels
        </CardTitle>
        <p className="text-sm text-dashboard-gray-600">
          Select the marketing channels you currently use or plan to use.
          {selectedTemplate && (
            <span className="text-brand-medium-blue font-medium">
              {" "}
              We've pre-selected channels recommended for{" "}
              {selectedTemplate.industry}.
            </span>
          )}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Channel Categories */}
        {Object.entries(MARKETING_CHANNEL_CATEGORIES).map(
          ([category, channels]) => (
            <div key={category}>
              <h3 className="font-medium mb-3 text-dashboard-gray-800 flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                {category}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {channels.map((channel) => {
                  const isSelected =
                    formData.marketing_channels.includes(channel);
                  const isRecommended = isChannelRecommended(channel);

                  return (
                    <div
                      key={channel}
                      className={`flex items-start space-x-3 p-3 rounded-lg border transition-colors ${
                        isSelected
                          ? "border-brand-medium-blue bg-brand-light-blue/10"
                          : "border-dashboard-gray-200 hover:border-dashboard-gray-300"
                      }`}
                    >
                      <Checkbox
                        id={`channel-${channel}`}
                        checked={isSelected}
                        onCheckedChange={(checked) =>
                          handleChannelToggle(channel, checked as boolean)
                        }
                        className="mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <Label
                          htmlFor={`channel-${channel}`}
                          className="text-sm font-medium text-dashboard-gray-800 cursor-pointer"
                        >
                          {channel}
                        </Label>
                        {isRecommended && (
                          <div className="mt-1">
                            <Badge variant="secondary" className="text-xs">
                              Recommended
                            </Badge>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ),
        )}

        {/* Selected channels summary */}
        {formData.marketing_channels.length > 0 && (
          <Card className="bg-brand-light-blue/5 border-brand-light-blue/20">
            <CardContent className="pt-4">
              <h4 className="font-medium text-sm text-dashboard-gray-800 mb-2">
                Selected Channels ({formData.marketing_channels.length})
              </h4>
              <div className="flex flex-wrap gap-2">
                {formData.marketing_channels.map((channel) => (
                  <Badge
                    key={channel}
                    variant={
                      isChannelRecommended(channel) ? "default" : "secondary"
                    }
                    className="text-xs"
                  >
                    {channel}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );
};
