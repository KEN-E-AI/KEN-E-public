import { useState, useEffect, useCallback, useRef } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import {
  Sparkles,
  Check,
} from 'lucide-react';
import { cn } from './ui/utils';
import { motion, AnimatePresence } from 'motion/react';
import {
  calendarActivities,
} from '../data/calendarData';

/* ========== Constants ========== */

const FUNNEL_STEPS = [
  { id: 'problem-awareness', label: 'Problem Awareness', color: '#3B82F6' },
  { id: 'brand-awareness', label: 'Brand Awareness', color: '#6366F1' },
  { id: 'consideration', label: 'Consideration', color: '#F59E0B' },
  { id: 'conversion', label: 'Conversion', color: '#2EC4B6' },
];

type Phase = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

const PHASE_DURATIONS: Record<Phase, number> = {
  0: 1200,
  1: 12000,
  2: 800,
  3: 12000,
  4: 800,
  5: 12000,
  6: 800,
  7: 1500,
};

const PROGRESS_PERCENTS: Record<Phase, number> = {
  0: 3,
  1: 15,
  2: 33,
  3: 45,
  4: 63,
  5: 75,
  6: 93,
  7: 100,
};

// Per-step progress increments within analyzing phases
const STEP_INCREMENT = 3.25; // (28-15)/4, (58-45)/4, (88-75)/4

type CellState = 'waiting' | 'analyzing' | 'computed';

const INSIGHT_LINES = [
  "Reviewing planned activities across Paid Search and Social channels",
  "Comparing against similar campaigns from the past 6 months",
  "Evaluating channel mix efficiency for Problem Awareness spend",
  "Cross-referencing seasonal patterns from prior Q2 periods",
  "Assessing how Brand Awareness momentum compounds into Consideration",
  "Estimating conversion rates based on historical funnel flow patterns",
  "Checking for diminishing returns at current spend levels",
  "Analyzing interaction effects between concurrent campaigns",
  "Weighting recent performance trends more heavily than older data",
  "Factoring in planned promotional activity impact on conversion",
  "Evaluating cross-channel synergies in your media mix",
  "Calibrating confidence intervals based on data consistency",
];

function formatCurrency(val: number): string {
  if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
  if (val >= 1000) return `$${(val / 1000).toFixed(1)}k`;
  return `$${val.toLocaleString()}`;
}

function getMockLift(monthIndex: number, stepIndex: number): number {
  const seed = (monthIndex + 1) * 1000 + stepIndex * 100;
  const x = Math.sin(seed * 9301 + 49297) * 49297;
  const rand = x - Math.floor(x);
  return +(1.5 + rand * 6).toFixed(1);
}

function getMonthActivityStats(month: number, year: number) {
  const acts = calendarActivities.filter(a => {
    if (a.category === 'holiday') return false;
    return a.launch_date.getMonth() === month && a.launch_date.getFullYear() === year;
  });
  const spend = acts.reduce((s, a) => s + (a.cost || 0), 0);
  return { count: acts.length, spend };
}

/* ========== Types ========== */

export type SimulationProgressState = {
  phase: Phase;
  progressPercent: number;
  phaseLabel: string;
  phaseSubLabel: string;
  shortPhaseLabel: string;
  elapsedSeconds: number;
};

type SimulationProgressPanelProps = {
  simulationMonths: { month: number; year: number; label: string; abbr: string }[];
  onComplete: () => void;
  onCancel: () => void;
  onProgressChange?: (state: SimulationProgressState) => void;
};

/* ========== Main Component ========== */

export function SimulationProgressPanel({
  simulationMonths,
  onComplete,
  onCancel,
  onProgressChange,
}: SimulationProgressPanelProps) {
  const [phase, setPhase] = useState<Phase>(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [cellStates, setCellStates] = useState<CellState[][]>(() =>
    Array.from({ length: 3 }, () => Array(4).fill('waiting') as CellState[])
  );
  const [completedMonths, setCompletedMonths] = useState<Set<number>>(new Set());
  const [insightIndex, setInsightIndex] = useState(0);
  const [insightVisible, setInsightVisible] = useState(true);
  const [completionStage, setCompletionStage] = useState<0 | 1 | 2 | 3>(0); // 0=running, 1=rainbow, 2=summary, 3=fadeout
  const [panelOpacity, setPanelOpacity] = useState(1);
  const cancelledRef = useRef(false);

  // Derive active month from phase
  const activeMonth = phase <= 2 ? 0 : phase <= 4 ? 1 : 2;

  // Phase labels
  const getPhaseLabels = useCallback((p: Phase) => {
    const m = simulationMonths;
    const labels: Record<Phase, { label: string; sub: string; short: string }> = {
      0: { label: 'Preparing your simulation', sub: 'Loading historical patterns and forecast data', short: 'Preparing...' },
      1: { label: `Analyzing ${m[0].label} plans`, sub: 'AI is reviewing your tactical plans against similar past campaigns', short: `Analyzing ${m[0].abbr}...` },
      2: { label: `Computing ${m[0].label} outcomes`, sub: 'Estimating how your plans may flow through the funnel based on historical patterns', short: `Computing ${m[0].abbr}...` },
      3: { label: `Analyzing ${m[1].label} plans`, sub: `Building on ${m[0].label}'s estimated outcomes as the new baseline`, short: `Analyzing ${m[1].abbr}...` },
      4: { label: `Computing ${m[1].label} outcomes`, sub: 'Propagating estimated effects through the funnel model', short: `Computing ${m[1].abbr}...` },
      5: { label: `Analyzing ${m[2].label} plans`, sub: 'Incorporating two months of estimated cumulative effects', short: `Analyzing ${m[2].abbr}...` },
      6: { label: `Computing ${m[2].label} outcomes`, sub: 'Finalizing the 3-month estimated outlook', short: `Computing ${m[2].abbr}...` },
      7: { label: 'Assembling your forecast', sub: 'Combining all periods into your simulation results', short: 'Assembling forecast...' },
    };
    return labels[p];
  }, [simulationMonths]);

  // Compute progress percent with per-step granularity
  const getProgressPercent = useCallback((p: Phase, cells: CellState[][]) => {
    const base = PROGRESS_PERCENTS[p];
    // For analyzing phases, add per-step increments
    if (p === 1 || p === 3 || p === 5) {
      const monthIdx = p === 1 ? 0 : p === 3 ? 1 : 2;
      const completedSteps = cells[monthIdx].filter(s => s === 'computed').length;
      return base + completedSteps * STEP_INCREMENT;
    }
    return base;
  }, []);

  // Report progress to parent
  useEffect(() => {
    if (onProgressChange) {
      const labels = getPhaseLabels(phase);
      onProgressChange({
        phase,
        progressPercent: getProgressPercent(phase, cellStates),
        phaseLabel: labels.label,
        phaseSubLabel: labels.sub,
        shortPhaseLabel: labels.short,
        elapsedSeconds,
      });
    }
  }, [phase, cellStates, elapsedSeconds, onProgressChange, getPhaseLabels, getProgressPercent]);

  // Elapsed timer
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds(s => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Insight rotation
  useEffect(() => {
    const interval = setInterval(() => {
      setInsightVisible(false);
      setTimeout(() => {
        setInsightIndex(i => (i + 1) % INSIGHT_LINES.length);
        setInsightVisible(true);
      }, 300);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Phase progression
  useEffect(() => {
    if (cancelledRef.current) return;
    if (completionStage > 0) return;

    if (phase === 1 || phase === 3 || phase === 5) {
      // Analyzing phases: animate cells sequentially
      const monthIdx = phase === 1 ? 0 : phase === 3 ? 1 : 2;
      const stepDuration = PHASE_DURATIONS[phase] / 4;

      const timeouts: ReturnType<typeof setTimeout>[] = [];

      for (let i = 0; i < 4; i++) {
        // Start analyzing
        timeouts.push(setTimeout(() => {
          if (cancelledRef.current) return;
          setCellStates(prev => {
            const next = prev.map(r => [...r]);
            next[monthIdx][i] = 'analyzing';
            return next;
          });
        }, i * stepDuration));

        // Complete step
        timeouts.push(setTimeout(() => {
          if (cancelledRef.current) return;
          setCellStates(prev => {
            const next = prev.map(r => [...r]);
            next[monthIdx][i] = 'computed';
            return next;
          });
        }, (i + 1) * stepDuration - 400));
      }

      // Move to next phase
      timeouts.push(setTimeout(() => {
        if (cancelledRef.current) return;
        setCompletedMonths(prev => new Set(prev).add(monthIdx));
        setPhase(p => Math.min(p + 1, 7) as Phase);
      }, PHASE_DURATIONS[phase]));

      return () => timeouts.forEach(clearTimeout);
    } else if (phase === 7) {
      // Completion sequence
      const t = setTimeout(() => {
        if (cancelledRef.current) return;
        setCompletionStage(1);
      }, PHASE_DURATIONS[phase]);
      return () => clearTimeout(t);
    } else {
      // Non-analyzing phases: just wait and advance
      const t = setTimeout(() => {
        if (cancelledRef.current) return;
        setPhase(p => Math.min(p + 1, 7) as Phase);
      }, PHASE_DURATIONS[phase]);
      return () => clearTimeout(t);
    }
  }, [phase, completionStage]);

  // Completion animation sequence
  useEffect(() => {
    if (completionStage === 1) {
      // Rainbow pulse for 800ms, then show summary
      const t = setTimeout(() => setCompletionStage(2), 800);
      return () => clearTimeout(t);
    }
    if (completionStage === 2) {
      // Show summary for 600ms, then fade out
      const t = setTimeout(() => setCompletionStage(3), 600);
      return () => clearTimeout(t);
    }
    if (completionStage === 3) {
      setPanelOpacity(0);
      const t = setTimeout(() => onComplete(), 500);
      return () => clearTimeout(t);
    }
  }, [completionStage, onComplete]);

  const handleCancel = () => {
    cancelledRef.current = true;
    onCancel();
  };

  const labels = getPhaseLabels(phase);
  const progressPercent = getProgressPercent(phase, cellStates);

  // Mock summary numbers
  const summaryData = [
    { label: 'Expected Revenue', value: '$1.2M' },
    { label: 'New Accounts', value: '847' },
    { label: 'Total Investment', value: formatCurrency(simulationMonths.reduce((s, m) => {
      const stats = getMonthActivityStats(m.month, m.year);
      return s + stats.spend;
    }, 0)) },
  ];

  return (
    <motion.div
      style={{ opacity: panelOpacity }}
      transition={{ duration: 0.5 }}
    >
      <Card
        className={cn(
          "p-6 border-2 bg-gradient-to-br from-[var(--color-violet-50)] to-[var(--color-bg-elevated)] transition-colors",
          completionStage === 1 ? "animate-[rainbow-border_0.8s_ease-in-out]" : "border-[var(--color-violet-300)]"
        )}
        style={{ transitionDuration: 'var(--duration-default)' }}
      >
        {/* Header: Phase label + Timer */}
        <div className="space-y-2 mb-6">
          <div className="flex items-center justify-between">
            <p className="text-sm" aria-live="polite">{labels.label}</p>
            <span className="text-xs font-mono text-muted-foreground tabular-nums" aria-hidden="true">{elapsedSeconds}s</span>
          </div>
          <p className="text-xs text-muted-foreground">{labels.sub}</p>

          {/* Progress bar */}
          <div
            className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--color-bg-secondary)]"
            role="progressbar"
            aria-valuenow={Math.round(progressPercent)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Simulation progress"
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${progressPercent}%`,
                background: 'linear-gradient(90deg, var(--color-blue-500), var(--color-violet-500))',
                transition: 'width 600ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            />
          </div>
        </div>

        {/* Month Stepper */}
        <div className="flex items-center justify-center gap-0 mb-5">
          {simulationMonths.map((month, mi) => {
            const isActive = activeMonth === mi;
            const isComplete = completedMonths.has(mi);
            const isPending = !isActive && !isComplete;

            return (
              <div key={month.label} className="contents">
                {mi > 0 && (
                  <div
                    className={cn(
                      "h-0.5 w-8 rounded-full transition-colors",
                      completedMonths.has(mi - 1) ? "bg-[var(--color-violet-500)]" : "bg-[var(--color-border-default)]"
                    )}
                    style={{ transitionDuration: 'var(--duration-moderate)' }}
                  />
                )}
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={cn(
                      "size-7 rounded-full flex items-center justify-center transition-all shrink-0",
                      isActive && "bg-[var(--color-violet-500)] shadow-md ring-2 ring-[var(--color-violet-200)]",
                      isComplete && "bg-[var(--color-violet-500)]",
                      isPending && "bg-[var(--color-bg-secondary)] border-2 border-[var(--color-border-default)]"
                    )}
                    style={{
                      transitionDuration: 'var(--duration-default)',
                      transitionTimingFunction: 'var(--ease-default)',
                    }}
                  >
                    {isComplete ? (
                      <Check className="size-3.5 text-white" strokeWidth={3} />
                    ) : isActive ? (
                      <span className="text-[0.625rem] text-white">{mi + 1}</span>
                    ) : (
                      <span className="text-[0.625rem] text-muted-foreground">{mi + 1}</span>
                    )}
                  </div>
                  <span
                    className={cn(
                      "text-[0.6875rem] transition-colors",
                      isActive ? "text-foreground" : "text-muted-foreground"
                    )}
                  >
                    {month.abbr}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Active Month Detail Card */}
        <AnimatePresence mode="wait">
          {completionStage === 0 && (
            <motion.div
              key={activeMonth}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
            >
              {(() => {
                const month = simulationMonths[activeMonth];
                const stats = getMonthActivityStats(month.month, month.year);
                return (
                  <div
                    className="rounded-[var(--radius-lg)] border-2 border-[var(--color-violet-400)] bg-[var(--color-bg-elevated)] shadow-md p-4"
                  >
                    <h3 className="text-sm mb-3 text-center">{month.label}</h3>
                    <div className="space-y-2.5">
                      {FUNNEL_STEPS.map((step, si) => (
                        <FunnelStepCell
                          key={step.id}
                          stepLabel={step.label}
                          stepColor={step.color}
                          state={cellStates[activeMonth][si]}
                          estimatedLift={getMockLift(activeMonth, si)}
                        />
                      ))}
                    </div>
                    <p className="text-[0.625rem] text-muted-foreground text-center mt-3">
                      {stats.count} activities &middot; {formatCurrency(stats.spend)}
                    </p>
                  </div>
                );
              })()}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Activity Insight Line */}
        <p
          className={cn(
            "text-[0.6875rem] text-muted-foreground/70 italic text-center mt-4 h-4 transition-opacity",
            insightVisible ? "opacity-100" : "opacity-0"
          )}
          style={{ transitionDuration: 'var(--duration-default)' }}
        >
          {INSIGHT_LINES[insightIndex]}
        </p>

        {/* Completion Summary */}
        <AnimatePresence>
          {completionStage >= 2 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t border-[var(--color-border-default)]"
            >
              {summaryData.map(item => (
                <div key={item.label} className="text-center">
                  <p className="text-[0.625rem] text-muted-foreground uppercase tracking-wide">{item.label}</p>
                  <p className="text-xl font-mono tabular-nums mt-1">{item.value}</p>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Cancel button */}
        {completionStage === 0 && (
          <div className="flex justify-end mt-4">
            <Button variant="ghost" size="sm" onClick={handleCancel} className="text-xs text-muted-foreground">
              Cancel
            </Button>
          </div>
        )}
      </Card>
    </motion.div>
  );
}

/* ========== Sub-components ========== */

function FunnelStepCell({
  stepLabel,
  stepColor,
  state,
  estimatedLift,
}: {
  stepLabel: string;
  stepColor: string;
  state: CellState;
  estimatedLift: number;
}) {
  if (state === 'waiting') {
    return (
      <div className="flex items-center gap-2.5 py-1.5 px-2 rounded-[var(--radius-sm)]">
        <div className="size-3 rounded-full border-2 shrink-0" style={{ borderColor: `${stepColor}50` }} />
        <span className="text-xs text-muted-foreground">{stepLabel}</span>
      </div>
    );
  }

  if (state === 'analyzing') {
    return (
      <div className="flex items-center gap-2.5 py-1.5 px-2 rounded-[var(--radius-sm)] relative overflow-hidden">
        <div
          className="absolute inset-0 animate-[shimmer_2s_ease-in-out_infinite]"
          style={{ background: `linear-gradient(90deg, transparent 0%, ${stepColor}15 50%, transparent 100%)` }}
        />
        <div className="size-3 rounded-full shrink-0 animate-pulse" style={{ backgroundColor: stepColor }} />
        <span className="text-xs relative z-10">{stepLabel}</span>
        <Sparkles className="size-3 text-[var(--color-violet-400)] ml-auto animate-pulse relative z-10" />
      </div>
    );
  }

  // computed
  return (
    <div className="flex items-center gap-2.5 py-1.5 px-2 rounded-[var(--radius-sm)]">
      <div className="size-3 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: stepColor }}>
        <Check className="size-2 text-white" strokeWidth={3} aria-label="Complete" />
      </div>
      <span className="text-xs">{stepLabel}</span>
      <span className="text-[0.6875rem] font-mono text-emerald-600 ml-auto tabular-nums">
        +{estimatedLift.toFixed(1)}%
      </span>
    </div>
  );
}