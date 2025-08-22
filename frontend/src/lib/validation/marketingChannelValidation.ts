import { MARKETING_CHANNELS } from "@/data/marketingChannels";
import {
  ValidationResult,
  MARKETING_CHANNEL_LIMITS,
  PAID_MARKETING_CHANNELS,
} from "@/types/validation";

/**
 * Validates marketing channel selections
 */
export const validateMarketingChannels = (
  channels: string[],
): ValidationResult => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Get allowed channel names from the data source
  const allowedChannelNames = [...MARKETING_CHANNELS];

  // Check for duplicates
  const uniqueChannels = new Set(channels);
  if (uniqueChannels.size !== channels.length) {
    errors.push(
      "Duplicate marketing channels detected. Please remove duplicates.",
    );
  }

  // Validate against allowed channels
  const invalidChannels = channels.filter(
    (name) => !allowedChannelNames.includes(name),
  );
  if (invalidChannels.length > 0) {
    errors.push(
      `Invalid marketing channels selected: ${invalidChannels.join(", ")}. Please select from the available options.`,
    );
  }

  // Check maximum limit
  if (channels.length > MARKETING_CHANNEL_LIMITS.MAX_CHANNELS) {
    errors.push(
      `Maximum ${MARKETING_CHANNEL_LIMITS.MAX_CHANNELS} marketing channels allowed. You have selected ${channels.length}.`,
    );
  }

  // Note: Removed the warning about limiting to 3 channels as requested

  // Check for paid channels mix
  const paidChannelsSelected = channels.filter((ch) =>
    PAID_MARKETING_CHANNELS.includes(ch as any),
  );
  const organicChannelsSelected = channels.filter(
    (ch) => !PAID_MARKETING_CHANNELS.includes(ch as any),
  );

  if (paidChannelsSelected.length > 0 && organicChannelsSelected.length === 0) {
    warnings.push(
      "Consider adding organic marketing channels (like SEO or content marketing) to complement your paid strategy.",
    );
  }

  if (organicChannelsSelected.length > 0 && paidChannelsSelected.length === 0) {
    warnings.push(
      "Consider adding paid marketing channels for faster results alongside your organic strategy.",
    );
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Validates marketing channels in context of budget
 */
export const validateMarketingChannelsWithBudget = (
  channels: string[],
  budget?: number | null,
): ValidationResult => {
  const baseValidation = validateMarketingChannels(channels);
  const warnings = [...baseValidation.warnings];
  const errors = [...baseValidation.errors];

  const paidChannelsSelected = channels.filter((ch) =>
    PAID_MARKETING_CHANNELS.includes(ch as any),
  );

  // Budget vs paid channels consistency
  // Removed warning about paid channels without budget as per user request

  if (budget && budget > 0 && paidChannelsSelected.length === 0) {
    warnings.push(
      "You set an advertising budget but selected no paid marketing channels. Consider adding paid channels or removing the budget.",
    );
  }

  // Budget amount warnings
  if (budget && budget > 0) {
    const channelCount = paidChannelsSelected.length;
    if (channelCount > 0) {
      const budgetPerChannel = budget / channelCount;

      if (budgetPerChannel < 1000) {
        warnings.push(
          `With ${channelCount} paid channels and a $${budget.toLocaleString()} budget, each channel gets ~$${Math.round(budgetPerChannel)}/year. Consider focusing on fewer channels or increasing budget.`,
        );
      }

      if (channelCount > 3 && budget < 50000) {
        warnings.push(
          "Managing many paid channels with a limited budget can be challenging. Consider focusing on 2-3 high-performing channels.",
        );
      }
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Get marketing channel validation rules
 */
export const getMarketingChannelRules = () => ({
  maxChannels: MARKETING_CHANNEL_LIMITS.MAX_CHANNELS,
  recommendedChannels: MARKETING_CHANNEL_LIMITS.RECOMMENDED_CHANNELS,
  allowedChannels: [...MARKETING_CHANNELS],
  paidChannels: PAID_MARKETING_CHANNELS,
});

/**
 * Check if a marketing channel is valid
 */
export const isValidMarketingChannel = (channelName: string): boolean => {
  return MARKETING_CHANNELS.includes(channelName as any);
};

/**
 * Remove invalid and duplicate marketing channels
 */
export const sanitizeMarketingChannels = (channels: string[]): string[] => {
  // Remove duplicates and invalid channels
  const uniqueValidChannels = Array.from(
    new Set(
      channels.filter((name) => MARKETING_CHANNELS.includes(name as any)),
    ),
  );

  // Respect max limit
  return uniqueValidChannels.slice(0, MARKETING_CHANNEL_LIMITS.MAX_CHANNELS);
};
