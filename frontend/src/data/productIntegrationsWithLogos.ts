import { BarChart3, Target, Search, Users, Mail, Calendar } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface ProductIntegration {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon; // Fallback icon if logo fails to load
  logo: string; // URL or path to logo image
  status: "available" | "coming_soon";
  category: "analytics" | "advertising" | "email" | "social" | "automation";
}

export const PRODUCT_INTEGRATIONS: ProductIntegration[] = [
  {
    id: "google_analytics",
    name: "Google Analytics",
    description:
      "Web analytics and insights platform for tracking website performance and user behavior",
    icon: BarChart3,
    logo: "https://www.gstatic.com/analytics-suite/header/suite/v2/ic_analytics.svg",
    status: "available",
    category: "analytics",
  },
  {
    id: "google_ads",
    name: "Google Ads",
    description:
      "Search and display advertising platform to reach customers across Google's network",
    icon: Target,
    logo: "https://upload.wikimedia.org/wikipedia/commons/c/c7/Google_Ads_logo.svg",
    status: "coming_soon",
    category: "advertising",
  },
  {
    id: "bing_ads",
    name: "Microsoft Ads",
    description:
      "Reach millions through Bing search and the Microsoft Advertising network",
    icon: Search,
    logo: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Microsoft_logo.svg/512px-Microsoft_logo.svg.png",
    status: "coming_soon",
    category: "advertising",
  },
  {
    id: "meta_ads",
    name: "Meta Ads",
    description:
      "Advertise across Facebook, Instagram, Messenger, and WhatsApp",
    icon: Users,
    logo: "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/512px-Meta_Platforms_Inc._logo.svg.png",
    status: "coming_soon",
    category: "advertising",
  },
  {
    id: "mailchimp",
    name: "Mailchimp",
    description:
      "All-in-one email marketing and automation platform for growing businesses",
    icon: Mail,
    logo: "https://cdn.worldvectorlogo.com/logos/mailchimp-freddie-icon.svg",
    status: "coming_soon",
    category: "email",
  },
  {
    id: "hubspot",
    name: "HubSpot",
    description:
      "Complete CRM platform with marketing, sales, and service hubs",
    icon: Calendar,
    logo: "https://cdn2.hubspot.net/hubfs/53/HubSpot%20Logos/HubSpot-Inversed-Favicon.png",
    status: "coming_soon",
    category: "automation",
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
