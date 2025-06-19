import { AccountData, StepChannelsAndTactics } from "@/types/dashboard";

export const DEFAULT_STEP_DATA: StepChannelsAndTactics = {
  channels: [],
  channelTactics: {},
};

export const ACCOUNTS_DATA: Record<string, AccountData> = {
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
