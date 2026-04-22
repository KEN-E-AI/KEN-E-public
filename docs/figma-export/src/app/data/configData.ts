/* ========== Config Page Data & Types ========== */

/* --- CLV --- */
export interface ClvConfig {
  value: number | null; // null = not configured
}

export const MOCK_CLV: ClvConfig = { value: 4200 };

/* --- Funnel Stage Mapping --- */
export interface KpiOption {
  id: string;
  name: string;
  dataSource: string;
  noData?: boolean;
}

export interface FunnelStageRow {
  stage: string;
  kpiId: string;
}

export const AVAILABLE_KPIS: KpiOption[] = [
  { id: 'kpi-1', name: 'Unbranded Search Volume', dataSource: 'raw_unbranded_search' },
  { id: 'kpi-2', name: 'Branded Search Volume', dataSource: 'raw_branded_search' },
  { id: 'kpi-3', name: 'PDP Views', dataSource: 'raw_pdp_views' },
  { id: 'kpi-4', name: 'First-Time Account Opens', dataSource: 'raw_account_opens' },
  { id: 'kpi-5', name: 'App Installs', dataSource: 'raw_app_installs', noData: true },
  { id: 'kpi-6', name: 'Newsletter Signups', dataSource: 'raw_newsletter_signups' },
  { id: 'kpi-7', name: 'Demo Requests', dataSource: 'raw_demo_requests', noData: true },
];

export const MOCK_FUNNEL_MAPPING: FunnelStageRow[] = [
  { stage: 'Problem Awareness', kpiId: 'kpi-1' },
  { stage: 'Brand Awareness', kpiId: 'kpi-2' },
  { stage: 'Consideration', kpiId: 'kpi-3' },
  { stage: 'Conversion', kpiId: 'kpi-4' },
];

/* --- Exogenous Events --- */
export type ExpectedDirection = 'positive' | 'negative' | 'none';

export interface ExogenousEvent {
  id: string;
  startDate: string; // ISO date string
  endDate: string;
  label: string;
  category: string;
  expectedDirection: ExpectedDirection;
}

export interface CategoryStatus {
  category: string;
  eventCount: number;
  isActive: boolean; // >= 5 events
  isCampaign?: boolean;
  coversFullTrainingPeriod?: boolean;
}

export const MOCK_CATEGORY_STATUS: CategoryStatus[] = [
  { category: 'campaign', eventCount: 8, isActive: true, isCampaign: true },
  { category: 'seasonal', eventCount: 6, isActive: true },
  { category: 'competitor', eventCount: 3, isActive: false },
];

export const MOCK_EVENTS: ExogenousEvent[] = [
  { id: 'ev-1', startDate: '2025-11-20', endDate: '2025-12-02', label: 'Black Friday', category: 'seasonal', expectedDirection: 'positive' },
  { id: 'ev-2', startDate: '2025-12-20', endDate: '2026-01-05', label: 'Holiday Season', category: 'seasonal', expectedDirection: 'positive' },
  { id: 'ev-3', startDate: '2026-01-15', endDate: '2026-01-22', label: 'Competitor Product Launch', category: 'competitor', expectedDirection: 'negative' },
  { id: 'ev-4', startDate: '2026-02-01', endDate: '2026-02-14', label: "Valentine's Day Promo", category: 'seasonal', expectedDirection: 'positive' },
  { id: 'ev-5', startDate: '2026-03-01', endDate: '2026-03-07', label: 'Industry Conference', category: 'competitor', expectedDirection: 'positive' },
  { id: 'ev-6', startDate: '2025-09-01', endDate: '2025-09-30', label: 'Back to School', category: 'seasonal', expectedDirection: 'positive' },
  { id: 'ev-7', startDate: '2025-10-10', endDate: '2025-10-17', label: 'Competitor Price Drop', category: 'competitor', expectedDirection: 'negative' },
  { id: 'ev-8', startDate: '2025-07-01', endDate: '2025-07-07', label: 'Summer Slowdown', category: 'seasonal', expectedDirection: 'negative' },
  { id: 'ev-9', startDate: '2025-08-15', endDate: '2025-08-22', label: 'Market Disruption', category: 'competitor', expectedDirection: 'none' },
];

export const KNOWN_CATEGORIES = ['campaign', 'seasonal', 'competitor'];

/* --- Auto-Detected Thresholds --- */
export type ThresholdMethod = 'percentage above median' | 'sd bands' | 'iqr';
export type MethodLabel = '% Above Median' | 'SD Bands' | 'IQR';

export interface ThresholdRow {
  id: string;
  funnelStep: string;
  channelName: string;
  channelSlug: string;
  method: ThresholdMethod;
  thresholdPct: number;
  rolling: string; // 'Static' or e.g. '12mo'
  lastValue: number | null; // null = '—'
  flag0Coverage: number | null; // null = 'N/A'
  overrideEnabled: boolean;
  override?: {
    method: MethodLabel;
    thresholdPct: number;
    rollingMedian: 'Static' | 'Rolling';
    windowMonths: number;
  };
  autoDetected: {
    method: ThresholdMethod;
    thresholdPct: number;
    rolling: string;
    coverage: number;
  };
}

export const MOCK_THRESHOLDS: ThresholdRow[] = [
  {
    id: 'th-1', funnelStep: 'Problem Awareness', channelName: 'Paid Search', channelSlug: 'paid_search',
    method: 'percentage above median', thresholdPct: 35.0, rolling: '12mo', lastValue: 12500,
    flag0Coverage: 32.5, overrideEnabled: false,
    autoDetected: { method: 'percentage above median', thresholdPct: 35.0, rolling: '12mo', coverage: 32.5 },
  },
  {
    id: 'th-2', funnelStep: 'Problem Awareness', channelName: 'Social Media', channelSlug: 'social_media',
    method: 'sd bands', thresholdPct: 28.5, rolling: 'Static', lastValue: 8200,
    flag0Coverage: 45.2, overrideEnabled: false,
    autoDetected: { method: 'sd bands', thresholdPct: 28.5, rolling: 'Static', coverage: 45.2 },
  },
  {
    id: 'th-3', funnelStep: 'Brand Awareness', channelName: 'Paid Search', channelSlug: 'paid_search',
    method: 'percentage above median', thresholdPct: 40.2, rolling: '12mo', lastValue: 15000,
    flag0Coverage: 35.1, overrideEnabled: true,
    override: { method: '% Above Median', thresholdPct: 42.0, rollingMedian: 'Rolling', windowMonths: 12 },
    autoDetected: { method: 'percentage above median', thresholdPct: 40.2, rolling: '12mo', coverage: 35.1 },
  },
  {
    id: 'th-4', funnelStep: 'Brand Awareness', channelName: 'Display', channelSlug: 'display',
    method: 'iqr', thresholdPct: 22.0, rolling: 'Static', lastValue: 5800,
    flag0Coverage: 18.5, overrideEnabled: false,
    autoDetected: { method: 'iqr', thresholdPct: 22.0, rolling: 'Static', coverage: 18.5 },
  },
];

/* --- Marketing Channels --- */
export interface ChannelCoverageRow {
  id: string;
  channelName: string;
  channelSlug: string;
  coverage: Record<string, { observed: number; required: number } | null>; // keyed by funnel stage
  overall: 'Pass' | 'Insufficient';
  excluded: boolean;
}

export const TRAINING_MONTHS = 24;
export const MIN_MONTHLY_OBS = 3;

export const MOCK_CHANNEL_COVERAGE: ChannelCoverageRow[] = [
  {
    id: 'cc-1', channelName: 'Paid Search', channelSlug: 'paid_search',
    coverage: {
      'Problem Awareness': { observed: 8, required: 3 },
      'Brand Awareness': { observed: 7, required: 3 },
      'Consideration': { observed: 5, required: 3 },
      'Conversion': { observed: 4, required: 3 },
    },
    overall: 'Pass', excluded: false,
  },
  {
    id: 'cc-2', channelName: 'Social Media', channelSlug: 'social_media',
    coverage: {
      'Problem Awareness': { observed: 6, required: 3 },
      'Brand Awareness': { observed: 5, required: 3 },
      'Consideration': { observed: 3, required: 3 },
      'Conversion': { observed: 2, required: 3 },
    },
    overall: 'Insufficient', excluded: false,
  },
  {
    id: 'cc-3', channelName: 'Display', channelSlug: 'display',
    coverage: {
      'Problem Awareness': { observed: 4, required: 3 },
      'Brand Awareness': { observed: 3, required: 3 },
      'Consideration': null,
      'Conversion': null,
    },
    overall: 'Insufficient', excluded: false,
  },
  {
    id: 'cc-4', channelName: 'Email', channelSlug: 'email',
    coverage: {
      'Problem Awareness': { observed: 5, required: 3 },
      'Brand Awareness': { observed: 4, required: 3 },
      'Consideration': { observed: 4, required: 3 },
      'Conversion': { observed: 3, required: 3 },
    },
    overall: 'Pass', excluded: false,
  },
  {
    id: 'cc-5', channelName: 'Affiliate', channelSlug: 'affiliate',
    coverage: {
      'Problem Awareness': { observed: 2, required: 3 },
      'Brand Awareness': { observed: 1, required: 3 },
      'Consideration': null,
      'Conversion': null,
    },
    overall: 'Insufficient', excluded: true,
  },
];

export const FUNNEL_STAGES = ['Problem Awareness', 'Brand Awareness', 'Consideration', 'Conversion'];
