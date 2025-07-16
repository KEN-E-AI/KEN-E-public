/**
 * Types and constants for organizations and accounts
 */

// Organization types
export interface Organization {
  organization_id: string;
  organization_name: string;
  plan: string;
  website: string;
  company_size: string;
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

// Constants
export const INDUSTRY_OPTIONS = [
  { value: "Technology", label: "Technology" },
  { value: "Healthcare", label: "Healthcare" },
  { value: "Finance", label: "Finance" },
  { value: "Education", label: "Education" },
  { value: "Retail", label: "Retail" },
  { value: "Manufacturing", label: "Manufacturing" },
  { value: "Services", label: "Services" },
  { value: "Other", label: "Other" },
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
