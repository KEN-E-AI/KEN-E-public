export interface Insight {
  insight_id: string;
  description: string;
  evidence: string;
  date_range: {
    start: string;
    end: string;
  };
  confidence_level: "high" | "medium" | "low";
  category: string;
  impact: "positive" | "negative" | "neutral";
}

export const insights: Insight[] = [
  {
    insight_id: "insight_001",
    description:
      "Between March 28, 2025 and March 30, 2025: transactions [Google Analytics] was moved in a positive direction because you offered a temporary promotion or discount to a product or service.",
    evidence:
      "Include all evidence reviewed by the user from the Analysis Workflow that was presented when this insight was created.\nactive_evidence: [...],\ninfluential_evidence: [...] >",
    date_range: {
      start: "2025-03-28",
      end: "2025-03-30",
    },
    confidence_level: "high",
    category: "promotional_impact",
    impact: "positive",
  },
  {
    insight_id: "insight_002",
    description:
      "Between <start date> and <end date>: <metric name> [<dataset product name>] was moved in a <direction> direction because <activity description>.",
    evidence:
      "Include all evidence reviewed by the user from the Analysis Workflow that was presented when this insight was created.\nactive_evidence: [...],\ninfluential_evidence: [...] >",
    date_range: {
      start: "2025-03-15",
      end: "2025-03-25",
    },
    confidence_level: "medium",
    category: "marketing_campaign",
    impact: "positive",
  },
  {
    insight_id: "insight_003",
    description:
      "Between <start date> and <end date>: <metric name> [<dataset product name>] was moved in a <direction> direction because <activity description>.",
    evidence:
      "Include all evidence reviewed by the user from the Analysis Workflow that was presented when this insight was created.\nactive_evidence: [...],\ninfluential_evidence: [...] >",
    date_range: {
      start: "2025-02-10",
      end: "2025-02-20",
    },
    confidence_level: "low",
    category: "seasonal_trend",
    impact: "negative",
  },
  {
    insight_id: "insight_004",
    description:
      "Weekly organic search traffic increased by 25% following the publication of blog content focused on industry best practices and thought leadership.",
    evidence:
      "Google Analytics data shows a consistent upward trend in organic sessions correlating with content publication dates. Search Console data indicates improved rankings for target keywords. Content engagement metrics show above-average time on page and low bounce rates for the new content.",
    date_range: {
      start: "2025-01-15",
      end: "2025-02-15",
    },
    confidence_level: "high",
    category: "content_marketing",
    impact: "positive",
  },
  {
    insight_id: "insight_005",
    description:
      "Email campaign click-through rates declined by 40% after implementing new email template design, suggesting the previous design was more effective at driving engagement.",
    evidence:
      "Email platform analytics show significant drop in CTR immediately following template change. A/B testing data indicates users prefer the previous template design. Heat map analysis reveals poor engagement with new call-to-action placement.",
    date_range: {
      start: "2025-01-01",
      end: "2025-01-31",
    },
    confidence_level: "high",
    category: "email_marketing",
    impact: "negative",
  },
];
