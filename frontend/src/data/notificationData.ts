import {
  Bell,
  AlertCircle,
  TrendingUp,
  Users,
  BarChart3,
  CheckCircle,
} from "lucide-react";

export interface Notification {
  id: string;
  created_date: Date;
  modified_timestamp: number; // Unix timestamp
  account_id: string;
  status: "unread" | "read" | "archived";
  category:
    | "news"
    | "activity"
    | "insight"
    | "quality"
    | "experiment"
    | "analysis";
  description: string;
  data: {
    title: string;
    type:
      | "news"
      | "activity"
      | "insight"
      | "quality"
      | "experiment"
      | "analysis";
    hasIndicator: boolean;
    icon: React.ComponentType<any>;
    metadata?: {
      source?: string;
      priority?: "low" | "medium" | "high";
      url?: string;
      tags?: string[];
    };
  };
}

export const notifications: Notification[] = [
  {
    id: "1",
    created_date: new Date("2024-02-10T09:15:00Z"),
    modified_timestamp: Date.now() - 86400000, // 1 day ago
    account_id: "intellipure-b2c",
    status: "unread",
    category: "news",
    description: "Your brand has been mentioned in recent news articles",
    data: {
      title: "You're in the news",
      type: "news",
      hasIndicator: true,
      icon: Bell,
      metadata: {
        source: "media_monitoring",
        priority: "medium",
        url: "/news-mentions",
        tags: ["brand", "media", "mentions"],
      },
    },
  },
  {
    id: "2",
    created_date: new Date("2024-02-09T14:30:00Z"),
    modified_timestamp: Date.now() - 172800000, // 2 days ago
    account_id: "intellipure-b2c",
    status: "unread",
    category: "activity",
    description: "New competitor campaigns detected in your market",
    data: {
      title: "Competitor activity",
      type: "activity",
      hasIndicator: true,
      icon: TrendingUp,
      metadata: {
        source: "competitor_tracking",
        priority: "high",
        url: "/competitor-analysis",
        tags: ["competitor", "campaigns", "market"],
      },
    },
  },
  {
    id: "3",
    created_date: new Date("2024-02-08T11:20:00Z"),
    modified_timestamp: Date.now() - 259200000, // 3 days ago
    account_id: "intellipure-b2c",
    status: "read",
    category: "insight",
    description: "Brand awareness metrics show a declining trend",
    data: {
      title: "Awareness is declining",
      type: "insight",
      hasIndicator: false,
      icon: AlertCircle,
      metadata: {
        source: "brand_analytics",
        priority: "high",
        url: "/brand-awareness",
        tags: ["awareness", "decline", "metrics"],
      },
    },
  },
  {
    id: "4",
    created_date: new Date("2024-02-07T16:45:00Z"),
    modified_timestamp: Date.now() - 345600000, // 4 days ago
    account_id: "intellipure-b2c",
    status: "unread",
    category: "quality",
    description: "Data inconsistency detected in recent analytics reports",
    data: {
      title: "Data quality issue found",
      type: "quality",
      hasIndicator: true,
      icon: AlertCircle,
      metadata: {
        source: "data_validation",
        priority: "high",
        url: "/data-quality",
        tags: ["data", "quality", "validation"],
      },
    },
  },
  {
    id: "5",
    created_date: new Date("2024-02-06T10:00:00Z"),
    modified_timestamp: Date.now() - 432000000, // 5 days ago
    account_id: "intellipure-b2c",
    status: "read",
    category: "experiment",
    description: "A/B test for Q1 campaign has finished running",
    data: {
      title: "Experiment complete",
      type: "experiment",
      hasIndicator: false,
      icon: CheckCircle,
      metadata: {
        source: "experimentation",
        priority: "medium",
        url: "/experiments/q1-campaign",
        tags: ["experiment", "ab-test", "campaign"],
      },
    },
  },
  {
    id: "6",
    created_date: new Date("2024-02-05T08:30:00Z"),
    modified_timestamp: Date.now() - 518400000, // 6 days ago
    account_id: "intellipure-b2c",
    status: "read",
    category: "analysis",
    description: "Weekly performance analysis report has been generated",
    data: {
      title: "Your scheduled analysis is ready",
      type: "analysis",
      hasIndicator: false,
      icon: BarChart3,
      metadata: {
        source: "scheduled_reports",
        priority: "low",
        url: "/reports/weekly-performance",
        tags: ["report", "analysis", "performance"],
      },
    },
  },
];

// Helper functions
export const getNotificationsByAccountId = (
  accountId: string,
): Notification[] => {
  return notifications.filter(
    (notification) => notification.account_id === accountId,
  );
};

export const getUnreadNotifications = (accountId?: string): Notification[] => {
  const filteredNotifications = accountId
    ? getNotificationsByAccountId(accountId)
    : notifications;
  return filteredNotifications.filter(
    (notification) => notification.status === "unread",
  );
};

export const getNotificationsByCategory = (
  category: string,
  accountId?: string,
): Notification[] => {
  const filteredNotifications = accountId
    ? getNotificationsByAccountId(accountId)
    : notifications;
  return filteredNotifications.filter(
    (notification) => notification.category === category,
  );
};

export const markNotificationAsRead = (notificationId: string): void => {
  const notification = notifications.find((n) => n.id === notificationId);
  if (notification) {
    notification.status = "read";
    notification.modified_timestamp = Date.now();
  }
};
