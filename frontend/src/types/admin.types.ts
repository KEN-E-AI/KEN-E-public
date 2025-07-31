/**
 * Types for admin functionality
 */

export interface IndustryKeyword {
  id: string;
  industry: string;
  keywords: string[];
  updated_by: string;
  updated_at: string;
}

export interface UpdateIndustryKeywordsRequest {
  industry: string;
  keywords: string[];
}

export interface AdminStats {
  total_users: number;
  total_organizations: number;
  total_accounts: number;
  active_subscriptions: number;
}

export interface InitialActivity {
  id: string;
  name: string;
  description: string;
  category: string;
  default_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface InitialMetric {
  id: string;
  name: string;
  description: string;
  category: string;
  calculation_method: string;
  default_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  features: string[];
  limits: {
    users: number;
    accounts: number;
    api_calls: number;
  };
  active: boolean;
  created_at: string;
  updated_at: string;
}
