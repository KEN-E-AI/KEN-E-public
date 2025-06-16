import MetricCard from "./MetricCard";

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

interface MetricsSectionProps {
  selectedChannel: string;
  selectedTactic: string;
  selectedTab: string;
  funnelSteps: FunnelStep[];
  channels: Channel[];
  channelTactics: Record<string, Tactic[]>;
}

const MetricsSection = ({
  selectedChannel,
  selectedTactic,
  selectedTab,
  funnelSteps,
  channels,
  channelTactics,
}: MetricsSectionProps) => {
  // Logic to determine the correct effectiveness and efficiency KPIs
  const getKPIs = () => {
    if (selectedChannel === "Overview") {
      // Use effectiveness_kpi from selected funnel step
      const step = funnelSteps.find((step) => step.name === selectedTab);
      return {
        effectivenessKPI:
          step?.effectivenessKPI || "Total Prospect Impressions",
        efficiencyKPI: step?.efficiencyKPI || "Total Media CPM",
      };
    } else if (selectedTactic === "Overview" || !selectedTactic) {
      // Use effectiveness_kpi from selected channel (Overview tactic means channel-level)
      const channel = channels.find(
        (channel) => channel.name === selectedChannel,
      );
      return {
        effectivenessKPI: channel?.effectivenessKPI || "Click-Through Rate",
        efficiencyKPI: channel?.efficiencyKPI || "Cost Per Click",
      };
    } else {
      // Use effectiveness_kpi from selected tactic
      const tactics = channelTactics[selectedChannel] || [];
      const tactic = tactics.find((tactic) => tactic.name === selectedTactic);
      return {
        effectivenessKPI: tactic?.effectivenessKPI || "Click-Through Rate",
        efficiencyKPI: tactic?.efficiencyKPI || "Cost Per Click",
      };
    }
  };

  const { effectivenessKPI, efficiencyKPI } = getKPIs();

  // Get description based on KPI name (simplified mapping)
  const getKPIDescription = (kpiName: string) => {
    const descriptions: Record<string, string> = {
      "Total Prospect Impressions":
        "The estimated portion of impressions served to new prospects across platforms, channels, websites and apps.",
      "Total Media CPM":
        "The average cost per 1,000 impressions across google ads and meta ads.",
      "Click-Through Rate":
        "The percentage of people who click on a specific link out of the total number of users who view a page, email, or advertisement.",
      "Cost Per Click":
        "The average amount paid for each click on an advertisement.",
      "Conversion Rate":
        "The percentage of visitors who complete a desired action on a website.",
      "Cost Per Acquisition":
        "The average cost to acquire a new customer through marketing efforts.",
      "Engagement Rate":
        "The percentage of users who interact with content in a meaningful way.",
      "Cost Per Engagement":
        "The average cost for each engagement with an advertisement or content.",
      "Email Open Rate":
        "The percentage of email recipients who open an email.",
      "Cost Per Send": "The average cost to send an email to one recipient.",
      "Customer Lifetime Value":
        "The predicted net profit attributed to the entire future relationship with a customer.",
      "Retention Cost":
        "The cost associated with retaining existing customers.",
      "View-Through Rate":
        "The percentage of users who view an advertisement but don't immediately click.",
      "Cost Per Impression":
        "The cost paid for every 1,000 impressions an advertisement receives.",
      "Video Completion Rate":
        "The percentage of users who watch a video advertisement to completion.",
      "Cost Per View":
        "The average cost paid for each view of a video advertisement.",
      "Organic Reach":
        "The number of people who see content without paid promotion.",
      "Cost Per Post":
        "The average cost to create and publish social media content.",
      "Social Conversion Rate":
        "The percentage of social media users who complete a desired action.",
      "Cost Per Social Click":
        "The average cost for each click on social media advertisements.",
      "Organic Click Rate":
        "The percentage of users who click on organic (non-paid) search results.",
      "Cost Per Organic Session":
        "The cost associated with driving traffic through organic search.",
      "Email Click Rate":
        "The percentage of email recipients who click on links within an email.",
      "Event Attendance Rate":
        "The percentage of registered participants who actually attend an event.",
      "Cost Per Attendee": "The average cost to acquire one event attendee.",
    };
    return (
      descriptions[kpiName] ||
      "Performance metric for measuring marketing effectiveness."
    );
  };

  const effectivenessData = {
    title: "EFFECTIVENESS",
    color: "effectiveness" as const,
    metric: {
      name: effectivenessKPI,
      description: getKPIDescription(effectivenessKPI),
      value: "1,529,204",
      change: "+20%",
      changeLabel: "month over month",
      isPositive: true,
    },
    chartData: [
      { month: "Aug", value: 1200000 },
      { month: "Sep", value: 1350000 },
      { month: "Oct", value: 1100000 },
      { month: "Nov", value: 1250000 },
      { month: "Dec", value: 1300000 },
      { month: "Jan", value: 1529204 },
    ],
  };

  const efficiencyData = {
    title: "EFFICIENCY",
    color: "efficiency" as const,
    metric: {
      name: efficiencyKPI,
      description: getKPIDescription(efficiencyKPI),
      value: "$33.29",
      change: "+4.4%",
      changeLabel: "month over month",
      isPositive: false,
    },
    chartData: [
      { month: "Aug", value: 30 },
      { month: "Sep", value: 32 },
      { month: "Oct", value: 31 },
      { month: "Nov", value: 33 },
      { month: "Dec", value: 32 },
      { month: "Jan", value: 33.29 },
    ],
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <MetricCard {...effectivenessData} />
      <MetricCard {...efficiencyData} />
    </div>
  );
};

export default MetricsSection;
