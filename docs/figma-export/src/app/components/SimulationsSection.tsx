import React, { useState, useMemo, useCallback } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  FlaskConical,
  Sparkles,
  Check,
  Calendar,
  TrendingUp,
  Layers,
  ExternalLink,
  Target,
  Lightbulb,
  RefreshCw,
  ArrowRight,
  BarChart3,
  ClipboardList,
} from 'lucide-react';
import { cn } from './ui/utils';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from './ui/accordion';
import {
  Line,
  Area,
  ReferenceArea,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ComposedChart,
} from 'recharts';
import {
  calendarActivities,
  getCampaignName,
  getActivityObjective,
} from '../data/calendarData';
import type { CalendarActivity, FunnelObjective } from '../data/calendarData';
import { useNavigate } from 'react-router';
import { SimulationProgressPanel } from './SimulationProgressPanel';
import type { SimulationProgressState } from './SimulationProgressPanel';
import { useGoals } from '../contexts/GoalsContext';
import { useActivities } from '../contexts/ActivitiesContext';
import { useToast } from './ToastProvider';
import { ActivityDetailPanel } from './ActivityDetailPanel';
import {
  MOCK_RECOMMENDATIONS,
  type SimulationRecommendation,
  type RecStatus,
} from '../data/simulationRecommendations';

/* ========== Constants ========== */

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const FUNNEL_STEPS: { id: string; label: string; objective: FunnelObjective; color: string }[] = [
  { id: 'problem-awareness', label: 'Problem Awareness', objective: 'Problem Awareness', color: '#3B82F6' },
  { id: 'brand-awareness', label: 'Brand Awareness', objective: 'Brand Awareness', color: '#6366F1' },
  { id: 'consideration', label: 'Consideration', objective: 'Consideration', color: '#F59E0B' },
  { id: 'conversion', label: 'Conversion', objective: 'Conversion', color: '#2EC4B6' },
];

/* ========== Helpers ========== */

function formatCurrency(val: number): string {
  if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
  if (val >= 1000) return `$${(val / 1000).toFixed(1)}k`;
  return `$${val.toLocaleString()}`;
}

function formatValue(val: number): string {
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
  if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
  return val.toString();
}

/** Get activities for a specific month/year, excluding holidays */
function getActivitiesForMonth(month: number, year: number): CalendarActivity[] {
  return calendarActivities.filter((a) => {
    if (a.category === 'holiday') return false;
    const d = a.launch_date;
    return d.getMonth() === month && d.getFullYear() === year;
  });
}

/** Group activities by funnel objective */
function groupByFunnelStep(activities: CalendarActivity[]): Record<FunnelObjective, CalendarActivity[]> {
  const groups: Record<FunnelObjective, CalendarActivity[]> = {
    'Problem Awareness': [],
    'Brand Awareness': [],
    'Consideration': [],
    'Conversion': [],
  };
  activities.forEach((a) => {
    const obj = getActivityObjective(a);
    if (obj && groups[obj]) {
      groups[obj].push(a);
    }
  });
  return groups;
}

/** Group activities by campaign within a funnel step */
function groupByCampaign(activities: CalendarActivity[]): { campaignId: string; campaignName: string; activities: CalendarActivity[]; totalSpend: number }[] {
  const map = new Map<string, CalendarActivity[]>();
  activities.forEach((a) => {
    const existing = map.get(a.campaign_id) || [];
    existing.push(a);
    map.set(a.campaign_id, existing);
  });

  return Array.from(map.entries())
    .map(([campaignId, acts]) => ({
      campaignId,
      campaignName: getCampaignName(campaignId),
      activities: acts,
      totalSpend: acts.reduce((s, a) => s + (a.cost || 0), 0),
    }))
    .sort((a, b) => b.totalSpend - a.totalSpend);
}

type GroupBy = 'campaign' | 'channel';

/** Unified grouping function */
function groupActivities(activities: CalendarActivity[], by: GroupBy): { groupId: string; groupName: string; activities: CalendarActivity[]; totalSpend: number }[] {
  if (by === 'campaign') {
    return groupByCampaign(activities).map(g => ({
      groupId: g.campaignId,
      groupName: g.campaignName,
      activities: g.activities,
      totalSpend: g.totalSpend,
    }));
  }

  // Group by channel
  const map = new Map<string, CalendarActivity[]>();
  activities.forEach((a) => {
    const key = a.channel || 'Unassigned';
    const existing = map.get(key) || [];
    existing.push(a);
    map.set(key, existing);
  });

  return Array.from(map.entries())
    .map(([channel, acts]) => ({
      groupId: channel,
      groupName: channel,
      activities: acts,
      totalSpend: acts.reduce((s, a) => s + (a.cost || 0), 0),
    }))
    .sort((a, b) => b.totalSpend - a.totalSpend);
}

function getMonthTotalSpend(month: number, year: number): number {
  return getActivitiesForMonth(month, year).reduce((s, a) => s + (a.cost || 0), 0);
}

function getNext3Months(startMonth: number, startYear: number): { month: number; year: number; label: string; abbr: string }[] {
  const result = [];
  for (let i = 0; i < 3; i++) {
    let m = startMonth + i;
    let y = startYear;
    if (m > 11) { m -= 12; y += 1; }
    result.push({ month: m, year: y, label: `${MONTHS_FULL[m]} ${y}`, abbr: `${MONTH_ABBR[m]} ${y}` });
  }
  return result;
}

/* ========== Trend & Forecast Helpers ========== */

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

function generateBaseline(historical: { name: string; value: number }[], futureMonths: { month: number; year: number }[]): { name: string; value: number | null; baseline: number; planned: number | null }[] {
  const last6 = historical.slice(-6);
  const slope = last6.length > 1 ? (last6[last6.length - 1].value - last6[0].value) / (last6.length - 1) : 0;
  const lastValue = historical[historical.length - 1].value;
  const avgLast3 = historical.slice(-3).reduce((s, p) => s + p.value, 0) / 3;

  return futureMonths.map((fm, i) => {
    const decayFactor = 0.3 * slope;
    const baselineValue = Math.max(0, Math.round(lastValue + decayFactor * (i + 1) - avgLast3 * 0.02 * (i + 1)));
    return {
      name: `${MONTH_ABBR[fm.month]} ${String(fm.year).slice(2)}`,
      value: null,
      baseline: baselineValue,
      planned: null,
    };
  });
}

function computePlannedForecast(
  historical: { name: string; value: number }[],
  futureMonths: { month: number; year: number }[],
  baselineData: { baseline: number }[],
  stepObjective: FunnelObjective,
): (number | null)[] {
  const lastVal = historical[historical.length - 1].value;
  return futureMonths.map((fm, i) => {
    const monthActivities = getActivitiesForMonth(fm.month, fm.year)
      .filter((a) => getActivityObjective(a) === stepObjective);
    const totalBudget = monthActivities.reduce((s, a) => s + (a.cost || 0), 0);
    if (totalBudget === 0) return baselineData[i].baseline;
    const baseVal = baselineData[i].baseline ?? lastVal;
    const upliftPct = Math.min(totalBudget / 1000 * 0.06, 0.35);
    return Math.round(baseVal * (1 + upliftPct));
  });
}

/* ========== Main Component ========== */

export function SimulationsSection({ onNavigateToGoals }: { onNavigateToGoals?: () => void }) {
  // Current month is March 2026 (0-indexed: 2)
  const CURRENT_MONTH = 2;
  const CURRENT_YEAR = 2026;

  // The 3 simulation months: current + next 2
  const simulationMonths = useMemo(() => getNext3Months(CURRENT_MONTH, CURRENT_YEAR), []);

  // Which of the 3 months is currently being viewed
  const [activeMonthIndex, setActiveMonthIndex] = useState(0);
  const [simulationRun, setSimulationRun] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [groupBy, setGroupBy] = useState<GroupBy>('campaign');
  const [simProgressState, setSimProgressState] = useState<SimulationProgressState | null>(null);
  const [resultsTab, setResultsTab] = useState<'plan' | 'results' | 'recommendations'>('plan');
  const [recStatuses, setRecStatuses] = useState<Record<string, RecStatus>>({});
  const [isResimulation, setIsResimulation] = useState(false);
  const [includedInSimIds, setIncludedInSimIds] = useState<Set<string>>(new Set());

  const pendingRecCount = MOCK_RECOMMENDATIONS.filter((r) => (recStatuses[r.id] ?? 'pending') === 'pending').length;

  const activeMonth = simulationMonths[activeMonthIndex];
  const selectedMonth = activeMonth.month;
  const selectedYear = activeMonth.year;

  const monthActivities = useMemo(() => getActivitiesForMonth(selectedMonth, selectedYear), [selectedMonth, selectedYear]);
  const funnelGroups = useMemo(() => groupByFunnelStep(monthActivities), [monthActivities]);
  const totalSpend = useMemo(() => monthActivities.reduce((s, a) => s + (a.cost || 0), 0), [monthActivities]);

  // Spend for each of the 3 months (for the tab bar)
  const monthSpends = useMemo(
    () => simulationMonths.map((m) => getMonthTotalSpend(m.month, m.year)),
    [simulationMonths]
  );
  const grandTotalSpend = monthSpends.reduce((s, v) => s + v, 0);

  const navigate = useNavigate();
  const { setForecastAsGoals, targetsSaved, setTargetsSaved } = useGoals();

  const handleRunSimulation = useCallback((resim = false) => {
    setSimulating(true);
    setSimulationRun(false);
    setTargetsSaved(false);
    setSimProgressState(null);
    setIsResimulation(resim);
    // Only reset rec statuses for fresh runs, not re-simulations
    if (!resim) {
      setRecStatuses({});
      setIncludedInSimIds(new Set());
    }
  }, [setTargetsSaved]);

  const handleSimulationComplete = useCallback(() => {
    setSimulating(false);
    setSimulationRun(true);
    setSimProgressState(null);
    setResultsTab(isResimulation ? 'recommendations' : 'results');
  }, [isResimulation]);

  const handleSimulationCancel = useCallback(() => {
    setSimulating(false);
    setSimProgressState(null);
  }, []);

  const handleSetForecastAsGoals = useCallback(() => {
    // Compute planned forecast values for all 4 funnel stages across 3 months
    const forecasts: { stageId: string; month: number; year: number; value: number }[] = [];
    FUNNEL_STEPS.forEach((step) => {
      const hist = generateStepTrend(step.id, CURRENT_MONTH, CURRENT_YEAR);
      const baseline = generateBaseline(hist, simulationMonths);
      const planned = computePlannedForecast(hist, simulationMonths, baseline, step.objective);
      simulationMonths.forEach((fm, i) => {
        const val = planned[i];
        if (val !== null) {
          forecasts.push({ stageId: step.id, month: fm.month, year: fm.year, value: val });
        }
      });
    });
    setForecastAsGoals(forecasts);
    setTargetsSaved(true);
    onNavigateToGoals?.();
  }, [simulationMonths, setForecastAsGoals, setTargetsSaved, onNavigateToGoals]);

  const RESULTS_TABS = [
    { id: 'plan' as const, label: 'Current Plan', icon: ClipboardList, badge: 0 },
    { id: 'results' as const, label: 'Simulated Results', icon: BarChart3, badge: 0 },
    { id: 'recommendations' as const, label: 'Recommendations', icon: Lightbulb, badge: pendingRecCount },
  ];
  
  return (
    <div className="flex gap-5">
      {/* Left: Main content */}
      <div className="flex-1 min-w-0 space-y-5">
        {/* 3-Month Tab Bar */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1 p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] flex-1">
            {simulationMonths.map((fm, i) => {
              const spend = monthSpends[i];
              const isActive = activeMonthIndex === i;
              return (
                <button
                  key={fm.label}
                  onClick={() => setActiveMonthIndex(i)}
                  className={cn(
                    "flex-1 flex flex-col items-center gap-0.5 px-4 py-2.5 rounded-[var(--radius-sm)] transition-all cursor-pointer",
                    isActive
                      ? "bg-[var(--color-bg-elevated)] shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                  style={{
                    transitionTimingFunction: 'var(--ease-default)',
                    transitionDuration: 'var(--duration-fast)',
                  }}
                >
                  <span className="text-sm">{fm.label}</span>
                  <span className={cn("text-xs", isActive ? "text-[var(--color-violet-600)]" : "text-muted-foreground")}>
                    {formatCurrency(spend)}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-4 py-2.5 flex flex-col items-center shrink-0">
            <span className="text-[0.625rem] text-muted-foreground uppercase tracking-wide">3-Mo Total</span>
            <span className="text-lg">{formatCurrency(grandTotalSpend)}</span>
          </div>
        </div>

        {/* Activity count for current month */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Layers className="size-3.5" />
          {monthActivities.length} activities · {monthActivities.filter(a => a.cost && a.cost > 0).length} with spend in {activeMonth.label}
        </div>

        {/* Results Tab Bar (shown after simulation) */}
        {simulationRun && !simulating && (
          <div className="flex items-center gap-1 p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)]">
            {RESULTS_TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = resultsTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setResultsTab(tab.id)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-[var(--radius-sm)] transition-all cursor-pointer",
                    isActive
                      ? "bg-[var(--color-bg-elevated)] shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                  style={{
                    transitionTimingFunction: 'var(--ease-default)',
                    transitionDuration: 'var(--duration-fast)',
                  }}
                >
                  <Icon className="size-3.5" />
                  <span className="text-sm">{tab.label}</span>
                  {tab.badge > 0 && (
                    <span
                      className="flex items-center justify-center size-5 rounded-full text-[0.625rem]"
                      style={{ backgroundColor: 'var(--color-violet-500)', color: 'white' }}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {/* Simulation Progress */}
        {simulating && (
          <SimulationProgressPanel
            simulationMonths={simulationMonths}
            onComplete={handleSimulationComplete}
            onCancel={handleSimulationCancel}
            onProgressChange={setSimProgressState}
          />
        )}

        {/* Tab Content */}
        {!simulating && (
          <>
            {/* Tab 1: Current Plan (always shown pre-simulation, or when tab selected post-simulation) */}
            {(!simulationRun || resultsTab === 'plan') && (
              <Card className="p-5">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-3">
                    <TrendingUp className="size-5 text-[var(--color-violet-500)]" />
                    <h2>Planned Spend by Funnel Stage</h2>
                  </div>
                  {/* Group-by segmented control */}
                  <div className="flex items-center gap-1 p-0.5 bg-[var(--color-bg-secondary)] rounded-[var(--radius-sm)]">
                    {([['campaign', 'By Campaign'], ['channel', 'By Channel']] as const).map(([value, label]) => (
                      <button
                        key={value}
                        onClick={() => setGroupBy(value)}
                        className={cn(
                          "px-3 py-1 text-[0.6875rem] rounded-[var(--radius-sm)] transition-all cursor-pointer",
                          groupBy === value
                            ? "bg-[var(--color-bg-elevated)] shadow-sm"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                        style={{
                          transitionTimingFunction: 'var(--ease-default)',
                          transitionDuration: 'var(--duration-fast)',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mb-5">
                  Spend breakdown for {activeMonth.label}, grouped by funnel stage and {groupBy}. Data sourced from your campaign calendar.
                </p>

                {monthActivities.length === 0 ? (
                  <div className="text-center py-12 text-sm text-muted-foreground">
                    <Calendar className="size-8 mx-auto mb-3 opacity-40" />
                    <p>No activities planned for {activeMonth.label}.</p>
                    <p className="text-xs mt-1">Add activities on the Calendar page to see spend data here.</p>
                  </div>
                ) : (
                  <Accordion type="single" collapsible>
                    {FUNNEL_STEPS.map((step, index) => {
                      const stepActivities = funnelGroups[step.objective] || [];
                      const stepSpend = stepActivities.reduce((s, a) => s + (a.cost || 0), 0);
                      const groups = groupActivities(stepActivities, groupBy);
                      const spendPct = totalSpend > 0 ? (stepSpend / totalSpend) * 100 : 0;

                      return (
                        <FunnelStepRow
                          key={step.id}
                          step={step}
                          index={index}
                          totalSteps={FUNNEL_STEPS.length}
                          activities={stepActivities}
                          spend={stepSpend}
                          spendPct={spendPct}
                          groups={groups}
                          groupBy={groupBy}
                          totalSpend={totalSpend}
                        />
                      );
                    })}
                  </Accordion>
                )}
              </Card>
            )}

            {/* Tab 2: Simulated Results */}
            {simulationRun && resultsTab === 'results' && (
              <SimulationResults
                selectedMonth={CURRENT_MONTH}
                selectedYear={CURRENT_YEAR}
                futureMonths={simulationMonths}
              />
            )}

            {/* Tab 3: Recommendations */}
            {simulationRun && resultsTab === 'recommendations' && (
              <RecommendationsTab
                onRunSimulation={handleRunSimulation}
                targetsSaved={targetsSaved}
                onSetTargets={handleSetForecastAsGoals}
                recStatuses={recStatuses}
                setRecStatuses={setRecStatuses}
                isResimulation={isResimulation}
                includedInSimIds={includedInSimIds}
                setIncludedInSimIds={setIncludedInSimIds}
              />
            )}
          </>
        )}
      </div>

      {/* Right: Simulation Sidebar */}
      <SimulationSidebar
        totalSpend={grandTotalSpend}
        selectedMonth={selectedMonth}
        selectedYear={selectedYear}
        simulationMonths={simulationMonths}
        simulating={simulating}
        simulationRun={simulationRun}
        targetsSaved={targetsSaved}
        onRunSimulation={handleRunSimulation}
        onSetTargets={handleSetForecastAsGoals}
        onSimulationComplete={handleSimulationComplete}
        onSimulationCancel={handleSimulationCancel}
        simProgressState={simProgressState}
        onViewRecommendations={() => setResultsTab('recommendations')}
      />
    </div>
  );
}

/* ========== Funnel Step Row ========== */

function FunnelStepRow({
  step,
  index,
  totalSteps,
  activities,
  spend,
  spendPct,
  groups,
  groupBy,
  totalSpend,
}: {
  step: (typeof FUNNEL_STEPS)[number];
  index: number;
  totalSteps: number;
  activities: CalendarActivity[];
  spend: number;
  spendPct: number;
  groups: ReturnType<typeof groupActivities>;
  groupBy: GroupBy;
  totalSpend: number;
}) {
  // Funnel shape widths
  const topWidthPercent = 100 - (index / totalSteps) * 55;
  const bottomWidthPercent = 100 - ((index + 1) / totalSteps) * 55;

  return (
    <AccordionItem value={step.id} className="border-b-0 mb-1">
      <AccordionTrigger className="py-2.5 hover:no-underline">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Funnel shape */}
          <div className="w-1/3 shrink-0 flex flex-col items-center">
            <div
              className="relative flex items-center justify-center"
              style={{
                width: `${topWidthPercent}%`,
                minHeight: '2.5rem',
                clipPath: `polygon(${((100 - topWidthPercent) / 2)}% 0%, ${100 - ((100 - topWidthPercent) / 2)}% 0%, ${100 - ((100 - bottomWidthPercent) / 2)}% 100%, ${((100 - bottomWidthPercent) / 2)}% 100%)`,
                backgroundColor: step.color,
                opacity: 0.85,
              }}
            >
              <span className="text-white text-xs relative z-10">{formatCurrency(spend)}</span>
            </div>
          </div>

          {/* Label + stats */}
          <div className="flex flex-col items-start min-w-0 flex-1">
            <span className="text-sm">{step.label}</span>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-muted-foreground">{formatCurrency(spend)}</span>
              {totalSpend > 0 && (
                <span className="text-muted-foreground">({spendPct.toFixed(0)}%)</span>
              )}
            </div>
          </div>

          {/* Mini spend bar */}
          <div className="w-24 shrink-0">
            <div className="h-1.5 w-full bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${spendPct}%`, backgroundColor: step.color }}
              />
            </div>
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent className="pt-2 pb-4 pl-8">
        {groups.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-4">
            No activities planned for this funnel stage this month.
          </p>
        ) : (
          <div className="space-y-3">
            {groups.map((group) => (
              <CampaignActivityGroup
                key={group.groupId}
                group={group}
                stepColor={step.color}
                groupBy={groupBy}
              />
            ))}
          </div>
        )}
      </AccordionContent>
    </AccordionItem>
  );
}

/* ========== Campaign Activity Group ========== */

function CampaignActivityGroup({
  group,
  stepColor,
  groupBy,
}: {
  group: ReturnType<typeof groupActivities>[number];
  stepColor: string;
  groupBy: GroupBy;
}) {
  const navigate = useNavigate();

  const handleViewActivity = (activityId: string) => {
    navigate('/calendar', { state: { viewActivityId: activityId } });
  };

  return (
    <div
      className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-3"
    >
      {/* Campaign header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="size-2 rounded-full shrink-0" style={{ backgroundColor: stepColor }} />
          <span className="text-xs truncate">{group.groupName}</span>
          <Badge variant="secondary" className="text-[0.625rem] shrink-0">
            {group.activities.length} {group.activities.length === 1 ? 'activity' : 'activities'}
          </Badge>
        </div>
        <span className="text-xs shrink-0 ml-2">{formatCurrency(group.totalSpend)}</span>
      </div>

      {/* Activities table */}
      <div className="overflow-hidden rounded-[var(--radius-sm)] border border-[var(--color-border-default)]">
        <table className="w-full text-[0.6875rem]">
          <thead>
            <tr className="bg-[var(--color-bg-primary)]">
              <th className="text-left p-2 text-muted-foreground">Activity</th>
              <th className="text-left p-2 text-muted-foreground">{groupBy === 'channel' ? 'Campaign' : 'Channel'}</th>
              <th className="text-left p-2 text-muted-foreground">Platform</th>
              <th className="text-left p-2 text-muted-foreground">Date</th>
              <th className="text-right p-2 text-muted-foreground">Cost</th>
              <th className="w-8 p-2"></th>
            </tr>
          </thead>
          <tbody>
            {group.activities.map((activity) => (
              <tr key={activity.activity_id} className="border-t border-[var(--color-border-default)] group">
                <td className="p-2 max-w-[12.5rem] truncate">{activity.name}</td>
                <td className="p-2 text-muted-foreground">{groupBy === 'channel' ? getCampaignName(activity.campaign_id) : (activity.channel || '—')}</td>
                <td className="p-2 text-muted-foreground">{activity.platform || '—'}</td>
                <td className="p-2 text-muted-foreground whitespace-nowrap">
                  {MONTH_ABBR[activity.launch_date.getMonth()]} {activity.launch_date.getDate()}
                </td>
                <td className="p-2 text-right">
                  {activity.cost ? formatCurrency(activity.cost) : '—'}
                </td>
                <td className="p-2 text-center">
                  <button
                    onClick={() => handleViewActivity(activity.activity_id)}
                    className="inline-flex items-center gap-1 text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] opacity-60 group-hover:opacity-100 transition-opacity cursor-pointer"
                    title="View on Calendar page"
                  >
                    <ExternalLink className="size-3" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ========== Simulation Results ========== */

function SimulationResults({
  selectedMonth,
  selectedYear,
  futureMonths,
}: {
  selectedMonth: number;
  selectedYear: number;
  futureMonths: ReturnType<typeof getNext3Months>;
}) {
  // Compute aggregate conversion and revenue numbers across all 3 months
  const conversionStep = FUNNEL_STEPS.find(s => s.id === 'conversion')!;
  const convHistorical = generateStepTrend(conversionStep.id, selectedMonth, selectedYear);
  const convBaseline = generateBaseline(convHistorical, futureMonths);
  const convPlanned = computePlannedForecast(convHistorical, futureMonths, convBaseline, conversionStep.objective);

  const totalBaselineConversions = convBaseline.reduce((s, b) => s + b.baseline, 0);
  const totalPlannedConversions = convPlanned.reduce((s, v) => s + (v ?? 0), 0);
  const convUplift = totalBaselineConversions > 0 ? ((totalPlannedConversions - totalBaselineConversions) / totalBaselineConversions) * 100 : 0;

  // Estimated revenue: assume ~$1,400 avg revenue per conversion
  const AVG_REV_PER_CONVERSION = 1400;
  const totalBaselineRevenue = totalBaselineConversions * AVG_REV_PER_CONVERSION;
  const totalPlannedRevenue = totalPlannedConversions * AVG_REV_PER_CONVERSION;
  const revUplift = totalBaselineRevenue > 0 ? ((totalPlannedRevenue - totalBaselineRevenue) / totalBaselineRevenue) * 100 : 0;

  // Conversions trend data: 9 prior historical months + bridge at current month + 2 future forecast months = 12 points
  // Note: futureMonths[0] is the current month (Mar 26), which overlaps with the last historical point.
  // We use it as the bridge and only forecast from futureMonths[1] onward.
  const lastHistValue = convHistorical[convHistorical.length - 1].value;
  const nowLabel = convHistorical[convHistorical.length - 1].name;
  // Build chart data with separate keys: actual (historical), simulated (forecast), baseline (forecast)
  // Using distinct keys avoids recharts conflicts between Area and Line sharing the same dataKey
  const convTrendData: { name: string; actual?: number; simulated?: number; baseline?: number }[] = [
    // 9 historical months before the current month
    ...convHistorical.slice(-10, -1).map((p) => ({
      name: p.name,
      actual: p.value,
    })),
    // Bridge point (current month) — actual meets forecast
    {
      name: nowLabel,
      actual: lastHistValue,
      simulated: lastHistValue,
      baseline: lastHistValue,
    },
    // 2 future forecast months (skip index 0 which is the current month already in bridge)
    ...futureMonths.slice(1).map((fm, i) => {
      const p = (convPlanned[i + 1] ?? 0);
      const b = convBaseline[i + 1].baseline;
      return {
        name: `${MONTH_ABBR[fm.month]} ${String(fm.year).slice(2)}`,
        simulated: p,
        baseline: b,
      };
    }),
  ];

  // Compute Y-axis bounds from all defined values
  const allYValues = convTrendData.flatMap(d => [d.actual, d.simulated, d.baseline].filter((v): v is number => v !== undefined));
  const yMin = Math.floor(Math.min(...allYValues) * 0.90);
  const yMax = Math.ceil(Math.max(...allYValues) * 1.08);

  return (
    <Card className="p-5 border-[var(--color-violet-300)] bg-gradient-to-br from-[var(--color-violet-50)] to-[var(--color-bg-elevated)]">
      <div className="flex items-center gap-2 mb-5">
        <Sparkles className="size-4 text-[var(--color-violet-500)]" />
        <h3 className="text-sm">Simulation Results</h3>
        <span className="text-xs text-muted-foreground ml-auto">3-month forecast vs. baseline (no marketing activity)</span>
      </div>

      {/* Analyst Summary — moved above visualizations */}
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-4 mb-6">
        <h4 className="text-xs text-muted-foreground tracking-wide uppercase mb-2">Analyst Summary</h4>
        <p className="text-xs leading-relaxed">
          Based on the planned spend from your campaign calendar for {futureMonths.map(m => m.abbr).join(', ')}, the simulation projects uplift over the do-nothing baseline across all funnel stages. The strongest gains are expected in stages with the highest budget concentration. Consider monitoring Consideration spend closely — the model suggests potential for higher ROI with incremental investment in mid-funnel activities that bridge awareness to conversion.
        </p>
      </div>

      {/* Scorecards + Trend row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Conversions Scorecard */}
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-4">
          <div className="mb-2">
            <span className="text-xs text-muted-foreground tracking-wide uppercase">Conversions</span>
            {' '}
            <span className="text-[0.6875rem] text-muted-foreground/70">· Account Opens</span>
          </div>
          <p className="text-3xl mb-1" style={{ fontFamily: 'var(--font-display)' }}>
            {totalPlannedConversions.toLocaleString()}
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <span className={convUplift >= 0 ? 'text-green-500' : 'text-red-500'}>
              {convUplift >= 0 ? '+' : ''}{convUplift.toFixed(1)}%
            </span>
            <span className="text-muted-foreground">vs. baseline</span>
          </div>
          <p className="text-[0.625rem] text-muted-foreground mt-2">
            Baseline: {totalBaselineConversions.toLocaleString()}
          </p>
        </div>

        {/* Estimated Revenue Scorecard */}
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-4">
          <p className="text-xs text-muted-foreground tracking-wide uppercase mb-2">Estimated Revenue</p>
          <p className="text-3xl mb-1" style={{ fontFamily: 'var(--font-display)' }}>
            {formatCurrency(totalPlannedRevenue)}
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <span className={revUplift >= 0 ? 'text-green-500' : 'text-red-500'}>
              {revUplift >= 0 ? '+' : ''}{revUplift.toFixed(1)}%
            </span>
            <span className="text-muted-foreground">vs. baseline</span>
          </div>
          <p className="text-[0.625rem] text-muted-foreground mt-2">
            Baseline: {formatCurrency(totalBaselineRevenue)}
          </p>
        </div>
      </div>

      {/* Conversions Trend Chart - full width below scorecards */}
      <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-4 mb-6">
        <h4 className="text-xs mb-3">Conversions Trend: Planned vs. Baseline</h4>
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={convTrendData} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-default)" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
              stroke="var(--color-border-default)"
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
              stroke="var(--color-border-default)"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => formatValue(v)}
              domain={[yMin, yMax]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border-default)',
                borderRadius: 'var(--radius-md)',
                fontSize: 11,
              }}
              formatter={(value: number | undefined, name: string) => {
                if (value === undefined) return ['-', name];
                return [
                  formatValue(value),
                  name === 'simulated' ? 'Simulated' : name === 'baseline' ? 'Baseline' : 'Actual',
                ];
              }}
              itemSorter={() => 0}
            />
            <ReferenceLine
              x={nowLabel}
              stroke="var(--color-border-strong)"
              strokeDasharray="4 4"
              strokeWidth={1}
              label={{ value: 'Now', position: 'top', fontSize: 10, fill: 'var(--color-text-secondary)' }}
            />
            {/* Uplift shading: ReferenceArea rectangles between baseline and simulated for each forecast segment */}
            {convTrendData.map((d, i) => {
              if (i === 0) return null;
              const prev = convTrendData[i - 1];
              if (d.simulated === undefined || d.baseline === undefined ||
                  prev.simulated === undefined || prev.baseline === undefined) return null;
              const minBaseline = Math.min(prev.baseline, d.baseline);
              const maxSimulated = Math.max(prev.simulated, d.simulated);
              if (maxSimulated <= minBaseline) return null;
              return (
                <ReferenceArea
                  key={`uplift-${i}`}
                  x1={prev.name}
                  x2={d.name}
                  y1={minBaseline}
                  y2={maxSimulated}
                  fill="rgba(20, 184, 166, 0.15)"
                  fillOpacity={1}
                  stroke="none"
                />
              );
            })}
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#14b8a6"
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 1.5, fill: 'white' }}
              activeDot={{ r: 5 }}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="simulated"
              stroke="#14b8a6"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={{ r: 3, strokeWidth: 2, fill: 'white' }}
              activeDot={{ r: 5 }}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="baseline"
              stroke="#9ca3af"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={{ r: 3, strokeWidth: 2, fill: 'white' }}
              activeDot={{ r: 5 }}
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="flex items-center justify-center gap-4 mt-2 text-[0.625rem]">
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 bg-[var(--color-teal-500,#14b8a6)]" /> Actual</span>
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: 'var(--color-teal-500, #14b8a6)' }} /> Simulated</span>
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 border-t-2 border-dashed border-gray-400" /> Baseline</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(20, 184, 166, 0.12)' }} /> Uplift</span>
        </div>
      </div>

      {/* Forecasted Performance — Funnel Accordion */}
      <h4 className="text-sm mb-4">Forecasted Performance</h4>
      <Accordion type="single" collapsible>
        {FUNNEL_STEPS.map((step, index) => (
          <ForecastFunnelStepRow
            key={step.id}
            step={step}
            index={index}
            totalSteps={FUNNEL_STEPS.length}
            futureMonths={futureMonths}
            selectedMonth={selectedMonth}
            selectedYear={selectedYear}
          />
        ))}
      </Accordion>
    </Card>
  );
}

/* ========== Forecast Chart ========== */

function ForecastChart({
  stepId,
  stepColor,
  stepLabel,
  stepObjective,
  futureMonths,
  selectedMonth,
  selectedYear,
}: {
  stepId: string;
  stepColor: string;
  stepLabel: string;
  stepObjective: FunnelObjective;
  futureMonths: ReturnType<typeof getNext3Months>;
  selectedMonth: number;
  selectedYear: number;
}) {
  const historicalData = useMemo(() => generateStepTrend(stepId, selectedMonth, selectedYear), [stepId, selectedMonth, selectedYear]);
  const baselineData = useMemo(() => generateBaseline(historicalData, futureMonths), [historicalData, futureMonths]);
  const plannedValues = useMemo(
    () => computePlannedForecast(historicalData, futureMonths, baselineData, stepObjective),
    [historicalData, futureMonths, baselineData, stepObjective]
  );

  const hasBudget = plannedValues.some((v) => v !== null && v !== baselineData[0]?.baseline);

  const chartData = useMemo(() => {
    const hist = historicalData.map((p) => ({
      name: p.name,
      actual: p.value,
      baseline: null as number | null,
      planned: null as number | null,
    }));

    const lastHist = historicalData[historicalData.length - 1];
    const forecast = baselineData.map((bp, i) => ({
      name: bp.name,
      actual: null as number | null,
      baseline: bp.baseline,
      planned: plannedValues[i],
    }));

    const bridge = {
      name: lastHist.name,
      actual: lastHist.value,
      baseline: lastHist.value,
      planned: hasBudget ? lastHist.value : null,
    };

    hist[hist.length - 1] = bridge;

    return [...hist, ...forecast];
  }, [historicalData, baselineData, plannedValues, hasBudget]);

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h4 className="text-xs">{stepLabel} — Trend & Forecast</h4>
          <p className="text-[0.625rem] text-muted-foreground mt-0.5">
            Solid = historical | Dashed gray = baseline {hasBudget && '| Dashed colored = planned'}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[0.625rem]">
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5" style={{ backgroundColor: stepColor }} /> Actual</span>
          <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 border-t-2 border-dashed border-gray-400" /> Baseline</span>
          {hasBudget && <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: stepColor }} /> Planned</span>}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-default)" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            stroke="var(--color-border-strong)"
            tickLine={false}
            interval={1}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            stroke="var(--color-border-strong)"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatValue(v)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border-default)',
              borderRadius: 'var(--radius-md)',
              fontSize: 11,
            }}
            formatter={(value: number | null, name: string) => {
              if (value === null) return ['-', name];
              const label = name === 'actual' ? 'Actual' : name === 'baseline' ? 'Baseline' : 'Planned';
              return [formatValue(value), label];
            }}
          />
          <ReferenceLine
            x={historicalData[historicalData.length - 1].name}
            stroke="var(--color-border-strong)"
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{ value: 'Now', position: 'top', fontSize: 10, fill: 'var(--color-text-secondary)' }}
          />
          <Line
            type="monotone"
            dataKey="actual"
            stroke={stepColor}
            strokeWidth={2}
            dot={{ r: 2.5, strokeWidth: 1.5, fill: 'var(--color-bg-elevated)' }}
            activeDot={{ r: 4 }}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="baseline"
            stroke="#9CA3AF"
            strokeWidth={1.5}
            strokeDasharray="6 3"
            dot={{ r: 2, fill: '#9CA3AF', strokeWidth: 0 }}
            connectNulls={false}
          />
          {hasBudget && (
            <Line
              type="monotone"
              dataKey="planned"
              stroke={stepColor}
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={{ r: 3, fill: stepColor, strokeWidth: 0 }}
              connectNulls={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ========== Recommendations Tab ========== */

const FUNNEL_COLORS: Record<string, string> = {
  'Problem Awareness': '#3B82F6',
  'Brand Awareness': '#6366F1',
  'Consideration': '#F59E0B',
  'Conversion': '#2EC4B6',
};

import { Plus, Pencil, Trash2, Square, CheckSquare, AlertTriangle } from 'lucide-react';

const ACTION_CONFIG = {
  add: { label: 'Add', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', icon: Plus },
  modify: { label: 'Modify', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', icon: Pencil },
  delete: { label: 'Remove', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', icon: Trash2 },
} as const;

function getRecActivityName(rec: SimulationRecommendation, allActivities: CalendarActivity[]): string {
  if (rec.action === 'add') return rec.proposedActivity.name;
  if (rec.action === 'delete') return rec.activitySnapshot.name;
  const act = allActivities.find((a) => a.activity_id === rec.activityId);
  return act?.name ?? `Activity ${rec.activityId}`;
}

function getRecActivity(rec: SimulationRecommendation, allActivities: CalendarActivity[]): CalendarActivity | null {
  if (rec.action === 'add') return rec.proposedActivity;
  if (rec.action === 'delete') return rec.activitySnapshot;
  return allActivities.find((a) => a.activity_id === rec.activityId) ?? null;
}

function RecommendationsTab({
  onRunSimulation,
  targetsSaved,
  onSetTargets,
  recStatuses,
  setRecStatuses,
  isResimulation,
  includedInSimIds,
  setIncludedInSimIds,
}: {
  onRunSimulation: (resim?: boolean) => void;
  targetsSaved: boolean;
  onSetTargets: () => void;
  recStatuses: Record<string, RecStatus>;
  setRecStatuses: React.Dispatch<React.SetStateAction<Record<string, RecStatus>>>;
  isResimulation: boolean;
  includedInSimIds: Set<string>;
  setIncludedInSimIds: React.Dispatch<React.SetStateAction<Set<string>>>;
}) {
  const navigate = useNavigate();
  const { activities, addActivity, updateActivity, deleteActivity } = useActivities();
  const { showToast } = useToast();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [viewingRecId, setViewingRecId] = useState<string | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  const pendingRecs = MOCK_RECOMMENDATIONS.filter((r) => (recStatuses[r.id] ?? 'pending') === 'pending');
  const acceptedCount = MOCK_RECOMMENDATIONS.filter((r) => recStatuses[r.id] === 'accepted').length;
  const rejectedCount = MOCK_RECOMMENDATIONS.filter((r) => recStatuses[r.id] === 'rejected').length;

  const allSelected = pendingRecs.length > 0 && pendingRecs.every((r) => selectedIds.has(r.id));
  const someSelected = selectedIds.size > 0;

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingRecs.map((r) => r.id)));
    }
  };

  const handleAcceptConfirmed = useCallback(() => {
    const toAccept = MOCK_RECOMMENDATIONS.filter((r) => selectedIds.has(r.id));

    toAccept.forEach((rec) => {
      if (rec.action === 'add') {
        addActivity(rec.proposedActivity);
      } else if (rec.action === 'modify') {
        updateActivity(rec.activityId, rec.changes);
      } else if (rec.action === 'delete') {
        deleteActivity(rec.activityId);
      }
    });

    const acceptedIds = toAccept.map((r) => r.id);
    setRecStatuses((prev) => {
      const next = { ...prev };
      acceptedIds.forEach((id) => { next[id] = 'accepted'; });
      return next;
    });
    setSelectedIds(new Set());
    setShowConfirmDialog(false);

    showToast(`${toAccept.length} recommendation${toAccept.length > 1 ? 's' : ''} applied to your campaign calendar`, {
      type: 'success',
      duration: 5000,
    });
  }, [selectedIds, addActivity, updateActivity, deleteActivity, setRecStatuses, showToast]);

  const handleReject = useCallback(() => {
    const toReject = MOCK_RECOMMENDATIONS.filter((r) => selectedIds.has(r.id));
    const rejectedIds = toReject.map((r) => r.id);

    setRecStatuses((prev) => {
      const next = { ...prev };
      rejectedIds.forEach((id) => { next[id] = 'rejected'; });
      return next;
    });
    setSelectedIds(new Set());

    showToast(`${toReject.length} recommendation${toReject.length > 1 ? 's' : ''} dismissed`, {
      type: 'info',
      duration: 5000,
      action: {
        label: 'Undo',
        onClick: () => {
          setRecStatuses((prev) => {
            const next = { ...prev };
            rejectedIds.forEach((id) => { next[id] = 'pending'; });
            return next;
          });
        },
      },
    });
  }, [selectedIds, setRecStatuses, showToast]);

  const handleAddToSimulation = useCallback(() => {
    setIncludedInSimIds(new Set(selectedIds));
    onRunSimulation(true);
  }, [onRunSimulation, selectedIds]);

  const viewingRec = viewingRecId ? MOCK_RECOMMENDATIONS.find((r) => r.id === viewingRecId) ?? null : null;
  const viewingActivity = viewingRec ? getRecActivity(viewingRec, activities) : null;

  return (
    <div className="flex gap-0">
      <div className="flex-1 min-w-0 space-y-4">
        {isResimulation && (
          <div className="flex items-start gap-2.5 px-4 py-3 rounded-[var(--radius-md)] bg-blue-50 border border-blue-200 text-xs text-blue-800">
            <FlaskConical className="size-3.5 shrink-0 mt-0.5" />
            <span>
              Showing results with recommended changes applied hypothetically. Changes have <strong>not</strong> been saved to your calendar.
            </span>
          </div>
        )}

        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Lightbulb className="size-4 text-[var(--color-violet-500)]" />
              <h3 className="text-xs text-muted-foreground tracking-wide uppercase">Recommendations</h3>
            </div>
            <button
              onClick={() => onRunSimulation()}
              className="flex items-center gap-1 text-[0.625rem] text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] cursor-pointer transition-colors"
              title="Re-run simulation"
            >
              <RefreshCw className="size-3" />
              Re-run
            </button>
          </div>

          <p className="text-[0.625rem] text-muted-foreground mb-3">
            {acceptedCount > 0 && <span className="text-emerald-600">{acceptedCount} applied</span>}
            {acceptedCount > 0 && (rejectedCount > 0 || pendingRecs.length > 0) && ' \u00b7 '}
            {rejectedCount > 0 && <span className="text-red-500">{rejectedCount} dismissed</span>}
            {rejectedCount > 0 && pendingRecs.length > 0 && ' \u00b7 '}
            {pendingRecs.length > 0 && <span>{pendingRecs.length} remaining</span>}
          </p>

          {pendingRecs.length > 0 && (
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-[var(--color-border-default)]">
              <button
                onClick={toggleSelectAll}
                className="flex items-center gap-1.5 text-[0.6875rem] text-muted-foreground hover:text-foreground cursor-pointer"
              >
                {allSelected ? <CheckSquare className="size-3.5" /> : <Square className="size-3.5" />}
                {allSelected ? 'Deselect All' : 'Select All'}
              </button>

              {someSelected && (
                <span className="text-[0.625rem] text-muted-foreground ml-1">
                  {selectedIds.size} selected
                </span>
              )}

              <div className="flex-1" />

              <Button
                size="sm"
                variant="outline"
                disabled={!someSelected}
                onClick={() => setShowConfirmDialog(true)}
                className="text-[0.6875rem] h-7 px-2.5"
              >
                <Check className="size-3 mr-1" />
                Accept
              </Button>

              <Button
                size="sm"
                variant="outline"
                disabled={!someSelected}
                onClick={handleReject}
                className="text-[0.6875rem] h-7 px-2.5"
              >
                <Trash2 className="size-3 mr-1" />
                Reject
              </Button>

              <Button
                size="sm"
                variant="outline"
                disabled={!someSelected}
                onClick={handleAddToSimulation}
                className="text-[0.6875rem] h-7 px-2.5"
              >
                <FlaskConical className="size-3 mr-1" />
                Include Selected & Re-Run Simulation
              </Button>
            </div>
          )}

          {pendingRecs.length === 0 ? (
            <div className="text-center py-10">
              <Lightbulb className="size-8 mx-auto mb-3 opacity-30" />
              <p className="text-sm text-muted-foreground">All recommendations have been addressed.</p>
              <p className="text-xs text-muted-foreground mt-1">
                Re-run the simulation to generate new insights.
              </p>
              <Button size="sm" variant="outline" className="mt-4" onClick={() => onRunSimulation()}>
                <RefreshCw className="size-3 mr-1.5" />
                Re-run Simulation
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {pendingRecs.map((rec) => {
                const cfg = ACTION_CONFIG[rec.action];
                const ActionIcon = cfg.icon;
                const isSelected = selectedIds.has(rec.id);
                const isViewing = viewingRecId === rec.id;
                const isIncludedInSim = isResimulation && includedInSimIds.has(rec.id);
                const actName = getRecActivityName(rec, activities);
                const funnelColor = FUNNEL_COLORS[rec.funnelStage] ?? '#8B5CF6';

                return (
                  <div
                    key={rec.id}
                    className={cn(
                      'flex gap-2.5 p-3 rounded-[var(--radius-md)] border transition-all cursor-pointer',
                      isIncludedInSim
                        ? 'border-blue-300 bg-blue-50/60 ring-1 ring-blue-200'
                        : isViewing
                        ? 'border-[var(--color-violet-400)] bg-[var(--color-violet-50)] shadow-sm'
                        : 'border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-strong)]',
                    )}
                  >
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleSelect(rec.id); }}
                      className="shrink-0 mt-0.5 cursor-pointer text-muted-foreground hover:text-foreground"
                    >
                      {isSelected ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
                    </button>

                    <div
                      className="min-w-0 flex-1"
                      onClick={() => setViewingRecId(isViewing ? null : rec.id)}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.5625rem] border', cfg.bg, cfg.text, cfg.border)}>
                          <ActionIcon className="size-2.5" />
                          {cfg.label}
                        </span>
                        <span className="text-xs truncate">{actName}</span>
                        {isIncludedInSim && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.5625rem] bg-blue-100 text-blue-700 border border-blue-200 shrink-0">
                            <FlaskConical className="size-2.5" />
                            Included
                          </span>
                        )}
                      </div>

                      <p className="text-[0.6875rem] text-muted-foreground leading-relaxed line-clamp-2 mb-1.5">
                        {rec.rationale}
                      </p>

                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5">
                          <div className="size-1.5 rounded-full" style={{ backgroundColor: funnelColor }} />
                          <span className="text-[0.5625rem] text-muted-foreground">{rec.funnelStage}</span>
                        </div>
                        <span className={cn(
                          'text-[0.5625rem]',
                          rec.estimatedImpact.changePercent >= 0 ? 'text-emerald-600' : 'text-red-500',
                        )}>
                          {rec.estimatedImpact.changePercent >= 0 ? '+' : ''}
                          {rec.estimatedImpact.changePercent.toFixed(1)}% {rec.estimatedImpact.metric}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

        </Card>
      </div>

      {viewingRec && viewingActivity && (
        <ActivityDetailPanel
          activity={viewingActivity}
          action={viewingRec.action}
          changes={viewingRec.action === 'modify' ? viewingRec.changes : undefined}
          originalValues={viewingRec.action === 'modify' ? viewingRec.originalValues : undefined}
          onClose={() => setViewingRecId(null)}
        />
      )}

      {showConfirmDialog && (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/40">
          <div className="bg-[var(--color-bg-elevated)] rounded-[var(--radius-lg)] shadow-xl border border-[var(--color-border-default)] p-6 max-w-sm w-full mx-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="size-5 text-amber-500" />
              <h3 className="text-sm">Apply Recommendations?</h3>
            </div>
            <p className="text-xs text-muted-foreground mb-1">
              This will apply <strong>{selectedIds.size}</strong> recommendation{selectedIds.size > 1 ? 's' : ''} to your campaign calendar:
            </p>
            <ul className="text-xs text-muted-foreground mb-5 space-y-1 pl-4 list-disc">
              {MOCK_RECOMMENDATIONS.filter((r) => selectedIds.has(r.id)).map((r) => {
                const cfg = ACTION_CONFIG[r.action];
                return (
                  <li key={r.id}>
                    <span className={cfg.text}>{cfg.label}</span>{' '}
                    {getRecActivityName(r, activities)}
                  </li>
                );
              })}
            </ul>
            <div className="flex gap-2 justify-end">
              <Button size="sm" variant="outline" onClick={() => setShowConfirmDialog(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleAcceptConfirmed}>
                Apply {selectedIds.size} Change{selectedIds.size > 1 ? 's' : ''}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ========== Simulation Sidebar ========== */

function SimulationSidebar({
  totalSpend,
  selectedMonth,
  selectedYear,
  simulationMonths,
  simulating,
  simulationRun,
  targetsSaved,
  onRunSimulation,
  onSetTargets,
  onSimulationComplete,
  onSimulationCancel,
  simProgressState,
  onViewRecommendations,
}: {
  totalSpend: number;
  selectedMonth: number;
  selectedYear: number;
  simulationMonths: ReturnType<typeof getNext3Months>;
  simulating: boolean;
  simulationRun: boolean;
  targetsSaved: boolean;
  onRunSimulation: (resim?: boolean) => void;
  onSetTargets: () => void;
  onSimulationComplete: () => void;
  onSimulationCancel: () => void;
  simProgressState: SimulationProgressState | null;
  onViewRecommendations: () => void;
}) {
  const navigate = useNavigate();

  return (
    <div className="w-72 shrink-0">
      <div className="sticky top-0 space-y-4">
        {/* Run Simulation CTA */}
        <Card className="p-4">
          {!simulationRun && !simulating && (
            <>
              <div className="flex items-center gap-2 mb-3">
                <FlaskConical className="size-4 text-[var(--color-violet-500)]" />
                <h3 className="text-xs text-muted-foreground tracking-wide uppercase">Simulation</h3>
              </div>
              <p className="text-xs text-muted-foreground mb-4">
                Simulate the impact of your planned spend across all funnel stages for the next 3 months.
              </p>
              <Button
                onClick={() => onRunSimulation()}
                disabled={totalSpend === 0}
                className="w-full"
                size="lg"
              >
                <FlaskConical className="size-4 mr-1.5" /> Run Simulation
              </Button>
            </>
          )}

          {simulating && (
            <div className="space-y-4 py-2">
              {/* Animated icon */}
              <div className="flex justify-center">
                <div className="size-12 rounded-full bg-[var(--color-violet-100)] flex items-center justify-center">
                  <FlaskConical className="size-5 text-[var(--color-violet-500)] animate-pulse" />
                </div>
              </div>

              {/* Phase label */}
              <p className="text-xs text-center">{simProgressState?.shortPhaseLabel || 'Preparing...'}</p>
              <p className="text-[0.6875rem] text-muted-foreground text-center">{simProgressState?.phaseSubLabel || 'Loading historical patterns and forecast data'}</p>

              {/* Mini progress */}
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
                <div className="h-full rounded-full" style={{
                  width: `${simProgressState?.progressPercent ?? 3}%`,
                  background: 'linear-gradient(90deg, var(--color-blue-500), var(--color-violet-500))',
                  transition: 'width 600ms cubic-bezier(0.4, 0, 0.2, 1)',
                }} />
              </div>

              {/* Timer */}
              <p className="text-center text-xs font-mono text-muted-foreground tabular-nums">{simProgressState?.elapsedSeconds ?? 0}s elapsed</p>

              {/* Cancel */}
              <Button variant="ghost" size="sm" onClick={onSimulationCancel} className="w-full text-xs">
                Cancel
              </Button>
            </div>
          )}

          {simulationRun && !simulating && (
            <>
              <div className="flex items-center gap-2 mb-3">
                <Check className="size-4 text-emerald-500" />
                <h3 className="text-xs text-muted-foreground tracking-wide uppercase">Simulation Complete</h3>
              </div>

              <p className="text-xs text-muted-foreground mb-4">
                Results are ready. Use the tabs to review your current plan, simulated outcomes, and AI-generated recommendations.
              </p>

              <div className="space-y-2">
                {targetsSaved ? (
                  <div className="flex items-center justify-center gap-2 py-2 rounded-[var(--radius-sm)] bg-emerald-50 border border-emerald-200">
                    <Check className="size-3.5 text-emerald-600" />
                    <span className="text-xs text-emerald-700">Targets Saved</span>
                  </div>
                ) : (
                  <Button
                    onClick={onSetTargets}
                    className="w-full"
                    size="sm"
                  >
                    <Target className="size-3.5 mr-1.5" />
                    Set Forecast As Goals
                  </Button>
                )}

                <button
                  onClick={() => onRunSimulation()}
                  className="flex items-center justify-center gap-1 w-full text-[0.625rem] text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] cursor-pointer transition-colors py-1.5"
                  title="Re-run simulation"
                >
                  <RefreshCw className="size-3" />
                  Re-run Simulation
                </button>
              </div>
            </>
          )}
        </Card>

        {/* Set Forecast As Goals (disabled pre-simulation) */}
        {!simulationRun && !simulating && (
          <Card className="p-4 opacity-60">
            <div className="flex items-center gap-2 mb-2">
              <Target className="size-4 text-muted-foreground" />
              <h3 className="text-xs text-muted-foreground tracking-wide uppercase">Set Forecast As Goals</h3>
            </div>
            <p className="text-[0.6875rem] text-muted-foreground">
              Run a simulation first to unlock goal setting. Goals save predicted KPI values for each funnel stage across the forecast period.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}

/* ========== Forecasted Performance — Funnel Accordion Step ========== */

const FORECAST_ANALYST_NOTES: Record<string, string> = {
  'problem-awareness': 'Problem Awareness is projected to see steady growth driven by top-of-funnel campaigns. The model indicates that Display and Social channels are contributing the most impressions. Consider A/B testing creative variations to maximize reach efficiency — small gains in CPM can compound significantly at this volume.',
  'brand-awareness': 'Brand Awareness uplift is being driven primarily by paid social and influencer partnerships. The simulation suggests momentum is building month-over-month. Retargeting audiences who engaged with Problem Awareness content could accelerate mid-funnel progression and improve overall brand recall metrics.',
  'consideration': 'Consideration stage shows the highest sensitivity to budget changes in the model. Current spend levels are generating solid engagement, but the marginal ROI curve suggests there is room for incremental investment. Email nurture sequences and content marketing are the most cost-effective levers here.',
  'conversion': 'Conversion uplift is closely tied to the volume and quality of Consideration-stage leads entering the pipeline. The forecast shows a compounding effect as earlier funnel stages build momentum. Ensure landing page experiences are optimized and that promotional offers are timed to coincide with peak intent windows in April and May.',
};

function ForecastFunnelStepRow({
  step,
  index,
  totalSteps,
  futureMonths,
  selectedMonth,
  selectedYear,
}: {
  step: (typeof FUNNEL_STEPS)[number];
  index: number;
  totalSteps: number;
  futureMonths: ReturnType<typeof getNext3Months>;
  selectedMonth: number;
  selectedYear: number;
}) {
  const topWidthPercent = 100 - (index / totalSteps) * 55;
  const bottomWidthPercent = 100 - ((index + 1) / totalSteps) * 55;

  const historicalData = useMemo(() => generateStepTrend(step.id, selectedMonth, selectedYear), [step.id, selectedMonth, selectedYear]);
  const baselineData = useMemo(() => generateBaseline(historicalData, futureMonths), [historicalData, futureMonths]);
  const plannedValues = useMemo(
    () => computePlannedForecast(historicalData, futureMonths, baselineData, step.objective),
    [historicalData, futureMonths, baselineData, step.objective]
  );

  // Compute per-month uplift percentages
  const monthlyUplifts = futureMonths.map((fm, i) => {
    const bl = baselineData[i].baseline;
    const pl = plannedValues[i] ?? bl;
    const pct = bl > 0 ? ((pl - bl) / bl) * 100 : 0;
    return { abbr: MONTH_ABBR[fm.month].toUpperCase(), pct };
  });

  // Total spend for this step across all 3 months
  const stepTotalSpend = futureMonths.reduce((sum, fm) => {
    const acts = getActivitiesForMonth(fm.month, fm.year).filter(a => getActivityObjective(a) === step.objective);
    return sum + acts.reduce((s, a) => s + (a.cost || 0), 0);
  }, 0);

  // Aggregate uplift across all 3 months
  const totalBaseline = baselineData.reduce((s, b) => s + b.baseline, 0);
  const totalPlanned = plannedValues.reduce((s, v) => s + (v ?? 0), 0);
  const aggregateUplift = totalBaseline > 0 ? ((totalPlanned - totalBaseline) / totalBaseline) * 100 : 0;

  return (
    <AccordionItem value={step.id} className="border-b-0 mb-1">
      <AccordionTrigger className="py-2.5 hover:no-underline">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Funnel shape */}
          <div className="w-1/3 shrink-0 flex flex-col items-center">
            <div
              className="relative flex items-center justify-center"
              style={{
                width: `${topWidthPercent}%`,
                minHeight: '2.5rem',
                clipPath: `polygon(${((100 - topWidthPercent) / 2)}% 0%, ${100 - ((100 - topWidthPercent) / 2)}% 0%, ${100 - ((100 - bottomWidthPercent) / 2)}% 100%, ${((100 - bottomWidthPercent) / 2)}% 100%)`,
                backgroundColor: step.color,
                opacity: 0.85,
              }}
            >
              <span className="text-white text-xs relative z-10">{formatCurrency(stepTotalSpend)}</span>
            </div>
          </div>

          {/* Label + monthly lift */}
          <div className="flex flex-col items-start min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm">{step.label}</span>
              {aggregateUplift > 0 && (
                <span className="text-[0.625rem] text-green-600">+{aggregateUplift.toFixed(1)}% avg</span>
              )}
            </div>
            <div className="flex items-center gap-1 mt-0.5 text-[0.6875rem]">
              {monthlyUplifts.map((m, i) => (
                <span key={m.abbr} className="flex items-center gap-1">
                  {i > 0 && <ArrowRight className="size-2.5 text-muted-foreground/50" />}
                  <span className="text-muted-foreground">{m.abbr}</span>
                  <span className={m.pct > 0 ? 'text-green-600' : m.pct < 0 ? 'text-red-500' : 'text-muted-foreground'}>
                    {m.pct > 0 ? '+' : ''}{m.pct.toFixed(1)}%
                  </span>
                </span>
              ))}
            </div>
          </div>

          {/* Mini uplift bar */}
          <div className="w-24 shrink-0">
            <div className="h-1.5 w-full bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${Math.min(aggregateUplift * 3, 100)}%`, backgroundColor: step.color }}
              />
            </div>
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent className="pt-2 pb-4">
        <div className="space-y-3">
          {/* Analyst Notes */}
          <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-3">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Sparkles className="size-3 text-[var(--color-violet-500)]" />
              <span className="text-[0.625rem] text-muted-foreground tracking-wide uppercase">Analyst Notes</span>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {FORECAST_ANALYST_NOTES[step.id]}
            </p>
          </div>

          {/* Forecast Chart */}
          <ForecastChart
            stepId={step.id}
            stepColor={step.color}
            stepLabel={step.label}
            stepObjective={step.objective}
            futureMonths={futureMonths}
            selectedMonth={selectedMonth}
            selectedYear={selectedYear}
          />
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}