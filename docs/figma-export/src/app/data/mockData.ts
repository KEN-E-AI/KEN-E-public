// Mock data for MER-E platform

import type { OutputFileType } from './automationDetailsData';

export interface Organization {
  id: string;
  name: string;
  slug: string;
  avatarColor: string;
}

export interface Account {
  id: string;
  name: string;
  organizationId: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
}

export interface AISession {
  id: string;
  name: string;
  status: 'working' | 'idle' | 'complete';
  color: string;
  lastMessage?: string;
  category?: string;
  isActive?: boolean;
  hasUnreviewedTasks?: boolean;
  createdAt: Date;
}

export interface Notification {
  id: string;
  title: string;
  description: string;
  timestamp: Date;
  isRead: boolean;
  actionRequired?: boolean;
  type: 'info' | 'warning' | 'success' | 'error';
}

export interface MarketingActivity {
  id: string;
  title: string;
  channel: 'email' | 'paid-search' | 'social' | 'content' | 'events' | 'seo';
  startDate: Date;
  endDate: Date;
  status: 'draft' | 'scheduled' | 'active' | 'completed';
  campaignId?: string;
}

export type DashboardViewType = 'bar' | 'line' | 'area' | 'point' | 'arc' | 'table';

export interface DashboardPlacement {
  id: string;
  nodeId: string;
  fileType: OutputFileType;
  viewOverride?: DashboardViewType;
  color?: string;
  showDataLabels?: boolean;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Workflow {
  id: string;
  name: string;
  type: 'freeform' | 'dashboard';
  schedule: string;
  lastRun: Date;
  nextRun?: Date;
  status: 'success' | 'failed' | 'running';
  description?: string;
  extensionId?: string;
  goal?: string;
  campaignId?: string;
  tags?: string[];
  createdBy?: string;
  isActive?: boolean;
  dashboardPlacements?: DashboardPlacement[];
}

export interface PerformanceMetric {
  id: string;
  name: string;
  value: number;
  target: number;
  change: number;
  trend: number[];
  unit?: string;
}

export interface Recommendation {
  id: string;
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  category: string;
}

export interface AnalysisSnapshot {
  id: string;
  completedAt: Date;
  metrics: PerformanceMetric[];
  recommendations: Recommendation[];
}

export interface Integration {
  id: string;
  name: string;
  status: 'connected' | 'disconnected' | 'error';
  icon: string;
  lastSync?: Date;
}

export interface AccountUser {
  id: string;
  name: string;
  email: string;
  avatarInitials: string;
  role: string;
}

export const mockAccountUsers: AccountUser[] = [
  { id: 'u1', name: 'Sarah Chen', email: 'sarah.chen@company.com', avatarInitials: 'SC', role: 'Admin' },
  { id: 'u2', name: 'Marcus Johnson', email: 'marcus.j@company.com', avatarInitials: 'MJ', role: 'Marketing Manager' },
  { id: 'u3', name: 'Priya Patel', email: 'priya.p@company.com', avatarInitials: 'PP', role: 'Campaign Strategist' },
  { id: 'u4', name: 'David Kim', email: 'david.kim@company.com', avatarInitials: 'DK', role: 'Analyst' },
  { id: 'u5', name: 'Elena Rodriguez', email: 'elena.r@company.com', avatarInitials: 'ER', role: 'Content Lead' },
];

export const mockSessions: AISession[] = [
  {
    id: '1',
    name: 'Building Q3 calendar',
    status: 'working',
    color: '#3b82f6',
    lastMessage: 'Adding 12 events across email and social channels...',
    category: 'Campaign Planning',
    isActive: true,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 13)
  },
  {
    id: '2',
    name: 'Analyzing campaign performance',
    status: 'idle',
    color: '#8b5cf6',
    lastMessage: 'Analysis complete. Ready for your next question.',
    category: 'Analytics',
    isActive: true,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 12)
  },
  {
    id: '3',
    name: 'Setting up automation',
    status: 'complete',
    color: '#10b981',
    lastMessage: 'Workflow created: Weekly performance digest',
    category: 'Automation',
    isActive: false,
    hasUnreviewedTasks: true,
    createdAt: new Date(2026, 1, 11)
  },
  {
    id: '4',
    name: 'Email subject line testing',
    status: 'complete',
    color: '#f59e0b',
    category: 'Email Marketing',
    isActive: false,
    hasUnreviewedTasks: true,
    createdAt: new Date(2026, 1, 10)
  },
  {
    id: '5',
    name: 'Budget allocation review',
    status: 'idle',
    color: '#ec4899',
    category: 'Budget',
    isActive: false,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 9)
  },
  {
    id: '6',
    name: 'Social media content calendar',
    status: 'complete',
    color: '#06b6d4',
    category: 'Social Media',
    isActive: false,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 8)
  },
  {
    id: '7',
    name: 'Landing page optimization',
    status: 'idle',
    color: '#8b5cf6',
    category: 'Conversion',
    isActive: false,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 7)
  },
  {
    id: '8',
    name: 'Q1 campaign retrospective',
    status: 'complete',
    color: '#10b981',
    category: 'Analytics',
    isActive: false,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 5)
  },
  {
    id: '9',
    name: 'Lead scoring model update',
    status: 'idle',
    color: '#3b82f6',
    category: 'Automation',
    isActive: false,
    hasUnreviewedTasks: false,
    createdAt: new Date(2026, 1, 4)
  },
  {
    id: '10',
    name: 'Competitor analysis - Feb',
    status: 'complete',
    color: '#ef4444',
    category: 'Research',
    isActive: false,
    hasUnreviewedTasks: true,
    createdAt: new Date(2026, 1, 3)
  },
  // Additional sessions to simulate hundreds
  ...Array.from({ length: 30 }, (_, i) => ({
    id: `${11 + i}`,
    name: `Session ${11 + i}: Marketing task`,
    status: (i % 3 === 0 ? 'complete' : i % 2 === 0 ? 'idle' : 'working') as 'working' | 'idle' | 'complete',
    color: ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4'][i % 6],
    category: ['Campaign Planning', 'Analytics', 'Automation', 'Email Marketing', 'Budget', 'Social Media', 'Research'][i % 7],
    isActive: false,
    hasUnreviewedTasks: i % 5 === 0,
    createdAt: new Date(2026, 0, 28 - i)
  }))
];

export const sessionCategories = [
  'Campaign Planning',
  'Analytics',
  'Automation',
  'Email Marketing',
  'Budget',
  'Social Media',
  'Conversion',
  'Research'
];

export const mockNotifications: Notification[] = [
  {
    id: '1',
    title: 'Campaign approval needed',
    description: 'Q3 Product Launch email campaign is ready for final review',
    timestamp: new Date(2026, 1, 15, 10, 30),
    isRead: false,
    actionRequired: true,
    type: 'warning'
  },
  {
    id: '2',
    title: 'Budget threshold alert',
    description: 'Google Ads campaign has spent 90% of allocated budget',
    timestamp: new Date(2026, 1, 15, 9, 15),
    isRead: false,
    actionRequired: true,
    type: 'error'
  },
  {
    id: '3',
    title: 'Workflow completed',
    description: 'Weekly Performance Digest has been generated and sent',
    timestamp: new Date(2026, 1, 15, 8, 0),
    isRead: false,
    actionRequired: false,
    type: 'success'
  },
  {
    id: '4',
    title: 'Integration sync issue',
    description: 'Salesforce integration failed to sync. Retrying in 30 minutes',
    timestamp: new Date(2026, 1, 14, 15, 30),
    isRead: true,
    actionRequired: true,
    type: 'error'
  },
  {
    id: '5',
    title: 'New AI insights available',
    description: 'KEN-E has identified 3 optimization opportunities for your campaigns',
    timestamp: new Date(2026, 1, 14, 14, 20),
    isRead: true,
    actionRequired: false,
    type: 'info'
  },
  {
    id: '6',
    title: 'Campaign performance milestone',
    description: 'LinkedIn campaign reached 10,000 impressions',
    timestamp: new Date(2026, 1, 14, 11, 45),
    isRead: true,
    actionRequired: false,
    type: 'success'
  },
  {
    id: '7',
    title: 'Action required: Update billing',
    description: 'Your payment method expires in 7 days',
    timestamp: new Date(2026, 1, 13, 16, 0),
    isRead: false,
    actionRequired: true,
    type: 'warning'
  },
  {
    id: '8',
    title: 'Session results ready',
    description: 'Email subject line testing analysis is complete',
    timestamp: new Date(2026, 1, 13, 12, 30),
    isRead: false,
    actionRequired: false,
    type: 'info'
  }
];

export interface Campaign {
  id: string;
  name: string;
  status: 'active' | 'complete';
  color: string;
  activityCount: number;
  description: string;
}

export const mockActivities: MarketingActivity[] = [
  {
    id: '1',
    title: 'Product Launch Email Campaign',
    channel: 'email',
    startDate: new Date(2026, 1, 20),
    endDate: new Date(2026, 1, 20),
    status: 'scheduled',
    campaignId: 'camp-1'
  },
  {
    id: '2',
    title: 'Google Ads - Brand Awareness',
    channel: 'paid-search',
    startDate: new Date(2026, 1, 15),
    endDate: new Date(2026, 1, 28),
    status: 'active',
    campaignId: 'camp-3'
  },
  {
    id: '3',
    title: 'Social Media Campaign - LinkedIn',
    channel: 'social',
    startDate: new Date(2026, 1, 18),
    endDate: new Date(2026, 1, 25),
    status: 'scheduled',
    campaignId: 'camp-2'
  },
  {
    id: '4',
    title: 'Blog Post Series',
    channel: 'content',
    startDate: new Date(2026, 1, 14),
    endDate: new Date(2026, 1, 21),
    status: 'active',
    campaignId: 'camp-3'
  },
  {
    id: '5',
    title: 'Webinar: Product Demo',
    channel: 'events',
    startDate: new Date(2026, 1, 27),
    endDate: new Date(2026, 1, 27),
    status: 'scheduled',
    campaignId: 'camp-1'
  },
  {
    id: '6',
    title: 'SEO Audit & Optimization',
    channel: 'seo',
    startDate: new Date(2026, 1, 16),
    endDate: new Date(2026, 1, 22),
    status: 'active'
  },
  {
    id: '7',
    title: 'Retargeting Ad Set',
    channel: 'paid-search',
    startDate: new Date(2026, 1, 10),
    endDate: new Date(2026, 1, 17),
    status: 'completed',
    campaignId: 'camp-2'
  },
  {
    id: '8',
    title: 'Newsletter - Feb Edition',
    channel: 'email',
    startDate: new Date(2026, 1, 1),
    endDate: new Date(2026, 1, 1),
    status: 'completed'
  }
];

export const mockCampaigns: Campaign[] = [
  {
    id: 'camp-1',
    name: 'New product launch campaign',
    status: 'active',
    color: '#8b5cf6',
    activityCount: 2,
    description: 'Full-funnel launch for the new product line targeting enterprise buyers.'
  },
  {
    id: 'camp-2',
    name: 'New customer acquisition campaign',
    status: 'active',
    color: '#3b82f6',
    activityCount: 2,
    description: 'Multi-channel acquisition campaign focused on expanding into new verticals.'
  },
  {
    id: 'camp-3',
    name: 'Evergreen brand awareness',
    status: 'active',
    color: '#10b981',
    activityCount: 2,
    description: 'Always-on brand visibility across paid and organic channels.'
  },
  {
    id: 'camp-4',
    name: 'Holiday season promo 2025',
    status: 'complete',
    color: '#f59e0b',
    activityCount: 5,
    description: 'Q4 2025 holiday promotion campaign across all channels.'
  },
  {
    id: 'camp-5',
    name: 'Q1 webinar series',
    status: 'complete',
    color: '#ef4444',
    activityCount: 3,
    description: 'Educational webinar series for Q1 thought leadership positioning.'
  }
];

export const mockWorkflows: Workflow[] = [
  {
    id: '1',
    name: 'Weekly Performance Digest',
    type: 'dashboard',
    schedule: 'Every Monday 9:00 AM',
    lastRun: new Date(2026, 1, 10, 9, 0),
    nextRun: new Date(2026, 1, 17, 9, 0),
    status: 'success',
    description: 'Automated weekly report with key marketing metrics and channel breakdowns',
    extensionId: 'dashboard-creator',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['reporting', 'weekly'],
    createdBy: 'Sarah Chen',
    isActive: true,
  },
  {
    id: '2',
    name: 'Monthly Executive Dashboard',
    type: 'dashboard',
    schedule: '1st of every month',
    lastRun: new Date(2026, 1, 1, 8, 0),
    nextRun: new Date(2026, 2, 1, 8, 0),
    status: 'success',
    description: 'Executive summary with forecasts, ROI analysis, and strategic recommendations',
    extensionId: 'dashboard-creator',
    goal: 'Revenue Growth',
    campaignId: 'camp-1',
    tags: ['reporting', 'executive'],
    createdBy: 'Marcus Johnson',
    isActive: true,
  },
  {
    id: '3',
    name: 'Campaign ROI Tracker',
    type: 'dashboard',
    schedule: 'Every Friday 5:00 PM',
    lastRun: new Date(2026, 1, 7, 17, 0),
    nextRun: new Date(2026, 1, 14, 17, 0),
    status: 'success',
    description: 'Real-time ROI tracking across all active campaigns with spend vs. revenue',
    extensionId: 'dashboard-creator',
    goal: 'Revenue Growth',
    campaignId: 'camp-2',
    tags: ['roi', 'tracking'],
    createdBy: 'David Kim',
    isActive: true,
  },
  {
    id: 'd-4',
    name: 'Channel Mix Overview',
    type: 'dashboard',
    schedule: 'Daily at 6:00 AM',
    lastRun: new Date(2026, 3, 21, 6, 0),
    nextRun: new Date(2026, 3, 22, 6, 0),
    status: 'success',
    description: 'Daily snapshot of traffic and conversion distribution across all marketing channels',
    extensionId: 'dashboard-creator',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['channels', 'daily'],
    createdBy: 'Priya Patel',
    isActive: true,
  },
  {
    id: 'd-5',
    name: 'Lead Funnel Health',
    type: 'dashboard',
    schedule: 'Every Wednesday 8:00 AM',
    lastRun: new Date(2026, 3, 16, 8, 0),
    nextRun: new Date(2026, 3, 23, 8, 0),
    status: 'success',
    description: 'Tracks MQL-to-SQL conversion rates, pipeline velocity, and funnel drop-off points',
    goal: 'Lead Generation',
    campaignId: 'camp-2',
    tags: ['leads', 'funnel'],
    createdBy: 'Sarah Chen',
    isActive: true,
  },
  {
    id: 'd-6',
    name: 'Social Engagement Pulse',
    type: 'dashboard',
    schedule: 'Daily at 9:00 AM',
    lastRun: new Date(2026, 3, 21, 9, 0),
    nextRun: new Date(2026, 3, 22, 9, 0),
    status: 'success',
    description: 'Aggregates engagement metrics across Instagram, LinkedIn, Twitter, and TikTok',
    extensionId: 'dashboard-creator',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['social', 'engagement'],
    createdBy: 'Priya Patel',
    isActive: true,
  },
  {
    id: 'd-7',
    name: 'Ad Spend Efficiency Report',
    type: 'dashboard',
    schedule: 'Every Monday 7:00 AM',
    lastRun: new Date(2026, 3, 14, 7, 0),
    nextRun: new Date(2026, 3, 21, 7, 0),
    status: 'failed',
    description: 'Compares cost-per-click, cost-per-acquisition, and ROAS across paid channels',
    goal: 'Cost Efficiency',
    campaignId: 'camp-1',
    tags: ['ads', 'efficiency'],
    createdBy: 'Marcus Johnson',
    isActive: true,
  },
  {
    id: 'd-8',
    name: 'Customer Retention Scorecard',
    type: 'dashboard',
    schedule: 'Bi-weekly on Friday',
    lastRun: new Date(2026, 3, 11, 16, 0),
    nextRun: new Date(2026, 3, 25, 16, 0),
    status: 'success',
    description: 'Monitors churn rates, NPS trends, and retention campaign effectiveness',
    goal: 'Customer Retention',
    campaignId: 'camp-4',
    tags: ['retention', 'churn'],
    createdBy: 'Elena Rodriguez',
    isActive: false,
  },
  {
    id: '4',
    name: 'Optimize blog post SEO',
    type: 'freeform',
    schedule: 'On demand',
    lastRun: new Date(2026, 1, 12, 14, 30),
    status: 'success',
    description: 'Analyze and optimize SEO elements of a blog post including meta tags, keywords, and readability',
    goal: 'Lead Generation',
    campaignId: 'camp-3',
    tags: ['seo', 'content'],
    createdBy: 'Elena Rodriguez',
    isActive: true,
  },
  {
    id: '5',
    name: 'Generate social posts from YouTube video',
    type: 'freeform',
    schedule: 'On demand',
    lastRun: new Date(2026, 1, 13, 10, 15),
    status: 'running',
    description: 'Extract key moments from a YouTube video and generate platform-specific social media posts',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['social', 'content', 'video'],
    createdBy: 'Priya Patel',
    isActive: true,
  },
  {
    id: '6',
    name: 'Lead Scoring Automation',
    type: 'freeform',
    schedule: 'Real-time',
    lastRun: new Date(2026, 1, 13, 11, 0),
    status: 'running',
    description: 'Automatically score and route leads based on engagement signals and firmographic data',
    goal: 'Lead Generation',
    campaignId: 'camp-2',
    tags: ['leads', 'scoring', 'automation'],
    createdBy: 'David Kim',
    isActive: true,
  },
  {
    id: '7',
    name: 'Campaign Budget Optimizer',
    type: 'freeform',
    schedule: 'Daily at 2:00 AM',
    lastRun: new Date(2026, 1, 13, 2, 0),
    status: 'success',
    description: 'Optimize budget allocation across channels based on real-time performance data',
    extensionId: 'performance-optimizer',
    goal: 'Revenue Growth',
    campaignId: 'camp-1',
    tags: ['budget', 'optimization'],
    createdBy: 'Marcus Johnson',
    isActive: true,
  },
  {
    id: '8',
    name: 'Repurpose webinar into content assets',
    type: 'freeform',
    schedule: 'On demand',
    lastRun: new Date(2026, 1, 8, 16, 0),
    status: 'success',
    description: 'Transform a webinar recording into blog posts, email sequences, and social snippets',
    goal: 'Lead Generation',
    campaignId: 'camp-5',
    tags: ['content', 'webinar', 'repurpose'],
    createdBy: 'Elena Rodriguez',
    isActive: true,
  },
  // Additional freeform automations for pagination demo
  {
    id: '9',
    name: 'Daily Ad Spend Monitor',
    type: 'freeform',
    schedule: 'Daily at 8:00 AM',
    lastRun: new Date(2026, 1, 13, 8, 0),
    status: 'success',
    description: 'Monitor daily ad spend across Google, Meta, and LinkedIn. Alert if spend exceeds threshold.',
    goal: 'Cost Efficiency',
    campaignId: 'camp-1',
    tags: ['monitoring', 'budget', 'alerts'],
    createdBy: 'Sarah Chen',
    isActive: true,
  },
  {
    id: '10',
    name: 'Competitor Content Tracker',
    type: 'freeform',
    schedule: 'Weekly on Wednesday',
    lastRun: new Date(2026, 1, 12, 6, 0),
    status: 'success',
    description: 'Scrape and analyze competitor blog and social content to identify trending topics.',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['competitor', 'research', 'content'],
    createdBy: 'Priya Patel',
    isActive: true,
  },
  {
    id: '11',
    name: 'Email List Hygiene Cleanup',
    type: 'freeform',
    schedule: 'Monthly on 15th',
    lastRun: new Date(2026, 0, 15, 3, 0),
    status: 'success',
    description: 'Remove bounced emails, unsubscribes, and inactive subscribers from mailing lists.',
    goal: 'Cost Efficiency',
    tags: ['email', 'hygiene', 'cleanup'],
    createdBy: 'Marcus Johnson',
    isActive: true,
  },
  {
    id: '12',
    name: 'UTM Parameter Validator',
    type: 'freeform',
    schedule: 'On demand',
    lastRun: new Date(2026, 1, 10, 11, 30),
    status: 'failed',
    description: 'Validate UTM parameters across all active campaign URLs and flag inconsistencies.',
    goal: 'Lead Generation',
    campaignId: 'camp-2',
    tags: ['tracking', 'utm', 'quality'],
    createdBy: 'David Kim',
    isActive: true,
  },
  {
    id: '13',
    name: 'Social Listening Digest',
    type: 'freeform',
    schedule: 'Daily at 7:00 AM',
    lastRun: new Date(2026, 1, 13, 7, 0),
    status: 'success',
    description: 'Aggregate brand mentions, sentiment analysis, and trending conversations across social platforms.',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['social', 'listening', 'sentiment'],
    createdBy: 'Priya Patel',
    isActive: true,
  },
  {
    id: '14',
    name: 'Landing Page A/B Test Monitor',
    type: 'freeform',
    schedule: 'Every 6 hours',
    lastRun: new Date(2026, 1, 13, 12, 0),
    status: 'running',
    description: 'Track conversion rates across active A/B test variants and alert when statistical significance is reached.',
    goal: 'Customer Retention',
    campaignId: 'camp-1',
    tags: ['testing', 'conversion', 'landing-page'],
    createdBy: 'Sarah Chen',
    isActive: true,
  },
  {
    id: '15',
    name: 'Weekly Newsletter Builder',
    type: 'freeform',
    schedule: 'Every Thursday 2:00 PM',
    lastRun: new Date(2026, 1, 13, 14, 0),
    status: 'success',
    description: 'Auto-curate top-performing content into a weekly newsletter draft for review.',
    goal: 'Customer Retention',
    tags: ['email', 'newsletter', 'content'],
    createdBy: 'Elena Rodriguez',
    isActive: true,
  },
  {
    id: '16',
    name: 'Abandoned Cart Recovery Trigger',
    type: 'freeform',
    schedule: 'Real-time',
    lastRun: new Date(2026, 1, 13, 13, 45),
    status: 'running',
    description: 'Trigger personalized recovery emails when a user abandons their cart after 30 minutes.',
    goal: 'Revenue Growth',
    campaignId: 'camp-4',
    tags: ['email', 'ecommerce', 'recovery'],
    createdBy: 'Marcus Johnson',
    isActive: true,
  },
  {
    id: '17',
    name: 'Keyword Rank Tracker',
    type: 'freeform',
    schedule: 'Daily at 5:00 AM',
    lastRun: new Date(2026, 1, 13, 5, 0),
    status: 'success',
    description: 'Track daily keyword rankings for target SEO terms and flag significant position changes.',
    extensionId: 'performance-optimizer',
    goal: 'Lead Generation',
    campaignId: 'camp-3',
    tags: ['seo', 'tracking', 'keywords'],
    createdBy: 'David Kim',
    isActive: true,
  },
  {
    id: '18',
    name: 'Influencer Outreach Scheduler',
    type: 'freeform',
    schedule: 'On demand',
    lastRun: new Date(2026, 1, 5, 10, 0),
    status: 'success',
    description: 'Queue and schedule personalized outreach emails to influencer prospects.',
    goal: 'Brand Awareness',
    campaignId: 'camp-3',
    tags: ['influencer', 'outreach', 'social'],
    createdBy: 'Priya Patel',
    isActive: false,
  },
  {
    id: '19',
    name: 'CRM Lead Sync',
    type: 'freeform',
    schedule: 'Every 30 minutes',
    lastRun: new Date(2026, 1, 13, 13, 30),
    status: 'failed',
    description: 'Sync new marketing qualified leads from HubSpot to Salesforce with enrichment data.',
    goal: 'Lead Generation',
    campaignId: 'camp-2',
    tags: ['crm', 'sync', 'leads'],
    createdBy: 'Sarah Chen',
    isActive: true,
  },
  {
    id: '20',
    name: 'Cross-Channel Attribution Report',
    type: 'freeform',
    schedule: 'Weekly on Monday',
    lastRun: new Date(2026, 1, 10, 9, 0),
    status: 'success',
    description: 'Generate multi-touch attribution reports across all marketing channels.',
    goal: 'Revenue Growth',
    campaignId: 'camp-1',
    tags: ['attribution', 'reporting', 'analytics'],
    createdBy: 'David Kim',
    isActive: true,
  },
  {
    id: '21',
    name: 'Event Registration Reminder',
    type: 'freeform',
    schedule: 'Daily at 10:00 AM',
    lastRun: new Date(2026, 1, 13, 10, 0),
    status: 'success',
    description: 'Send reminder emails to registered attendees 7 days, 1 day, and 1 hour before events.',
    goal: 'Customer Retention',
    campaignId: 'camp-5',
    tags: ['events', 'email', 'reminders'],
    createdBy: 'Elena Rodriguez',
    isActive: true,
  },
  {
    id: '22',
    name: 'Dynamic Pricing Adjuster',
    type: 'freeform',
    schedule: 'Every 4 hours',
    lastRun: new Date(2026, 1, 13, 12, 0),
    status: 'success',
    description: 'Adjust promotional pricing based on inventory levels, competitor pricing, and demand signals.',
    goal: 'Revenue Growth',
    campaignId: 'camp-4',
    tags: ['pricing', 'ecommerce', 'automation'],
    createdBy: 'Marcus Johnson',
    isActive: false,
  },
  {
    id: '23',
    name: 'Brand Sentiment Alert',
    type: 'freeform',
    schedule: 'Real-time',
    lastRun: new Date(2026, 1, 13, 14, 20),
    status: 'running',
    description: 'Monitor brand sentiment in real-time and alert the team when negative sentiment spikes.',
    goal: 'Brand Awareness',
    tags: ['sentiment', 'alerts', 'social'],
    createdBy: 'Priya Patel',
    isActive: true,
  },
  {
    id: '24',
    name: 'Content Performance Scorer',
    type: 'freeform',
    schedule: 'Weekly on Friday',
    lastRun: new Date(2026, 1, 7, 17, 0),
    status: 'success',
    description: 'Score all published content based on engagement, SEO ranking, and conversion contribution.',
    extensionId: 'performance-optimizer',
    goal: 'Lead Generation',
    campaignId: 'camp-3',
    tags: ['content', 'scoring', 'analytics'],
    createdBy: 'Elena Rodriguez',
    isActive: true,
  },
  {
    id: '25',
    name: 'Retargeting Audience Builder',
    type: 'freeform',
    schedule: 'Daily at 1:00 AM',
    lastRun: new Date(2026, 1, 13, 1, 0),
    status: 'success',
    description: 'Build and refresh retargeting audiences based on website behavior and engagement signals.',
    goal: 'Customer Retention',
    campaignId: 'camp-2',
    tags: ['retargeting', 'audience', 'ads'],
    createdBy: 'Sarah Chen',
    isActive: true,
  },
  {
    id: '26',
    name: 'Invoice & Billing Reconciler',
    type: 'freeform',
    schedule: 'Monthly on 1st',
    lastRun: new Date(2026, 1, 1, 4, 0),
    status: 'success',
    description: 'Reconcile ad platform invoices against internal budget records and flag discrepancies.',
    goal: 'Cost Efficiency',
    tags: ['billing', 'reconciliation', 'budget'],
    createdBy: 'Marcus Johnson',
    isActive: false,
  },
  {
    id: '27',
    name: 'Webinar Follow-Up Sequencer',
    type: 'freeform',
    schedule: 'On demand',
    lastRun: new Date(2026, 1, 9, 9, 0),
    status: 'success',
    description: 'Trigger post-webinar email sequences segmented by attendee engagement level.',
    goal: 'Lead Generation',
    campaignId: 'camp-5',
    tags: ['webinar', 'email', 'follow-up'],
    createdBy: 'Elena Rodriguez',
    isActive: true,
  },
  {
    id: '28',
    name: 'Ad Creative Fatigue Detector',
    type: 'freeform',
    schedule: 'Daily at 6:00 AM',
    lastRun: new Date(2026, 1, 13, 6, 0),
    status: 'success',
    description: 'Detect declining CTR trends on ad creatives and recommend refresh or rotation.',
    extensionId: 'performance-optimizer',
    goal: 'Cost Efficiency',
    campaignId: 'camp-1',
    tags: ['ads', 'creative', 'optimization'],
    createdBy: 'David Kim',
    isActive: true,
  },
];

export const mockMetrics: PerformanceMetric[] = [
  {
    id: '1',
    name: 'Total Conversions',
    value: 2847,
    target: 3000,
    change: 12.5,
    trend: [2100, 2300, 2500, 2650, 2847],
    unit: 'conversions'
  },
  {
    id: '2',
    name: 'Cost Per Acquisition',
    value: 48.32,
    target: 45,
    change: -8.2,
    trend: [58, 55, 52, 50, 48.32],
    unit: 'USD'
  },
  {
    id: '3',
    name: 'Email Open Rate',
    value: 28.4,
    target: 30,
    change: 3.1,
    trend: [25, 26, 27, 27.5, 28.4],
    unit: '%'
  },
  {
    id: '4',
    name: 'Social Engagement',
    value: 15234,
    target: 16000,
    change: 22.8,
    trend: [10000, 11500, 13000, 14200, 15234],
    unit: 'engagements'
  }
];

export const mockRecommendations: Recommendation[] = [
  {
    id: '1',
    title: 'Increase LinkedIn ad budget by 25%',
    description: 'Current LinkedIn campaigns showing 2.3x higher conversion rate than other channels. Recommend reallocating budget from underperforming Facebook ads.',
    impact: 'high',
    category: 'Budget Optimization'
  },
  {
    id: '2',
    title: 'Update email send times',
    description: 'Analysis shows 18% higher open rates when emails sent between 10-11 AM. Current schedule is 8 AM.',
    impact: 'medium',
    category: 'Email Marketing'
  },
  {
    id: '3',
    title: 'A/B test new landing page variant',
    description: 'AI-generated landing page variant predicted to increase conversion rate by 12-15% based on industry benchmarks.',
    impact: 'high',
    category: 'Conversion Optimization'
  }
];

// ─── Analysis Snapshots (current + 11 historical months) ───

const historicalRecommendations: Record<number, Recommendation[]> = {
  0: [ // Jan 2026
    { id: 'r-jan-1', title: 'Consolidate underperforming Facebook ad sets', description: 'Three ad sets have overlapping audiences. Merging could reduce CPA by 10-15%.', impact: 'high', category: 'Budget Optimization' },
    { id: 'r-jan-2', title: 'Introduce referral incentive program', description: 'Competitor analysis shows referral programs driving 8% of new customer acquisition in similar companies.', impact: 'medium', category: 'Customer Acquisition' },
  ],
  1: [ // Dec 2025
    { id: 'r-dec-1', title: 'Extend holiday campaign by 5 days', description: 'Post-holiday purchase intent remains high through Jan 5. Extending could capture an additional 400 conversions.', impact: 'high', category: 'Campaign Planning' },
    { id: 'r-dec-2', title: 'Reduce paid search spend on branded terms', description: 'Branded search CTR is 85% organic. Shift $2K/mo to non-brand terms.', impact: 'medium', category: 'Budget Optimization' },
    { id: 'r-dec-3', title: 'Refresh stale email automations', description: 'Welcome series last updated 6 months ago. Open rates declined 15% since last refresh.', impact: 'medium', category: 'Email Marketing' },
  ],
  2: [ // Nov 2025
    { id: 'r-nov-1', title: 'Pre-load holiday creatives across channels', description: 'Early creative deployment correlates with 20% higher impression share during peak days.', impact: 'high', category: 'Campaign Planning' },
    { id: 'r-nov-2', title: 'Segment email list by engagement tier', description: 'Sending to inactive subscribers is dragging down overall open rate by 4 percentage points.', impact: 'high', category: 'Email Marketing' },
  ],
  3: [ // Oct 2025
    { id: 'r-oct-1', title: 'Launch retargeting campaign for blog readers', description: 'Blog visitors show 3x higher conversion potential but are not currently retargeted.', impact: 'high', category: 'Conversion Optimization' },
    { id: 'r-oct-2', title: 'Test short-form video ads on Instagram Reels', description: 'Reels engagement rate is 2.5x higher than static posts for similar brands.', impact: 'medium', category: 'Social Media' },
    { id: 'r-oct-3', title: 'Update meta descriptions for top 20 pages', description: 'SEO audit shows outdated meta descriptions reducing organic CTR by ~12%.', impact: 'low', category: 'SEO' },
  ],
  4: [ // Sep 2025
    { id: 'r-sep-1', title: 'Reallocate Q4 budget toward LinkedIn', description: 'LinkedIn CPL decreased 18% this quarter while conversion quality improved.', impact: 'high', category: 'Budget Optimization' },
    { id: 'r-sep-2', title: 'Automate lead nurture sequence for MQLs', description: 'MQL-to-SQL conversion takes 14 days on average. Automated nurture could reduce this to 9 days.', impact: 'medium', category: 'Automation' },
  ],
  5: [ // Aug 2025
    { id: 'r-aug-1', title: 'Increase content publishing frequency', description: 'Competitors publish 3x more blog content monthly. Increasing cadence could improve organic traffic by 25%.', impact: 'high', category: 'Content Marketing' },
    { id: 'r-aug-2', title: 'Fix mobile landing page load times', description: 'Mobile bounce rate is 62% vs 38% desktop. Core Web Vitals show LCP of 4.2s on mobile.', impact: 'high', category: 'Conversion Optimization' },
    { id: 'r-aug-3', title: 'Run win-back campaign for churned subscribers', description: '2,400 subscribers became inactive in the last 90 days. Win-back emails typically recover 8-12%.', impact: 'medium', category: 'Email Marketing' },
  ],
  6: [ // Jul 2025
    { id: 'r-jul-1', title: 'Pause low-performing display campaigns', description: 'Two display campaigns have CPA 3x above average with no improvement trend.', impact: 'medium', category: 'Budget Optimization' },
    { id: 'r-jul-2', title: 'Implement UTM tracking consistency', description: 'Inconsistent UTM parameters causing 15% of conversions to be unattributed.', impact: 'high', category: 'Analytics' },
  ],
  7: [ // Jun 2025
    { id: 'r-jun-1', title: 'Test personalized subject lines', description: 'Personalized subject lines show 22% higher open rates in industry benchmarks.', impact: 'medium', category: 'Email Marketing' },
    { id: 'r-jun-2', title: 'Expand into TikTok advertising', description: 'Target audience (25-34) shows 40% higher engagement on TikTok than Instagram.', impact: 'high', category: 'Social Media' },
    { id: 'r-jun-3', title: 'Create gated content for lead capture', description: 'Blog traffic is high but lead capture rate is only 1.2%. Gated assets could improve to 4-6%.', impact: 'high', category: 'Content Marketing' },
  ],
  8: [ // May 2025
    { id: 'r-may-1', title: 'Reduce email send frequency for low-engagement segment', description: 'Over-mailing correlates with 30% higher unsubscribe rate in bottom engagement tier.', impact: 'medium', category: 'Email Marketing' },
    { id: 'r-may-2', title: 'Implement cross-channel attribution model', description: 'Last-click attribution is undervaluing social touchpoints by approximately 35%.', impact: 'high', category: 'Analytics' },
  ],
  9: [ // Apr 2025
    { id: 'r-apr-1', title: 'Launch customer testimonial campaign', description: 'Pages with testimonials show 2.1x higher conversion rate. Currently only 3 of 12 landing pages have them.', impact: 'high', category: 'Conversion Optimization' },
    { id: 'r-apr-2', title: 'Optimize Google Ads bid strategy', description: 'Switching from manual CPC to target CPA bidding predicted to reduce waste by 20%.', impact: 'high', category: 'Budget Optimization' },
    { id: 'r-apr-3', title: 'Improve social response time', description: 'Average response time is 4.5 hours. Reducing to under 1 hour could improve sentiment score by 15%.', impact: 'low', category: 'Social Media' },
  ],
  10: [ // Mar 2025
    { id: 'r-mar-1', title: 'Set up automated reporting pipeline', description: 'Manual reporting takes 6 hours/week. Automation would free up resources for strategic work.', impact: 'medium', category: 'Automation' },
    { id: 'r-mar-2', title: 'Audit and refresh underperforming landing pages', description: '4 landing pages have conversion rates below 1%. Redesign could bring them to the 3% benchmark.', impact: 'high', category: 'Conversion Optimization' },
  ],
};

function generateAnalysisSnapshots(): AnalysisSnapshot[] {
  // Base values for Feb 2026 (current, index -1 conceptually)
  const baseConversions = 2847;
  const baseCPA = 48.32;
  const baseOpenRate = 28.4;
  const baseEngagement = 15234;

  const snapshots: AnalysisSnapshot[] = [];

  // Current analysis - Feb 14, 2026
  snapshots.push({
    id: 'analysis-current',
    completedAt: new Date(2026, 1, 14, 9, 0),
    metrics: mockMetrics,
    recommendations: mockRecommendations,
  });

  // 11 historical months (Jan 2026 → Mar 2025)
  for (let i = 0; i < 11; i++) {
    const monthsBack = i + 1;
    const date = new Date(2026, 1 - monthsBack, 14, 9, 0);
    const decay = 1 - (monthsBack * 0.06); // values get progressively worse going back
    const cpaInflation = 1 + (monthsBack * 0.07); // CPA gets worse (higher) going back

    const conversions = Math.round(baseConversions * decay);
    const cpa = parseFloat((baseCPA * cpaInflation).toFixed(2));
    const openRate = parseFloat((baseOpenRate * (1 - monthsBack * 0.03)).toFixed(1));
    const engagement = Math.round(baseEngagement * decay);

    const prevConversions = Math.round(baseConversions * (1 - ((monthsBack + 1) * 0.06)));
    const prevCPA = parseFloat((baseCPA * (1 + ((monthsBack + 1) * 0.07))).toFixed(2));
    const prevOpenRate = parseFloat((baseOpenRate * (1 - (monthsBack + 1) * 0.03)).toFixed(1));
    const prevEngagement = Math.round(baseEngagement * (1 - ((monthsBack + 1) * 0.06)));

    const convChange = prevConversions > 0 ? parseFloat((((conversions - prevConversions) / prevConversions) * 100).toFixed(1)) : 0;
    const cpaChange = prevCPA > 0 ? parseFloat((((cpa - prevCPA) / prevCPA) * 100).toFixed(1)) : 0;
    const openRateChange = prevOpenRate > 0 ? parseFloat((((openRate - prevOpenRate) / prevOpenRate) * 100).toFixed(1)) : 0;
    const engChange = prevEngagement > 0 ? parseFloat((((engagement - prevEngagement) / prevEngagement) * 100).toFixed(1)) : 0;

    snapshots.push({
      id: `analysis-${i}`,
      completedAt: date,
      metrics: [
        {
          id: '1',
          name: 'Total Conversions',
          value: conversions,
          target: 3000,
          change: convChange,
          trend: Array.from({ length: 5 }, (_, j) => Math.round(conversions * (0.85 + j * 0.04))),
          unit: 'conversions',
        },
        {
          id: '2',
          name: 'Cost Per Acquisition',
          value: cpa,
          target: 45,
          change: cpaChange,
          trend: Array.from({ length: 5 }, (_, j) => parseFloat((cpa * (1.1 - j * 0.025)).toFixed(2))),
          unit: 'USD',
        },
        {
          id: '3',
          name: 'Email Open Rate',
          value: Math.max(openRate, 12),
          target: 30,
          change: openRateChange,
          trend: Array.from({ length: 5 }, (_, j) => parseFloat((Math.max(openRate, 12) * (0.9 + j * 0.025)).toFixed(1))),
          unit: '%',
        },
        {
          id: '4',
          name: 'Social Engagement',
          value: engagement,
          target: 16000,
          change: engChange,
          trend: Array.from({ length: 5 }, (_, j) => Math.round(engagement * (0.85 + j * 0.04))),
          unit: 'engagements',
        },
      ],
      recommendations: historicalRecommendations[i] || [
        { id: `r-gen-${i}-1`, title: 'Review and optimize channel mix', description: 'Quarterly channel performance review suggests rebalancing budget allocation.', impact: 'medium' as const, category: 'Budget Optimization' },
      ],
    });
  }

  return snapshots;
}

export const mockAnalysisHistory: AnalysisSnapshot[] = generateAnalysisSnapshots();

export const NEXT_ANALYSIS_DATE = new Date(2026, 1, 21, 9, 0);

export const mockIntegrations: Integration[] = [
  {
    id: '1',
    name: 'Google Ads',
    status: 'connected',
    icon: '🔍',
    lastSync: new Date(2026, 1, 13, 10, 30)
  },
  {
    id: '2',
    name: 'HubSpot',
    status: 'connected',
    icon: '🧡',
    lastSync: new Date(2026, 1, 13, 9, 15)
  },
  {
    id: '3',
    name: 'Meta Ads',
    status: 'connected',
    icon: '📘',
    lastSync: new Date(2026, 1, 13, 11, 0)
  },
  {
    id: '4',
    name: 'Salesforce',
    status: 'error',
    icon: '☁️',
    lastSync: new Date(2026, 1, 12, 15, 30)
  },
  {
    id: '5',
    name: 'LinkedIn Ads',
    status: 'connected',
    icon: '💼',
    lastSync: new Date(2026, 1, 13, 10, 45)
  },
  {
    id: '6',
    name: 'Mailchimp',
    status: 'disconnected',
    icon: '📧'
  }
];

export const channelColors = {
  email: '#f59e0b',
  'paid-search': '#3b82f6',
  social: '#8b5cf6',
  content: '#10b981',
  events: '#ef4444',
  seo: '#06b6d4'
};

// ─── Agent, Skill, and Tool types for Workflows ───

export interface AgentTool {
  id: string;
  name: string;
  description: string;
  category: 'native' | 'integration' | 'skill';
  icon?: string;
  connected?: boolean; // for integration tools
  skillId?: string; // for skill-type tools
}

export interface Agent {
  id: string;
  name: string;
  model: string;
  instructions: string;
  tools: AgentTool[];
  createdAt: Date;
  lastUsed?: Date;
  automationsGenerated: number;
  status: 'active' | 'inactive';
  extensionId?: string;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  category: string;
  uses: number;
  usedByAgents: string[];
  extensionId?: string;
}

export const availableModels = [
  { id: 'fastest', name: 'Fastest', description: 'Optimized for speed and high-volume tasks', icon: '⚡' },
  { id: 'goldilocks', name: 'Goldilocks', description: 'Balanced speed, cost, and intelligence', icon: '✨', badge: 'Recommended' },
  { id: 'smartest', name: 'Smartest', description: 'Maximum reasoning for complex tasks', icon: '🧠' },
];

export const availableTools: AgentTool[] = [
  // Native tools
  { id: 'tool-viz', name: 'Create Data Visualization', description: 'Generate charts, graphs, and interactive dashboards from marketing data', category: 'native' },
  { id: 'tool-report', name: 'Generate Report', description: 'Compile comprehensive marketing performance reports with insights', category: 'native' },
  { id: 'tool-schedule', name: 'Schedule Post', description: 'Schedule social media or blog posts to publishing queues', category: 'native' },
  { id: 'tool-email-compose', name: 'Compose Email', description: 'Draft marketing emails with subject line suggestions and body copy', category: 'native' },
  { id: 'tool-ab-test', name: 'A/B Test Creator', description: 'Set up and manage A/B tests for landing pages, emails, and ads', category: 'native' },
  { id: 'tool-audience', name: 'Audience Segmenter', description: 'Create and refine audience segments based on behavioral and demographic data', category: 'native' },
  { id: 'tool-budget', name: 'Budget Allocator', description: 'Optimize and redistribute campaign budgets based on performance signals', category: 'native' },
  // Integration tools
  { id: 'tool-ga', name: 'Query Google Analytics', description: 'Pull traffic, conversion, and audience data from Google Analytics', category: 'integration', connected: true },
  { id: 'tool-gads', name: 'Google Ads Manager', description: 'Read and adjust Google Ads campaigns, bids, and budgets', category: 'integration', connected: true },
  { id: 'tool-hubspot', name: 'HubSpot CRM', description: 'Access contacts, deals, and marketing automation data from HubSpot', category: 'integration', connected: false },
  { id: 'tool-salesforce', name: 'Salesforce Query', description: 'Pull lead and opportunity data from Salesforce CRM', category: 'integration', connected: false },
  { id: 'tool-slack', name: 'Slack Notifications', description: 'Send messages and alerts to Slack channels', category: 'integration', connected: true },
  { id: 'tool-semrush', name: 'SEMrush SEO Data', description: 'Pull keyword rankings, backlink data, and competitor analysis', category: 'integration', connected: false },
  { id: 'tool-meta', name: 'Meta Ads Manager', description: 'Manage Facebook and Instagram ad campaigns and reporting', category: 'integration', connected: true },
  { id: 'tool-linkedin', name: 'LinkedIn Campaign Manager', description: 'Manage LinkedIn ad campaigns and access audience insights', category: 'integration', connected: false },
];

export const mockSkills: Skill[] = [
  { id: 'skill-1', name: 'Create Headline Image', description: 'Creates a headline image for a blog post that is aligned with brand standards, and requests proper approvals.', category: 'Content Creation', uses: 42, usedByAgents: ['agent-1', 'agent-3'] },
  { id: 'skill-2', name: 'Generate Social Hook', description: 'Searches for trending hooks by reviewing popular videos in my niche from the past week.', category: 'Social Media', uses: 28, usedByAgents: ['agent-2'] },
  { id: 'skill-3', name: 'SEO Keyword Research', description: 'Analyzes top-ranking content for target keywords and provides optimization recommendations.', category: 'SEO', uses: 35, usedByAgents: ['agent-1'], extensionId: 'performance-optimizer' },
  { id: 'skill-4', name: 'Competitor Analysis', description: 'Monitors competitor content strategy and identifies gaps in your content calendar.', category: 'Research', uses: 19, usedByAgents: [], extensionId: 'performance-optimizer' },
  { id: 'skill-5', name: 'Email Subject Line Tester', description: 'Generates and A/B tests email subject lines based on historical performance data.', category: 'Email Marketing', uses: 51, usedByAgents: ['agent-2', 'agent-3'] },
];

// Convert skills to AgentTool references
export const skillTools: AgentTool[] = mockSkills.map(s => ({
  id: `tool-${s.id}`,
  name: s.name,
  description: s.description,
  category: 'skill' as const,
  skillId: s.id,
}));

export const mockAgents: Agent[] = [
  {
    id: 'agent-1',
    name: 'Google Analytics Specialist',
    model: 'goldilocks',
    instructions: 'You are a content marketing strategist. Analyze performance data, identify content gaps, and generate comprehensive content calendars. Always align recommendations with brand voice guidelines and target audience personas.',
    tools: [
      availableTools[0], // Create Data Visualization
      availableTools[1], // Generate Report
      availableTools[7], // Google Analytics
      { id: 'tool-skill-1', name: 'Create Headline Image', description: 'Creates a headline image for a blog post', category: 'skill', skillId: 'skill-1' },
      { id: 'tool-skill-3', name: 'SEO Keyword Research', description: 'Analyzes top-ranking content for target keywords', category: 'skill', skillId: 'skill-3' },
    ],
    createdAt: new Date(2026, 0, 15),
    lastUsed: new Date(2026, 2, 17),
    automationsGenerated: 4,
    status: 'active',
  },
  {
    id: 'agent-2',
    name: 'Google Ads Specialist',
    model: 'goldilocks',
    instructions: 'You manage social media campaigns across all platforms. Monitor engagement metrics, suggest optimal posting times, create platform-specific content variations, and track competitor social strategies.',
    tools: [
      availableTools[2], // Schedule Post
      availableTools[13], // Meta Ads
      { id: 'tool-skill-2', name: 'Generate Social Hook', description: 'Searches for trending hooks', category: 'skill', skillId: 'skill-2' },
      { id: 'tool-skill-5', name: 'Email Subject Line Tester', description: 'Generates email subject lines', category: 'skill', skillId: 'skill-5' },
    ],
    createdAt: new Date(2026, 0, 22),
    lastUsed: new Date(2026, 2, 16),
    automationsGenerated: 2,
    status: 'active',
  },
  {
    id: 'agent-3',
    name: 'Meta Ads Specialist',
    model: 'smartest',
    instructions: 'You are a marketing performance analyst. Deep-dive into campaign metrics, identify trends and anomalies, produce executive-ready dashboards, and recommend budget reallocation based on ROI data.',
    tools: [
      availableTools[0], // Create Data Visualization
      availableTools[1], // Generate Report
      availableTools[6], // Budget Allocator
      availableTools[7], // Google Analytics
      availableTools[8], // Google Ads
    ],
    createdAt: new Date(2026, 1, 3),
    lastUsed: new Date(2026, 2, 18),
    automationsGenerated: 6,
    status: 'active',
    extensionId: 'performance-optimizer',
  },
  {
    id: 'agent-4',
    name: 'Content Specialist',
    model: 'fastest',
    instructions: 'You specialize in email marketing. Create email sequences, optimize deliverability, segment audiences, and run A/B tests on subject lines and content.',
    tools: [
      availableTools[3], // Compose Email
      availableTools[4], // A/B Test Creator
      availableTools[5], // Audience Segmenter
    ],
    createdAt: new Date(2026, 2, 1),
    lastUsed: undefined,
    automationsGenerated: 0,
    status: 'inactive',
  },
];

// ─── Organizations & Accounts ───

export const mockOrganizations: Organization[] = [
  {
    id: 'org-1',
    name: 'Costco',
    slug: 'costco',
    avatarColor: '#E53935',
  },
  {
    id: 'org-2',
    name: 'Bank of America',
    slug: 'bank-of-america',
    avatarColor: '#1565C0',
  },
];

export const mockAccounts: Account[] = [
  {
    id: 'acct-1',
    name: 'Appliances',
    organizationId: 'org-1',
    role: 'owner',
  },
  {
    id: 'acct-2',
    name: 'Groceries',
    organizationId: 'org-1',
    role: 'admin',
  },
  {
    id: 'acct-3',
    name: 'Retail Banking',
    organizationId: 'org-2',
    role: 'member',
  },
  {
    id: 'acct-4',
    name: 'Commercial Banking',
    organizationId: 'org-2',
    role: 'viewer',
  },
];