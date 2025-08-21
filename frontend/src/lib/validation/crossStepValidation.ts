import type { AccountCreationData } from "@/components/settings/AccountCreationWizard";
import {
  ValidationResult,
  PAID_MARKETING_CHANNELS,
  CHANNEL_INTEGRATION_RECOMMENDATIONS,
} from "@/types/validation";
import { validateMarketingChannelsWithBudget } from "./marketingChannelValidation";
import {
  validateProductIntegrations,
  suggestComplementaryIntegrations,
} from "./productIntegrationValidation";
import { MARKETING_CHANNELS } from "@/data/marketingChannels";
import { PRODUCT_INTEGRATIONS } from "@/data/productIntegrations";

/**
 * Validates consistency across all wizard steps
 */
export const validateCrossStepConsistency = (
  formData: AccountCreationData,
): ValidationResult => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Validate individual steps first
  const marketingValidation = validateMarketingChannelsWithBudget(
    formData.marketing_channels,
    formData.estimated_annual_ad_budget,
  );
  const integrationValidation = validateProductIntegrations(
    formData.product_integrations,
  );

  errors.push(...marketingValidation.errors);
  errors.push(...integrationValidation.errors);
  warnings.push(...marketingValidation.warnings);
  warnings.push(...integrationValidation.warnings);

  // Cross-step specific validations
  const crossStepValidation = validateMarketingIntegrationConsistency(
    formData.marketing_channels,
    formData.product_integrations,
    formData.estimated_annual_ad_budget,
  );

  errors.push(...crossStepValidation.errors);
  warnings.push(...crossStepValidation.warnings);

  // Industry-specific validations
  const industryValidation = validateIndustryConsistency(
    formData.industry,
    formData.marketing_channels,
    formData.product_integrations,
  );

  warnings.push(...industryValidation.warnings);

  // Website and channel consistency
  const websiteValidation = validateWebsiteChannelConsistency(
    formData.websites,
    formData.marketing_channels,
  );

  warnings.push(...websiteValidation.warnings);

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Validates consistency between marketing channels and product integrations
 */
export const validateMarketingIntegrationConsistency = (
  marketingChannels: string[],
  productIntegrations: string[],
  budget?: number | null,
): ValidationResult => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Check for recommended integrations based on selected channels
  marketingChannels.forEach((channel) => {
    const recommendations = CHANNEL_INTEGRATION_RECOMMENDATIONS[channel] || [];
    const missingRecommendations = recommendations.filter(
      (rec) =>
        !productIntegrations.includes(rec) &&
        PRODUCT_INTEGRATIONS.some(
          (int) => int.id === rec && int.status === "available",
        ),
    );

    if (missingRecommendations.length > 0) {
      const channelName =
        MARKETING_CHANNELS.find((ch) => ch.id === channel)?.name || channel;
      const recNames = missingRecommendations.map((id) => {
        const int = PRODUCT_INTEGRATIONS.find((i) => i.id === id);
        return int?.name || id;
      });

      warnings.push(
        `For ${channelName}, consider adding: ${recNames.join(", ")} for better tracking and optimization.`,
      );
    }
  });

  // Check for integration without corresponding channel
  const integrationsWithoutChannels: string[] = [];

  productIntegrations.forEach((integration) => {
    // Check if this integration suggests a marketing channel
    const suggestedChannels = Object.entries(
      CHANNEL_INTEGRATION_RECOMMENDATIONS,
    )
      .filter(([_, recommendations]) => recommendations.includes(integration))
      .map(([channel, _]) => channel);

    if (suggestedChannels.length > 0) {
      const hasMatchingChannel = suggestedChannels.some((channel) =>
        marketingChannels.includes(channel),
      );

      if (!hasMatchingChannel) {
        const integrationName =
          PRODUCT_INTEGRATIONS.find((int) => int.id === integration)?.name ||
          integration;
        const channelNames = suggestedChannels.map((id) => {
          const ch = MARKETING_CHANNELS.find((c) => c.id === id);
          return ch?.name || id;
        });

        warnings.push(
          `You have ${integrationName} integration but no corresponding marketing channels. Consider adding: ${channelNames.join(" or ")}.`,
        );
      }
    }
  });

  // Advanced paid channel optimization warnings
  const paidChannelsSelected = marketingChannels.filter((ch) =>
    PAID_MARKETING_CHANNELS.includes(ch as any),
  );

  if (paidChannelsSelected.length > 0) {
    // Check for conversion tracking
    const hasConversionTracking = productIntegrations.some((id) =>
      ["google_analytics", "facebook_pixel", "google_tag_manager"].includes(id),
    );

    if (!hasConversionTracking) {
      warnings.push(
        "With paid marketing channels, consider adding conversion tracking (Google Analytics, Facebook Pixel) to measure ROI effectively.",
      );
    }

    // Budget efficiency warning
    if (budget && paidChannelsSelected.length > 3 && budget < 25000) {
      warnings.push(
        `Spreading a $${budget.toLocaleString()} budget across ${paidChannelsSelected.length} paid channels may limit effectiveness. Consider focusing on your top 2-3 performing channels.`,
      );
    }
  }

  // E-commerce specific validations
  const hasEcommerceIntegration = productIntegrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return integration?.category === "ecommerce";
  });

  if (hasEcommerceIntegration) {
    const hasEmailMarketing = productIntegrations.some((id) => {
      const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
      return integration?.category === "email_marketing";
    });

    if (!hasEmailMarketing && !marketingChannels.includes("email")) {
      warnings.push(
        "For e-commerce businesses, email marketing is typically essential for customer retention and increased lifetime value.",
      );
    }

    if (
      !marketingChannels.includes("seo") &&
      !marketingChannels.includes("content")
    ) {
      warnings.push(
        "Consider adding SEO or content marketing for long-term organic growth in e-commerce.",
      );
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Validates consistency with selected industry
 */
export const validateIndustryConsistency = (
  industry: string,
  marketingChannels: string[],
  productIntegrations: string[],
): ValidationResult => {
  const warnings: string[] = [];

  // Industry-specific recommendations
  const industryRecommendations: Record<
    string,
    {
      recommendedChannels: string[];
      recommendedIntegrations: string[];
      warningMessage?: string;
    }
  > = {
    "E-commerce": {
      recommendedChannels: ["google_ads", "facebook", "email", "seo"],
      recommendedIntegrations: ["google_analytics", "mailchimp", "shopify"],
      warningMessage:
        "E-commerce typically benefits from paid ads, email marketing, and robust analytics.",
    },
    SaaS: {
      recommendedChannels: ["content", "seo", "linkedin_ads", "email"],
      recommendedIntegrations: ["google_analytics", "hubspot", "intercom"],
      warningMessage:
        "SaaS companies often succeed with content marketing, SEO, and comprehensive CRM integration.",
    },
    "Local Services": {
      recommendedChannels: ["google_ads", "facebook", "local_seo"],
      recommendedIntegrations: ["google_analytics", "google_my_business"],
      warningMessage:
        "Local services should focus on location-based marketing and local SEO.",
    },
    "B2B Services": {
      recommendedChannels: ["linkedin_ads", "content", "email", "seo"],
      recommendedIntegrations: ["google_analytics", "hubspot", "linkedin"],
      warningMessage:
        "B2B services typically require longer sales cycles with content and LinkedIn focus.",
    },
  };

  const recommendation = industryRecommendations[industry];
  if (recommendation) {
    const missingChannels = recommendation.recommendedChannels.filter(
      (ch) => !marketingChannels.includes(ch),
    );
    const missingIntegrations = recommendation.recommendedIntegrations.filter(
      (int) =>
        !productIntegrations.includes(int) &&
        PRODUCT_INTEGRATIONS.some(
          (i) => i.id === int && i.status === "available",
        ),
    );

    if (missingChannels.length > 0 || missingIntegrations.length > 0) {
      let message = `For ${industry} businesses: `;

      if (missingChannels.length > 0) {
        const channelNames = missingChannels.map((id) => {
          const ch = MARKETING_CHANNELS.find((c) => c.id === id);
          return ch?.name || id;
        });
        message += `Consider adding ${channelNames.join(", ")} marketing channels`;
      }

      if (missingIntegrations.length > 0) {
        const integrationNames = missingIntegrations.map((id) => {
          const int = PRODUCT_INTEGRATIONS.find((i) => i.id === id);
          return int?.name || id;
        });
        if (missingChannels.length > 0) {
          message += ` and ${integrationNames.join(", ")} integrations`;
        } else {
          message += `Consider adding ${integrationNames.join(", ")} integrations`;
        }
      }

      message += ".";
      warnings.push(message);
    }
  }

  return {
    isValid: true,
    errors: [],
    warnings,
  };
};

/**
 * Validates consistency between websites and marketing channels
 */
export const validateWebsiteChannelConsistency = (
  websites: string[],
  marketingChannels: string[],
): ValidationResult => {
  const warnings: string[] = [];

  // Check if they have websites but no web-focused channels
  if (websites.length > 0) {
    const webFocusedChannels = ["seo", "content", "google_ads", "facebook"];
    const hasWebChannel = marketingChannels.some((ch) =>
      webFocusedChannels.includes(ch),
    );

    if (!hasWebChannel) {
      warnings.push(
        "You have websites listed but no web-focused marketing channels. Consider adding SEO, content marketing, or paid search.",
      );
    }

    // Multiple websites warning
    if (websites.length > 3 && marketingChannels.includes("seo")) {
      warnings.push(
        "Managing SEO for multiple websites can be challenging. Consider focusing your SEO efforts on your primary domain.",
      );
    }
  }

  // Check for channels that require websites
  const websiteRequiredChannels = ["seo", "content"];
  const hasWebsiteRequiredChannel = marketingChannels.some((ch) =>
    websiteRequiredChannels.includes(ch),
  );

  if (hasWebsiteRequiredChannel && websites.length === 0) {
    warnings.push(
      "SEO and content marketing require websites to be effective. Please add your website URLs.",
    );
  }

  return {
    isValid: true,
    errors: [],
    warnings,
  };
};

/**
 * Get suggestions for improving the overall marketing strategy
 */
export const getMarketingStrategySuggestions = (
  formData: AccountCreationData,
): string[] => {
  const suggestions: string[] = [];

  // Get complementary integration suggestions
  const integrationSuggestions = suggestComplementaryIntegrations(
    formData.product_integrations,
  );

  if (integrationSuggestions.length > 0) {
    const suggestionNames = integrationSuggestions
      .map((id) => {
        const int = PRODUCT_INTEGRATIONS.find((i) => i.id === id);
        return int?.name || id;
      })
      .slice(0, 3); // Limit to top 3 suggestions

    suggestions.push(
      `Consider adding these integrations to enhance your marketing: ${suggestionNames.join(", ")}`,
    );
  }

  // Budget optimization suggestions
  if (
    formData.estimated_annual_ad_budget &&
    formData.estimated_annual_ad_budget > 0
  ) {
    const paidChannels = formData.marketing_channels.filter((ch) =>
      PAID_MARKETING_CHANNELS.includes(ch as any),
    );

    if (paidChannels.length === 0) {
      suggestions.push(
        "You have advertising budget allocated but no paid marketing channels selected. Consider adding Google Ads or social media advertising.",
      );
    }
  }

  return suggestions;
};
