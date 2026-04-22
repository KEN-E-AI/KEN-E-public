import {
  LayoutDashboard,
  Search,
  Video,
  Linkedin as LinkedinIcon,
  Newspaper,
  type LucideIcon,
} from 'lucide-react';

export interface ExtensionConfigStep {
  id: string;
  title: string;
  description: string;
}

export interface ExtensionDefinition {
  id: string;
  slug: string;
  name: string;
  description: string;
  longDescription: string;
  icon: LucideIcon;
  category: string;
  color: string;
  shadow: string;
  rotation: string;
  configSteps: ExtensionConfigStep[];
  source: 'official' | 'community';
  author?: string;
}

export interface ExtensionInstance {
  extensionId: string;
  activatedAt: Date;
  config: Record<string, unknown>;
}

export const extensionCatalog: ExtensionDefinition[] = [
  {
    id: 'dashboard-creator',
    slug: 'dashboard-creator',
    name: 'Dashboard Creator',
    description: 'Create and manage automated marketing dashboards with scheduled refreshes.',
    longDescription:
      'Build automated dashboards that pull from your connected data sources, refresh on a schedule, and deliver key marketing metrics at a glance. Perfect for executive reporting and campaign tracking.',
    icon: LayoutDashboard,
    category: 'Analytics',
    color: 'var(--color-blue-500)',
    shadow: 'var(--shadow-color-blue)',
    rotation: '',
    configSteps: [],
    source: 'official',
  },
  {
    id: 'seo-optimizer',
    slug: 'seo-optimizer',
    name: 'SEO Optimizer',
    description: 'Analyze your search engine optimization data to improve the SEO quality of your website content.',
    longDescription:
      'Run comprehensive audits of your site\'s on-page and technical SEO, track keyword rankings over time, and receive AI-generated recommendations to boost organic visibility. Integrates with Google Search Console and third-party crawlers to surface issues and opportunities.',
    icon: Search,
    category: 'Content',
    color: 'var(--color-emerald-500)',
    shadow: 'var(--shadow-color-emerald)',
    rotation: '',
    configSteps: [
      {
        id: 'connect-search-console',
        title: 'Search Console',
        description: 'Connect your Google Search Console account for ranking data.',
      },
      {
        id: 'target-keywords',
        title: 'Target Keywords',
        description: 'Define the primary keywords and pages you want to track.',
      },
    ],
    source: 'official',
  },
  {
    id: 'tiktok-analyzer',
    slug: 'tiktok-analyzer',
    name: 'TikTok Analyzer',
    description: 'Identifies popular TikTok content in your niche to surface trends and recommend content strategies.',
    longDescription:
      'Monitor trending TikTok videos, hashtags, and audio in your industry vertical. Get AI-powered recommendations on content formats, posting cadence, and trend-jacking opportunities to grow your brand\'s short-form video presence.',
    icon: Video,
    category: 'Social',
    color: 'var(--color-pink-500)',
    shadow: 'var(--shadow-color-pink)',
    rotation: '',
    configSteps: [
      {
        id: 'niche-selection',
        title: 'Select Niche',
        description: 'Choose the industry verticals and topics to monitor.',
      },
    ],
    source: 'community',
    author: 'SocialPulse Labs',
  },
  {
    id: 'linkedin-cold-outreach',
    slug: 'linkedin-cold-outreach',
    name: 'LinkedIn Cold Outreach',
    description: 'Connects with prospective customers who might be interested in your product or service.',
    longDescription:
      'Automate personalized LinkedIn outreach sequences targeting prospects that match your ideal customer profile. Uses AI to craft connection requests and follow-up messages, track response rates, and manage your pipeline from first touch to booked meeting.',
    icon: LinkedinIcon,
    category: 'Sales',
    color: 'var(--color-sky-500)',
    shadow: 'var(--shadow-color-sky)',
    rotation: '',
    configSteps: [
      {
        id: 'connect-linkedin',
        title: 'LinkedIn Account',
        description: 'Connect your LinkedIn account to enable outreach.',
      },
      {
        id: 'ideal-customer',
        title: 'Ideal Customer Profile',
        description: 'Define the job titles, industries, and company sizes to target.',
      },
    ],
    source: 'community',
    author: 'OutboundFlow',
  },
  {
    id: 'news-monitoring',
    slug: 'news-monitoring',
    name: 'News Monitoring',
    description: 'Monitor the news for updates about your company, your customers, your products or your competitors.',
    longDescription:
      'Stay on top of breaking news and media mentions relevant to your brand, competitors, and industry. Automatically scans thousands of news sources, blogs, and press releases to surface stories that matter, so you can react quickly and stay ahead of the narrative.',
    icon: Newspaper,
    category: 'Analytics',
    color: 'var(--color-amber-500)',
    shadow: 'var(--shadow-color-amber)',
    rotation: '',
    configSteps: [
      {
        id: 'topics',
        title: 'Topics & Keywords',
        description: 'Define the companies, products, and competitors you want to monitor.',
      },
      {
        id: 'sources',
        title: 'News Sources',
        description: 'Choose which news sources and regions to include in monitoring.',
      },
    ],
    source: 'official',
  },
];

export function getExtensionBySlug(slug: string): ExtensionDefinition | undefined {
  return extensionCatalog.find((p) => p.slug === slug);
}

export function getExtensionById(id: string): ExtensionDefinition | undefined {
  return extensionCatalog.find((p) => p.id === id);
}