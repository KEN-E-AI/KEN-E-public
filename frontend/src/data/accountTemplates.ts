import {
  ShoppingCart,
  Laptop,
  Building,
  Users,
  Heart,
  BookOpen,
  Car,
  Home,
  Gamepad2,
  Utensils,
} from "lucide-react";

export interface AccountTemplate {
  id: string;
  name: string;
  description: string;
  icon: any;
  category: string;
  defaultObjectives: string[];
  defaultChannels: string[];
  defaultKPIs: string[];
  recommendedSettings: {
    timezone: string;
    data_region: string;
    industry: string;
  };
}

export const ACCOUNT_TEMPLATES: Record<string, AccountTemplate> = {
  "e-commerce": {
    id: "e-commerce",
    name: "E-Commerce",
    description: "Online retail and e-commerce businesses",
    icon: ShoppingCart,
    category: "Retail",
    defaultObjectives: [
      "Drive website traffic",
      "Increase conversion rates",
      "Boost average order value",
      "Improve customer retention",
    ],
    defaultChannels: [
      "Search Engine Marketing",
      "Display Advertising",
      "Social Media",
      "Email Marketing",
      "Shopping Ads",
    ],
    defaultKPIs: [
      "Revenue",
      "Conversion Rate",
      "Average Order Value",
      "Customer Acquisition Cost",
      "Return on Ad Spend",
    ],
    recommendedSettings: {
      timezone: "America/New_York",
      data_region: "United States",
      industry: "Retail Trade [B2C]",
    },
  },
  saas: {
    id: "saas",
    name: "SaaS",
    description: "Software as a Service companies",
    icon: Laptop,
    category: "Technology",
    defaultObjectives: [
      "Generate qualified leads",
      "Increase trial signups",
      "Improve trial-to-paid conversion",
      "Reduce customer churn",
    ],
    defaultChannels: [
      "Content Marketing",
      "Search Engine Marketing",
      "Social Media",
      "Email Marketing",
      "Webinars",
    ],
    defaultKPIs: [
      "Monthly Recurring Revenue",
      "Customer Acquisition Cost",
      "Customer Lifetime Value",
      "Churn Rate",
      "Trial Conversion Rate",
    ],
    recommendedSettings: {
      timezone: "America/Los_Angeles",
      data_region: "United States",
      industry: "Enterprise Software and SaaS [B2B]",
    },
  },
  "b2b-services": {
    id: "b2b-services",
    name: "B2B Services",
    description: "Professional services and B2B companies",
    icon: Building,
    category: "Services",
    defaultObjectives: [
      "Generate qualified leads",
      "Schedule consultations",
      "Build brand awareness",
      "Nurture long-term relationships",
    ],
    defaultChannels: [
      "LinkedIn Advertising",
      "Content Marketing",
      "Email Marketing",
      "Search Engine Marketing",
      "Industry Events",
    ],
    defaultKPIs: [
      "Lead Quality Score",
      "Cost per Lead",
      "Consultation Booking Rate",
      "Pipeline Value",
      "Customer Lifetime Value",
    ],
    recommendedSettings: {
      timezone: "America/New_York",
      data_region: "United States",
      industry: "Professional, Scientific, and Technical Services [B2B]",
    },
  },
  healthcare: {
    id: "healthcare",
    name: "Healthcare",
    description: "Healthcare providers and medical services",
    icon: Heart,
    category: "Healthcare",
    defaultObjectives: [
      "Attract new patients",
      "Increase appointment bookings",
      "Build trust and credibility",
      "Promote health awareness",
    ],
    defaultChannels: [
      "Search Engine Marketing",
      "Local Advertising",
      "Content Marketing",
      "Social Media",
      "Email Marketing",
    ],
    defaultKPIs: [
      "Patient Acquisition Cost",
      "Appointment Booking Rate",
      "Patient Retention Rate",
      "Online Reputation Score",
      "Local Search Rankings",
    ],
    recommendedSettings: {
      timezone: "America/Chicago",
      data_region: "United States",
      industry: "Health Care and Social Assistance",
    },
  },
  education: {
    id: "education",
    name: "Education",
    description: "Educational institutions and e-learning platforms",
    icon: BookOpen,
    category: "Education",
    defaultObjectives: [
      "Increase student enrollment",
      "Boost course completion rates",
      "Enhance student engagement",
      "Build institutional reputation",
    ],
    defaultChannels: [
      "Social Media",
      "Content Marketing",
      "Search Engine Marketing",
      "Email Marketing",
      "Video Marketing",
    ],
    defaultKPIs: [
      "Enrollment Rate",
      "Course Completion Rate",
      "Student Engagement Score",
      "Cost per Enrollment",
      "Student Satisfaction",
    ],
    recommendedSettings: {
      timezone: "America/New_York",
      data_region: "United States",
      industry: "Educational Services",
    },
  },
  automotive: {
    id: "automotive",
    name: "Automotive",
    description: "Car dealerships and automotive services",
    icon: Car,
    category: "Automotive",
    defaultObjectives: [
      "Generate dealer leads",
      "Increase test drives",
      "Promote service appointments",
      "Build brand loyalty",
    ],
    defaultChannels: [
      "Local Advertising",
      "Display Advertising",
      "Search Engine Marketing",
      "Social Media",
      "Video Marketing",
    ],
    defaultKPIs: [
      "Lead Generation",
      "Test Drive Bookings",
      "Service Appointments",
      "Cost per Lead",
      "Customer Satisfaction",
    ],
    recommendedSettings: {
      timezone: "America/Detroit",
      data_region: "United States",
      industry: "Retail Trade [B2C]",
    },
  },
  "real-estate": {
    id: "real-estate",
    name: "Real Estate",
    description: "Real estate agencies and property management",
    icon: Home,
    category: "Real Estate",
    defaultObjectives: [
      "Generate property leads",
      "Increase property views",
      "Build agent reputation",
      "Facilitate property sales",
    ],
    defaultChannels: [
      "Local Advertising",
      "Search Engine Marketing",
      "Social Media",
      "Display Advertising",
      "Email Marketing",
    ],
    defaultKPIs: [
      "Lead Generation",
      "Property Inquiries",
      "Listing Views",
      "Cost per Lead",
      "Sale Conversion Rate",
    ],
    recommendedSettings: {
      timezone: "America/New_York",
      data_region: "United States",
      industry: "Real Estate and Rental and Leasing",
    },
  },
  gaming: {
    id: "gaming",
    name: "Gaming",
    description: "Game developers and gaming companies",
    icon: Gamepad2,
    category: "Entertainment",
    defaultObjectives: [
      "Increase game downloads",
      "Boost in-app purchases",
      "Improve user retention",
      "Build gaming community",
    ],
    defaultChannels: [
      "Mobile App Advertising",
      "Social Media",
      "Influencer Marketing",
      "Video Marketing",
      "Display Advertising",
    ],
    defaultKPIs: [
      "Download Rate",
      "In-App Purchase Revenue",
      "User Retention Rate",
      "Daily Active Users",
      "Cost per Install",
    ],
    recommendedSettings: {
      timezone: "America/Los_Angeles",
      data_region: "United States",
      industry: "Arts, Entertainment, and Recreation",
    },
  },
  "food-beverage": {
    id: "food-beverage",
    name: "Food & Beverage",
    description: "Restaurants and food service businesses",
    icon: Utensils,
    category: "Food & Beverage",
    defaultObjectives: [
      "Increase foot traffic",
      "Boost online orders",
      "Build customer loyalty",
      "Promote special offers",
    ],
    defaultChannels: [
      "Local Advertising",
      "Social Media",
      "Search Engine Marketing",
      "Email Marketing",
      "Display Advertising",
    ],
    defaultKPIs: [
      "Foot Traffic",
      "Online Order Volume",
      "Customer Retention Rate",
      "Average Order Value",
      "Local Search Rankings",
    ],
    recommendedSettings: {
      timezone: "America/New_York",
      data_region: "United States",
      industry: "Hospitality, Accommodation and Food Services",
    },
  },
  nonprofit: {
    id: "nonprofit",
    name: "Non-Profit",
    description: "Non-profit organizations and charities",
    icon: Users,
    category: "Non-Profit",
    defaultObjectives: [
      "Increase donations",
      "Boost volunteer signups",
      "Raise awareness",
      "Build community support",
    ],
    defaultChannels: [
      "Social Media",
      "Content Marketing",
      "Email Marketing",
      "Search Engine Marketing",
      "Community Outreach",
    ],
    defaultKPIs: [
      "Donation Amount",
      "Volunteer Signups",
      "Social Media Engagement",
      "Email Open Rate",
      "Campaign Reach",
    ],
    recommendedSettings: {
      timezone: "America/New_York",
      data_region: "United States",
      industry: "Nonprofit Organizations and NGOs",
    },
  },
};

export const TEMPLATE_CATEGORIES = [
  "All",
  "Retail",
  "Technology",
  "Services",
  "Healthcare",
  "Education",
  "Automotive",
  "Real Estate",
  "Entertainment",
  "Food & Beverage",
  "Non-Profit",
];

export const getTemplatesByCategory = (category: string) => {
  if (category === "All") {
    return Object.values(ACCOUNT_TEMPLATES);
  }
  return Object.values(ACCOUNT_TEMPLATES).filter(
    (template) => template.category === category,
  );
};

export const getTemplateById = (id: string) => {
  return ACCOUNT_TEMPLATES[id];
};
