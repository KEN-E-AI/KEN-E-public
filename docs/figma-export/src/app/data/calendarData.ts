// ─── Campaign Calendar Data Model & Mock Data ───
// Aligned with Campaign Calendar UI Requirements Specification v1.0

// ─── Types ───

export type FunnelObjective = 'Problem Awareness' | 'Brand Awareness' | 'Consideration' | 'Conversion';

export type ActivityStatus =
  | 'Draft'
  | 'Awaiting Approval'
  | 'Approved'
  | 'Rejected'
  | 'Revision Requested'
  | 'Complete';

export type ActivityCategory = 'task' | 'promotion' | 'holiday' | 'event';

export type PromotionType = 'Discount' | 'Bundle' | 'Free Trial' | 'BOGO' | 'Flash Sale' | 'Seasonal' | 'Launch Offer';

export type HolidayType = 'Public' | 'Religious' | 'Cultural' | 'Observance' | 'Company';

export interface CalendarCampaign {
  campaign_id: string;
  objective: FunnelObjective;
  name: string;
}

export interface CalendarActivity {
  activity_id: string;
  name: string;
  /** Nullable — a task may not belong to any campaign. Objective is derived via getActivityObjective. */
  campaign_id: string | null;
  channel: string | null;
  platform: string | null;
  cost: number | null;
  launch_date: Date;
  launch_time_utc: string | null; // HH:mm format, e.g. "14:30"
  category: ActivityCategory;
  task_type: string | null; // e.g. Brand, Demand Gen, etc.
  tags: string[];
  owner: string | null;
  status: ActivityStatus;
  created_date: Date;
  created_by: string;
  last_updated_at: Date;
  last_updated_by: string;
  revision_comment?: string | null;

  // Promotion-specific fields
  product_service?: string | null;
  promotion_type?: PromotionType | null;
  discount_details?: string | null;
  end_date?: Date | null;
  promo_url?: string | null;
  region?: string | null;

  // Holiday-specific fields
  holiday_type?: HolidayType | null;
  recurring?: boolean;

  // Project membership. `null` / absent = orphan (standalone task).
  plan_id?: string | null;

  // Orphan-only. When true, the task has no due date and is not placed on the
  // calendar grid. It appears in the Unscheduled Tasks panel until the owner
  // schedules it, assigns it to a project, or deletes it.
  unscheduled?: boolean;

  // Task-level recurrence. When set and enabled, the task spawns virtual
  // occurrences on the calendar according to the schedule. Stored as
  // AutomationSchedule from automationDetailsData to share the scheduling UI.
  // Imported lazily (via `any`) here to avoid a circular import.
  schedule?: import('./automationDetailsData').AutomationSchedule | null;
}

export interface ChannelGuideline {
  channel: string;
}

export interface AllowedUser {
  email: string;
  name: string;
  avatar?: string;
}

// ─── Platform → Color Mapping ───
// Platforms sharing a channel use related hues.

export interface PlatformColor {
  platform: string;
  channel: string;
  color: string;
  textColor: string; // for contrast on the bar
}

export const platformColors: PlatformColor[] = [
  // Paid Search — oranges
  { platform: 'Google Ads', channel: 'Paid Search', color: '#E37400', textColor: '#FFFFFF' },
  { platform: 'Bing Ads', channel: 'Paid Search', color: '#F5A623', textColor: '#1E293B' },
  // Social — blues
  { platform: 'Facebook', channel: 'Social', color: '#1877F2', textColor: '#FFFFFF' },
  { platform: 'Instagram', channel: 'Social', color: '#5B8DEF', textColor: '#FFFFFF' },
  { platform: 'LinkedIn', channel: 'Social', color: '#0A66C2', textColor: '#FFFFFF' },
  // Email — greens
  { platform: 'MailChimp', channel: 'Email', color: '#10B981', textColor: '#FFFFFF' },
  { platform: 'SendGrid', channel: 'Email', color: '#6AD8CC', textColor: '#1E293B' },
  // Display — purples
  { platform: 'Google Display', channel: 'Display', color: '#7C3AED', textColor: '#FFFFFF' },
  { platform: 'Programmatic', channel: 'Display', color: '#A78BFA', textColor: '#1E293B' },
  // Content — teals
  { platform: 'WordPress', channel: 'Content', color: '#0E7490', textColor: '#FFFFFF' },
  { platform: 'Medium', channel: 'Content', color: '#67E8F9', textColor: '#1E293B' },
  // Events — reds
  { platform: 'Zoom', channel: 'Events', color: '#2D8CFF', textColor: '#FFFFFF' },
  { platform: 'Eventbrite', channel: 'Events', color: '#F05537', textColor: '#FFFFFF' },
];

// Neutral color for activities with no platform
export const neutralPlatformColor: PlatformColor = {
  platform: '',
  channel: '',
  color: '#94A3B8',
  textColor: '#FFFFFF',
};

export function getPlatformColor(platform: string | null): PlatformColor {
  if (!platform) return neutralPlatformColor;
  return platformColors.find(p => p.platform === platform) || neutralPlatformColor;
}

// ─── Status Badge Styling ───

export const statusStyles: Record<ActivityStatus, { bg: string; text: string; border: string }> = {
  'Draft': { bg: '#F1F5F9', text: '#475569', border: '#CBD5E1' },
  'Awaiting Approval': { bg: '#FEF3C7', text: '#92400E', border: '#FDE68A' },
  'Approved': { bg: '#D1FAE5', text: '#065F46', border: '#6EE7B7' },
  'Rejected': { bg: '#FEE2E2', text: '#991B1B', border: '#FCA5A5' },
  'Revision Requested': { bg: '#FFEDD5', text: '#9A3412', border: '#FDBA74' },
  'Complete': { bg: '#DBEAFE', text: '#1E40AF', border: '#93C5FD' },
};

// ─── Lookup Lists ───

export const channelGuidelines: ChannelGuideline[] = [
  { channel: 'Paid Search' },
  { channel: 'Social' },
  { channel: 'Email' },
  { channel: 'Display' },
  { channel: 'Content' },
  { channel: 'Events' },
];

export const allowedUsers: AllowedUser[] = [
  { email: 'sarah.chen@example.com', name: 'Sarah Chen' },
  { email: 'mike.johnson@example.com', name: 'Mike Johnson' },
  { email: 'priya.patel@example.com', name: 'Priya Patel' },
  { email: 'alex.rivera@example.com', name: 'Alex Rivera' },
  { email: 'jordan.lee@example.com', name: 'Jordan Lee' },
  { email: 'emma.thompson@example.com', name: 'Emma Thompson' },
];

export function getUserName(email: string | null): string {
  if (!email) return '';
  const user = allowedUsers.find(u => u.email === email);
  return user ? user.name : email;
}

// ─── Mock Campaigns ───

const GENERIC_CAMPAIGN_IDS: Record<FunnelObjective, string> = {
  'Problem Awareness': 'cc-gen-pa',
  'Brand Awareness': 'cc-gen-ba',
  'Consideration': 'cc-gen-c',
  'Conversion': 'cc-gen-cv',
};

export const calendarCampaigns: CalendarCampaign[] = [
  { campaign_id: 'cc-gen-pa', objective: 'Problem Awareness', name: 'General Problem Awareness' },
  { campaign_id: 'cc-gen-ba', objective: 'Brand Awareness', name: 'General Brand Awareness' },
  { campaign_id: 'cc-gen-c', objective: 'Consideration', name: 'General Consideration' },
  { campaign_id: 'cc-gen-cv', objective: 'Conversion', name: 'General Conversion' },
  { campaign_id: 'cc-1', objective: 'Problem Awareness', name: 'Market Education Initiative' },
  { campaign_id: 'cc-2', objective: 'Brand Awareness', name: 'Evergreen Brand Visibility' },
  { campaign_id: 'cc-3', objective: 'Brand Awareness', name: 'Q1 Thought Leadership' },
  { campaign_id: 'cc-4', objective: 'Consideration', name: 'Product Evaluation Push' },
  { campaign_id: 'cc-5', objective: 'Consideration', name: 'Competitive Displacement' },
  { campaign_id: 'cc-6', objective: 'Conversion', name: 'Spring Promo 2026' },
  { campaign_id: 'cc-7', objective: 'Conversion', name: 'Enterprise Pipeline Accelerator' },
  { campaign_id: 'cc-8', objective: 'Problem Awareness', name: 'Industry Trends Awareness' },
];

export function getCampaignsByObjective(objective?: FunnelObjective): CalendarCampaign[] {
  return objective ? calendarCampaigns.filter(c => c.objective === objective) : calendarCampaigns;
}

export const getCampaignsForObjective = getCampaignsByObjective;

export function getGenericCampaignId(objective: FunnelObjective): string {
  return GENERIC_CAMPAIGN_IDS[objective];
}

export function addCampaign(name: string, objective: FunnelObjective): CalendarCampaign {
  const id = `cc-new-${Date.now()}`;
  const campaign: CalendarCampaign = { campaign_id: id, objective, name };
  calendarCampaigns.push(campaign);
  return campaign;
}

export function getCampaignName(campaignId: string | null): string {
  if (!campaignId) return '—';
  const c = calendarCampaigns.find(c => c.campaign_id === campaignId);
  return c ? c.name : 'Unknown Campaign';
}

export function getCampaignObjective(campaignId: string | null): FunnelObjective | null {
  if (!campaignId) return null;
  const c = calendarCampaigns.find(c => c.campaign_id === campaignId);
  return c ? c.objective : null;
}

export function getActivityObjective(activity: Pick<CalendarActivity, 'campaign_id'>): FunnelObjective | null {
  return getCampaignObjective(activity.campaign_id);
}

// ─── Existing Tags & Categories (for typeahead) ───

export const existingTaskTypes = [
  'Brand',
  'Demand Gen',
  'Product Launch',
  'Seasonal',
  'Thought Leadership',
  'Retention',
  'Competitive',
];

// Keep backward compat alias
export const existingCategories = existingTaskTypes;

export const promotionTypes: PromotionType[] = [
  'Discount', 'Bundle', 'Free Trial', 'BOGO', 'Flash Sale', 'Seasonal', 'Launch Offer',
];

export const holidayTypes: HolidayType[] = [
  'Public', 'Religious', 'Cultural', 'Observance', 'Company',
];

export const knownRegions = [
  'Global', 'US', 'EMEA', 'APAC', 'LATAM', 'CN', 'JP', 'UK', 'DE', 'FR', 'AU', 'IN', 'BR',
];

export const existingTags = [
  'enterprise',
  'smb',
  'retargeting',
  'awareness',
  'video',
  'webinar',
  'blog',
  'whitepaper',
  'case-study',
  'promo',
  'A/B test',
  'seasonal',
  'evergreen',
  'new-market',
];

// ─── Known Platforms (for form dropdowns) ───

export const knownPlatforms = platformColors.map(p => p.platform);

// ─── Mock Activities ───
// Dates centered around March 2026 (today = March 24, 2026)

const _rawActivities: Array<Omit<CalendarActivity, 'category' | 'task_type'> & { category: string | null }> = [
  // ── Awaiting Approval (3 standalone items for the queue) ──
  {
    activity_id: 'act-01',
    name: 'Spring Promo 2026 - Google Ads Launch',
    campaign_id: 'cc-6',
    channel: 'Display',
    platform: 'Google Display',
    cost: 12000,
    launch_date: new Date(2026, 2, 25),
    launch_time_utc: '14:30',
    category: 'Seasonal',
    tags: ['promo', 'retargeting'],
    owner: 'sarah.chen@example.com',
    status: 'Awaiting Approval',
    created_date: new Date(2026, 2, 18),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'sarah.chen@example.com',
  },
  {
    activity_id: 'act-02',
    name: 'LinkedIn Brand Awareness - Q1 Thought Leadership',
    campaign_id: 'cc-2',
    channel: 'Social',
    platform: 'LinkedIn',
    cost: 5000,
    launch_date: new Date(2026, 2, 26),
    launch_time_utc: '10:00',
    category: 'Thought Leadership',
    tags: ['awareness', 'video'],
    owner: 'mike.johnson@example.com',
    status: 'Awaiting Approval',
    created_date: new Date(2026, 2, 19),
    created_by: 'mike.johnson@example.com',
    last_updated_at: new Date(2026, 2, 23),
    last_updated_by: 'mike.johnson@example.com',
  },
  {
    activity_id: 'act-03',
    name: 'MailChimp Product Evaluation Push - Enterprise',
    campaign_id: 'cc-4',
    channel: 'Email',
    platform: 'MailChimp',
    cost: 800,
    launch_date: new Date(2026, 2, 27),
    launch_time_utc: null,
    category: 'Demand Gen',
    tags: ['enterprise', 'case-study'],
    owner: 'priya.patel@example.com',
    status: 'Awaiting Approval',
    created_date: new Date(2026, 2, 20),
    created_by: 'priya.patel@example.com',
    last_updated_at: new Date(2026, 2, 23),
    last_updated_by: 'priya.patel@example.com',
  },

  // ── Awaiting Approval – Daily Paid Search Spend (March 2026, batch of 14) ──
  // These represent daily budget allocations for a month-long paid search campaign
  ...Array.from({ length: 14 }, (_, i) => ({
    activity_id: `act-ps-${String(i + 1).padStart(2, '0')}`,
    name: `Paid Search Daily Spend - Mar ${i + 17}`,
    campaign_id: 'cc-6',
    channel: 'Paid Search',
    platform: 'Google Ads',
    cost: 850 + Math.round(Math.random() * 300),
    launch_date: new Date(2026, 2, 17 + i),
    launch_time_utc: '06:00',
    category: 'Demand Gen',
    tags: ['paid-search', 'daily-spend'],
    owner: 'sarah.chen@example.com',
    status: 'Awaiting Approval' as ActivityStatus,
    created_date: new Date(2026, 2, 15),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 16),
    last_updated_by: 'sarah.chen@example.com',
  })),

  // ── Approved activities (active on the calendar) ──
  {
    activity_id: 'act-04',
    name: 'Facebook Brand Awareness - Evergreen Brand Visibility',
    campaign_id: 'cc-2',
    channel: 'Social',
    platform: 'Facebook',
    cost: 8500,
    launch_date: new Date(2026, 2, 16),
    launch_time_utc: null,
    category: 'Brand',
    tags: ['awareness', 'video', 'evergreen'],
    owner: 'mike.johnson@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 10),
    created_by: 'mike.johnson@example.com',
    last_updated_at: new Date(2026, 2, 14),
    last_updated_by: 'alex.rivera@example.com',
  },
  {
    activity_id: 'act-05',
    name: 'Instagram Brand Awareness - Evergreen Brand Visibility',
    campaign_id: 'cc-2',
    channel: 'Social',
    platform: 'Instagram',
    cost: 4200,
    launch_date: new Date(2026, 2, 18),
    launch_time_utc: '13:00',
    category: 'Brand',
    tags: ['awareness', 'video'],
    owner: 'jordan.lee@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 12),
    created_by: 'jordan.lee@example.com',
    last_updated_at: new Date(2026, 2, 15),
    last_updated_by: 'alex.rivera@example.com',
  },
  {
    activity_id: 'act-06',
    name: 'Google Ads Spring Promo 2026 - Seasonal',
    campaign_id: 'cc-6',
    channel: 'Paid Search',
    platform: 'Google Ads',
    cost: 15000,
    launch_date: new Date(2026, 2, 23),
    launch_time_utc: '08:00',
    category: 'Seasonal',
    tags: ['promo', 'retargeting', 'A/B test'],
    owner: 'sarah.chen@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 15),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 20),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-07',
    name: 'Bing Ads Enterprise Pipeline Accelerator - Demand Gen',
    campaign_id: 'cc-7',
    channel: 'Paid Search',
    platform: 'Bing Ads',
    cost: 3500,
    launch_date: new Date(2026, 2, 24),
    launch_time_utc: '16:00',
    category: 'Demand Gen',
    tags: ['enterprise'],
    owner: 'alex.rivera@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 17),
    created_by: 'alex.rivera@example.com',
    last_updated_at: new Date(2026, 2, 21),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-08',
    name: 'WordPress Market Education Initiative - Thought Leadership',
    campaign_id: 'cc-1',
    channel: 'Content',
    platform: 'WordPress',
    cost: null,
    launch_date: new Date(2026, 2, 20),
    launch_time_utc: null,
    category: 'Thought Leadership',
    tags: ['blog', 'awareness'],
    owner: 'emma.thompson@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 13),
    created_by: 'emma.thompson@example.com',
    last_updated_at: new Date(2026, 2, 18),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-09',
    name: 'SendGrid Product Evaluation Push - Enterprise',
    campaign_id: 'cc-4',
    channel: 'Email',
    platform: 'SendGrid',
    cost: 1200,
    launch_date: new Date(2026, 2, 22),
    launch_time_utc: null,
    category: 'Demand Gen',
    tags: ['enterprise', 'whitepaper'],
    owner: 'priya.patel@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 14),
    created_by: 'priya.patel@example.com',
    last_updated_at: new Date(2026, 2, 19),
    last_updated_by: 'priya.patel@example.com',
  },
  {
    activity_id: 'act-10',
    name: 'Zoom Q1 Thought Leadership - Brand Awareness',
    campaign_id: 'cc-3',
    channel: 'Events',
    platform: 'Zoom',
    cost: 2000,
    launch_date: new Date(2026, 2, 26),
    launch_time_utc: '11:00',
    category: 'Thought Leadership',
    tags: ['webinar', 'awareness'],
    owner: 'jordan.lee@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 16),
    created_by: 'jordan.lee@example.com',
    last_updated_at: new Date(2026, 2, 20),
    last_updated_by: 'jordan.lee@example.com',
  },
  {
    activity_id: 'act-11',
    name: 'Google Display Spring Promo 2026 - Seasonal',
    campaign_id: 'cc-6',
    channel: 'Display',
    platform: 'Google Display',
    cost: 6000,
    launch_date: new Date(2026, 2, 25),
    launch_time_utc: '09:00',
    category: 'Seasonal',
    tags: ['promo', 'retargeting'],
    owner: 'sarah.chen@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 18),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'emma.thompson@example.com',
  },

  // ── Draft activities ──
  {
    activity_id: 'act-12',
    name: 'Medium Industry Trends Awareness - Thought Leadership',
    campaign_id: 'cc-8',
    channel: 'Content',
    platform: 'Medium',
    cost: null,
    launch_date: new Date(2026, 3, 1),
    launch_time_utc: null,
    category: 'Thought Leadership',
    tags: ['blog', 'new-market'],
    owner: 'emma.thompson@example.com',
    status: 'Draft',
    created_date: new Date(2026, 2, 22),
    created_by: 'emma.thompson@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-13',
    name: 'Programmatic Competitive Displacement - Competitive',
    campaign_id: 'cc-5',
    channel: 'Display',
    platform: 'Programmatic',
    cost: 9500,
    launch_date: new Date(2026, 3, 5),
    launch_time_utc: '15:30',
    category: 'Competitive',
    tags: ['retargeting', 'A/B test'],
    owner: 'alex.rivera@example.com',
    status: 'Draft',
    created_date: new Date(2026, 2, 23),
    created_by: 'alex.rivera@example.com',
    last_updated_at: new Date(2026, 2, 23),
    last_updated_by: 'alex.rivera@example.com',
  },
  {
    activity_id: 'act-14',
    name: 'MailChimp Enterprise Pipeline Accelerator - Demand Gen',
    campaign_id: 'cc-7',
    channel: 'Email',
    platform: 'MailChimp',
    cost: 500,
    launch_date: new Date(2026, 3, 2),
    launch_time_utc: '07:00',
    category: 'Demand Gen',
    tags: ['enterprise', 'case-study'],
    owner: 'priya.patel@example.com',
    status: 'Draft',
    created_date: new Date(2026, 2, 24),
    created_by: 'priya.patel@example.com',
    last_updated_at: new Date(2026, 2, 24),
    last_updated_by: 'priya.patel@example.com',
  },

  // ── Completed activities ──
  {
    activity_id: 'act-15',
    name: 'LinkedIn Brand Awareness - Market Education Initiative',
    campaign_id: 'cc-1',
    channel: 'Social',
    platform: 'LinkedIn',
    cost: 3800,
    launch_date: new Date(2026, 2, 2),
    launch_time_utc: null,
    category: 'Thought Leadership',
    tags: ['awareness', 'video'],
    owner: 'mike.johnson@example.com',
    status: 'Complete',
    created_date: new Date(2026, 1, 24),
    created_by: 'mike.johnson@example.com',
    last_updated_at: new Date(2026, 2, 14),
    last_updated_by: 'mike.johnson@example.com',
  },
  {
    activity_id: 'act-16',
    name: 'Google Ads Brand Awareness - Evergreen Brand Visibility',
    campaign_id: 'cc-2',
    channel: 'Paid Search',
    platform: 'Google Ads',
    cost: 10000,
    launch_date: new Date(2026, 2, 1),
    launch_time_utc: null,
    category: 'Brand',
    tags: ['awareness', 'evergreen'],
    owner: 'sarah.chen@example.com',
    status: 'Complete',
    created_date: new Date(2026, 1, 20),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 15),
    last_updated_by: 'sarah.chen@example.com',
  },
  {
    activity_id: 'act-17',
    name: 'Eventbrite Product Evaluation Push - Enterprise',
    campaign_id: 'cc-4',
    channel: 'Events',
    platform: 'Eventbrite',
    cost: 4500,
    launch_date: new Date(2026, 2, 5),
    launch_time_utc: '18:00',
    category: 'Demand Gen',
    tags: ['webinar', 'enterprise'],
    owner: 'jordan.lee@example.com',
    status: 'Complete',
    created_date: new Date(2026, 1, 25),
    created_by: 'jordan.lee@example.com',
    last_updated_at: new Date(2026, 2, 6),
    last_updated_by: 'jordan.lee@example.com',
  },

  // ── Rejected ──
  {
    activity_id: 'act-18',
    name: 'Facebook Spring Promo 2026 - Seasonal',
    campaign_id: 'cc-6',
    channel: 'Social',
    platform: 'Facebook',
    cost: 7000,
    launch_date: new Date(2026, 2, 28),
    launch_time_utc: null,
    category: 'Seasonal',
    tags: ['promo', 'smb'],
    owner: 'mike.johnson@example.com',
    status: 'Rejected',
    created_date: new Date(2026, 2, 19),
    created_by: 'mike.johnson@example.com',
    last_updated_at: new Date(2026, 2, 21),
    last_updated_by: 'emma.thompson@example.com',
  },

  // ── Revision Requested ──
  {
    activity_id: 'act-19',
    name: 'Programmatic Brand Awareness - Industry Trends Awareness',
    campaign_id: 'cc-8',
    channel: 'Display',
    platform: 'Programmatic',
    cost: 5500,
    launch_date: new Date(2026, 2, 30),
    launch_time_utc: '12:00',
    category: 'Brand',
    tags: ['awareness', 'new-market'],
    owner: 'alex.rivera@example.com',
    status: 'Revision Requested',
    revision_comment: 'Budget seems high for the target audience size. Please revise the targeting parameters and adjust cost accordingly.',
    created_date: new Date(2026, 2, 20),
    created_by: 'alex.rivera@example.com',
    last_updated_at: new Date(2026, 2, 23),
    last_updated_by: 'emma.thompson@example.com',
  },

  // ── More Approved to fill the calendar ──
  {
    activity_id: 'act-20',
    name: 'Google Ads Competitive Displacement - Competitive',
    campaign_id: 'cc-5',
    channel: 'Paid Search',
    platform: 'Google Ads',
    cost: 7500,
    launch_date: new Date(2026, 2, 30),
    launch_time_utc: '14:00',
    category: 'Competitive',
    tags: ['retargeting', 'enterprise'],
    owner: 'sarah.chen@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 21),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 23),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-21',
    name: 'WordPress Brand Awareness - Q1 Thought Leadership',
    campaign_id: 'cc-3',
    channel: 'Content',
    platform: 'WordPress',
    cost: null,
    launch_date: new Date(2026, 2, 24),
    launch_time_utc: null,
    category: 'Thought Leadership',
    tags: ['blog', 'awareness', 'evergreen'],
    owner: 'emma.thompson@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 18),
    created_by: 'emma.thompson@example.com',
    last_updated_at: new Date(2026, 2, 21),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-22',
    name: 'SendGrid Enterprise Pipeline Accelerator - Demand Gen',
    campaign_id: 'cc-7',
    channel: 'Email',
    platform: 'SendGrid',
    cost: 950,
    launch_date: new Date(2026, 3, 1),
    launch_time_utc: '09:30',
    category: 'Demand Gen',
    tags: ['enterprise'],
    owner: 'priya.patel@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 22),
    created_by: 'priya.patel@example.com',
    last_updated_at: new Date(2026, 2, 24),
    last_updated_by: 'emma.thompson@example.com',
  },
  // No platform — should render as neutral gray
  {
    activity_id: 'act-23',
    name: 'Market Education Initiative - Problem Awareness',
    campaign_id: 'cc-1',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2026, 3, 6),
    launch_time_utc: null,
    category: null,
    tags: [],
    owner: null,
    status: 'Draft',
    created_date: new Date(2026, 2, 24),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 24),
    last_updated_by: 'sarah.chen@example.com',
  },
  {
    activity_id: 'act-24',
    name: 'Facebook Brand Awareness - Evergreen Brand Visibility',
    campaign_id: 'cc-2',
    channel: 'Social',
    platform: 'Facebook',
    cost: 3200,
    launch_date: new Date(2026, 3, 3),
    launch_time_utc: '17:00',
    category: 'Brand',
    tags: ['awareness', 'A/B test'],
    owner: 'jordan.lee@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 23),
    created_by: 'jordan.lee@example.com',
    last_updated_at: new Date(2026, 2, 24),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-25',
    name: 'Bing Ads Spring Promo 2026 - Seasonal',
    campaign_id: 'cc-6',
    channel: 'Paid Search',
    platform: 'Bing Ads',
    cost: 2800,
    launch_date: new Date(2026, 3, 8),
    launch_time_utc: null,
    category: 'Seasonal',
    tags: ['promo'],
    owner: 'alex.rivera@example.com',
    status: 'Draft',
    created_date: new Date(2026, 2, 24),
    created_by: 'alex.rivera@example.com',
    last_updated_at: new Date(2026, 2, 24),
    last_updated_by: 'alex.rivera@example.com',
  },

  // ── Additional single-day activities to fill the calendar ──
  {
    activity_id: 'act-26',
    name: 'Facebook Retargeting - Spring Promo Day 2',
    campaign_id: 'cc-6',
    channel: 'Social',
    platform: 'Facebook',
    cost: 2500,
    launch_date: new Date(2026, 2, 24),
    launch_time_utc: '10:00',
    category: 'Seasonal',
    tags: ['promo', 'retargeting'],
    owner: 'mike.johnson@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 20),
    created_by: 'mike.johnson@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-27',
    name: 'LinkedIn Sponsored Content - Competitive',
    campaign_id: 'cc-5',
    channel: 'Social',
    platform: 'LinkedIn',
    cost: 3000,
    launch_date: new Date(2026, 2, 25),
    launch_time_utc: null,
    category: 'Competitive',
    tags: ['enterprise', 'awareness'],
    owner: 'alex.rivera@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 19),
    created_by: 'alex.rivera@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-28',
    name: 'MailChimp Newsletter - Market Education',
    campaign_id: 'cc-1',
    channel: 'Email',
    platform: 'MailChimp',
    cost: 350,
    launch_date: new Date(2026, 2, 26),
    launch_time_utc: '08:00',
    category: 'Thought Leadership',
    tags: ['blog', 'awareness'],
    owner: 'priya.patel@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 20),
    created_by: 'priya.patel@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'priya.patel@example.com',
  },
  {
    activity_id: 'act-29',
    name: 'Google Ads Remarketing - Pipeline Accelerator',
    campaign_id: 'cc-7',
    channel: 'Paid Search',
    platform: 'Google Ads',
    cost: 4000,
    launch_date: new Date(2026, 2, 27),
    launch_time_utc: '06:00',
    category: 'Demand Gen',
    tags: ['enterprise', 'retargeting'],
    owner: 'sarah.chen@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 21),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 23),
    last_updated_by: 'emma.thompson@example.com',
  },
  {
    activity_id: 'act-30',
    name: 'Instagram Stories - Evergreen Brand',
    campaign_id: 'cc-2',
    channel: 'Social',
    platform: 'Instagram',
    cost: 1800,
    launch_date: new Date(2026, 2, 25),
    launch_time_utc: '16:00',
    category: 'Brand',
    tags: ['awareness', 'video'],
    owner: 'jordan.lee@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 19),
    created_by: 'jordan.lee@example.com',
    last_updated_at: new Date(2026, 2, 22),
    last_updated_by: 'emma.thompson@example.com',
  },
];

// Migrate raw activities: old category → task_type, category → 'task'
const migratedActivities: CalendarActivity[] = _rawActivities.map(raw => ({
  ...raw,
  category: 'task' as ActivityCategory,
  task_type: raw.category,
}));

// ── Sample Promotions ──
const samplePromotions: CalendarActivity[] = [
  {
    activity_id: 'promo-01',
    name: 'Spring Sale — Widget Pro 30% Off',
    campaign_id: 'generic_conversion',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2026, 2, 20),
    launch_time_utc: null,
    category: 'promotion',
    task_type: null,
    tags: ['promo', 'seasonal'],
    owner: 'sarah.chen@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 10),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(2026, 2, 15),
    last_updated_by: 'sarah.chen@example.com',
    product_service: 'Widget Pro',
    promotion_type: 'Discount',
    discount_details: '30% off all Widget Pro plans',
    end_date: new Date(2026, 3, 3),
    promo_url: 'https://example.com/spring-sale',
    region: 'Global',
  },
  {
    activity_id: 'promo-02',
    name: 'Enterprise Bundle — Buy 2 Get 1 Free',
    campaign_id: 'generic_conversion',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2026, 3, 1),
    launch_time_utc: null,
    category: 'promotion',
    task_type: null,
    tags: ['enterprise', 'promo'],
    owner: 'alex.rivera@example.com',
    status: 'Approved',
    created_date: new Date(2026, 2, 18),
    created_by: 'alex.rivera@example.com',
    last_updated_at: new Date(2026, 2, 20),
    last_updated_by: 'alex.rivera@example.com',
    product_service: 'Enterprise Suite',
    promotion_type: 'BOGO',
    discount_details: 'Buy 2 Enterprise licenses, get 1 free',
    end_date: new Date(2026, 3, 15),
    promo_url: 'https://example.com/enterprise-bundle',
    region: 'US',
  },
];

// ── Sample Holidays ──
const sampleHolidays: CalendarActivity[] = [
  {
    activity_id: 'hol-01',
    name: 'Easter Weekend',
    campaign_id: 'generic_problem_awareness',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2026, 3, 3),
    launch_time_utc: null,
    category: 'holiday',
    task_type: null,
    tags: [],
    owner: null,
    status: 'Approved',
    created_date: new Date(2026, 0, 1),
    created_by: 'emma.thompson@example.com',
    last_updated_at: new Date(2026, 0, 1),
    last_updated_by: 'emma.thompson@example.com',
    holiday_type: 'Religious',
    recurring: true,
    region: 'Global',
    end_date: new Date(2026, 3, 6),
  },
  {
    activity_id: 'hol-02',
    name: 'Christmas',
    campaign_id: 'generic_problem_awareness',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2025, 11, 24),
    launch_time_utc: null,
    category: 'holiday',
    task_type: null,
    tags: [],
    owner: null,
    status: 'Approved',
    created_date: new Date(2025, 10, 1),
    created_by: 'emma.thompson@example.com',
    last_updated_at: new Date(2025, 10, 1),
    last_updated_by: 'emma.thompson@example.com',
    holiday_type: 'Religious',
    recurring: true,
    region: 'Global',
    end_date: new Date(2025, 11, 25),
  },
  {
    activity_id: 'hol-03',
    name: 'Company Wellness Day',
    campaign_id: 'generic_problem_awareness',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2026, 2, 27),
    launch_time_utc: null,
    category: 'holiday',
    task_type: null,
    tags: [],
    owner: null,
    status: 'Approved',
    created_date: new Date(2026, 1, 1),
    created_by: 'emma.thompson@example.com',
    last_updated_at: new Date(2026, 1, 1),
    last_updated_by: 'emma.thompson@example.com',
    holiday_type: 'Company',
    recurring: false,
    region: 'Global',
  },
];

export const calendarActivities: CalendarActivity[] = [
  ...migratedActivities,
  ...samplePromotions,
  ...sampleHolidays,
];