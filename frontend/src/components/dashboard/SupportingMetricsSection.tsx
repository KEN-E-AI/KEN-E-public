import { useState } from "react";
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface SupportingMetric {
  id: string;
  title: string;
  value: string;
  change: string;
  changeType: "positive" | "negative";
  description: string;
  category: string;
}

interface FunnelStep {
  id: string;
  name: string;
  objective: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  order: number;
}

interface Channel {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

interface Tactic {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

interface SupportingMetricsSectionProps {
  selectedChannel: string;
  selectedTactic: string;
  selectedTab: string;
  funnelSteps: FunnelStep[];
  channels: Channel[];
  channelTactics: Record<string, Tactic[]>;
}

const SupportingMetricsSection = ({
  selectedChannel,
  selectedTactic,
  selectedTab,
  funnelSteps,
  channels,
  channelTactics,
}: SupportingMetricsSectionProps) => {
  const [expandedMetrics, setExpandedMetrics] = useState<Set<string>>(
    new Set(),
  );

  // Logic to determine the correct supporting metrics (same as KPI logic)
  const getSupportingMetrics = (): string[] => {
    if (selectedChannel === "Overview") {
      // Use supporting metrics from selected funnel step (if they exist)
      const step = funnelSteps.find((step) => step.name === selectedTab);
      // Note: Funnel steps don't currently have supporting metrics, so return empty array
      return [];
    } else if (selectedTactic === "Overview" || !selectedTactic) {
      // Use supporting metrics from selected channel
      const channel = channels.find(
        (channel) => channel.name === selectedChannel,
      );
      return channel?.supportingMetrics || [];
    } else {
      // Use supporting metrics from selected tactic
      const tactics = channelTactics[selectedChannel] || [];
      const tactic = tactics.find((tactic) => tactic.name === selectedTactic);
      return tactic?.supportingMetrics || [];
    }
  };

  // Get description for metric names
  const getMetricDescription = (metricName: string): string => {
    const descriptions: Record<string, string> = {
      Reach: "Number of unique users who saw your content",
      Frequency: "Average number of times each person saw your content",
      "Brand Awareness Lift": "Increase in brand recognition and recall",
      Impressions: "Total number of times your content was displayed",
      "View-Through Rate":
        "Percentage of users who viewed your content completely",
      "Cost Per Mille": "Cost per 1,000 impressions",
      "Social Shares": "Number of times content was shared on social platforms",
      "Comment Rate": "Percentage of users who commented on your content",
      "Click-Through Rate": "Percentage of users who clicked on your content",
      "Quality Score": "Platform's rating of your content quality",
      "Impression Share": "Percentage of available impressions you received",
      "Email Click Rate": "Percentage of email recipients who clicked links",
      "Bounce Rate": "Percentage of emails that couldn't be delivered",
      "Unsubscribe Rate": "Percentage of recipients who unsubscribed",
      "Ad Recall": "Percentage of users who remember seeing your ad",
      "Brand Lift": "Increase in brand metrics after exposure to ads",
      "Viewability Rate": "Percentage of ads that were actually viewable",
      "Play Rate": "Percentage of users who played your video content",
      "Engagement Rate": "Percentage of users who interacted with content",
      "Share Rate": "Percentage of users who shared your content",
      "Follower Growth": "Rate of increase in social media followers",
      "Save Rate": "Percentage of users who saved your content",
      "Social CTR": "Click-through rate specifically on social platforms",
      "Social CPM": "Cost per 1,000 impressions on social platforms",
      "Social Frequency": "Average times each user saw social content",
      "Search Impression Share": "Share of available search impressions",
      "Average Position": "Average ranking position in search results",
      "Organic Impressions": "Number of unpaid search result views",
      "Page Load Speed": "Time taken for your pages to load",
      "Open Rate": "Percentage of emails that were opened",
      "Forward Rate": "Percentage of emails that were forwarded",
      "List Growth Rate": "Rate of growth in email subscriber list",
      "Registration Rate": "Percentage of users who registered for events",
      "Lead Generation Rate": "Rate at which leads are generated",
      "Post-Event Engagement": "User interaction after event completion",
      "Download Rate": "Percentage of users who downloaded content",
      "Sharing Rate": "Rate at which content is shared",
      "Contact Form Fills": "Number of contact forms completed",
      "Booth Visitors": "Number of people who visited event booth",
      "Business Cards Collected": "Number of business cards gathered",
      "Demo Requests": "Number of product demonstration requests",
      "Profile Views": "Number of times profiles were viewed",
      "Connection Requests": "Number of professional connection requests",
      "InMail Response Rate": "Response rate to InMail messages",
      Likes: "Number of likes received on content",
      Shares: "Number of times content was shared",
      Comments: "Number of comments received on content",
      "Blog Traffic": "Number of visitors to blog content",
      "Whitepaper Downloads": "Number of whitepaper downloads",
      "Webinar Attendance": "Number of people attending webinars",
      Votes: "Number of votes received (e.g., Product Hunt)",
      "Maker Followers": "Number of followers gained by makers",
      "TechCrunch Features": "Number of features in TechCrunch",
      "HackerNews Points": "Points scored on HackerNews",
      "Reddit Upvotes": "Number of upvotes received on Reddit",
    };
    return (
      descriptions[metricName] ||
      "Performance metric for measuring marketing effectiveness."
    );
  };

  // Generate random realistic values for demo purposes
  const generateMetricValue = (metricName: string): SupportingMetric => {
    const metricId = metricName.toLowerCase().replace(/\s+/g, "-");

    // Generate different types of values based on metric type
    let value: string;
    let change: string;
    let changeType: "positive" | "negative";

    if (
      metricName.toLowerCase().includes("rate") ||
      metricName.toLowerCase().includes("percentage")
    ) {
      // Percentage values
      const baseValue = Math.random() * 15 + 1; // 1-16%
      value = `${baseValue.toFixed(1)}%`;
      const changeValue = (Math.random() - 0.5) * 2; // -1 to +1
      change = `${changeValue >= 0 ? "+" : ""}${changeValue.toFixed(1)}%`;
      changeType = changeValue >= 0 ? "positive" : "negative";
    } else if (metricName.toLowerCase().includes("cost")) {
      // Cost values
      const baseValue = Math.random() * 5 + 0.5; // $0.50-$5.50
      value = `$${baseValue.toFixed(2)}`;
      const changeValue = (Math.random() - 0.5) * 1; // -0.5 to +0.5
      change = `${changeValue >= 0 ? "+" : ""}$${Math.abs(changeValue).toFixed(2)}`;
      changeType = changeValue >= 0 ? "negative" : "positive"; // Higher cost is negative
    } else if (
      metricName.toLowerCase().includes("impression") ||
      metricName.toLowerCase().includes("reach") ||
      metricName.toLowerCase().includes("traffic")
    ) {
      // Large number values
      const baseValue = Math.floor(Math.random() * 900000 + 100000); // 100k-1M
      value = baseValue.toLocaleString();
      const changePercentage = (Math.random() - 0.3) * 30; // -9% to +21%
      change = `${changePercentage >= 0 ? "+" : ""}${changePercentage.toFixed(1)}%`;
      changeType = changePercentage >= 0 ? "positive" : "negative";
    } else {
      // Medium number values
      const baseValue = Math.floor(Math.random() * 10000 + 1000); // 1k-11k
      value = baseValue.toLocaleString();
      const changePercentage = (Math.random() - 0.3) * 25; // -7.5% to +17.5%
      change = `${changePercentage >= 0 ? "+" : ""}${changePercentage.toFixed(1)}%`;
      changeType = changePercentage >= 0 ? "positive" : "negative";
    }

    return {
      id: metricId,
      title: metricName,
      value,
      change,
      changeType,
      description: getMetricDescription(metricName),
      category: "Performance",
    };
  };

  const currentSupportingMetrics = getSupportingMetrics();
  const supportingMetrics: SupportingMetric[] =
    currentSupportingMetrics.map(generateMetricValue);

  const toggleMetric = (metricId: string) => {
    const newExpanded = new Set(expandedMetrics);
    if (newExpanded.has(metricId)) {
      newExpanded.delete(metricId);
    } else {
      newExpanded.add(metricId);
    }
    setExpandedMetrics(newExpanded);
  };

  const getContextDescription = () => {
    if (selectedChannel === "Overview") {
      return `Supporting metrics for the ${selectedTab} funnel step.`;
    } else if (selectedTactic === "Overview" || !selectedTactic) {
      return `Supporting metrics for the ${selectedChannel} channel.`;
    } else {
      return `Supporting metrics for the ${selectedTactic} tactic in ${selectedChannel}.`;
    }
  };

  return (
    <div className="bg-white border border-dashboard-gray-200 rounded-lg p-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-2">
          Supporting Metrics
        </h2>
        <p className="text-sm text-dashboard-gray-600">
          {getContextDescription()}
        </p>
      </div>

      {supportingMetrics.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-dashboard-gray-500 mb-4">
            No supporting metrics configured for this selection.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="bg-dashboard-gray-800 text-white hover:bg-dashboard-gray-700 border-dashboard-gray-800"
          >
            Add Metric
          </Button>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {supportingMetrics.map((metric) => {
              const isExpanded = expandedMetrics.has(metric.id);
              return (
                <Card
                  key={metric.id}
                  className="border-dashboard-gray-200 hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => toggleMetric(metric.id)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-dashboard-gray-900">
                        {metric.title}
                      </h4>
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-dashboard-gray-500" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-dashboard-gray-500" />
                      )}
                    </div>

                    <div className="flex items-center justify-between mb-2">
                      <span className="text-2xl font-bold text-dashboard-gray-900">
                        {metric.value}
                      </span>
                      <div
                        className={`flex items-center gap-1 text-sm ${
                          metric.changeType === "positive"
                            ? "text-dashboard-effectiveness-600"
                            : "text-dashboard-efficiency-600"
                        }`}
                      >
                        {metric.changeType === "positive" ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        <span>{metric.change}</span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="pt-2 border-t border-dashboard-gray-100">
                        <p className="text-xs text-dashboard-gray-600">
                          {metric.description}
                        </p>
                        <div className="mt-3 flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs px-3 py-1 h-auto bg-dashboard-gray-800 text-white hover:bg-dashboard-gray-700 border-dashboard-gray-800"
                          >
                            Create Alert
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default SupportingMetricsSection;
