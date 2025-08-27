import { BarChart3, Target, Search, Users, Mail, Calendar } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface ProductIntegration {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  status: "available" | "coming_soon";
  category: "analytics" | "advertising" | "email" | "social" | "automation";
  features?: string[];
}

export const PRODUCT_INTEGRATIONS: ProductIntegration[] = [
  {
    id: "google_analytics",
    name: "Google Analytics",
    description: "Web analytics and insights platform",
    icon: BarChart3,
    status: "available",
    category: "analytics",
    features: [
      "Website traffic analysis",
      "Conversion tracking",
      "Audience insights",
    ],
  },
  {
    id: "google_ads",
    name: "Google Ads",
    description: "Search and display advertising platform",
    icon: Target,
    status: "coming_soon",
    category: "advertising",
    features: ["Search campaigns", "Display network", "Shopping ads"],
  },
  {
    id: "bing_ads",
    name: "Microsoft Ads",
    description: "Bing search advertising platform",
    icon: Search,
    status: "coming_soon",
    category: "advertising",
    features: [
      "Bing search ads",
      "LinkedIn targeting",
      "Microsoft Audience Network",
    ],
  },
  {
    id: "meta_ads",
    name: "Meta Ads",
    description: "Facebook and Instagram advertising",
    icon: Users,
    status: "coming_soon",
    category: "advertising",
    features: ["Facebook ads", "Instagram ads", "Audience Network"],
  },
  {
    id: "mailchimp",
    name: "Mailchimp",
    description: "Email marketing and automation",
    icon: Mail,
    status: "coming_soon",
    category: "email",
    features: [
      "Email campaigns",
      "Marketing automation",
      "Audience segmentation",
    ],
  },
  {
    id: "hubspot",
    name: "HubSpot",
    description: "CRM and marketing automation platform",
    icon: Calendar,
    status: "coming_soon",
    category: "automation",
    features: ["CRM integration", "Lead scoring", "Marketing automation"],
  },
];

export const INTEGRATION_CATEGORIES = {
  analytics: "Analytics & Reporting",
  advertising: "Paid Advertising",
  email: "Email Marketing",
  social: "Social Media",
  automation: "Marketing Automation",
} as const;

export type IntegrationCategory = keyof typeof INTEGRATION_CATEGORIES;
