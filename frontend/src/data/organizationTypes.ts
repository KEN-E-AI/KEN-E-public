/**
 * Types and constants for organizations and accounts
 */

// Organization types
export interface Organization {
  organization_id: string;
  organization_name: string;
  plan: string;
  website: string;
  company_size?: string;
  agency: boolean;
  child_organizations?: string[];
  subscription: {
    plan_name: string;
    plan_description: string;
    price: number;
    currency: string;
    billing_cycle: string;
    next_billing_date: string;
    features: string[];
    usage: {
      reports_generated: number;
      reports_limit: number;
    };
  };
  billing: {
    payment_method: {
      last_four: string;
      brand: string;
      expires: string;
    };
    address: string;
    tax_id: string;
  };
  team: {
    members_used: number;
    members_limit: number;
    pending_invitations: number;
  };
  accounts: Array<{
    account_id: string;
    account_name: string;
  }>;
  created_at?: string;
  updated_at?: string;
}

// Account types
export interface Account {
  account_id: string;
  account_name: string;
  organization_id: string;
  industry: string;
  status: string;
  websites: string[];
  timezone: string;
  data_region: string;
  region: string[];
  created_at?: string;
  updated_at?: string;
}

// Option types
export interface IndustryOption {
  value: string;
  label: string;
  definition: string;
}

// Constants
export const INDUSTRY_OPTIONS: IndustryOption[] = [
  {
    value: "Agriculture, Forestry, Fishing and Hunting",
    label: "Agriculture, Forestry, Fishing and Hunting",
    definition:
      "Growing crops, raising livestock, logging, and harvesting wild resources (fish, game, sap, etc.).",
  },
  {
    value: "Utilities",
    label: "Utilities",
    definition:
      "Providing electric power, natural gas, steam supply, water supply, and sewage removal services.",
  },
  {
    value: "Construction",
    label: "Construction",
    definition:
      "Building, repairing, and renovating residential, commercial, and civil structures and infrastructure.",
  },
  {
    value: "Manufacturing",
    label: "Manufacturing",
    definition:
      "Transforming raw materials into finished goods by mechanical, chemical, or electronic processes.",
  },
  {
    value: "Wholesale Trade [B2B]",
    label: "Wholesale Trade [B2B]",
    definition:
      "Buying and selling goods in bulk—typically to retailers, other merchants, or institutional users.",
  },
  {
    value: "Retail Trade [B2C]",
    label: "Retail Trade [B2C]",
    definition:
      "Selling goods directly to consumers through stores, online, or other direct channels.",
  },
  {
    value: "Transportation and Warehousing",
    label: "Transportation and Warehousing",
    definition:
      "Moving people or goods by road, rail, air, or water, plus storage and logistics services.",
  },
  {
    value: "Finance and Insurance",
    label: "Finance and Insurance",
    definition:
      "Facilitating financial transactions: banking, investment, securities, insurance carriers, and related services.",
  },
  {
    value: "Real Estate and Rental and Leasing",
    label: "Real Estate and Rental and Leasing",
    definition:
      "Selling, renting, and managing real property (land and buildings) and leasing machinery, equipment, and vehicles.",
  },
  {
    value: "Professional, Scientific, and Technical Services [B2B]",
    label: "Professional, Scientific, and Technical Services [B2B]",
    definition:
      "Specialized services provided to businesses. Services require high intellectual effort and training: legal, accounting, engineering, design, consulting, R&D, and advertising.",
  },
  {
    value: "Professional, Scientific, and Technical Services [B2C]",
    label: "Professional, Scientific, and Technical Services [B2C]",
    definition:
      "Specialized services provided to consumers. Services require high intellectual effort and training: legal, accounting, engineering, design, consulting, R&D, and advertising.",
  },
  {
    value: "Educational Services",
    label: "Educational Services",
    definition:
      "Providing instruction and training at the high school level or below: schools or tutoring centers.",
  },
  {
    value: "Higher Educational Services",
    label: "Higher Educational Services",
    definition:
      "Providing instruction and training above the high school level, such as colleges, universities, and technical centers.",
  },
  {
    value: "Health Care and Social Assistance",
    label: "Health Care and Social Assistance",
    definition:
      "Delivering medical, dental, and mental health services, plus social assistance (child care, community services).",
  },
  {
    value: "Arts, Entertainment, and Recreation",
    label: "Arts, Entertainment, and Recreation",
    definition:
      "Performing arts, spectator sports, museums, heritage sites, amusement parks, and recreational facilities.",
  },
  {
    value: "Hospitality, Accommodation and Food Services",
    label: "Hospitality, Accommodation and Food Services",
    definition:
      "Lodging (hotels, motels) and food/beverage preparation and serving (restaurants, bars, catering).",
  },
  {
    value: "Public Administration",
    label: "Public Administration",
    definition:
      "Government agencies at the federal, state, and local levels, including legislative, judicial, and executive functions.",
  },
  {
    value: "Media and Publishing",
    label: "Media and Publishing",
    definition:
      "Producing, curating and distributing editorial content across print, digital and broadcast channels—newspapers, magazines, websites, newsletters, podcasts and streaming platforms focused on news, lifestyle and entertainment.",
  },
  {
    value: "Pharmaceuticals and Biotechnology [Direct to Consumer]",
    label: "Pharmaceuticals and Biotechnology [Direct to Consumer]",
    definition:
      "Researching, developing, manufacturing, and distributing medicinal drugs, biologics, vaccines, and therapies—covering drug discovery, clinical trials, regulatory approval, and commercialization. Marketed directly to consumers.",
  },
  {
    value: "Pharmaceuticals and Biotechnology [Healthcare Professionals]",
    label: "Pharmaceuticals and Biotechnology [Healthcare Professionals]",
    definition:
      "Researching, developing, manufacturing, and distributing medicinal drugs, biologics, vaccines, and therapies—covering drug discovery, clinical trials, regulatory approval, and commercialization. Marketed to healthcare professionals.",
  },
  {
    value: "Enterprise Software and SaaS [B2B]",
    label: "Enterprise Software and SaaS [B2B]",
    definition:
      "Developing and providing subscription-based, cloud-hosted software applications and platforms to businesses—CRM, ERP, analytics, collaboration, and developer tools delivered over the internet.",
  },
  {
    value: "Consumer Software and SaaS [B2C]",
    label: "Consumer Software and SaaS [B2C]",
    definition:
      "Developing and providing subscription-based, cloud-hosted software applications and platforms to consumers.",
  },
  {
    value: "Nonprofit Organizations and NGOs",
    label: "Nonprofit Organizations and NGOs",
    definition:
      "Charitable, philanthropic, and non-governmental organizations operating on a not-for-profit basis—advocacy, grantmaking, research, social services, and community development in areas such as health, education, the environment, and human rights.",
  },
  {
    value: "Other Services (except Public Administration)",
    label: "Other Services (except Public Administration)",
    definition:
      "Personal and laundry services, repair and maintenance, religious organizations, civic and social advocacy.",
  },
  {
    value: "Other",
    label: "Other",
    definition:
      "Businesses that do not fit clearly into any of the other categories.",
  },
];

export const COMPANY_SIZE_OPTIONS = [
  { value: "1-10", label: "1-10 employees" },
  { value: "11-50", label: "11-50 employees" },
  { value: "51-200", label: "51-200 employees" },
  { value: "201-500", label: "201-500 employees" },
  { value: "501-1000", label: "501-1000 employees" },
  { value: "1000+", label: "1000+ employees" },
];

export const TIMEZONE_OPTIONS = [
  { value: "America/New_York", label: "America/New_York (ET)" },
  { value: "America/Chicago", label: "America/Chicago (CT)" },
  { value: "America/Denver", label: "America/Denver (MT)" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles (PT)" },
  { value: "America/Phoenix", label: "America/Phoenix (MST)" },
  { value: "America/Anchorage", label: "America/Anchorage (AKST)" },
  { value: "Pacific/Honolulu", label: "Pacific/Honolulu (HST)" },
  { value: "America/Toronto", label: "America/Toronto (ET)" },
  { value: "America/Vancouver", label: "America/Vancouver (PT)" },
  { value: "Europe/London", label: "Europe/London (GMT)" },
  { value: "Europe/Paris", label: "Europe/Paris (CET)" },
  { value: "Europe/Berlin", label: "Europe/Berlin (CET)" },
  { value: "Europe/Moscow", label: "Europe/Moscow (MSK)" },
  { value: "Asia/Dubai", label: "Asia/Dubai (GST)" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata (IST)" },
  { value: "Asia/Bangkok", label: "Asia/Bangkok (ICT)" },
  { value: "Asia/Shanghai", label: "Asia/Shanghai (CST)" },
  { value: "Asia/Hong_Kong", label: "Asia/Hong_Kong (HKT)" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo (JST)" },
  { value: "Asia/Seoul", label: "Asia/Seoul (KST)" },
  { value: "Australia/Sydney", label: "Australia/Sydney (AEDT)" },
  { value: "Pacific/Auckland", label: "Pacific/Auckland (NZDT)" },
];
