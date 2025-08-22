import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { BarChart3, Search, Check } from "lucide-react";
import {
  MARKETING_CHANNELS_WITH_DESCRIPTIONS,
  MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS,
  CATEGORY_DESCRIPTIONS,
  getChannelInfoByName,
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
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
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

  const isChannelRecommended = (channelName: string) => {
    return selectedTemplate?.marketingChannels?.includes(channelName) || false;
  };

  // Filter channels based on category and search term
  const filteredChannels = useMemo(() => {
    let channels: MarketingChannelInfo[] = [];

    if (selectedCategory === "All") {
      channels = MARKETING_CHANNELS_WITH_DESCRIPTIONS;
    } else {
      channels =
        MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS[selectedCategory] || [];
    }

    if (searchTerm) {
      channels = channels.filter(
        (channel) =>
          channel.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          channel.description.toLowerCase().includes(searchTerm.toLowerCase()),
      );
    }

    return channels;
  }, [selectedCategory, searchTerm]);

  // Get category counts for badges
  const getCategoryCount = (category: string) => {
    if (category === "All") {
      return formData.marketing_channels.length;
    }
    const categoryChannels =
      MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS[category] || [];
    return categoryChannels.filter((channel) =>
      formData.marketing_channels.includes(channel.name),
    ).length;
  };

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

  const categories = [
    "All",
    ...Object.keys(MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS),
  ];

  return (
    <Card className="w-full max-w-5xl mx-auto">
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
              We've highlighted channels recommended for{" "}
              {selectedTemplate.industry}.
            </span>
          )}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Validation Messages */}
        {showValidation && validationMessages.length > 0 && (
          <ValidationAlert messages={validationMessages} />
        )}

        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dashboard-gray-400" />
          <Input
            type="text"
            placeholder="Search marketing channels..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Category Tabs */}
        <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
          <TabsList className="w-full flex-wrap h-auto p-1 gap-1">
            {categories.map((category) => {
              const count = getCategoryCount(category);
              return (
                <TabsTrigger
                  key={category}
                  value={category}
                  className="data-[state=active]:bg-brand-medium-blue data-[state=active]:text-white relative"
                >
                  {category}
                  {count > 0 && (
                    <Badge
                      variant="secondary"
                      className="ml-2 h-5 px-1.5 min-w-[20px] bg-brand-light-blue/20 text-brand-dark-blue"
                    >
                      {count}
                    </Badge>
                  )}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {/* Channel List for Each Category */}
          {categories.map((category) => (
            <TabsContent
              key={category}
              value={category}
              className="mt-4 space-y-2"
            >
              {category !== "All" && CATEGORY_DESCRIPTIONS[category] && (
                <p className="text-sm text-dashboard-gray-600 mb-3">
                  {CATEGORY_DESCRIPTIONS[category]}
                </p>
              )}

              <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
                {filteredChannels.length === 0 ? (
                  <div className="text-center py-8 text-dashboard-gray-500">
                    No channels found matching your search.
                  </div>
                ) : (
                  filteredChannels.map((channel) => {
                    const isSelected = formData.marketing_channels.includes(
                      channel.name,
                    );
                    const isRecommended = isChannelRecommended(channel.name);

                    return (
                      <div
                        key={channel.id}
                        className={`flex items-start space-x-3 p-4 rounded-lg border transition-all ${
                          isSelected
                            ? "border-brand-medium-blue bg-brand-light-blue/5"
                            : "border-dashboard-gray-200 hover:border-dashboard-gray-300 hover:bg-dashboard-gray-50"
                        }`}
                      >
                        <Checkbox
                          id={`channel-${channel.id}`}
                          checked={isSelected}
                          onCheckedChange={(checked) =>
                            handleChannelToggle(
                              channel.name,
                              checked as boolean,
                            )
                          }
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <Label
                                htmlFor={`channel-${channel.id}`}
                                className="text-sm font-medium text-dashboard-gray-800 cursor-pointer flex items-center gap-2"
                              >
                                {channel.name}
                                {isRecommended && (
                                  <Badge
                                    variant="outline"
                                    className="text-xs border-brand-medium-blue text-brand-medium-blue"
                                  >
                                    Recommended
                                  </Badge>
                                )}
                              </Label>
                              <p className="text-sm text-dashboard-gray-600 mt-1">
                                {channel.description}
                              </p>
                            </div>
                            {isSelected && (
                              <Check className="h-5 w-5 text-brand-medium-blue ml-2 flex-shrink-0" />
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </TabsContent>
          ))}
        </Tabs>

        {/* Selected channels summary */}
        {formData.marketing_channels.length > 0 && (
          <Card className="bg-brand-light-blue/5 border-brand-light-blue/20">
            <CardContent className="pt-4">
              <h4 className="font-medium text-sm text-dashboard-gray-800 mb-2">
                Selected Channels ({formData.marketing_channels.length})
              </h4>
              <div className="flex flex-wrap gap-2">
                {formData.marketing_channels.map((channelName) => {
                  const channelInfo = getChannelInfoByName(channelName);
                  return (
                    <Badge
                      key={channelName}
                      variant={
                        isChannelRecommended(channelName)
                          ? "default"
                          : "secondary"
                      }
                      className="text-xs"
                    >
                      {channelName}
                    </Badge>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );
};
