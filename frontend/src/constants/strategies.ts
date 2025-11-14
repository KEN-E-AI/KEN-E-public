/**
 * Constants for strategy selection and configuration
 */

export const VALID_STRATEGY_TYPES = [
  "business_strategy",
  "competitive_strategy",
  "marketing_strategy",
  "brand_guidelines",
] as const;

export type StrategyType = (typeof VALID_STRATEGY_TYPES)[number];

export const STRATEGY_LABELS: Record<StrategyType, string> = {
  business_strategy: "Business Strategy",
  competitive_strategy: "Competitive Analysis",
  marketing_strategy: "Marketing Strategy",
  brand_guidelines: "Brand Guidelines",
};

export const STRATEGY_DESCRIPTIONS: Record<StrategyType, string> = {
  business_strategy: "Product portfolio, SWOT analysis, and strategic goals",
  competitive_strategy: "Competitor analysis and market positioning",
  marketing_strategy: "Customer profiles and marketing campaigns",
  brand_guidelines: "Brand identity, voice, and visual guidelines",
};

export const DEFAULT_PRODUCT_CATEGORIES = [
  "Core Products & Services",
  "Premium Offerings",
  "Subscription Services",
  "Professional Solutions",
  "Digital Products",
];
