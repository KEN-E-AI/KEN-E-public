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
} from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '../../components/ui/accordion';
import { mockAnalysisHistory, NEXT_ANALYSIS_DATE } from '../../data/mockData';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import type { PerformanceMetric, AnalysisSnapshot, Recommendation } from '../../data/mockData';
import {
  getOnTargetCount,
  getBelowTargetMetrics,
  formatMetricValue,
  formatTargetValue,
} from './performanceUtils';

export function PerformanceOptimizerExtension() {
  const currentAnalysis = mockAnalysisHistory[0];
  const previousAnalyses = mockAnalysisHistory.slice(1);

  return (
    <div className="px-6 pb-6 space-y-6">
      {/* Current Analysis */}
      <AnalysisCard snapshot={currentAnalysis} isCurrent />

      {/* Previous Analyses */}
      <div className="bg-card rounded-lg border">
        <div className="p-5 pb-2">
          <div className="flex items-center gap-3 mb-1">
            <div
              className="size-9 rounded-[var(--radius-md)] bg-[var(--color-slate-500,#64748b)] flex items-center justify-center"
              style={{ boxShadow: '0 4px 14px rgba(100, 116, 139, 0.25)' }}
            >
              <History className="size-4 text-[var(--color-text-inverse)]" />
            </div>
            <div>
              <h2>Previous Analyses</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {previousAnalyses.length} historical analyses available
              </p>
            </div>
          </div>
        </div>

        <Accordion type="single" collapsible className="px-5 pb-3">
          {previousAnalyses.map((snapshot) => {
            const onTargetCount = getOnTargetCount(snapshot.metrics);
            const totalMetrics = snapshot.metrics.length;

            return (
              <AccordionItem key={snapshot.id} value={snapshot.id} className="border-b-0">
                <AccordionTrigger className="py-3 hover:no-underline">
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm shrink-0">
                        {snapshot.completedAt.toLocaleDateString('en-US', {
                          month: 'long',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge
                        variant={
                          onTargetCount === totalMetrics
                            ? 'default'
                            : onTargetCount >= totalMetrics / 2
                              ? 'secondary'
                              : 'destructive'
                        }
                      >
                        {onTargetCount} of {totalMetrics} KPIs on target
                      </Badge>
                      <Badge variant="outline">
                        {snapshot.recommendations.length} recommendation
                        {snapshot.recommendations.length !== 1 ? 's' : ''}
                      </Badge>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-2 pb-4">
                  <AnalysisSnapshotContent snapshot={snapshot} />
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </div>
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
              className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center -rotate-2"
              style={{ boxShadow: 'var(--shadow-color-violet)' }}
            >
              <BarChart3 className="size-4 text-[var(--color-text-inverse)]" />
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