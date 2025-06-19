export interface ActivityIntuition {
  [metricName: string]: "increase" | "decrease";
}

export interface ActivityLog {
  activity_log_id: string;
  start_date: string;
  end_date: string;
  description: string;
}

export interface Activity {
  activity_id: string;
  internal: boolean;
  known_activity: boolean;
  description: string;
  expected_impact: string;
  intuition: ActivityIntuition[];
  logs: ActivityLog[];
}

export const activities: Activity[] = [
  {
    activity_id: "ggg777",
    internal: false,
    known_activity: true,
    description:
      "Your brand or products are featured or referenced in news and press outlets.",
    expected_impact:
      "This activity is expected to build awareness of the brand and drive users to the website.",
    intuition: [
      { "Brand Mentions": "increase" },
      { "Website Traffic": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz123",
        start_date: "2024-01-01",
        end_date: "2024-01-31",
        description: "Q1 PR campaign launch",
      },
      {
        activity_log_id: "azaz124",
        start_date: "2024-02-01",
        end_date: "2024-02-28",
        description: "Product announcement coverage",
      },
    ],
  },
  {
    activity_id: "ggg778",
    internal: true,
    known_activity: true,
    description:
      "Offer a temporary promotion or discount to a product/service.",
    expected_impact:
      "Expected to drive short-term conversions and clear inventory.",
    intuition: [
      { "Conversion Rate": "increase" },
      { "Average Order Value": "decrease" },
    ],
    logs: [
      {
        activity_log_id: "azaz125",
        start_date: "2024-03-01",
        end_date: "2024-03-15",
        description: "Spring sale promotion",
      },
    ],
  },
  {
    activity_id: "ggg779",
    internal: false,
    known_activity: false,
    description:
      "Launch a new social media campaign targeting younger demographics.",
    expected_impact:
      "Expected to increase brand awareness among Gen Z and millennial audiences.",
    intuition: [
      { "Social Media Engagement": "increase" },
      { "Brand Awareness": "increase" },
      { "Website Traffic": "increase" },
    ],
    logs: [],
  },
  {
    activity_id: "ggg780",
    internal: true,
    known_activity: true,
    description: "Implement new email marketing automation sequences.",
    expected_impact:
      "Improve customer retention and lifecycle marketing effectiveness.",
    intuition: [
      { "Email Open Rate": "increase" },
      { "Customer Lifetime Value": "increase" },
      { "Repeat Purchase Rate": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz126",
        start_date: "2024-04-01",
        end_date: "2024-04-30",
        description: "Welcome series automation rollout",
      },
    ],
  },
  {
    activity_id: "ggg781",
    internal: false,
    known_activity: true,
    description: "Partner with influencers for product endorsements.",
    expected_impact:
      "Leverage influencer reach to drive brand credibility and product awareness.",
    intuition: [
      { "Social Media Impressions": "increase" },
      { "Brand Mentions": "increase" },
      { "Conversion Rate": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz127",
        start_date: "2024-05-01",
        end_date: "2024-05-31",
        description: "Micro-influencer campaign phase 1",
      },
      {
        activity_log_id: "azaz128",
        start_date: "2024-06-01",
        end_date: "2024-06-15",
        description: "Macro-influencer collaboration",
      },
    ],
  },
  {
    activity_id: "ggg782",
    internal: true,
    known_activity: true,
    description: "Optimize website user experience and checkout process.",
    expected_impact:
      "Reduce friction in the conversion funnel and improve customer satisfaction.",
    intuition: [
      { "Conversion Rate": "increase" },
      { "Cart Abandonment Rate": "decrease" },
      { "Page Load Speed": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz129",
        start_date: "2024-07-01",
        end_date: "2024-07-31",
        description: "UX audit and optimization phase 1",
      },
    ],
  },
  {
    activity_id: "ggg783",
    internal: false,
    known_activity: true,
    description:
      "Launch content marketing strategy with blog and video content.",
    expected_impact:
      "Establish thought leadership and improve organic search visibility.",
    intuition: [
      { "Organic Traffic": "increase" },
      { "Time on Site": "increase" },
      { "Brand Authority": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz130",
        start_date: "2024-08-01",
        end_date: "2024-08-31",
        description: "Content calendar launch - month 1",
      },
      {
        activity_log_id: "azaz131",
        start_date: "2024-09-01",
        end_date: "2024-09-30",
        description: "Video content series rollout",
      },
    ],
  },
  {
    activity_id: "ggg784",
    internal: true,
    known_activity: false,
    description: "Implement AI-powered personalization across the website.",
    expected_impact:
      "Deliver more relevant experiences to increase engagement and conversions.",
    intuition: [
      { "Personalization Score": "increase" },
      { "Click-Through Rate": "increase" },
      { "Revenue Per Visitor": "increase" },
    ],
    logs: [],
  },
  {
    activity_id: "ggg785",
    internal: false,
    known_activity: true,
    description: "Participate in industry conferences and trade shows.",
    expected_impact:
      "Build industry relationships and generate qualified leads.",
    intuition: [
      { "Lead Generation": "increase" },
      { "Brand Recognition": "increase" },
      { "Industry Partnerships": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz132",
        start_date: "2024-10-15",
        end_date: "2024-10-17",
        description: "TechCrunch Disrupt conference participation",
      },
    ],
  },
  {
    activity_id: "ggg786",
    internal: true,
    known_activity: true,
    description: "Launch customer referral program.",
    expected_impact:
      "Leverage existing customers to acquire new ones at lower cost.",
    intuition: [
      { "Customer Acquisition Cost": "decrease" },
      { "Referral Rate": "increase" },
      { "Customer Lifetime Value": "increase" },
    ],
    logs: [
      {
        activity_log_id: "azaz133",
        start_date: "2024-11-01",
        end_date: "2024-11-30",
        description: "Referral program beta launch",
      },
    ],
  },
];

// Helper function to get activity by ID
export const getActivityById = (activityId: string): Activity | undefined => {
  return activities.find((activity) => activity.activity_id === activityId);
};

// Helper function to get activities by type
export const getActivitiesByType = (internal: boolean): Activity[] => {
  return activities.filter((activity) => activity.internal === internal);
};

// Helper function to get known activities
export const getKnownActivities = (): Activity[] => {
  return activities.filter((activity) => activity.known_activity === true);
};

// Helper function to get activities with logs
export const getActivitiesWithLogs = (): Activity[] => {
  return activities.filter((activity) => activity.logs.length > 0);
};

// Helper function to get all unique metric names from intuitions
export const getUniqueMetricNames = (): string[] => {
  const metricNames = new Set<string>();
  activities.forEach((activity) => {
    activity.intuition.forEach((intuition) => {
      Object.keys(intuition).forEach((metricName) => {
        metricNames.add(metricName);
      });
    });
  });
  return Array.from(metricNames);
};
