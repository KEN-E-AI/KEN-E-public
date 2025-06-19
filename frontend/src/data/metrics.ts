export interface Metric {
  metric_id: string;
  verbose_name: string;
  metric_name: string;
  expression: string;
  format: string;
  currency: string;
  dataset: string;
  product: string;
  description: string;
}

export const metrics: Metric[] = [
  {
    metric_id: "888ttt",
    verbose_name: "Engaged Sessions",
    metric_name: "engaged_sessions",
    expression: "sum(case when engaged_session_ind = 1 then 1 end)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "Engaged sessions are a subset of total sessions. An engaged session indicates a user's meaningful interaction with a website or app. An engaged session is a session that lasts longer than 10 seconds, having at least one conversion event, or having ten or more page views or screen views. These sessions are used to calculate engagement rate, which represents the percentage of engaged sessions on your website or app.",
  },
  {
    metric_id: "m001",
    verbose_name: "Transactions",
    metric_name: "transactions",
    expression: "sum(case when event_name = 'purchase' then 1 end)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The total count of orders that were successfully completed in Google Analytics 4.",
  },
  {
    metric_id: "m002",
    verbose_name: "Total Users",
    metric_name: "total_users",
    expression: "count(distinct user_pseudo_id)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The total number of unique users who initiated sessions on your website or app during the specified date range.",
  },
  {
    metric_id: "m003",
    verbose_name: "New Users",
    metric_name: "new_users",
    expression:
      "count(distinct case when new_user_ind = 1 then user_pseudo_id end)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The number of users who interacted with your site or app for the first time (users who had no previous sessions).",
  },
  {
    metric_id: "m004",
    verbose_name: "Sessions",
    metric_name: "sessions",
    expression: "count(distinct session_id)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The total number of sessions initiated by users on your website or app during the specified date range.",
  },
  {
    metric_id: "m005",
    verbose_name: "Page Views",
    metric_name: "page_views",
    expression: "sum(case when event_name = 'page_view' then 1 end)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The total number of page views across all sessions. Multiple views of the same page are counted separately.",
  },
  {
    metric_id: "m006",
    verbose_name: "Bounce Rate",
    metric_name: "bounce_rate",
    expression:
      "safe_divide(sum(case when bounced_session_ind = 1 then 1 end), count(distinct session_id)) * 100",
    format: "Percent",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The percentage of single-page sessions (sessions in which the user left your site from the entrance page without interacting with the page).",
  },
  {
    metric_id: "m007",
    verbose_name: "Average Session Duration",
    metric_name: "avg_session_duration",
    expression:
      "safe_divide(sum(session_duration_seconds), count(distinct session_id))",
    format: "Double",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The average length of a session. This metric is calculated as the total duration of all sessions (in seconds) divided by the number of sessions.",
  },
  {
    metric_id: "m008",
    verbose_name: "Conversion Rate",
    metric_name: "conversion_rate",
    expression:
      "safe_divide(sum(case when conversion_ind = 1 then 1 end), count(distinct session_id)) * 100",
    format: "Percent",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The percentage of sessions that resulted in a conversion (purchase, sign-up, or other goal completion).",
  },
  {
    metric_id: "m009",
    verbose_name: "Revenue",
    metric_name: "revenue",
    expression: "sum(case when event_name = 'purchase' then revenue_usd end)",
    format: "Double",
    currency: "USD",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The total revenue generated from e-commerce transactions on your website or app.",
  },
  {
    metric_id: "m010",
    verbose_name: "Average Order Value",
    metric_name: "avg_order_value",
    expression:
      "safe_divide(sum(case when event_name = 'purchase' then revenue_usd end), sum(case when event_name = 'purchase' then 1 end))",
    format: "Double",
    currency: "USD",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The average monetary value of e-commerce transactions. Calculated as total revenue divided by the number of transactions.",
  },
  {
    metric_id: "m011",
    verbose_name: "Add to Cart Events",
    metric_name: "add_to_cart_events",
    expression: "sum(case when event_name = 'add_to_cart' then 1 end)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The total number of times users added items to their shopping cart.",
  },
  {
    metric_id: "m012",
    verbose_name: "Checkout Events",
    metric_name: "checkout_events",
    expression: "sum(case when event_name = 'begin_checkout' then 1 end)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The total number of times users initiated the checkout process.",
  },
  {
    metric_id: "m013",
    verbose_name: "Event Count",
    metric_name: "event_count",
    expression: "count(*)",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The total count of events triggered across all sessions, including both automatically collected and custom events.",
  },
  {
    metric_id: "m014",
    verbose_name: "Unique Events",
    metric_name: "unique_events",
    expression: "count(distinct concat(session_id, event_name))",
    format: "Integer",
    currency: "None",
    dataset: "GA4 Events",
    product: "Google Analytics",
    description:
      "The number of unique events per session. Multiple instances of the same event in a session are counted as one.",
  },
  {
    metric_id: "m015",
    verbose_name: "Sessions per User",
    metric_name: "sessions_per_user",
    expression:
      "safe_divide(count(distinct session_id), count(distinct user_pseudo_id))",
    format: "Double",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The average number of sessions per user. Calculated as total sessions divided by total users.",
  },
  {
    metric_id: "m016",
    verbose_name: "Engagement Rate",
    metric_name: "engagement_rate",
    expression:
      "safe_divide(sum(case when engaged_session_ind = 1 then 1 end), count(distinct session_id)) * 100",
    format: "Percent",
    currency: "None",
    dataset: "GA4 Sessions",
    product: "Google Analytics",
    description:
      "The percentage of engaged sessions out of total sessions. An engaged session is one that lasts longer than 10 seconds, has a conversion event, or has 2 or more page views.",
  },
  {
    metric_id: "m017",
    verbose_name: "Click-Through Rate",
    metric_name: "click_through_rate",
    expression: "safe_divide(sum(clicks), sum(impressions)) * 100",
    format: "Percent",
    currency: "None",
    dataset: "Google Ads",
    product: "Google Ads",
    description:
      "The percentage of ad impressions that resulted in clicks. Calculated as clicks divided by impressions.",
  },
  {
    metric_id: "m018",
    verbose_name: "Cost Per Click",
    metric_name: "cost_per_click",
    expression: "safe_divide(sum(cost), sum(clicks))",
    format: "Double",
    currency: "USD",
    dataset: "Google Ads",
    product: "Google Ads",
    description:
      "The average amount paid for each click on your ads. Calculated as total cost divided by total clicks.",
  },
  {
    metric_id: "m019",
    verbose_name: "Cost Per Acquisition",
    metric_name: "cost_per_acquisition",
    expression: "safe_divide(sum(cost), sum(conversions))",
    format: "Double",
    currency: "USD",
    dataset: "Google Ads",
    product: "Google Ads",
    description:
      "The average cost to acquire one conversion. Calculated as total cost divided by total conversions.",
  },
  {
    metric_id: "m020",
    verbose_name: "Impressions",
    metric_name: "impressions",
    expression: "sum(impressions)",
    format: "Integer",
    currency: "None",
    dataset: "Google Ads",
    product: "Google Ads",
    description: "The total number of times your ads were shown to users.",
  },
];

// Helper function to get metric by ID
export const getMetricById = (metricId: string): Metric | undefined => {
  return metrics.find((metric) => metric.metric_id === metricId);
};

// Helper function to get metrics by dataset
export const getMetricsByDataset = (dataset: string): Metric[] => {
  return metrics.filter((metric) => metric.dataset === dataset);
};

// Helper function to get metrics by product
export const getMetricsByProduct = (product: string): Metric[] => {
  return metrics.filter((metric) => metric.product === product);
};

// Helper function to get all unique datasets
export const getUniqueDatasets = (): string[] => {
  return [...new Set(metrics.map((metric) => metric.dataset))];
};

// Helper function to get all unique products
export const getUniqueProducts = (): string[] => {
  return [...new Set(metrics.map((metric) => metric.product))];
};
