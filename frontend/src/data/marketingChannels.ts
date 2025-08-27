export const MARKETING_CHANNELS = [
  "Search Engine Marketing",
  "Display Advertising",
  "Social Media",
  "Email Marketing",
  "Content Marketing",
  "LinkedIn Advertising",
  "Shopping Ads",
  "Local Advertising",
  "Video Marketing",
  "Mobile App Advertising",
  "Influencer Marketing",
  "Webinars",
  "Industry Events",
  "Community Outreach",
  "Print Advertising",
  "Radio Advertising",
  "Television Advertising",
  "Outdoor Advertising",
  "Direct Mail",
  "Referral Marketing",
] as const;

export type MarketingChannel = (typeof MARKETING_CHANNELS)[number];

export const MARKETING_CHANNEL_CATEGORIES = {
  "Digital Advertising": [
    "Search Engine Marketing",
    "Display Advertising",
    "Social Media",
    "Shopping Ads",
    "Mobile App Advertising",
  ],
  "Content & Social": [
    "Content Marketing",
    "Social Media",
    "Video Marketing",
    "Influencer Marketing",
  ],
  "Professional & B2B": ["LinkedIn Advertising", "Industry Events", "Webinars"],
  "Local & Community": [
    "Local Advertising",
    "Community Outreach",
    "Direct Mail",
  ],
  "Traditional Media": [
    "Print Advertising",
    "Radio Advertising",
    "Television Advertising",
    "Outdoor Advertising",
  ],
  "Relationship Building": ["Email Marketing", "Referral Marketing"],
} as const;
