import { useState, useCallback, useMemo } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from './ui/accordion';
import { ChevronDown, Plus, Trash2, Save, Pencil, X, Eye } from 'lucide-react';
import { cn } from './ui/utils';
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar, ReferenceLine, Cell } from 'recharts';

/* ---------- Types ---------- */

interface Channel {
  id: string;
  name: string;
  spend: number;
  tacticalPlan: string;
}

interface ExternalFactor {
  id: string;
  description: string;
}

interface FunnelStepData {
  id: string;
  label: string;
  value: number;
  change: number;
  color: string;
  channels: Channel[];
  externalFactors: ExternalFactor[];
}

/* --- Related Metric Types --- */

interface RelatedMetric {
  id: string;
  name: string;
  description: string;
  insight: string;
}

interface MetricMonthData {
  month: string;
  value: number;
}

const AVAILABLE_METRICS: RelatedMetric[] = [
  { id: 'rm-1', name: 'Total Engaged Users from Paid Sources', description: 'The total count of unique first-time visitors to the website/app from paid ads who have not been identified as current customers, and who generated an engaged session.', insight: 'A rising engaged-user count signals that creative and targeting are resonating. When planning future campaigns, prioritize the channels and audiences that drove engaged sessions over raw clicks to improve downstream conversion efficiency.' },
  { id: 'rm-2', name: 'Cost Per Qualified Lead', description: 'Total media spend divided by the number of leads that passed qualification criteria during the reporting period.', insight: 'CPQL reveals the true cost of acquiring sales-ready prospects. If CPQL trends upward, reassess audience targeting or creative fatigue before scaling spend — cheaper leads that never convert waste more budget than fewer, pricier qualified ones.' },
  { id: 'rm-3', name: 'Branded Search Volume', description: 'The total number of organic and paid search queries containing brand terms, measured via Google Search Console and Ads.', insight: 'Branded search is a lagging indicator of upper-funnel investment. A sustained lift here confirms that awareness campaigns are building mental availability — use it to justify continued brand spend even when direct-response metrics plateau.' },
  { id: 'rm-4', name: 'Email Click-Through Rate', description: 'The percentage of delivered marketing emails where the recipient clicked at least one link within the email body.', insight: 'CTR reflects how well subject lines and content match subscriber intent. Declining rates suggest list fatigue or misaligned messaging — segment by engagement recency and test personalized content before reducing send frequency.' },
  { id: 'rm-5', name: 'Return on Ad Spend (ROAS)', description: 'Total attributed revenue divided by total media spend across all paid channels for the reporting period.', insight: 'ROAS is the fastest feedback loop on media efficiency. Use it to shift budget toward high-performing channels mid-flight, but remember that last-click ROAS under-credits upper-funnel activity — pair it with assisted-conversion data for a fuller picture.' },
  { id: 'rm-6', name: 'Landing Page Conversion Rate', description: 'The percentage of landing page sessions that resulted in a completed form submission or sign-up action.', insight: 'Even small conversion-rate gains compound into significant lead volume. Prioritize A/B testing page headlines, form length, and social proof elements before investing more in driving additional traffic to an under-performing page.' },
  { id: 'rm-7', name: 'Social Media Engagement Rate', description: 'Total interactions (likes, comments, shares) divided by total impressions across owned social media channels.', insight: 'High engagement signals content relevance and algorithmic favor, which reduces future distribution costs. Track which content formats (video, carousel, polls) drive the most shares to inform the organic content calendar.' },
  { id: 'rm-8', name: 'Average Session Duration', description: 'The mean time in seconds that users spend on the website per session, excluding bounced sessions.', insight: 'Longer sessions correlate with higher purchase intent and better SEO signals. If duration drops after a site change, investigate navigation friction — users who explore more pages are significantly more likely to convert.' },
  { id: 'rm-9', name: 'Customer Acquisition Cost', description: 'Total marketing and sales spend divided by the number of new customers acquired during the period.', insight: 'CAC sets the ceiling for sustainable growth. Compare it against customer lifetime value (LTV) to ensure each acquisition is profitable — if CAC exceeds 30% of LTV, explore retention and referral programs to improve unit economics.' },
  { id: 'rm-10', name: 'Pipeline Velocity', description: 'The average number of days from first marketing touch to closed-won deal across all attributed opportunities.', insight: 'Faster pipeline velocity means revenue arrives sooner and forecasts become more reliable. Identify which nurture sequences and content pieces accelerate deals, then double down on those assets in future campaigns.' },
  { id: 'rm-11', name: 'Content Download Rate', description: 'The percentage of content landing page visitors who completed a gated content download during the period.', insight: 'Download rate measures how compelling your thought-leadership offer is relative to the friction of a form. Low rates suggest the perceived value doesn\'t justify the ask — test ungated previews or shorter forms to lift volume.' },
  { id: 'rm-12', name: 'Net Promoter Score (NPS)', description: 'The difference between the percentage of promoters and detractors from the latest quarterly customer survey.', insight: 'NPS is a leading indicator of organic growth through word-of-mouth. A declining score should trigger immediate investigation into product or service issues before amplifying acquisition spend that brings in customers likely to churn.' },
  { id: 'rm-13', name: 'Video Completion Rate', description: 'The percentage of video ad impressions where the viewer watched at least 75% of the video content.', insight: 'Completion rate reveals whether creative storytelling holds attention. Use it to identify the optimal video length for each platform and to build retargeting audiences from high-completion viewers who are primed for mid-funnel messaging.' },
  { id: 'rm-14', name: 'Share of Voice', description: 'The brand\'s percentage of total category mentions across social media, news, and review sites during the period.', insight: 'Share of Voice is a strong predictor of future market share. When SOV exceeds share of market, growth tends to follow — use this metric to benchmark competitive positioning and justify sustained investment in brand-building.' },
  { id: 'rm-15', name: 'Cart Abandonment Rate', description: 'The percentage of users who added items to their cart but did not complete the checkout process.', insight: 'High abandonment often points to checkout friction, unexpected costs, or missing trust signals rather than lack of purchase intent. Implement exit-intent offers, transparent pricing, and remarketing sequences to recover this high-intent audience.' },
  { id: 'rm-16', name: 'Organic Traffic Growth', description: 'Month-over-month percentage change in sessions from organic search sources, excluding branded queries.', insight: 'Steady organic growth reduces dependency on paid channels and lowers blended CAC over time. Invest in evergreen SEO content that compounds — each ranking page becomes a persistent, zero-marginal-cost acquisition channel.' },
];

function generateMetricData(metricId: string, endMonth: number, endYear: number, compareMode: 'mom' | 'yoy' | 'goal' = 'mom'): { currentValue: number; change: number; history: MetricMonthData[] } {
  const idNum = parseInt(metricId.replace('rm-', ''), 10) || 1;
  const baseSeed = endYear * 100 + endMonth + idNum * 777;
  const rand = (i: number) => {
    const x = Math.sin(baseSeed * 9301 + i * 49297 + 233280) * 49297;
    return x - Math.floor(x);
  };

  const baseValue = Math.round(50 + rand(1) * 400);
  const history: MetricMonthData[] = [];

  for (let i = 5; i >= 0; i--) {
    let m = endMonth - i;
    let y = endYear;
    while (m < 0) { m += 12; y -= 1; }
    const variation = 0.7 + rand(i + 10) * 0.6;
    history.push({
      month: `${MONTH_ABBR[m]} ${String(y).slice(2)}`,
      value: Math.round(baseValue * variation),
    });
  }

  const currentValue = history[history.length - 1].value;

  // Compute comparison value based on compareMode
  let compValue: number;
  if (compareMode === 'yoy') {
    // Generate value for same month, prior year
    let compMonth = endMonth;
    let compYear = endYear - 1;
    const compSeed = compYear * 100 + compMonth + idNum * 777;
    const compRand = (i: number) => {
      const x = Math.sin(compSeed * 9301 + i * 49297 + 233280) * 49297;
      return x - Math.floor(x);
    };
    const compBase = Math.round(50 + compRand(1) * 400);
    compValue = Math.round(compBase * (0.7 + compRand(15) * 0.6));
  } else if (compareMode === 'goal') {
    // Goal is a synthetic target ~10-20% above average
    const avg = history.reduce((sum, d) => sum + d.value, 0) / history.length;
    compValue = Math.round(avg * (1.1 + rand(50) * 0.1));
  } else {
    // Month over month: compare to prior month
    compValue = history[history.length - 2].value;
  }

  const change = compValue > 0 ? +((((currentValue - compValue) / compValue) * 100).toFixed(1)) : 0;

  return { currentValue, change, history };
}

/* ---------- Mock Data Generator ---------- */

function generateFunnelData(month: number, year: number): FunnelStepData[] {
  const seed = year * 100 + month;
  const rand = (i: number) => {
    const x = Math.sin(seed * 9301 + i * 49297 + 233280) * 49297;
    return x - Math.floor(x);
  };

  const awareness = Math.round(50000 + rand(10) * 80000);
  const brandAwareness = Math.round(awareness * (0.55 + rand(11) * 0.15));
  const consideration = Math.round(brandAwareness * (0.45 + rand(12) * 0.2));
  const conversion = Math.round(consideration * (0.015 + rand(13) * 0.015));

  return [
    {
      id: 'problem-awareness',
      label: 'Problem Awareness',
      value: awareness,
      change: +((-10 + rand(20) * 20).toFixed(1)),
      color: '#3B82F6',
      channels: [
        { id: 'c1', name: 'Display', spend: Math.round(15000 + rand(30) * 10000), tacticalPlan: 'Broad reach display campaigns targeting finance-interested audiences across premium publisher network.' },
        { id: 'c2', name: 'Paid Social', spend: Math.round(12000 + rand(31) * 8000), tacticalPlan: 'Awareness-stage video ads on Meta and LinkedIn highlighting key pain points.' },
      ],
      externalFactors: [
        { id: 'e1', description: 'Tax season driving increased financial product research behavior.' },
      ],
    },
    {
      id: 'brand-awareness',
      label: 'Brand Awareness',
      value: brandAwareness,
      change: +((-15 + rand(21) * 20).toFixed(1)),
      color: '#6366F1',
      channels: [
        { id: 'c3', name: 'Paid Search', spend: Math.round(20000 + rand(32) * 12000), tacticalPlan: 'Brand keyword campaigns with expanded match to capture adjacent queries.' },
        { id: 'c4', name: 'Paid Social', spend: Math.round(8000 + rand(33) * 6000), tacticalPlan: 'Retargeting carousel ads showcasing product differentiators.' },
        { id: 'c5', name: 'Display', spend: Math.round(5000 + rand(34) * 4000), tacticalPlan: 'Contextual targeting on personal finance and investment sites.' },
      ],
      externalFactors: [
        { id: 'e2', description: 'Competitor launched a major brand campaign in the same period.' },
        { id: 'e3', description: 'Industry conference generated organic brand mentions.' },
      ],
    },
    {
      id: 'consideration',
      label: 'Consideration',
      value: consideration,
      change: +((-10 + rand(22) * 15).toFixed(1)),
      color: '#F59E0B',
      channels: [
        { id: 'c6', name: 'Paid Search', spend: Math.round(25000 + rand(35) * 15000), tacticalPlan: 'Non-brand keyword campaigns with comparison and review intent targeting.' },
        { id: 'c7', name: 'Paid Social', spend: Math.round(10000 + rand(36) * 7000), tacticalPlan: 'Lead-gen forms on Meta with product comparison content offers.' },
      ],
      externalFactors: [
        { id: 'e4', description: 'App store review rating dropped from 4.5 to 4.2 due to a bug in v3.2 release.' },
      ],
    },
    {
      id: 'conversion',
      label: 'Conversion',
      value: conversion,
      change: +((-8 + rand(23) * 12).toFixed(1)),
      color: '#2EC4B6',
      channels: [
        { id: 'c8', name: 'Paid Search', spend: Math.round(18000 + rand(37) * 10000), tacticalPlan: 'High-intent branded and product-specific keyword campaigns with promotional extensions.' },
        { id: 'c9', name: 'Paid Social', spend: Math.round(6000 + rand(38) * 5000), tacticalPlan: 'Dynamic product ads retargeting site visitors who reached the application page.' },
        { id: 'c10', name: 'Display', spend: Math.round(3000 + rand(39) * 3000), tacticalPlan: 'Retargeting display ads with limited-time offer messaging for abandoned applications.' },
      ],
      externalFactors: [
        { id: 'e5', description: 'Federal holiday weekend reduced weekday conversion volume by an estimated 12%.' },
      ],
    },
  ];
}

function formatValue(val: number): string {
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
  if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
  return val.toString();
}

function formatCurrency(val: number): string {
  return `$${val.toLocaleString()}`;
}

let nextId = 100;
function uid() {
  return `gen-${nextId++}`;
}

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Generate 13 months of KPI trend data ending at the given month/year for a funnel step */
function generateStepTrend(stepId: string, endMonth: number, endYear: number): { name: string; value: number }[] {
  const points: { name: string; value: number }[] = [];
  for (let i = 12; i >= 0; i--) {
    let m = endMonth - i;
    let y = endYear;
    while (m < 0) { m += 12; y -= 1; }

    const seed = y * 100 + m;
    const rand = (j: number) => {
      const x = Math.sin(seed * 9301 + j * 49297 + 233280) * 49297;
      return x - Math.floor(x);
    };

    const awareness = Math.round(50000 + rand(10) * 80000);
    const brandAwareness = Math.round(awareness * (0.55 + rand(11) * 0.15));
    const consideration = Math.round(brandAwareness * (0.45 + rand(12) * 0.2));
    const conversion = Math.round(consideration * (0.015 + rand(13) * 0.015));

    let value: number;
    switch (stepId) {
      case 'problem-awareness': value = awareness; break;
      case 'brand-awareness': value = brandAwareness; break;
      case 'consideration': value = consideration; break;
      case 'conversion': value = conversion; break;
      default: value = awareness;
    }

    points.push({ name: `${MONTH_ABBR[m]} ${String(y).slice(2)}`, value });
  }
  return points;
}

/* ---------- Main Component ---------- */

function generateSummary(funnelData: FunnelStepData[], month: number, year: number): string {
  const monthName = MONTH_ABBR[month];
  const topStep = funnelData.reduce((best, s) => (s.change > best.change ? s : best), funnelData[0]);
  const weakStep = funnelData.reduce((worst, s) => (s.change < worst.change ? s : worst), funnelData[0]);
  const totalSpend = funnelData.reduce((sum, s) => sum + s.channels.reduce((cs, c) => cs + c.spend, 0), 0);
  const conversionStep = funnelData.find((s) => s.id === 'conversion');
  const awarenessStep = funnelData.find((s) => s.id === 'problem-awareness');

  const parts: string[] = [];
  parts.push(`In ${monthName} ${year}, total media investment was ${formatCurrency(totalSpend)} across ${funnelData.reduce((n, s) => n + s.channels.length, 0)} active channel activations.`);

  if (awarenessStep) {
    parts.push(`Top-of-funnel Problem Awareness reached ${formatValue(awarenessStep.value)} (${awarenessStep.change >= 0 ? '+' : ''}${awarenessStep.change}%), narrowing to ${conversionStep ? formatValue(conversionStep.value) : 'N/A'} conversions at the bottom of the funnel.`);
  }

  if (topStep.change > 0) {
    parts.push(`${topStep.label} was the strongest stage with a ${topStep.change}% lift, suggesting that ${topStep.channels[0]?.name || 'key channel'} investments are paying off.`);
  }

  if (weakStep.change < 0) {
    parts.push(`${weakStep.label} saw the largest decline at ${weakStep.change}%, which may be attributed to ${weakStep.externalFactors[0]?.description?.toLowerCase() || 'market headwinds that warrant further investigation'}.`);
  }

  parts.push('Review the funnel stages below for channel-level detail and external factors.');

  return parts.join(' ');
}

export function WhatHappenedCard({ month, year, compareMode = 'mom' }: { month: number; year: number; compareMode?: 'mom' | 'yoy' | 'goal' }) {
  const [funnelData, setFunnelData] = useState<FunnelStepData[]>(() => generateFunnelData(month, year));
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [savedData, setSavedData] = useState<FunnelStepData[] | null>(null);
  const [selectedMetricIds, setSelectedMetricIds] = useState<string[]>(() =>
    AVAILABLE_METRICS.slice(0, 6).map((m) => m.id)
  );
  const [editingMetrics, setEditingMetrics] = useState(false);
  const [savedMetricIds, setSavedMetricIds] = useState<string[] | null>(null);

  // Regenerate when month/year changes
  const key = `${month}-${year}`;
  const [prevKey, setPrevKey] = useState(key);
  if (key !== prevKey) {
    setPrevKey(key);
    const newData = generateFunnelData(month, year);
    setFunnelData(newData);
    setSavedData(null);
    setEditingStepId(null);
  }

  const handleEdit = (stepId: string) => {
    setSavedData(JSON.parse(JSON.stringify(funnelData)));
    setEditingStepId(stepId);
  };

  const handleCancel = () => {
    if (savedData) setFunnelData(savedData);
    setSavedData(null);
    setEditingStepId(null);
  };

  const handleSave = () => {
    setSavedData(null);
    setEditingStepId(null);
  };

  const updateStep = useCallback((stepId: string, updater: (step: FunnelStepData) => FunnelStepData) => {
    setFunnelData((prev) => prev.map((s) => (s.id === stepId ? updater(s) : s)));
  }, []);

  const maxValue = Math.max(...funnelData.map((s) => s.value));

  const summary = useMemo(() => generateSummary(funnelData, month, year), [funnelData, month, year]);

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-5">
        <h2>What Happened</h2>
      </div>

      {/* Key Takeaways Summary */}
      <div className="mb-5 rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-4">
        <h4 className="text-xs text-muted-foreground tracking-wide uppercase mb-2">Key Takeaways</h4>
        <p className="text-sm text-[var(--color-text-primary)] leading-relaxed">{summary}</p>
      </div>

      <Accordion type="single" collapsible>
        {funnelData.map((step, index) => (
          <FunnelRow
            key={step.id}
            step={step}
            index={index}
            total={funnelData.length}
            maxValue={maxValue}
            editing={editingStepId === step.id}
            onUpdate={updateStep}
            onEdit={() => handleEdit(step.id)}
            onCancel={handleCancel}
            onSave={handleSave}
            month={month}
            year={year}
          />
        ))}
      </Accordion>

      {/* Related Metrics Section */}
      <RelatedMetricsSection
        selectedMetricIds={selectedMetricIds}
        setSelectedMetricIds={setSelectedMetricIds}
        editingMetrics={editingMetrics}
        setEditingMetrics={setEditingMetrics}
        savedMetricIds={savedMetricIds}
        setSavedMetricIds={setSavedMetricIds}
        month={month}
        year={year}
        compareMode={compareMode}
      />
    </Card>
  );
}

/* ---------- Funnel Row ---------- */

function FunnelRow({
  step,
  index,
  total,
  maxValue,
  editing,
  onUpdate,
  onEdit,
  onCancel,
  onSave,
  month,
  year,
}: {
  step: FunnelStepData;
  index: number;
  total: number;
  maxValue: number;
  editing: boolean;
  onUpdate: (id: string, updater: (s: FunnelStepData) => FunnelStepData) => void;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  month: number;
  year: number;
}) {
  // Funnel widths: top is 100%, bottom narrows
  const topWidthPercent = 100 - (index / total) * 55;
  const bottomWidthPercent = 100 - ((index + 1) / total) * 55;

  return (
    <AccordionItem value={step.id} className="border-b-0 mb-1">
      <AccordionTrigger className="py-2 hover:no-underline">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Funnel shape */}
          <div className="w-1/2 shrink-0 flex flex-col items-center">
            <div
              className="relative flex items-center justify-center"
              style={{
                width: `${topWidthPercent}%`,
                minHeight: '40px',
                clipPath: `polygon(${((100 - topWidthPercent) / 2)}% 0%, ${100 - ((100 - topWidthPercent) / 2)}% 0%, ${100 - ((100 - bottomWidthPercent) / 2)}% 100%, ${((100 - bottomWidthPercent) / 2)}% 100%)`,
                backgroundColor: step.color,
                opacity: 0.85,
              }}
            >
              <span className="text-white text-xs relative z-10">{formatValue(step.value)}</span>
            </div>
          </div>

          {/* Label + stats */}
          <div className="flex flex-col items-start min-w-0">
            <span className="text-sm">{step.label}</span>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">{formatValue(step.value)}</span>
              <span className={step.change >= 0 ? 'text-green-500' : 'text-red-500'}>
                {step.change >= 0 ? '+' : ''}{step.change}%
              </span>
            </div>
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent className="pt-2 pb-4 pl-44">
        <div className="space-y-5">
          {/* 13-Month Trendline */}
          <StepTrendChart stepId={step.id} stepColor={step.color} month={month} year={year} />

          {/* Edit Memory Controls */}
          <div className="flex items-center gap-2">
            {editing ? (
              <>
                <Button size="sm" variant="outline" onClick={onCancel}>
                  <X className="size-3 mr-1" /> Cancel
                </Button>
                <Button size="sm" variant="default" onClick={onSave}>
                  <Save className="size-3 mr-1" /> Save
                </Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={onEdit}>
                <Pencil className="size-3 mr-1" /> Edit Memory
              </Button>
            )}
          </div>

          {/* Channels Activated */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs text-muted-foreground tracking-wide uppercase">Channels Activated</h4>
              {editing && (
                <button
                  onClick={() =>
                    onUpdate(step.id, (s) => ({
                      ...s,
                      channels: [
                        ...s.channels,
                        { id: uid(), name: '', spend: 0, tacticalPlan: '' },
                      ],
                    }))
                  }
                  className="text-xs text-violet-500 hover:text-violet-600 flex items-center gap-0.5 cursor-pointer"
                >
                  <Plus className="size-3" /> Add Channel
                </button>
              )}
            </div>

            <div className="space-y-3">
              {step.channels.map((channel) => (
                <ChannelItem
                  key={channel.id}
                  channel={channel}
                  editing={editing}
                  onChange={(updated) =>
                    onUpdate(step.id, (s) => ({
                      ...s,
                      channels: s.channels.map((c) => (c.id === channel.id ? updated : c)),
                    }))
                  }
                  onRemove={() =>
                    onUpdate(step.id, (s) => ({
                      ...s,
                      channels: s.channels.filter((c) => c.id !== channel.id),
                    }))
                  }
                />
              ))}
            </div>
          </div>

          {/* External Factors */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs text-muted-foreground tracking-wide uppercase">External Factors</h4>
              {editing && (
                <button
                  onClick={() =>
                    onUpdate(step.id, (s) => ({
                      ...s,
                      externalFactors: [
                        ...s.externalFactors,
                        { id: uid(), description: '' },
                      ],
                    }))
                  }
                  className="text-xs text-violet-500 hover:text-violet-600 flex items-center gap-0.5 cursor-pointer"
                >
                  <Plus className="size-3" /> Add Factor
                </button>
              )}
            </div>

            <div className="space-y-2">
              {step.externalFactors.map((factor) => (
                <div key={factor.id} className="flex items-start gap-2">
                  {editing ? (
                    <>
                      <textarea
                        className="flex-1 text-xs p-2.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
                        rows={2}
                        value={factor.description}
                        placeholder="Describe the external factor..."
                        onChange={(e) =>
                          onUpdate(step.id, (s) => ({
                            ...s,
                            externalFactors: s.externalFactors.map((f) =>
                              f.id === factor.id ? { ...f, description: e.target.value } : f
                            ),
                          }))
                        }
                      />
                      <button
                        onClick={() =>
                          onUpdate(step.id, (s) => ({
                            ...s,
                            externalFactors: s.externalFactors.filter((f) => f.id !== factor.id),
                          }))
                        }
                        className="text-red-400 hover:text-red-500 mt-1 cursor-pointer"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </>
                  ) : (
                    <div className="text-xs p-2.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] w-full">
                      {factor.description || <span className="text-muted-foreground italic">No description</span>}
                    </div>
                  )}
                </div>
              ))}
              {step.externalFactors.length === 0 && !editing && (
                <p className="text-xs text-muted-foreground italic">No external factors recorded.</p>
              )}
            </div>
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}

/* ---------- Channel Item ---------- */

function ChannelItem({
  channel,
  editing,
  onChange,
  onRemove,
}: {
  channel: Channel;
  editing: boolean;
  onChange: (c: Channel) => void;
  onRemove: () => void;
}) {
  if (editing) {
    return (
      <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] space-y-2">
        <div className="flex items-center gap-2">
          <input
            type="text"
            className="flex-1 text-xs p-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
            placeholder="Channel name"
            value={channel.name}
            onChange={(e) => onChange({ ...channel, name: e.target.value })}
          />
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">$</span>
            <input
              type="number"
              className="w-24 text-xs p-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
              placeholder="Spend"
              value={channel.spend || ''}
              onChange={(e) => onChange({ ...channel, spend: Number(e.target.value) })}
            />
          </div>
          <button onClick={onRemove} className="text-red-400 hover:text-red-500 cursor-pointer">
            <Trash2 className="size-3.5" />
          </button>
        </div>
        <textarea
          className="w-full text-xs p-2 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
          rows={2}
          placeholder="Describe the tactical plan..."
          value={channel.tacticalPlan}
          onChange={(e) => onChange({ ...channel, tacticalPlan: e.target.value })}
        />
      </div>
    );
  }

  return (
    <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs">{channel.name || <span className="italic text-muted-foreground">Unnamed</span>}</span>
        <Badge variant="outline" className="text-[11px]">
          {formatCurrency(channel.spend)}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        {channel.tacticalPlan || <span className="italic">No tactical plan described.</span>}
      </p>
    </div>
  );
}

/* ---------- Step Trend Chart ---------- */

function StepTrendChart({ stepId, stepColor, month, year }: { stepId: string; stepColor: string; month: number; year: number }) {
  const trendData = useMemo(() => generateStepTrend(stepId, month, year), [stepId, month, year]);

  return (
    <div className="rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-3">
      <h4 className="text-xs text-muted-foreground tracking-wide uppercase mb-2">13-Month Trend</h4>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={trendData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid key="grid" strokeDasharray="3 3" stroke="var(--color-border-default)" />
          <XAxis
            key="xaxis"
            dataKey="name"
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            stroke="var(--color-border-strong)"
            tickLine={false}
            interval={1}
          />
          <YAxis
            key="yaxis"
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            stroke="var(--color-border-strong)"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatValue(v)}
          />
          <Tooltip
            key="tooltip"
            contentStyle={{
              backgroundColor: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border-default)',
              borderRadius: 'var(--radius-md)',
              fontSize: 11,
            }}
            formatter={(value: number) => [formatValue(value), 'Value']}
          />
          <Line
            key="line"
            type="monotone"
            dataKey="value"
            stroke={stepColor}
            strokeWidth={2}
            dot={{ r: 2.5, strokeWidth: 1.5, fill: 'var(--color-bg-elevated)' }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------- Related Metrics Section ---------- */

function RelatedMetricsSection({
  selectedMetricIds,
  setSelectedMetricIds,
  editingMetrics,
  setEditingMetrics,
  savedMetricIds,
  setSavedMetricIds,
  month,
  year,
  compareMode,
}: {
  selectedMetricIds: string[];
  setSelectedMetricIds: (ids: string[]) => void;
  editingMetrics: boolean;
  setEditingMetrics: (editing: boolean) => void;
  savedMetricIds: string[] | null;
  setSavedMetricIds: (ids: string[] | null) => void;
  month: number;
  year: number;
  compareMode: 'mom' | 'yoy' | 'goal';
}) {
  const handleEditMetrics = () => {
    setSavedMetricIds([...selectedMetricIds]);
    setEditingMetrics(true);
  };

  const handleCancelMetrics = () => {
    if (savedMetricIds) setSelectedMetricIds(savedMetricIds);
    setSavedMetricIds(null);
    setEditingMetrics(false);
  };

  const handleSaveMetrics = () => {
    setSavedMetricIds(null);
    setEditingMetrics(false);
  };

  const toggleMetric = (metricId: string) => {
    if (selectedMetricIds.includes(metricId)) {
      setSelectedMetricIds(selectedMetricIds.filter((id) => id !== metricId));
    } else if (selectedMetricIds.length < 12) {
      setSelectedMetricIds([...selectedMetricIds, metricId]);
    }
  };

  const selectedMetrics = selectedMetricIds
    .map((id) => AVAILABLE_METRICS.find((m) => m.id === id))
    .filter(Boolean) as RelatedMetric[];

  return (
    <div className="mt-6 pt-6 border-t border-[var(--color-border-default)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm">Related Insights</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {selectedMetrics.length} of 12 metrics tracked
          </p>
        </div>
        <div className="flex items-center gap-2">
          {editingMetrics ? (
            <>
              <Button size="sm" variant="outline" onClick={handleCancelMetrics}>
                <X className="size-3 mr-1" /> Cancel
              </Button>
              <Button size="sm" variant="default" onClick={handleSaveMetrics}>
                <Save className="size-3 mr-1" /> Save
              </Button>
            </>
          ) : (
            <Button size="sm" variant="outline" onClick={handleEditMetrics}>
              <Pencil className="size-3 mr-1" /> Edit
            </Button>
          )}
        </div>
      </div>

      {/* Edit mode: show all available metrics as a checklist */}
      {editingMetrics && (
        <div className="mb-5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-4">
          <p className="text-xs text-muted-foreground mb-3">
            Select up to 12 metrics to track. {selectedMetricIds.length}/12 selected.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {AVAILABLE_METRICS.map((metric) => {
              const isSelected = selectedMetricIds.includes(metric.id);
              const isDisabled = !isSelected && selectedMetricIds.length >= 12;
              return (
                <label
                  key={metric.id}
                  className={cn(
                    'flex items-start gap-2.5 p-2.5 rounded-[var(--radius-sm)] border cursor-pointer transition-colors',
                    isSelected
                      ? 'border-[var(--color-violet-400)] bg-[var(--color-violet-100)]'
                      : 'border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] hover:bg-[var(--color-bg-primary)]',
                    isDisabled && 'opacity-40 cursor-not-allowed'
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-[var(--color-violet-500)]"
                    checked={isSelected}
                    disabled={isDisabled}
                    onChange={() => toggleMetric(metric.id)}
                  />
                  <div className="min-w-0">
                    <span className="text-xs">{metric.name}</span>
                    <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">{metric.description}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Metric cards grid */}
      {selectedMetrics.length > 0 ? (
        <div className="grid grid-cols-3 gap-3">
          {selectedMetrics.map((metric) => (
            <RelatedMetricCard key={metric.id} metric={metric} month={month} year={year} compareMode={compareMode} />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-xs text-muted-foreground italic">
          No related metrics selected. Click "Edit" to add metrics.
        </div>
      )}
    </div>
  );
}

/* ---------- Related Metric Card ---------- */

function RelatedMetricCard({ metric, month, year, compareMode }: { metric: RelatedMetric; month: number; year: number; compareMode: 'mom' | 'yoy' | 'goal' }) {
  const data = useMemo(() => generateMetricData(metric.id, month, year, compareMode), [metric.id, month, year, compareMode]);
  const average = Math.round(data.history.reduce((sum, d) => sum + d.value, 0) / data.history.length);

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-4 flex flex-col">
      {/* Header: Name + Scorecard */}
      <p className="text-xs text-muted-foreground line-clamp-2 min-h-[2rem]">{metric.name}</p>
      <div className="text-center mt-2 mb-1">
        <span className="text-2xl text-[var(--color-text-primary)]">{data.currentValue.toLocaleString()}</span>
        <div className="flex items-center justify-center gap-1.5 mt-1">
          <span className={cn('text-xs', data.change >= 0 ? 'text-green-600' : 'text-red-500')}>
            {data.change >= 0 ? '\u25B2' : '\u25BC'} {Math.abs(data.change)}%
          </span>
        </div>
      </div>

      {/* Description */}
      <div className="mt-2 mb-1 py-2 px-2.5 rounded-[var(--radius-sm)] bg-[var(--color-bg-secondary)] border border-[var(--color-border-subtle)]">
        <p className="text-[10px] text-muted-foreground leading-relaxed">{metric.description}</p>
      </div>

      {/* Insight */}
      <div className="flex-1 mb-3 py-2 px-2.5 rounded-[var(--radius-sm)] bg-violet-50 border border-violet-200">
        <p className="text-[10px] text-muted-foreground leading-relaxed"><span className="text-violet-600">Insight:</span> {metric.insight}</p>
      </div>

      {/* Chart */}
      <div className="h-[130px] mt-auto">
        <ResponsiveContainer width="100%" height={130}>
          <BarChart data={data.history} margin={{ top: 16, right: 4, bottom: 0, left: -24 }}>
            <CartesianGrid key="grid" strokeDasharray="3 3" stroke="var(--color-border-default)" vertical={false} />
            <XAxis
              key="xaxis"
              dataKey="month"
              tick={{ fontSize: 9, fill: 'var(--color-text-secondary)' }}
              stroke="var(--color-border-strong)"
              tickLine={false}
              interval={0}
            />
            <YAxis
              key="yaxis"
              tick={{ fontSize: 9, fill: 'var(--color-text-secondary)' }}
              stroke="var(--color-border-strong)"
              tickLine={false}
              axisLine={false}
              domain={[0, 'auto']}
            />
            <Tooltip
              key="tooltip"
              contentStyle={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border-default)',
                borderRadius: 'var(--radius-md)',
                fontSize: 11,
              }}
              formatter={(value: number) => [value.toLocaleString(), 'Value']}
            />
            <Bar key="bar" dataKey="value" fill="#3B82F6" radius={[2, 2, 0, 0]} barSize={24} />
            <ReferenceLine
              key="refline"
              y={average}
              stroke="#F59E0B"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={(props: any) => {
                const { viewBox } = props;
                const x = (viewBox?.x ?? 0) + 4;
                const y = (viewBox?.y ?? 0) - 2;
                return (
                  <g key="avg-label-group">
                    <rect key="avg-bg" x={x - 2} y={y - 9} width={22} height={13} rx={3} fill="white" stroke="#F59E0B" strokeWidth={0.75} />
                    <text key="avg-text" x={x + 9} y={y + 1} textAnchor="middle" fill="#F59E0B" fontSize={9} fontWeight={600}>Avg</text>
                  </g>
                );
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}