import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { TrendingUp } from "lucide-react";
import {
  MARKETING_CHANNELS,
  MARKETING_CHANNEL_CATEGORIES,
} from "@/data/marketingChannels";

interface MarketingChannelsSelectorProps {
  value: string[];
  onChange: (channels: string[]) => void;
  showRecommended?: boolean;
  recommendedChannels?: string[];
  compact?: boolean;
}

export const MarketingChannelsSelector = ({
  value,
  onChange,
  showRecommended = false,
  recommendedChannels = [],
  compact = false,
}: MarketingChannelsSelectorProps) => {
  const handleChannelToggle = (channel: string, checked: boolean) => {
    if (checked) {
      onChange([...value, channel]);
    } else {
      onChange(value.filter((c) => c !== channel));
    }
  };

  const isChannelRecommended = (channel: string) => {
    return recommendedChannels.includes(channel);
  };

  return (
    <div className="space-y-4">
      {/* Channel Categories */}
      {Object.entries(MARKETING_CHANNEL_CATEGORIES).map(
        ([category, channels]) => (
          <div key={category}>
            <h4
              className={`font-medium mb-2 text-dashboard-gray-800 flex items-center gap-2 ${
                compact ? "text-sm" : ""
              }`}
            >
              <TrendingUp className={`${compact ? "h-3 w-3" : "h-4 w-4"}`} />
              {category}
            </h4>
            <div
              className={`grid gap-2 ${
                compact ? "grid-cols-1" : "grid-cols-1 md:grid-cols-2"
              }`}
            >
              {channels.map((channel) => {
                const isSelected = value.includes(channel);
                const isRecommended =
                  showRecommended && isChannelRecommended(channel);

                return (
                  <div
                    key={channel}
                    className={`flex items-start space-x-2 p-2 rounded border transition-colors ${
                      isSelected
                        ? "border-brand-medium-blue bg-brand-light-blue/10"
                        : "border-dashboard-gray-200 hover:border-dashboard-gray-300"
                    } ${compact ? "text-sm" : ""}`}
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
                        className={`font-medium text-dashboard-gray-800 cursor-pointer ${
                          compact ? "text-sm" : ""
                        }`}
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
      {value.length > 0 && (
        <Card className="bg-brand-light-blue/5 border-brand-light-blue/20">
          <CardContent className="pt-3">
            <h5
              className={`font-medium text-dashboard-gray-800 mb-2 ${
                compact ? "text-sm" : ""
              }`}
            >
              Selected Channels ({value.length})
            </h5>
            <div className="flex flex-wrap gap-1">
              {value.map((channel) => (
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
    </div>
  );
};
