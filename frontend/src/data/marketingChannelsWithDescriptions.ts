export interface MarketingChannelInfo {
  id: string;
  name: string;
  description: string;
  category: string;
}

export const MARKETING_CHANNELS_WITH_DESCRIPTIONS: MarketingChannelInfo[] = [
  // Digital Advertising
  {
    id: "search-engine-marketing",
    name: "Search Engine Marketing",
    description:
      "Paid ads on search engines like Google and Bing to reach users actively searching for your products or services",
    category: "Digital Advertising",
  },
  {
    id: "display-advertising",
    name: "Display Advertising",
    description:
      "Visual banner ads shown on websites, apps, and social platforms to build brand awareness and drive traffic",
    category: "Digital Advertising",
  },
  {
    id: "social-media-ads",
    name: "Social Media",
    description:
      "Paid advertising on social platforms like Facebook, Instagram, and Twitter to engage targeted audiences",
    category: "Digital Advertising",
  },
  {
    id: "shopping-ads",
    name: "Shopping Ads",
    description:
      "Product listing ads that appear in search results with images, prices, and merchant information",
    category: "Digital Advertising",
  },
  {
    id: "mobile-app-advertising",
    name: "Mobile App Advertising",
    description:
      "Ads displayed within mobile applications to reach users on smartphones and tablets",
    category: "Digital Advertising",
  },

  // Content & Social
  {
    id: "content-marketing",
    name: "Content Marketing",
    description:
      "Creating valuable content like blogs, guides, and resources to attract and engage your target audience",
    category: "Content & Social",
  },
  {
    id: "video-marketing",
    name: "Video Marketing",
    description:
      "Using video content on platforms like YouTube and TikTok to demonstrate products and tell your brand story",
    category: "Content & Social",
  },
  {
    id: "influencer-marketing",
    name: "Influencer Marketing",
    description:
      "Partnering with influencers and content creators to promote your brand to their engaged audiences",
    category: "Content & Social",
  },

  // Professional & B2B
  {
    id: "linkedin-advertising",
    name: "LinkedIn Advertising",
    description:
      "Targeted B2B advertising on LinkedIn to reach professionals and decision-makers in specific industries",
    category: "Professional & B2B",
  },
  {
    id: "industry-events",
    name: "Industry Events",
    description:
      "Participating in trade shows, conferences, and industry gatherings to network and showcase your offerings",
    category: "Professional & B2B",
  },
  {
    id: "webinars",
    name: "Webinars",
    description:
      "Hosting online seminars and presentations to educate prospects and demonstrate expertise",
    category: "Professional & B2B",
  },

  // Local & Community
  {
    id: "local-advertising",
    name: "Local Advertising",
    description:
      "Targeted ads in local newspapers, directories, and community platforms to reach nearby customers",
    category: "Local & Community",
  },
  {
    id: "community-outreach",
    name: "Community Outreach",
    description:
      "Engaging with local communities through sponsorships, events, and grassroots marketing initiatives",
    category: "Local & Community",
  },
  {
    id: "direct-mail",
    name: "Direct Mail",
    description:
      "Sending physical marketing materials like postcards and catalogs directly to potential customers",
    category: "Local & Community",
  },

  // Traditional Media
  {
    id: "print-advertising",
    name: "Print Advertising",
    description:
      "Ads in newspapers, magazines, and print publications to reach specific demographics and regions",
    category: "Traditional Media",
  },
  {
    id: "radio-advertising",
    name: "Radio Advertising",
    description:
      "Audio commercials on radio stations to reach local and regional audiences during their daily routines",
    category: "Traditional Media",
  },
  {
    id: "television-advertising",
    name: "Television Advertising",
    description:
      "TV commercials on broadcast and cable networks for mass market reach and brand building",
    category: "Traditional Media",
  },
  {
    id: "outdoor-advertising",
    name: "Outdoor Advertising",
    description:
      "Billboards, transit ads, and outdoor signage to capture attention in high-traffic locations",
    category: "Traditional Media",
  },

  // Relationship Building
  {
    id: "email-marketing",
    name: "Email Marketing",
    description:
      "Sending targeted emails to nurture leads, share updates, and drive customer engagement",
    category: "Relationship Building",
  },
  {
    id: "referral-marketing",
    name: "Referral Marketing",
    description:
      "Encouraging satisfied customers to recommend your business through word-of-mouth and referral programs",
    category: "Relationship Building",
  },
];

export const MARKETING_CHANNEL_CATEGORIES_WITH_DESCRIPTIONS =
  MARKETING_CHANNELS_WITH_DESCRIPTIONS.reduce(
    (acc, channel) => {
      if (!acc[channel.category]) {
        acc[channel.category] = [];
      }
      acc[channel.category].push(channel);
      return acc;
    },
    {} as Record<string, MarketingChannelInfo[]>,
  );

// Helper function to get channel info by name (for compatibility with existing data)
export function getChannelInfoByName(
  channelName: string,
): MarketingChannelInfo | undefined {
  return MARKETING_CHANNELS_WITH_DESCRIPTIONS.find(
    (channel) => channel.name === channelName,
  );
}

// Category descriptions for tab tooltips
export const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  "Digital Advertising": "Online paid advertising channels",
  "Content & Social": "Content creation and social media engagement",
  "Professional & B2B": "Business-to-business marketing channels",
  "Local & Community": "Location-based and community marketing",
  "Traditional Media": "Traditional advertising channels",
  "Relationship Building": "Direct customer engagement channels",
};
