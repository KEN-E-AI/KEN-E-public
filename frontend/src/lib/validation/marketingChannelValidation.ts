import { MARKETING_CHANNELS } from "@/data/marketingChannels";
import {
  ValidationResult,
  MARKETING_CHANNEL_LIMITS,
  PAID_MARKETING_CHANNELS,
} from "@/types/validation";

/**
 * Validates marketing channels in context of budget
 */
export const validateMarketingChannelsWithBudget = (
  channels: string[],
  budget?: number | null,
): ValidationResult => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Only keep essential validation - check for at least one channel
  if (channels.length === 0) {
    errors.push("Please select at least one marketing channel.");
  }

  // Check maximum limit
  if (channels.length > MARKETING_CHANNEL_LIMITS.MAX_CHANNELS) {
    errors.push(
      `Maximum ${MARKETING_CHANNEL_LIMITS.MAX_CHANNELS} marketing channels allowed. You have selected ${channels.length}.`,
    );
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
