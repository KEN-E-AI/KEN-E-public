export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ValidationRule<T> {
  name: string;
  validate: (value: T) => ValidationResult;
}

// Marketing channel validation constraints
export const MARKETING_CHANNEL_LIMITS = {
  MIN_CHANNELS: 0,
  MAX_CHANNELS: 8, // Prevent performance issues with too many channels
  RECOMMENDED_CHANNELS: 3,
} as const;

// Product integration limits
export const PRODUCT_INTEGRATION_LIMITS = {
  MIN_INTEGRATIONS: 0,
  MAX_INTEGRATIONS: 12, // Reasonable limit for performance
  RECOMMENDED_INTEGRATIONS: 5,
} as const;

// Integration conflict definitions
export const INTEGRATION_CONFLICTS: Record<string, string[]> = {
  google_analytics: ["adobe_analytics", "mixpanel"], // Can't have multiple analytics
  adobe_analytics: ["google_analytics", "mixpanel"],
  mixpanel: ["google_analytics", "adobe_analytics"],
  shopify: ["woocommerce", "magento"], // Can't have multiple ecommerce platforms
  woocommerce: ["shopify", "magento"],
  magento: ["shopify", "woocommerce"],
  mailchimp: ["constant_contact", "klaviyo"], // Can't have multiple email platforms
  constant_contact: ["mailchimp", "klaviyo"],
  klaviyo: ["mailchimp", "constant_contact"],
};

// Integration prerequisite definitions
export const INTEGRATION_PREREQUISITES: Record<string, string[]> = {
  google_ads_enhanced: ["google_analytics"], // Enhanced features need analytics
  facebook_pixel: ["facebook"], // Pixel needs basic Facebook integration
  google_tag_manager: ["google_analytics"], // GTM works best with GA
};

// Paid marketing channels that require budget
export const PAID_MARKETING_CHANNELS = [
  "Search Engine Marketing",
  "Display Advertising",
  "Social Media",
  "LinkedIn Advertising",
  "Shopping Ads",
  "Mobile App Advertising",
] as const;

// Marketing channels that work well with specific integrations
export const CHANNEL_INTEGRATION_RECOMMENDATIONS: Record<string, string[]> = {
  "Search Engine Marketing": ["google_analytics", "google_tag_manager"],
  "Social Media": ["meta_ads", "google_analytics"],
  "Email Marketing": ["mailchimp", "hubspot"],
  "Content Marketing": ["google_analytics", "hubspot"],
  "Display Advertising": ["google_analytics", "google_tag_manager"],
  "LinkedIn Advertising": ["hubspot", "google_analytics"],
  "Shopping Ads": ["google_analytics", "google_tag_manager"],
};

export type ValidationSeverity = "error" | "warning" | "info";

export interface ValidationMessage {
  severity: ValidationSeverity;
  message: string;
  field?: string;
  code?: string;
}

export interface FormValidationState {
  isValid: boolean;
  messages: ValidationMessage[];
  fieldErrors: Record<string, string[]>;
  fieldWarnings: Record<string, string[]>;
}
