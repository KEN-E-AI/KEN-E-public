// ─── Automation Details Data Model & Mock Data ───
// Each automation is a DAG of tasks displayed in React Flow.

import type { ActivityStatus } from './calendarData';

export type ScheduleFrequency = 'once' | 'daily' | 'weekly' | 'monthly' | 'custom_cron';

export interface AutomationSchedule {
  enabled: boolean;
  frequency: ScheduleFrequency;
  days_of_week: number[]; // 0=Sun..6=Sat, used for 'weekly'
  day_of_month: number | null; // used for 'monthly'
  time_utc: string; // HH:mm
  cron_expression: string | null; // used for 'custom_cron'
  run_date: Date | null; // used for 'once' — the specific calendar day to run
  next_run: Date | null;
  last_run: Date | null;
}

export const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const;

/** Compute the next occurrence from a schedule config relative to `from`. */
export function computeNextRun(schedule: AutomationSchedule, from: Date = new Date()): Date | null {
  if (!schedule.enabled) return null;
  const [hours, minutes] = schedule.time_utc.split(':').map(Number);

  if (schedule.frequency === 'daily') {
    const next = new Date(from);
    next.setUTCHours(hours, minutes, 0, 0);
    if (next <= from) next.setUTCDate(next.getUTCDate() + 1);
    return next;
  }

  if (schedule.frequency === 'weekly' && schedule.days_of_week.length > 0) {
    const sorted = [...schedule.days_of_week].sort((a, b) => a - b);
    const currentDay = from.getUTCDay();
    // Try to find next day in this week
    for (const day of sorted) {
      const diff = day - currentDay;
      if (diff > 0 || (diff === 0 && (() => { const t = new Date(from); t.setUTCHours(hours, minutes, 0, 0); return t > from; })())) {
        const next = new Date(from);
        next.setUTCDate(next.getUTCDate() + (day - currentDay));
        next.setUTCHours(hours, minutes, 0, 0);
        if (next > from) return next;
      }
    }
    // Wrap to next week
    const next = new Date(from);
    const daysUntil = 7 - currentDay + sorted[0];
    next.setUTCDate(next.getUTCDate() + daysUntil);
    next.setUTCHours(hours, minutes, 0, 0);
    return next;
  }

  if (schedule.frequency === 'monthly' && schedule.day_of_month != null) {
    const next = new Date(from);
    next.setUTCDate(schedule.day_of_month);
    next.setUTCHours(hours, minutes, 0, 0);
    if (next <= from) next.setUTCMonth(next.getUTCMonth() + 1);
    return next;
  }

  if (schedule.frequency === 'once') {
    if (!schedule.run_date) return null;
    const next = new Date(schedule.run_date);
    next.setUTCHours(hours, minutes, 0, 0);
    return next > from ? next : null;
  }

  return null;
}

/** Human-readable summary of a schedule */
export function describeSchedule(schedule: AutomationSchedule): string {
  if (!schedule.enabled) return 'Not scheduled';
  const time = schedule.time_utc + ' UTC';
  switch (schedule.frequency) {
    case 'daily':
      return `Daily at ${time}`;
    case 'weekly': {
      const days = schedule.days_of_week
        .sort((a, b) => a - b)
        .map((d) => DAY_LABELS[d])
        .join(', ');
      return days ? `Every ${days} at ${time}` : `Weekly at ${time}`;
    }
    case 'monthly':
      return `Monthly on the ${schedule.day_of_month}${ordinalSuffix(schedule.day_of_month ?? 1)} at ${time}`;
    case 'once':
      if (!schedule.run_date) return `Once (date not set)`;
      return `Once on ${schedule.run_date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} at ${time}`;
    case 'custom_cron':
      return schedule.cron_expression ? `Cron: ${schedule.cron_expression}` : `Custom schedule at ${time}`;
    default:
      return `At ${time}`;
  }
}

function ordinalSuffix(n: number): string {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}

export function createDefaultSchedule(): AutomationSchedule {
  return {
    enabled: false,
    frequency: 'weekly',
    days_of_week: [1], // Monday
    day_of_month: null,
    time_utc: '14:00',
    cron_expression: null,
    run_date: null,
    next_run: null,
    last_run: null,
  };
}

// ─── Output File Types ───

export type OutputFileType = 'image' | 'document' | 'csv' | 'json' | 'text' | 'html' | 'video' | 'audio' | 'visualization' | 'other';

export interface OutputFile {
  file_id: string;
  filename: string;
  file_type: OutputFileType;
  mime_type: string;
  size_bytes: number;
  preview_url: string | null;
  content_preview: string | null;
  created_at: Date;
}

export interface TaskRunOutput {
  run_id: string;
  run_timestamp: Date;
  outputs: OutputFile[];
}

export interface OutputConfig {
  enabled: boolean;
  expected_file_types: OutputFileType[];
  description: string | null;
}

export const FILE_TYPE_LABELS: Record<OutputFileType, string> = {
  image: 'Image',
  document: 'Document',
  csv: 'CSV',
  json: 'JSON',
  text: 'Text',
  html: 'HTML',
  video: 'Video',
  audio: 'Audio',
  visualization: 'Visualization',
  other: 'Other',
};

export interface AutomationTask {
  task_id: string;
  title: string;
  description: string | null;
  assignee_type: 'human' | 'agent';
  assignee_name: string | null;
  status: ActivityStatus;
  depends_on: string[];
  cost: number | null;
  due_date: Date | null;
  launch_time_utc: string | null;
  platform: string | null;
  tags: string[];
  estimated_effort: string | null;
  completion_notes: string | null;
  revision_comment: string | null;
  output_config: OutputConfig | null;
  run_outputs: TaskRunOutput[];
}

export interface AutomationDetail {
  automationId: string;
  tasks: AutomationTask[];
  schedule: AutomationSchedule;
}

// ─── Mock task sets per automation ───

const automationTaskSets: Record<string, AutomationTask[]> = {
  // 4 — Optimize blog post SEO
  '4': [
    {
      task_id: 't4-1', title: 'Fetch Blog URL & Content', description: 'Scrape the target blog post URL and extract raw HTML content for analysis.', assignee_type: 'agent', assignee_name: 'SEO Agent', status: 'Complete', depends_on: [], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '08:00', platform: 'WordPress', tags: ['seo', 'content'], estimated_effort: '5m', completion_notes: 'Fetched 3,200 words.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['html'], description: 'Raw HTML content of the blog post' },
      run_outputs: [{ run_id: 'run-a4-001', run_timestamp: new Date(2026, 3, 14, 8, 1), outputs: [
        { file_id: 'f4-1a', filename: 'blog-content-raw.html', file_type: 'html', mime_type: 'text/html', size_bytes: 48200, preview_url: null, content_preview: '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <title>10 Proven Strategies for B2B Content Marketing in 2026</title>\n  <meta name="description" content="Discover the top B2B content marketing strategies that drive leads and revenue in 2026. From AI-powered personalization to interactive content experiences.">\n</head>\n<body>\n  <article>\n    <h1>10 Proven Strategies for B2B Content Marketing in 2026</h1>\n    <p>Content marketing continues to evolve at a rapid pace. In this comprehensive guide, we explore the strategies that leading B2B companies are using to generate qualified leads...</p>\n    <h2>1. AI-Powered Content Personalization</h2>\n    <p>The days of one-size-fits-all content are over. Modern B2B buyers expect personalized experiences...</p>\n  </article>\n</body>\n</html>', created_at: new Date(2026, 3, 14, 8, 1) },
      ] }],
    },
    {
      task_id: 't4-2', title: 'Analyze Meta Tags', description: 'Check title tag, meta description, OG tags and canonical URL.', assignee_type: 'agent', assignee_name: 'SEO Agent', status: 'Complete', depends_on: ['t4-1'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '08:05', platform: 'WordPress', tags: ['seo'], estimated_effort: '3m', completion_notes: 'Title too long (72 chars).', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Meta tag analysis results' },
      run_outputs: [{ run_id: 'run-a4-001', run_timestamp: new Date(2026, 3, 14, 8, 5), outputs: [
        { file_id: 'f4-2a', filename: 'meta-analysis.json', file_type: 'json', mime_type: 'application/json', size_bytes: 2140, preview_url: null, content_preview: '{\n  "title": {\n    "content": "10 Proven Strategies for B2B Content Marketing in 2026 | MarketingPro Blog",\n    "length": 72,\n    "status": "warning",\n    "recommendation": "Shorten to under 60 characters for optimal display in SERPs"\n  },\n  "meta_description": {\n    "content": "Discover the top B2B content marketing strategies that drive leads and revenue in 2026.",\n    "length": 87,\n    "status": "pass"\n  },\n  "og_tags": {\n    "og:title": "present",\n    "og:description": "present",\n    "og:image": "missing",\n    "status": "warning"\n  },\n  "canonical": {\n    "url": "https://blog.example.com/b2b-content-marketing-2026",\n    "status": "pass"\n  }\n}', created_at: new Date(2026, 3, 14, 8, 5) },
      ] }],
    },
    {
      task_id: 't4-3', title: 'Analyze Keywords', description: 'Extract keyword density and compare with target keywords.', assignee_type: 'agent', assignee_name: 'SEO Agent', status: 'Complete', depends_on: ['t4-1'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '08:05', platform: 'WordPress', tags: ['seo', 'keywords'], estimated_effort: '5m', completion_notes: 'Primary keyword density at 1.8%.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['csv'], description: 'Keyword density report' },
      run_outputs: [{ run_id: 'run-a4-001', run_timestamp: new Date(2026, 3, 14, 8, 6), outputs: [
        { file_id: 'f4-3a', filename: 'keyword-report.csv', file_type: 'csv', mime_type: 'text/csv', size_bytes: 1580, preview_url: null, content_preview: 'keyword,density_pct,occurrences,status,recommendation\n"content marketing",1.8,24,pass,"Good density range (1-2%)"\n"B2B",1.2,16,pass,"Appropriate usage"\n"lead generation",0.6,8,warning,"Consider increasing to 1%+"\n"marketing strategy",0.9,12,pass,"Good supporting keyword"\n"AI personalization",0.4,5,warning,"Add 2-3 more mentions"\n"content creation",0.7,9,pass,"Well distributed"\n"buyer journey",0.3,4,info,"Consider as secondary keyword"\n"conversion rate",0.2,3,info,"Low but acceptable for supporting term"', created_at: new Date(2026, 3, 14, 8, 6) },
      ] }],
    },
    {
      task_id: 't4-4', title: 'Check Readability', description: 'Run Flesch-Kincaid and other readability checks.', assignee_type: 'agent', assignee_name: 'SEO Agent', status: 'Approved', depends_on: ['t4-1'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '08:05', platform: 'WordPress', tags: ['seo', 'readability'], estimated_effort: '3m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Readability scores and suggestions' },
      run_outputs: [],
    },
    {
      task_id: 't4-5', title: 'Generate SEO Report', description: 'Compile findings into a structured optimization report.', assignee_type: 'agent', assignee_name: 'SEO Agent', status: 'Draft', depends_on: ['t4-2', 't4-3', 't4-4'], cost: 0, due_date: new Date(2026, 1, 15), launch_time_utc: '09:00', platform: null, tags: ['seo', 'report'], estimated_effort: '10m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['html', 'json'], description: 'Compiled SEO optimization report' },
      run_outputs: [],
    },
    {
      task_id: 't4-6', title: 'Review & Apply Fixes', description: 'Human reviews the report and applies recommended fixes to the CMS.', assignee_type: 'human', assignee_name: 'Sarah Chen', status: 'Draft', depends_on: ['t4-5'], cost: 50, due_date: new Date(2026, 1, 16), launch_time_utc: '14:00', platform: 'WordPress', tags: ['seo', 'manual'], estimated_effort: '1h', completion_notes: null, revision_comment: null,
      output_config: null,
      run_outputs: [],
    },
  ],

  // 5 — Generate social posts from YouTube video
  '5': [
    {
      task_id: 't5-1', title: 'Extract Video Transcript', description: 'Pull transcript from YouTube video using captions API.', assignee_type: 'agent', assignee_name: 'Content Agent', status: 'Complete', depends_on: [], cost: 0, due_date: new Date(2026, 1, 15), launch_time_utc: '10:00', platform: null, tags: ['youtube', 'transcript'], estimated_effort: '2m', completion_notes: '12 min transcript extracted.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['text'], description: 'Raw video transcript' },
      run_outputs: [{ run_id: 'run-a5-001', run_timestamp: new Date(2026, 3, 16, 10, 1), outputs: [
        { file_id: 'f5-1a', filename: 'transcript.txt', file_type: 'text', mime_type: 'text/plain', size_bytes: 14200, preview_url: null, content_preview: '[00:00] Welcome back to the channel! Today we\'re diving deep into the future of marketing automation.\n[00:15] I\'m going to share five key trends that every marketer needs to know about in 2026.\n[00:28] First up — AI-driven campaign orchestration. This isn\'t just about scheduling posts anymore.\n[00:42] We\'re talking about systems that can analyze your audience in real-time and adjust messaging dynamically.\n[01:05] Let me show you a real example from one of our recent campaigns...\n[01:20] The second trend is hyper-personalization at scale.\n[01:35] Gone are the days when segmenting by demographics was enough.\n[02:10] Now we\'re looking at behavioral micro-segments that update in real-time...', created_at: new Date(2026, 3, 16, 10, 1) },
      ] }],
    },
    {
      task_id: 't5-2', title: 'Identify Key Themes', description: 'Analyze transcript to find 3-5 shareable themes and quotes.', assignee_type: 'agent', assignee_name: 'Content Agent', status: 'Complete', depends_on: ['t5-1'], cost: 0, due_date: new Date(2026, 1, 15), launch_time_utc: '10:05', platform: null, tags: ['content', 'analysis'], estimated_effort: '5m', completion_notes: '4 themes found.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Extracted themes and quotable moments' },
      run_outputs: [{ run_id: 'run-a5-001', run_timestamp: new Date(2026, 3, 16, 10, 6), outputs: [
        { file_id: 'f5-2a', filename: 'themes-analysis.json', file_type: 'json', mime_type: 'application/json', size_bytes: 3200, preview_url: null, content_preview: '{\n  "themes": [\n    {\n      "id": 1,\n      "title": "AI-Driven Campaign Orchestration",\n      "quote": "This isn\'t just about scheduling posts anymore — we\'re talking about systems that analyze your audience in real-time.",\n      "timestamp": "00:28",\n      "sentiment": "exciting",\n      "shareability_score": 0.92\n    },\n    {\n      "id": 2,\n      "title": "Hyper-Personalization at Scale",\n      "quote": "Gone are the days when segmenting by demographics was enough.",\n      "timestamp": "01:20",\n      "sentiment": "informative",\n      "shareability_score": 0.88\n    },\n    {\n      "id": 3,\n      "title": "Privacy-First Marketing",\n      "quote": "The brands that win will be the ones that make privacy a feature, not an obstacle.",\n      "timestamp": "04:15",\n      "sentiment": "thought-provoking",\n      "shareability_score": 0.95\n    },\n    {\n      "id": 4,\n      "title": "Interactive Content Experiences",\n      "quote": "Static content is dead. Every piece should invite participation.",\n      "timestamp": "08:30",\n      "sentiment": "bold",\n      "shareability_score": 0.90\n    }\n  ]\n}', created_at: new Date(2026, 3, 16, 10, 6) },
      ] }],
    },
    {
      task_id: 't5-3', title: 'Draft LinkedIn Post', description: 'Create a professional long-form post for LinkedIn.', assignee_type: 'agent', assignee_name: 'Content Agent', status: 'Awaiting Approval', depends_on: ['t5-2'], cost: 0, due_date: new Date(2026, 1, 16), launch_time_utc: '11:00', platform: 'LinkedIn', tags: ['social', 'linkedin'], estimated_effort: '5m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['text'], description: 'LinkedIn post draft' },
      run_outputs: [{ run_id: 'run-a5-001', run_timestamp: new Date(2026, 3, 16, 10, 12), outputs: [
        { file_id: 'f5-3a', filename: 'linkedin-draft.txt', file_type: 'text', mime_type: 'text/plain', size_bytes: 1850, preview_url: null, content_preview: 'The future of marketing automation isn\'t what you think.\n\nAfter spending 12 months researching trends, here are 4 shifts every B2B marketer needs to prepare for:\n\n1/ AI-Driven Campaign Orchestration\nForget simple scheduling. Modern systems analyze your audience in real-time and adjust messaging dynamically. The ROI difference? 3.2x on average.\n\n2/ Hyper-Personalization at Scale\nDemographic segmentation is table stakes. The leaders are using behavioral micro-segments that update in real-time.\n\n3/ Privacy-First Marketing\n"The brands that win will be the ones that make privacy a feature, not an obstacle."\n\n4/ Interactive Content\nStatic content is dead. Every piece should invite participation.\n\nWhich of these trends are you already implementing? Drop a comment below.\n\n#MarketingAutomation #B2BMarketing #ContentStrategy #FutureOfMarketing', created_at: new Date(2026, 3, 16, 10, 12) },
      ] }],
    },
    {
      task_id: 't5-4', title: 'Draft Twitter Thread', description: 'Create a 5-tweet thread with key takeaways.', assignee_type: 'agent', assignee_name: 'Content Agent', status: 'Awaiting Approval', depends_on: ['t5-2'], cost: 0, due_date: new Date(2026, 1, 16), launch_time_utc: '11:00', platform: null, tags: ['social', 'twitter'], estimated_effort: '5m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Twitter thread as structured tweets' },
      run_outputs: [{ run_id: 'run-a5-001', run_timestamp: new Date(2026, 3, 16, 10, 12), outputs: [
        { file_id: 'f5-4a', filename: 'twitter-thread.json', file_type: 'json', mime_type: 'application/json', size_bytes: 2100, preview_url: null, content_preview: '{\n  "thread": [\n    {\n      "tweet_number": 1,\n      "text": "The future of marketing automation is changing FAST. Here are 4 trends every marketer needs to know about in 2026: A thread"\n    },\n    {\n      "tweet_number": 2,\n      "text": "1/ AI-Driven Campaign Orchestration\\n\\nForget scheduling tools. Modern systems analyze audiences in real-time and adjust messaging dynamically.\\n\\nAverage ROI lift: 3.2x"\n    },\n    {\n      "tweet_number": 3,\n      "text": "2/ Hyper-Personalization at Scale\\n\\nDemographic segmentation is dead.\\n\\nBehavioral micro-segments that update in real-time are the new standard."\n    },\n    {\n      "tweet_number": 4,\n      "text": "3/ Privacy as a Feature\\n\\n\\"The brands that win will be the ones that make privacy a feature, not an obstacle.\\"\\n\\nFirst-party data strategies > third-party cookies"\n    },\n    {\n      "tweet_number": 5,\n      "text": "4/ Interactive Content\\n\\nStatic content is dead. Every piece should invite participation.\\n\\nWhich of these are you already implementing?"\n    }\n  ]\n}', created_at: new Date(2026, 3, 16, 10, 12) },
      ] }],
    },
    {
      task_id: 't5-5', title: 'Draft Instagram Caption', description: 'Create an engaging caption with relevant hashtags.', assignee_type: 'agent', assignee_name: 'Content Agent', status: 'Draft', depends_on: ['t5-2'], cost: 0, due_date: new Date(2026, 1, 16), launch_time_utc: '11:00', platform: 'Instagram', tags: ['social', 'instagram'], estimated_effort: '3m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['text', 'image'], description: 'Instagram caption + cover image' },
      run_outputs: [{ run_id: 'run-a5-001', run_timestamp: new Date(2026, 3, 16, 10, 13), outputs: [
        { file_id: 'f5-5a', filename: 'instagram-caption.txt', file_type: 'text', mime_type: 'text/plain', size_bytes: 620, preview_url: null, content_preview: 'Marketing automation in 2026 looks completely different.\n\nFrom AI-powered campaigns to privacy-first strategies, the game is changing fast.\n\nSwipe to see the 4 biggest trends every marketer needs to know.\n\n#MarketingAutomation #DigitalMarketing #B2BMarketing #ContentMarketing #MarketingTrends #AI #FutureOfMarketing #GrowthMarketing', created_at: new Date(2026, 3, 16, 10, 13) },
        { file_id: 'f5-5b', filename: 'cover-image.png', file_type: 'image', mime_type: 'image/png', size_bytes: 245000, preview_url: 'https://images.unsplash.com/photo-1537731121640-bc1c4aba9b80?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzb2NpYWwlMjBtZWRpYSUyMG1hcmtldGluZyUyMGNvbnRlbnR8ZW58MXx8fHwxNzc2NDIzNzI4fDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral', content_preview: null, created_at: new Date(2026, 3, 16, 10, 13) },
      ] }],
    },
    {
      task_id: 't5-6', title: 'Human Review & Publish', description: 'Review all drafts, make edits, and schedule for publishing.', assignee_type: 'human', assignee_name: 'Mike Johnson', status: 'Draft', depends_on: ['t5-3', 't5-4', 't5-5'], cost: 0, due_date: new Date(2026, 1, 17), launch_time_utc: '14:00', platform: null, tags: ['review', 'publish'], estimated_effort: '30m', completion_notes: null, revision_comment: null,
      output_config: null,
      run_outputs: [],
    },
  ],

  // 6 — Lead Scoring Automation
  '6': [
    {
      task_id: 't6-1', title: 'Ingest Lead Data', description: 'Pull new leads from CRM webhook in real-time.', assignee_type: 'agent', assignee_name: 'Data Agent', status: 'Complete', depends_on: [], cost: 0, due_date: null, launch_time_utc: null, platform: null, tags: ['crm', 'data'], estimated_effort: '1m', completion_notes: '47 leads processed today.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['csv'], description: 'Raw lead data from CRM' },
      run_outputs: [{ run_id: 'run-a6-001', run_timestamp: new Date(2026, 3, 17, 6, 1), outputs: [
        { file_id: 'f6-1a', filename: 'leads-raw.csv', file_type: 'csv', mime_type: 'text/csv', size_bytes: 8400, preview_url: null, content_preview: 'lead_id,company,contact_name,email,source,created_at\nL-4001,"Acme Corp","Jane Smith","jane@acme.com","webinar","2026-04-17T05:30:00Z"\nL-4002,"TechFlow Inc","Bob Lee","bob@techflow.io","organic","2026-04-17T05:45:00Z"\nL-4003,"GreenScale","Maria Garcia","maria@greenscale.com","paid_search","2026-04-17T05:50:00Z"\nL-4004,"DataVista","Chris Park","chris@datavista.ai","referral","2026-04-17T05:55:00Z"\nL-4005,"NovaByte","Alex Rivera","alex@novabyte.com","content","2026-04-17T06:00:00Z"', created_at: new Date(2026, 3, 17, 6, 1) },
      ] }],
    },
    {
      task_id: 't6-2', title: 'Enrich Lead Profile', description: 'Append firmographic and technographic data from enrichment APIs.', assignee_type: 'agent', assignee_name: 'Data Agent', status: 'Complete', depends_on: ['t6-1'], cost: 5, due_date: null, launch_time_utc: null, platform: null, tags: ['enrichment'], estimated_effort: '2m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Enriched lead profiles with firmographic data' },
      run_outputs: [{ run_id: 'run-a6-001', run_timestamp: new Date(2026, 3, 17, 6, 3), outputs: [
        { file_id: 'f6-2a', filename: 'enriched-leads.json', file_type: 'json', mime_type: 'application/json', size_bytes: 12400, preview_url: null, content_preview: '[\n  {\n    "lead_id": "L-4001",\n    "company": "Acme Corp",\n    "industry": "Manufacturing",\n    "employee_count": 2500,\n    "annual_revenue": "$50M-$100M",\n    "tech_stack": ["Salesforce", "HubSpot", "Google Analytics"],\n    "linkedin_followers": 12400,\n    "website_traffic_rank": 45000\n  },\n  {\n    "lead_id": "L-4002",\n    "company": "TechFlow Inc",\n    "industry": "SaaS",\n    "employee_count": 120,\n    "annual_revenue": "$10M-$25M",\n    "tech_stack": ["Segment", "Mixpanel", "Intercom"],\n    "linkedin_followers": 3200,\n    "website_traffic_rank": 120000\n  }\n]', created_at: new Date(2026, 3, 17, 6, 3) },
      ] }],
    },
    {
      task_id: 't6-3', title: 'Score Lead', description: 'Apply ML scoring model to assign 0-100 score.', assignee_type: 'agent', assignee_name: 'ML Agent', status: 'Approved', depends_on: ['t6-2'], cost: 0, due_date: null, launch_time_utc: null, platform: null, tags: ['ml', 'scoring'], estimated_effort: '3m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['csv'], description: 'Scored leads with routing recommendation' },
      run_outputs: [],
    },
    {
      task_id: 't6-4', title: 'Route to Sales', description: 'If score > 70, push to sales team via CRM.', assignee_type: 'agent', assignee_name: 'CRM Agent', status: 'Draft', depends_on: ['t6-3'], cost: 0, due_date: null, launch_time_utc: null, platform: null, tags: ['crm', 'routing'], estimated_effort: '1m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'CRM push confirmation' },
      run_outputs: [],
    },
    {
      task_id: 't6-5', title: 'Add to Nurture Sequence', description: 'If score < 70, enroll in email drip campaign.', assignee_type: 'agent', assignee_name: 'Email Agent', status: 'Draft', depends_on: ['t6-3'], cost: 2, due_date: null, launch_time_utc: null, platform: 'MailChimp', tags: ['email', 'nurture'], estimated_effort: '1m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Email enrollment confirmation' },
      run_outputs: [],
    },
  ],

  // 7 — Campaign Budget Optimizer
  '7': [
    {
      task_id: 't7-1', title: 'Pull Performance Data', description: 'Fetch last 7 days of campaign metrics from all ad platforms.', assignee_type: 'agent', assignee_name: 'Analytics Agent', status: 'Complete', depends_on: [], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '02:00', platform: 'Google Ads', tags: ['analytics', 'data'], estimated_effort: '5m', completion_notes: 'Fetched 12 campaigns across 3 platforms.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['csv'], description: 'Campaign performance metrics' },
      run_outputs: [{ run_id: 'run-a7-001', run_timestamp: new Date(2026, 3, 16, 2, 1), outputs: [
        { file_id: 'f7-1a', filename: 'performance-data.csv', file_type: 'csv', mime_type: 'text/csv', size_bytes: 5600, preview_url: null, content_preview: 'campaign_id,platform,campaign_name,spend_7d,impressions,clicks,conversions,revenue\nC-001,Google Ads,"Brand Search - US",$2450,45200,3200,128,$12800\nC-002,Google Ads,"Competitor Keywords",$1800,28400,1900,42,$4200\nC-003,Facebook,"Lookalike - Enterprise",$3200,125000,4800,96,$19200\nC-004,Facebook,"Retargeting - Website",$1200,42000,2100,84,$8400\nC-005,LinkedIn,"Decision Makers - SaaS",$4500,18000,720,36,$14400\nC-006,Google Ads,"Display - Remarketing",$800,95000,1200,24,$2400', created_at: new Date(2026, 3, 16, 2, 1) },
      ] }],
    },
    {
      task_id: 't7-2', title: 'Calculate ROAS per Campaign', description: 'Compute return on ad spend and CPA for each campaign.', assignee_type: 'agent', assignee_name: 'Analytics Agent', status: 'Complete', depends_on: ['t7-1'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '02:10', platform: null, tags: ['analytics', 'roas'], estimated_effort: '3m', completion_notes: 'Average ROAS: 3.2x', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json', 'image'], description: 'ROAS breakdown and visualization' },
      run_outputs: [{ run_id: 'run-a7-001', run_timestamp: new Date(2026, 3, 16, 2, 5), outputs: [
        { file_id: 'f7-2a', filename: 'roas-breakdown.json', file_type: 'json', mime_type: 'application/json', size_bytes: 3100, preview_url: null, content_preview: '{\n  "summary": {\n    "total_spend": 13950,\n    "total_revenue": 61400,\n    "overall_roas": 4.4,\n    "total_conversions": 410,\n    "avg_cpa": 34.02\n  },\n  "campaigns": [\n    { "id": "C-001", "name": "Brand Search - US", "roas": 5.22, "cpa": 19.14, "status": "top_performer" },\n    { "id": "C-003", "name": "Lookalike - Enterprise", "roas": 6.0, "cpa": 33.33, "status": "top_performer" },\n    { "id": "C-005", "name": "Decision Makers - SaaS", "roas": 3.2, "cpa": 125.0, "status": "moderate" },\n    { "id": "C-002", "name": "Competitor Keywords", "roas": 2.33, "cpa": 42.86, "status": "underperformer" },\n    { "id": "C-006", "name": "Display - Remarketing", "roas": 3.0, "cpa": 33.33, "status": "moderate" }\n  ]\n}', created_at: new Date(2026, 3, 16, 2, 5) },
        { file_id: 'f7-2b', filename: 'roas-chart.png', file_type: 'image', mime_type: 'image/png', size_bytes: 186000, preview_url: 'https://images.unsplash.com/photo-1759661966728-4a02e3c6ed91?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkYXRhJTIwYW5hbHl0aWNzJTIwZGFzaGJvYXJkJTIwY2hhcnR8ZW58MXx8fHwxNzc2NDA1Mjc2fDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral', content_preview: null, created_at: new Date(2026, 3, 16, 2, 5) },
      ] }],
    },
    {
      task_id: 't7-3', title: 'Generate Reallocation Plan', description: 'Shift budget from underperformers to top performers.', assignee_type: 'agent', assignee_name: 'Budget Agent', status: 'Awaiting Approval', depends_on: ['t7-2'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '02:15', platform: null, tags: ['budget', 'optimization'], estimated_effort: '5m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['csv'], description: 'Budget reallocation recommendations' },
      run_outputs: [],
    },
    {
      task_id: 't7-4', title: 'Apply Budget Changes', description: 'Push updated budgets to ad platform APIs.', assignee_type: 'agent', assignee_name: 'Budget Agent', status: 'Draft', depends_on: ['t7-3'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '02:20', platform: 'Google Ads', tags: ['budget', 'api'], estimated_effort: '3m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'API response confirmations' },
      run_outputs: [],
    },
    {
      task_id: 't7-5', title: 'Send Summary to Slack', description: 'Post a summary of changes to the #marketing-ops Slack channel.', assignee_type: 'agent', assignee_name: 'Notification Agent', status: 'Draft', depends_on: ['t7-4'], cost: 0, due_date: new Date(2026, 1, 14), launch_time_utc: '02:25', platform: null, tags: ['notification', 'slack'], estimated_effort: '1m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['text'], description: 'Slack message content' },
      run_outputs: [],
    },
  ],
};

// ─── Mock schedules per automation ───

const automationSchedules: Record<string, AutomationSchedule> = {
  '4': {
    enabled: true,
    frequency: 'weekly',
    days_of_week: [1], // Monday
    day_of_month: null,
    time_utc: '08:00',
    cron_expression: null,
    run_date: null,
    next_run: null,
    last_run: new Date(2026, 3, 14, 8, 0),
  },
  '5': {
    enabled: true,
    frequency: 'weekly',
    days_of_week: [1, 3, 5], // Mon, Wed, Fri
    day_of_month: null,
    time_utc: '10:00',
    cron_expression: null,
    run_date: null,
    next_run: null,
    last_run: new Date(2026, 3, 16, 10, 0),
  },
  '6': {
    enabled: true,
    frequency: 'daily',
    days_of_week: [],
    day_of_month: null,
    time_utc: '06:00',
    cron_expression: null,
    run_date: null,
    next_run: null,
    last_run: new Date(2026, 3, 17, 6, 0),
  },
  '7': {
    enabled: true,
    frequency: 'weekly',
    days_of_week: [0, 3], // Sun, Wed
    day_of_month: null,
    time_utc: '02:00',
    cron_expression: null,
    run_date: null,
    next_run: null,
    last_run: new Date(2026, 3, 16, 2, 0),
  },
};

// Build a default task set for any automation without specific mock data
function generateDefaultTasks(automationId: string): AutomationTask[] {
  const prefix = `t${automationId}`;
  return [
    {
      task_id: `${prefix}-1`, title: 'Initialize', description: 'Gather inputs and validate configuration.', assignee_type: 'agent', assignee_name: 'Orchestrator Agent', status: 'Complete', depends_on: [], cost: 0, due_date: new Date(2026, 2, 1), launch_time_utc: '09:00', platform: null, tags: ['setup'], estimated_effort: '2m', completion_notes: 'Ready.', revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'Configuration validation result' }, run_outputs: [],
    },
    {
      task_id: `${prefix}-2`, title: 'Process Data', description: 'Run the core processing logic.', assignee_type: 'agent', assignee_name: 'Processing Agent', status: 'Approved', depends_on: [`${prefix}-1`], cost: 10, due_date: new Date(2026, 2, 2), launch_time_utc: '10:00', platform: null, tags: ['processing'], estimated_effort: '15m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['csv'], description: 'Processed data output' }, run_outputs: [],
    },
    {
      task_id: `${prefix}-3`, title: 'Quality Check', description: 'Validate output against quality rules.', assignee_type: 'agent', assignee_name: 'QA Agent', status: 'Draft', depends_on: [`${prefix}-2`], cost: 0, due_date: new Date(2026, 2, 3), launch_time_utc: '11:00', platform: null, tags: ['qa'], estimated_effort: '5m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['json'], description: 'QA validation report' }, run_outputs: [],
    },
    {
      task_id: `${prefix}-4`, title: 'Human Review', description: 'A team member reviews the final output.', assignee_type: 'human', assignee_name: 'Alex Rivera', status: 'Draft', depends_on: [`${prefix}-3`], cost: 25, due_date: new Date(2026, 2, 4), launch_time_utc: '14:00', platform: null, tags: ['review'], estimated_effort: '20m', completion_notes: null, revision_comment: null,
      output_config: null, run_outputs: [],
    },
    {
      task_id: `${prefix}-5`, title: 'Deploy & Notify', description: 'Push results and send notification.', assignee_type: 'agent', assignee_name: 'Deploy Agent', status: 'Draft', depends_on: [`${prefix}-4`], cost: 0, due_date: new Date(2026, 2, 5), launch_time_utc: '15:00', platform: null, tags: ['deploy'], estimated_effort: '3m', completion_notes: null, revision_comment: null,
      output_config: { enabled: true, expected_file_types: ['text'], description: 'Deployment notification' }, run_outputs: [],
    },
  ];
}

export function getAutomationDetail(automationId: string): AutomationDetail {
  const tasks = automationTaskSets[automationId] ?? generateDefaultTasks(automationId);
  const schedule = automationSchedules[automationId]
    ? { ...automationSchedules[automationId], next_run: computeNextRun(automationSchedules[automationId]) }
    : createDefaultSchedule();
  return { automationId, tasks, schedule };
}