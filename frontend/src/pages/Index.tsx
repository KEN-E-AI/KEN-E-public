import { useState } from "react";
import Layout from "@/components/layout/Layout";
import DashboardControls from "@/components/dashboard/DashboardControls";

import AnalysisSection from "@/components/dashboard/AnalysisSection";
import SupportingMetricsSection from "@/components/dashboard/SupportingMetricsSection";
import EditStepsModal from "@/components/dashboard/EditStepsModal";

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

interface StepChannelsAndTactics {
  channels: Channel[];
  channelTactics: Record<string, Tactic[]>;
}

interface AccountData {
  funnelSteps: FunnelStep[];
  stepChannelsAndTactics: Record<string, StepChannelsAndTactics>;
}

// Account-specific data
const accountsData: Record<string, AccountData> = {
  "acme-corp": {
    funnelSteps: [
      {
        id: "awareness",
        name: "Awareness",
        objective:
          "Increase the number of prospective customers who are aware of the brand and its unique positioning in the market.",
        effectivenessKPI: "Total Prospect Impressions",
        efficiencyKPI: "Total Media CPM",
        order: 0,
      },
      {
        id: "consideration",
        name: "Consideration",
        objective:
          "Encourage potential customers to actively consider our brand as a viable solution to their needs.",
        effectivenessKPI: "Click-Through Rate",
        efficiencyKPI: "Cost Per Click",
        order: 1,
      },
      {
        id: "conversion",
        name: "Conversion",
        objective:
          "Convert interested prospects into paying customers through compelling offers and streamlined purchase processes.",
        effectivenessKPI: "Conversion Rate",
        efficiencyKPI: "Cost Per Acquisition",
        order: 2,
      },
      {
        id: "loyalty",
        name: "Loyalty",
        objective:
          "Build long-term customer relationships and encourage repeat purchases while reducing churn.",
        effectivenessKPI: "Customer Lifetime Value",
        efficiencyKPI: "Retention Cost",
        order: 3,
      },
    ],
    stepChannelsAndTactics: {
      Awareness: {
        channels: [
          {
            id: "display",
            name: "Display",
            effectivenessKPI: "Click-Through Rate",
            efficiencyKPI: "Cost Per Click",
            supportingMetrics: [
              "Impressions",
              "View-Through Rate",
              "Cost Per Mille",
            ],
          },
          {
            id: "social",
            name: "Social",
            effectivenessKPI: "Engagement Rate",
            efficiencyKPI: "Cost Per Engagement",
            supportingMetrics: ["Social Shares", "Comment Rate", "Reach"],
          },
          {
            id: "search",
            name: "Search",
            effectivenessKPI: "Conversion Rate",
            efficiencyKPI: "Cost Per Acquisition",
            supportingMetrics: [
              "Click-Through Rate",
              "Quality Score",
              "Impression Share",
            ],
          },
          {
            id: "email",
            name: "Email",
            effectivenessKPI: "Email Open Rate",
            efficiencyKPI: "Cost Per Send",
            supportingMetrics: [
              "Email Click Rate",
              "Bounce Rate",
              "Unsubscribe Rate",
            ],
          },
        ],
        channelTactics: {
          Display: [
            {
              id: "banner-ads",
              name: "Banner Ads",
              effectivenessKPI: "View-Through Rate",
              efficiencyKPI: "Cost Per Impression",
              supportingMetrics: [
                "Ad Recall",
                "Brand Lift",
                "Viewability Rate",
              ],
            },
            {
              id: "video-ads",
              name: "Video Ads",
              effectivenessKPI: "Video Completion Rate",
              efficiencyKPI: "Cost Per View",
              supportingMetrics: ["Play Rate", "Engagement Rate", "Share Rate"],
            },
          ],
          Social: [
            {
              id: "organic-social",
              name: "Organic Social",
              effectivenessKPI: "Organic Reach",
              efficiencyKPI: "Cost Per Post",
              supportingMetrics: ["Follower Growth", "Share Rate", "Save Rate"],
            },
            {
              id: "paid-social",
              name: "Paid Social",
              effectivenessKPI: "Social Conversion Rate",
              efficiencyKPI: "Cost Per Social Click",
              supportingMetrics: [
                "Social CTR",
                "Social CPM",
                "Social Frequency",
              ],
            },
          ],
          Search: [
            {
              id: "sem",
              name: "SEM",
              effectivenessKPI: "Search Conversion Rate",
              efficiencyKPI: "Cost Per Click",
              supportingMetrics: [
                "Search Impression Share",
                "Average Position",
                "Quality Score",
              ],
            },
            {
              id: "seo",
              name: "SEO",
              effectivenessKPI: "Organic Click Rate",
              efficiencyKPI: "Cost Per Organic Session",
              supportingMetrics: [
                "Organic Impressions",
                "Average Position",
                "Page Load Speed",
              ],
            },
          ],
          Email: [
            {
              id: "newsletter",
              name: "Newsletter",
              effectivenessKPI: "Email Click Rate",
              efficiencyKPI: "Cost Per Click",
              supportingMetrics: [
                "Open Rate",
                "Forward Rate",
                "List Growth Rate",
              ],
            },
            {
              id: "conference",
              name: "Conference",
              effectivenessKPI: "Event Attendance Rate",
              efficiencyKPI: "Cost Per Attendee",
              supportingMetrics: [
                "Registration Rate",
                "Lead Generation Rate",
                "Post-Event Engagement",
              ],
            },
          ],
        },
      },
      Consideration: {
        channels: [],
        channelTactics: {},
      },
      Conversion: {
        channels: [],
        channelTactics: {},
      },
      Loyalty: {
        channels: [],
        channelTactics: {},
      },
    },
  },
  "digital-solutions": {
    funnelSteps: [
      {
        id: "awareness",
        name: "Awareness",
        objective:
          "Build brand recognition among enterprise software decision-makers and increase visibility in the B2B market.",
        effectivenessKPI: "Brand Awareness Lift",
        efficiencyKPI: "Cost Per Brand Impression",
        order: 0,
      },
      {
        id: "engagement",
        name: "Engagement",
        objective:
          "Drive meaningful interactions with potential clients through thought leadership and solution demonstrations.",
        effectivenessKPI: "Engagement Rate",
        efficiencyKPI: "Cost Per Engagement",
        order: 1,
      },
      {
        id: "conversion",
        name: "Conversion",
        objective:
          "Convert engaged prospects into qualified leads and ultimately into paying enterprise clients.",
        effectivenessKPI: "Lead Conversion Rate",
        efficiencyKPI: "Cost Per Qualified Lead",
        order: 2,
      },
    ],
    stepChannelsAndTactics: {
      Awareness: {
        channels: [
          {
            id: "linkedin",
            name: "LinkedIn",
            effectivenessKPI: "Professional Reach",
            efficiencyKPI: "Cost Per Professional Click",
            supportingMetrics: [
              "Profile Views",
              "Connection Requests",
              "InMail Response Rate",
            ],
          },
          {
            id: "content",
            name: "Content Marketing",
            effectivenessKPI: "Content Engagement Rate",
            efficiencyKPI: "Cost Per Content View",
            supportingMetrics: [
              "Blog Traffic",
              "Whitepaper Downloads",
              "Webinar Attendance",
            ],
          },
        ],
        channelTactics: {
          LinkedIn: [
            {
              id: "sponsored-content",
              name: "Sponsored Content",
              effectivenessKPI: "Sponsored Post Engagement",
              efficiencyKPI: "Cost Per Sponsored Engagement",
              supportingMetrics: ["Likes", "Shares", "Comments"],
            },
          ],
          "Content Marketing": [],
        },
      },
      Engagement: {
        channels: [],
        channelTactics: {},
      },
      Conversion: {
        channels: [],
        channelTactics: {},
      },
    },
  },
  "tech-startup": {
    funnelSteps: [
      {
        id: "discovery",
        name: "Discovery",
        objective:
          "Get discovered by early adopters and tech enthusiasts who are looking for innovative solutions.",
        effectivenessKPI: "Organic Search Visibility",
        efficiencyKPI: "Cost Per Discovery",
        order: 0,
      },
      {
        id: "trial",
        name: "Trial",
        objective:
          "Convert interested users into trial users who experience the product firsthand.",
        effectivenessKPI: "Trial Conversion Rate",
        efficiencyKPI: "Cost Per Trial User",
        order: 1,
      },
      {
        id: "activation",
        name: "Activation",
        objective:
          "Help trial users achieve their first success milestone within the product.",
        effectivenessKPI: "Activation Rate",
        efficiencyKPI: "Cost Per Activated User",
        order: 2,
      },
      {
        id: "subscription",
        name: "Subscription",
        objective:
          "Convert activated trial users into paying subscribers with high lifetime value.",
        effectivenessKPI: "Trial to Paid Conversion",
        efficiencyKPI: "Customer Acquisition Cost",
        order: 3,
      },
    ],
    stepChannelsAndTactics: {
      Discovery: {
        channels: [
          {
            id: "product-hunt",
            name: "Product Hunt",
            effectivenessKPI: "Launch Day Ranking",
            efficiencyKPI: "Cost Per Hunter",
            supportingMetrics: ["Votes", "Comments", "Maker Followers"],
          },
          {
            id: "tech-blogs",
            name: "Tech Blogs",
            effectivenessKPI: "Tech Blog Mentions",
            efficiencyKPI: "Cost Per Tech Mention",
            supportingMetrics: [
              "TechCrunch Features",
              "HackerNews Points",
              "Reddit Upvotes",
            ],
          },
        ],
        channelTactics: {
          "Product Hunt": [],
          "Tech Blogs": [],
        },
      },
      Trial: {
        channels: [],
        channelTactics: {},
      },
      Activation: {
        channels: [],
        channelTactics: {},
      },
      Subscription: {
        channels: [],
        channelTactics: {},
      },
    },
  },
  "marketing-agency": {
    funnelSteps: [
      {
        id: "visibility",
        name: "Visibility",
        objective:
          "Increase visibility among potential clients who need marketing services and establish thought leadership.",
        effectivenessKPI: "Industry Recognition",
        efficiencyKPI: "Cost Per Industry Impression",
        order: 0,
      },
      {
        id: "consultation",
        name: "Consultation",
        objective:
          "Convert interested prospects into consultation requests and demonstrate expertise.",
        effectivenessKPI: "Consultation Request Rate",
        efficiencyKPI: "Cost Per Consultation",
        order: 1,
      },
      {
        id: "proposal",
        name: "Proposal",
        objective:
          "Turn consultation meetings into formal proposals with high win rates.",
        effectivenessKPI: "Proposal Win Rate",
        efficiencyKPI: "Cost Per Proposal",
        order: 2,
      },
      {
        id: "retention",
        name: "Retention",
        objective:
          "Maintain long-term client relationships and generate referrals and upsells.",
        effectivenessKPI: "Client Retention Rate",
        efficiencyKPI: "Cost Per Retained Client",
        order: 3,
      },
    ],
    stepChannelsAndTactics: {
      Visibility: {
        channels: [
          {
            id: "case-studies",
            name: "Case Studies",
            effectivenessKPI: "Case Study Views",
            efficiencyKPI: "Cost Per Case Study View",
            supportingMetrics: [
              "Download Rate",
              "Sharing Rate",
              "Contact Form Fills",
            ],
          },
          {
            id: "industry-events",
            name: "Industry Events",
            effectivenessKPI: "Event Lead Quality",
            efficiencyKPI: "Cost Per Event Lead",
            supportingMetrics: [
              "Booth Visitors",
              "Business Cards Collected",
              "Demo Requests",
            ],
          },
        ],
        channelTactics: {
          "Case Studies": [],
          "Industry Events": [],
        },
      },
      Consultation: {
        channels: [],
        channelTactics: {},
      },
      Proposal: {
        channels: [],
        channelTactics: {},
      },
      Retention: {
        channels: [],
        channelTactics: {},
      },
    },
  },
};

// Default empty structure for steps with no channels
const defaultStepChannelsAndTactics: StepChannelsAndTactics = {
  channels: [],
  channelTactics: {},
};

const Index = () => {
  const [selectedAccount, setSelectedAccount] = useState("acme-corp");
  const [selectedChannel, setSelectedChannel] = useState("Overview");
  const [selectedTactic, setSelectedTactic] = useState("");
  const [selectedTab, setSelectedTab] = useState("Awareness");
  const [accountDataVersion, setAccountDataVersion] = useState(0);
  const [dateRange, setDateRange] = useState({
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  });
  const [comparisonDateRange, setComparisonDateRange] = useState<
    | {
        from: Date;
        to: Date;
      }
    | undefined
  >(undefined);
  const [editStepsModalOpen, setEditStepsModalOpen] = useState(false);

  // Get current account data
  const getCurrentAccountData = () => {
    return accountsData[selectedAccount] || accountsData["acme-corp"];
  };

  // Get current step's channels and tactics
  const getCurrentStepData = () => {
    const accountData = getCurrentAccountData();
    return (
      accountData.stepChannelsAndTactics[selectedTab] ||
      defaultStepChannelsAndTactics
    );
  };

  // Handle account change - reset selections and update tab to first available step
  const handleAccountChange = (newAccount: string) => {
    setSelectedAccount(newAccount);
    setSelectedChannel("Overview");
    setSelectedTactic("");

    // Set tab to first step of new account
    const newAccountData = accountsData[newAccount];
    if (newAccountData && newAccountData.funnelSteps.length > 0) {
      const firstStep = newAccountData.funnelSteps
        .slice()
        .sort((a, b) => a.order - b.order)[0];
      setSelectedTab(firstStep.name);
    }
  };

  // Handle channel updates
  const handleChannelsChange = (newChannels: Channel[]) => {
    const currentAccountData = getCurrentAccountData();
    const currentStepData = getCurrentStepData();

    // Update the current step's channels
    const updatedStepData = {
      ...currentStepData,
      channels: newChannels,
    };

    // Update the account data
    const updatedAccountData = {
      ...currentAccountData,
      stepChannelsAndTactics: {
        ...currentAccountData.stepChannelsAndTactics,
        [selectedTab]: updatedStepData,
      },
    };

    // Update the global account data
    accountsData[selectedAccount] = updatedAccountData;

    // Trigger re-render
    setAccountDataVersion((prev) => prev + 1);
  };

  // Handle channel tactics updates
  const handleChannelTacticsChange = (
    channelName: string,
    newTactics: Tactic[],
  ) => {
    const currentAccountData = getCurrentAccountData();
    const currentStepData = getCurrentStepData();

    // Update the current step's channel tactics
    const updatedChannelTactics = {
      ...currentStepData.channelTactics,
      [channelName]: newTactics,
    };

    const updatedStepData = {
      ...currentStepData,
      channelTactics: updatedChannelTactics,
    };

    // Update the account data
    const updatedAccountData = {
      ...currentAccountData,
      stepChannelsAndTactics: {
        ...currentAccountData.stepChannelsAndTactics,
        [selectedTab]: updatedStepData,
      },
    };

    // Update the global account data
    accountsData[selectedAccount] = updatedAccountData;

    // Trigger re-render
    setAccountDataVersion((prev) => prev + 1);
  };

  // Update selected tab when funnel steps change to ensure it's still valid
  const handleFunnelStepsChange = (newSteps: FunnelStep[]) => {
    const currentAccountData = getCurrentAccountData();
    const updatedAccountData = {
      ...currentAccountData,
      funnelSteps: newSteps,
    };

    // Update the account data
    accountsData[selectedAccount] = updatedAccountData;

    // Check if current selected tab still exists in new steps
    const sortedSteps = newSteps.slice().sort((a, b) => a.order - b.order);
    const currentTabExists = sortedSteps.some(
      (step) => step.name === selectedTab,
    );

    // If current tab doesn't exist, select the first step
    if (!currentTabExists && sortedSteps.length > 0) {
      setSelectedTab(sortedSteps[0].name);
    }
  };

  // Reset channel and tactic selection when changing tabs to ensure valid selections
  const handleTabChange = (newTab: string) => {
    setSelectedTab(newTab);

    // Get the new step's data
    const newStepData = getCurrentStepData();

    // Override to use the new tab data
    const accountData = getCurrentAccountData();
    const actualNewStepData =
      accountData.stepChannelsAndTactics[newTab] ||
      defaultStepChannelsAndTactics;

    // Overview is always available, check if current channel exists in new step
    const channelExists =
      selectedChannel === "Overview" ||
      actualNewStepData.channels.some(
        (channel) => channel.name === selectedChannel,
      );

    if (!channelExists) {
      setSelectedChannel("Overview");
      setSelectedTactic("");
    } else if (selectedChannel !== "Overview") {
      // Check if current tactic still exists for the current channel
      const tactics = actualNewStepData.channelTactics[selectedChannel] || [];
      const tacticExists = tactics.some(
        (tactic) => tactic.name === selectedTactic,
      );
      if (!tacticExists) {
        // Select Overview by default for non-overview channels
        setSelectedTactic("Overview");
      }
    } else {
      // If Overview channel is selected, clear tactics since Overview doesn't have tactics
      setSelectedTactic("");
    }
  };

  const currentAccountData = getCurrentAccountData();

  return (
    <Layout
      selectedTab={selectedTab}
      selectedChannel={selectedChannel}
      selectedTactic={selectedTactic}
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      {/* Channel and Tactic Controls */}
      <DashboardControls
        selectedChannel={selectedChannel}
        setSelectedChannel={setSelectedChannel}
        selectedTactic={selectedTactic}
        setSelectedTactic={setSelectedTactic}
        selectedTab={selectedTab}
        setSelectedTab={handleTabChange}
        onEditSteps={() => setEditStepsModalOpen(true)}
        funnelSteps={currentAccountData.funnelSteps}
        channels={getCurrentStepData().channels}
        channelTactics={getCurrentStepData().channelTactics}
        onChannelsChange={handleChannelsChange}
        onChannelTacticsChange={handleChannelTacticsChange}
        dateRange={dateRange}
        setDateRange={setDateRange}
        comparisonDateRange={comparisonDateRange}
        setComparisonDateRange={setComparisonDateRange}
      />

      {/* Conditional Sections based on Channel Selection */}
      {selectedChannel === "Overview" ? (
        <>
          {/* Analysis Section - Only shown for Overview (includes Recommendations as child) */}
          <AnalysisSection
            effectivenessKPI={
              currentAccountData.funnelSteps.find(
                (step) => step.name === selectedTab,
              )?.effectivenessKPI || ""
            }
            efficiencyKPI={
              currentAccountData.funnelSteps.find(
                (step) => step.name === selectedTab,
              )?.efficiencyKPI || ""
            }
            dateRange={dateRange}
          />
        </>
      ) : (
        <>
          {/* Supporting Metrics Section - Shown for all non-Overview channels */}
          <SupportingMetricsSection
            selectedChannel={selectedChannel}
            selectedTactic={selectedTactic}
            selectedTab={selectedTab}
            funnelSteps={currentAccountData.funnelSteps}
            channels={getCurrentStepData().channels}
            channelTactics={getCurrentStepData().channelTactics}
          />
        </>
      )}
      {/* Edit Steps Modal */}
      <EditStepsModal
        open={editStepsModalOpen}
        onOpenChange={setEditStepsModalOpen}
        steps={currentAccountData.funnelSteps}
        onStepsChange={handleFunnelStepsChange}
      />
    </Layout>
  );
};

export default Index;
