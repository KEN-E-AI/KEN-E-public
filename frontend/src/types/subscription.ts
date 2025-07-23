export interface SubscriptionPlanFeatures {
  max_users: number;
  max_reports: number;
  features: string[];
}

export interface SubscriptionPlanDefinition {
  plan_id: string;
  plan_name: string;
  plan_description: string;
  price: number;
  currency: string;
  billing_cycle: string;
  features: SubscriptionPlanFeatures;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
