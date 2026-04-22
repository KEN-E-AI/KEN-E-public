import {
  TrendingUp,
  TrendingDown,
  Lightbulb,
  AlertTriangle,
  BarChart3,
  Target,
  CheckCircle2,
  ArrowRight,
  CalendarClock,
  History,
  FlaskConical,
  Stethoscope,
  Settings,
  LayoutDashboard,
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { MonthYearPicker } from '../components/MonthYearPicker';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '../components/ui/accordion';
import { mockAnalysisHistory, NEXT_ANALYSIS_DATE } from '../data/mockData';
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import type { PerformanceMetric, AnalysisSnapshot, Recommendation } from '../data/mockData';
import {
  getOnTargetCount,
  getBelowTargetMetrics,
  formatMetricValue,
  formatTargetValue,
} from './extensions/performanceUtils';
import { cn } from '../components/ui/utils';
import { WhatHappenedCard } from '../components/WhatHappenedCard';
import { SimulationsSection } from '../components/SimulationsSection';
import { GoalsSection } from '../components/GoalsSection';
import { GoalsProvider } from '../contexts/GoalsContext';
import { DiagnosticsSection } from '../components/DiagnosticsSection';
import { ConfigSection } from '../components/ConfigSection';
import { DashboardsSection } from '../components/DashboardsSection';

type PerformanceTab = 'analysis' | 'dashboards' | 'simulations' | 'goals' | 'diagnostics' | 'config';
type CompareMode = 'mom' | 'yoy' | 'goal';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const YEARS = ['2024', '2025', '2026'];

// Mock data keyed by "YYYY-MM"
function generateMonthlyData(month: number, year: number) {
  // Seeded pseudo-random based on month+year for consistency
  const seed = year * 100 + month;
  const rand = (i: number) => {
    const x = Math.sin(seed * 9301 + i * 49297 + 233280) * 49297;
    return x - Math.floor(x);
  };
  return {
    conversions: Math.round(1200 + rand(1) * 800),
    estimatedRevenue: Math.round((1000000 + rand(2) * 1200000) / 1000) * 1000,
    goal: { conversions: 1500, revenue: 1500000 },
  };
}

function getComparisonLabel(compare: CompareMode) {
  switch (compare) {
    case 'mom': return 'Prior Month';
    case 'yoy': return 'Prior Year';
    case 'goal': return 'Goal';
  }
}

function getComparisonPeriod(month: number, year: number, compare: CompareMode) {
  if (compare === 'mom') {
    const m = month === 0 ? 11 : month - 1;
    const y = month === 0 ? year - 1 : year;
    return { month: m, year: y };
  }
  if (compare === 'yoy') {
    return { month, year: year - 1 };
  }
  return null; // goal mode
}

function getComparisonDescription(month: number, year: number, compare: CompareMode) {
  if (compare === 'goal') return `Goal: ${MONTHS[month]} ${year}`;
  const comp = getComparisonPeriod(month, year, compare)!;
  return `Comparison: ${MONTHS[comp.month]} ${comp.year}`;
}

function generateTrendData(month: number, year: number, compare: CompareMode) {
  // Generate 6 months of data ending at the selected period
  const points: { name: string; current: number; comparison: number }[] = [];
  for (let i = 5; i >= 0; i--) {
    let m = month - i;
    let y = year;
    while (m < 0) { m += 12; y -= 1; }

    const data = generateMonthlyData(m, y);

    let compVal: number;
    if (compare === 'goal') {
      compVal = data.goal.conversions;
    } else {
      const comp = getComparisonPeriod(m, y, compare)!;
      compVal = generateMonthlyData(comp.month, comp.year).conversions;
    }

    points.push({
      name: MONTH_ABBR[m],
      current: data.conversions,
      comparison: compVal,
    });
  }
  return points;
}

const performanceTabs: { name: string; value: PerformanceTab; icon: typeof BarChart3 }[] = [
  { name: 'Analysis', value: 'analysis', icon: BarChart3 },
  { name: 'Dashboards', value: 'dashboards', icon: LayoutDashboard },
  { name: 'Simulations', value: 'simulations', icon: FlaskConical },
  { name: 'Goals', value: 'goals', icon: Target },
  { name: 'Diagnostics', value: 'diagnostics', icon: Stethoscope },
  { name: 'Config', value: 'config', icon: Settings },
];

export function PerformancePage() {
  const [activeTab, setActiveTab] = useState<PerformanceTab>('analysis');

  return (
    <GoalsProvider>
    <div className="flex flex-col h-full">
      {/* Page Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center gap-3 mb-4">
          <div
            className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center"
            style={{ boxShadow: 'var(--shadow-color-violet)' }}
          >
            <TrendingUp className="size-4 text-[var(--color-text-inverse)]" />
          </div>
          <div>
            <h1>Performance</h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              AI-powered analysis of your marketing KPIs with actionable recommendations.
            </p>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1 p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] w-fit">
          {performanceTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] transition-all text-sm cursor-pointer",
                activeTab === tab.value
                  ? "bg-[var(--color-bg-elevated)] text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
              style={{
                transitionTimingFunction: 'var(--ease-default)',
                transitionDuration: 'var(--duration-fast)',
              }}
            >
              <tab.icon className="size-4" />
              <span>{tab.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        {activeTab === 'analysis' && <AnalysisSection />}
        {activeTab === 'dashboards' && <DashboardsSection />}
        {activeTab === 'simulations' && <SimulationsSection onNavigateToGoals={() => setActiveTab('goals')} />}
        {activeTab === 'goals' && <GoalsSection />}
        {activeTab === 'diagnostics' && <DiagnosticsSection />}
        {activeTab === 'config' && <ConfigSection />}
      </div>
    </div>
    </GoalsProvider>
  );
}

/* --- Analysis Section (existing content) --- */

function AnalysisSection() {
  const currentAnalysis = mockAnalysisHistory[0];
  const previousAnalyses = mockAnalysisHistory.slice(1);

  const [selectedMonth, setSelectedMonth] = useState(String(new Date().getMonth() === 0 ? 11 : new Date().getMonth() - 1));
  const [selectedYear, setSelectedYear] = useState(String(new Date().getMonth() === 0 ? new Date().getFullYear() - 1 : new Date().getFullYear()));
  const [compareMode, setCompareMode] = useState<CompareMode>('mom');

  const month = parseInt(selectedMonth, 10);
  const year = parseInt(selectedYear, 10);

  const currentData = useMemo(() => generateMonthlyData(month, year), [month, year]);
  const comparisonData = useMemo(() => {
    if (compareMode === 'goal') return currentData.goal;
    const comp = getComparisonPeriod(month, year, compareMode)!;
    const d = generateMonthlyData(comp.month, comp.year);
    return { conversions: d.conversions, revenue: d.estimatedRevenue };
  }, [month, year, compareMode, currentData]);

  const convChange = comparisonData.conversions === 0
    ? 0
    : ((currentData.conversions - comparisonData.conversions) / comparisonData.conversions) * 100;
  const revChange = comparisonData.revenue === 0
    ? 0
    : ((currentData.estimatedRevenue - comparisonData.revenue) / comparisonData.revenue) * 100;

  const trendData = useMemo(
    () => generateTrendData(month, year, compareMode),
    [month, year, compareMode]
  );

  const compareModes: { label: string; value: CompareMode }[] = [
    { label: 'Month over Month', value: 'mom' },
    { label: 'Year over Year', value: 'yoy' },
    { label: 'vs. Goal', value: 'goal' },
  ];

  return (
    <div className="space-y-6">
      {/* Period Selector Bar */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <MonthYearPicker
            month={month}
            year={year}
            onSelect={(m, y) => {
              setSelectedMonth(String(m));
              setSelectedYear(String(y));
            }}
          />
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 p-0.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)]">
            {compareModes.map((mode) => (
              <button
                key={mode.value}
                onClick={() => setCompareMode(mode.value)}
                className={cn(
                  "px-2.5 py-1 rounded-[var(--radius-xs)] text-xs transition-all cursor-pointer whitespace-nowrap",
                  compareMode === mode.value
                    ? "bg-[var(--color-violet-500)] text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
                style={{
                  transitionTimingFunction: 'var(--ease-default)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Target / Comparison context line */}
      <div className="flex items-center gap-4 text-xs">
        <span className="text-violet-500">
          Target: {MONTHS[month]} {year}
        </span>
        <span className="text-muted-foreground">
          {getComparisonDescription(month, year, compareMode)}
        </span>
      </div>

      {/* Scorecards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Conversions Scorecard */}
        <Card className="p-5">
          <div className="mb-2">
            <span className="text-xs text-muted-foreground tracking-wide uppercase">Conversions</span>
            {' '}
            <span className="text-[11px] text-muted-foreground/70">· Account Opens</span>
          </div>
          <p className="text-3xl mb-1" style={{ fontFamily: 'var(--font-display)' }}>
            {currentData.conversions.toLocaleString()}
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <span className={convChange >= 0 ? 'text-green-500' : 'text-red-500'}>
              {convChange >= 0 ? '+' : ''}{convChange.toFixed(1)}%
            </span>
            <span className="text-muted-foreground">vs. {getComparisonLabel(compareMode)}</span>
          </div>
        </Card>

        {/* Estimated Revenue Scorecard */}
        <Card className="p-5">
          <p className="text-xs text-muted-foreground tracking-wide uppercase mb-2">Estimated Revenue</p>
          <p className="text-3xl mb-1" style={{ fontFamily: 'var(--font-display)' }}>
            ${currentData.estimatedRevenue.toLocaleString()}
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <span className={revChange >= 0 ? 'text-green-500' : 'text-red-500'}>
              {revChange >= 0 ? '+' : ''}{revChange.toFixed(1)}%
            </span>
            <span className="text-muted-foreground">vs. {getComparisonLabel(compareMode)}</span>
          </div>
        </Card>
      </div>

      {/* Conversions Trend Chart */}
      <Card className="p-5">
        <h3 className="text-sm mb-4">Conversions Trend: Period Comparison</h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={trendData}>
            <CartesianGrid key="grid" strokeDasharray="3 3" stroke="var(--color-border-default)" />
            <XAxis
              key="xaxis"
              dataKey="name"
              tick={{ fontSize: 12 }}
              stroke="var(--color-border-default)"
              tickLine={false}
            />
            <YAxis
              key="yaxis"
              tick={{ fontSize: 12 }}
              stroke="var(--color-border-default)"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              key="tooltip"
              contentStyle={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border-default)',
                borderRadius: 'var(--radius-md)',
                fontSize: 12,
              }}
            />
            <Line
              key="current-line"
              type="monotone"
              dataKey="current"
              name={`${MONTHS[month]} ${year}`}
              stroke="var(--color-teal-500, #14b8a6)"
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2 }}
              activeDot={{ r: 6 }}
            />
            <Line
              key="comparison-line"
              type="monotone"
              dataKey="comparison"
              name={compareMode === 'goal' ? 'Goal' : (() => {
                const c = getComparisonPeriod(month, year, compareMode)!;
                return `${MONTHS[c.month]} ${c.year}`;
              })()}
              stroke="var(--color-text-tertiary, #9ca3af)"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={{ r: 4, strokeWidth: 2 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* What Happened */}
      <WhatHappenedCard month={month} year={year} compareMode={compareMode} />
    </div>
  );
}

/* --- Analysis Card --- */

function AnalysisCard({
  snapshot,
  isCurrent = false,
}: {
  snapshot: AnalysisSnapshot;
  isCurrent?: boolean;
}) {
  const dateStr = snapshot.completedAt.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div
      className="bg-card rounded-lg border"
      style={isCurrent ? { borderWidth: '2px', borderColor: 'var(--color-violet-500)' } : undefined}
    >
      <div className="p-5 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center"
              style={{ boxShadow: 'var(--shadow-color-violet)' }}
            >
              <TrendingUp className="size-4 text-[var(--color-text-inverse)]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2>{isCurrent ? 'Latest Analysis' : 'Analysis'}</h2>
                {isCurrent && (
                  <Badge variant="default" className="bg-[var(--color-violet-500)]">
                    Current
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">Completed {dateStr}</p>
            </div>
          </div>
          {isCurrent && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarClock className="size-3.5 text-blue-500" />
              Next analysis:{' '}
              {NEXT_ANALYSIS_DATE.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </div>
          )}
        </div>
      </div>

      <div className="p-5">
        <AnalysisSnapshotContent snapshot={snapshot} />
      </div>
    </div>
  );
}

function AnalysisSnapshotContent({ snapshot }: { snapshot: AnalysisSnapshot }) {
  const belowTargetMetrics = getBelowTargetMetrics(snapshot.metrics);

  return (
    <div className="space-y-6">
      {/* Overall Performance */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Target className="size-4 text-blue-500" />
          <h3 className="text-sm">Overall Performance</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {snapshot.metrics.map((metric) => (
            <KPICard key={metric.id} metric={metric} />
          ))}
        </div>
      </div>

      {/* Areas for Improvement */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="size-4 text-amber-500" />
          <h3 className="text-sm">Areas for Improvement</h3>
        </div>

        {belowTargetMetrics.length === 0 ? (
          <div className="text-center py-6 border-2 border-dashed border-[var(--color-border-default)] rounded-[var(--radius-md)]">
            <CheckCircle2 className="size-6 text-green-500 mx-auto mb-1.5" />
            <p className="text-xs text-muted-foreground">
              All KPIs meeting or exceeding targets
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {belowTargetMetrics.map((metric) => {
              const isCPA = metric.name === 'Cost Per Acquisition';
              const gap = isCPA ? metric.value - metric.target : metric.target - metric.value;
              const gapPercent = ((gap / metric.target) * 100).toFixed(1);

              return (
                <div
                  key={metric.id}
                  className="flex items-center gap-3 p-3 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)]"
                >
                  <div className="size-8 rounded-[var(--radius-md)] bg-red-500/10 flex items-center justify-center shrink-0">
                    <TrendingDown className="size-3.5 text-red-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{metric.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Current: {formatMetricValue(metric)} · Target: {formatTargetValue(metric)}
                    </p>
                  </div>
                  <Badge variant="destructive" className="shrink-0">
                    {isCPA ? '+' : '-'}
                    {gapPercent}% {isCPA ? 'over' : 'below'} target
                  </Badge>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recommendations */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="size-4 text-violet-500" />
          <h3 className="text-sm">Recommendations</h3>
          <Badge variant="outline" className="ml-1">
            {snapshot.recommendations.length}
          </Badge>
        </div>

        <div className="space-y-2">
          {snapshot.recommendations.map((rec) => (
            <RecommendationRow key={rec.id} rec={rec} />
          ))}
        </div>
      </div>
    </div>
  );
}

function RecommendationRow({ rec }: { rec: Recommendation }) {
  return (
    <div
      className="p-3 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all bg-[var(--color-bg-primary)]"
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-fast)',
      }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <p className="text-sm">{rec.title}</p>
            <Badge
              variant={
                rec.impact === 'high'
                  ? 'default'
                  : rec.impact === 'medium'
                    ? 'secondary'
                    : 'outline'
              }
            >
              {rec.impact} impact
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mb-1.5">{rec.description}</p>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ArrowRight className="size-3" />
            Addresses: {rec.category}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button size="sm" variant="default">
            Apply
          </Button>
          <Button size="sm" variant="outline">
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}

function KPICard({ metric }: { metric: PerformanceMetric }) {
  const chartData = metric.trend.map((value) => ({ value }));
  const isCPA = metric.name === 'Cost Per Acquisition';
  const isOnTarget = isCPA ? metric.value <= metric.target : metric.value >= metric.target;
  const progressPercent = isCPA
    ? Math.min(100, (metric.target / metric.value) * 100)
    : Math.min(100, (metric.value / metric.target) * 100);

  return (
    <Card className="p-3">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-xs text-muted-foreground mb-0.5">{metric.name}</p>
          <span className="text-lg" style={{ fontFamily: 'var(--font-display)' }}>
            {formatMetricValue(metric)}
          </span>
        </div>
        {metric.change > 0 ? (
          <TrendingUp className="size-3.5 text-green-500" />
        ) : (
          <TrendingDown className="size-3.5 text-red-500" />
        )}
      </div>

      <div className="mb-2">
        <ResponsiveContainer width="100%" height={32}>
          <LineChart data={chartData}>
            <Line
              type="monotone"
              dataKey="value"
              stroke={metric.change > 0 ? '#10b981' : '#ef4444'}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mb-1.5">
        <div className="flex items-center justify-between text-xs mb-0.5">
          <span className="text-muted-foreground">Target: {formatTargetValue(metric)}</span>
          <span className={isOnTarget ? 'text-green-500' : 'text-amber-500'}>
            {progressPercent.toFixed(0)}%
          </span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${isOnTarget ? 'bg-green-500' : 'bg-amber-500'}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      <div className="flex items-center gap-1 text-xs">
        <span className={metric.change > 0 ? 'text-green-500' : 'text-red-500'}>
          {metric.change > 0 ? '+' : ''}
          {metric.change}%
        </span>
        <span className="text-muted-foreground">vs last period</span>
      </div>
    </Card>
  );
}