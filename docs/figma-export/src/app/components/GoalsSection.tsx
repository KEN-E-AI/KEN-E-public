import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Target, Save, Loader2, Star, Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { cn } from './ui/utils';
import { useGoals } from '../contexts/GoalsContext';
import {
  FUNNEL_STAGES,
  CONFIG_FUNNEL_MAPPING,
  MONTHS_FULL,
  getHistoricMonths,
  getFutureMonths,
  generateActualValue,
  getHistoricGoal,
  getKpiForStageMonth,
  goalKey,
} from '../data/goalsData';

/* ========== Number formatting ========== */

function formatNumber(val: number): string {
  return val.toLocaleString('en-US');
}

function parseInputValue(raw: string): number | null {
  const cleaned = raw.replace(/[^0-9.-]/g, '');
  const n = parseFloat(cleaned);
  return isNaN(n) ? null : Math.round(n);
}

/* ========== GoalsSection ========== */

export function GoalsSection() {
  const { goals, setGoal, isDirty, isSaving, saveGoals, dirtyKeys } = useGoals();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const historicMonths = useMemo(() => getHistoricMonths(), []);
  const futureMonths = useMemo(() => getFutureMonths(), []);

  // Check scroll state
  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  const scrollBy = useCallback((direction: 'left' | 'right') => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: direction === 'left' ? -260 : 260, behavior: 'smooth' });
  }, []);

  // On mount, scroll to show the current month as the first visible column
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Each historic column is ~260px, so scroll to the end of historic columns
    const historicWidth = historicMonths.length * 260;
    el.scrollLeft = historicWidth;
    // Small delay to let layout settle
    requestAnimationFrame(updateScrollState);
  }, [historicMonths.length, updateScrollState]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener('scroll', updateScrollState, { passive: true });
    window.addEventListener('resize', updateScrollState);
    return () => {
      el.removeEventListener('scroll', updateScrollState);
      window.removeEventListener('resize', updateScrollState);
    };
  }, [updateScrollState]);

  const handleSave = async () => {
    await saveGoals();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2000);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Target className="size-5 text-[var(--color-violet-500)]" />
          <div>
            <h2>Goals</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Set future KPI targets and track performance against past goals.
            </p>
          </div>
        </div>
        {saveSuccess ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-sm)] bg-emerald-50 border border-emerald-200">
            <Check className="size-3.5 text-emerald-600" />
            <span className="text-xs text-emerald-700">Goals saved</span>
          </div>
        ) : (
          <Button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            size="sm"
            className={cn(
              "transition-all",
              isDirty && !isSaving
                ? "bg-gradient-to-r from-[var(--color-violet-600)] to-[var(--color-violet-500)] text-white shadow-[var(--shadow-color-violet)]"
                : ""
            )}
          >
            {isSaving ? (
              <>
                <Loader2 className="size-3.5 mr-1.5 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="size-3.5 mr-1.5" />
                Save Goals
              </>
            )}
          </Button>
        )}
      </div>

      {/* Table container */}
      <Card className="overflow-hidden">
        <div className="relative">
          {/* Left scroll fade + arrow */}
          {canScrollLeft && (
            <>
              <div
                className="absolute left-[12.5rem] top-0 bottom-0 w-8 z-20 pointer-events-none"
                style={{
                  background: 'linear-gradient(to right, rgba(0,0,0,0.06), transparent)',
                }}
              />
              <button
                onClick={() => scrollBy('left')}
                className="absolute left-[12.75rem] top-1/2 -translate-y-1/2 z-30 size-8 rounded-full bg-white/90 border border-[var(--color-border-default)] shadow-sm flex items-center justify-center hover:bg-white hover:shadow-md transition-all cursor-pointer"
                aria-label="Scroll left"
              >
                <ChevronLeft className="size-4 text-[var(--color-text-secondary)]" />
              </button>
            </>
          )}
          {/* Right scroll fade + arrow */}
          {canScrollRight && (
            <>
              <div
                className="absolute right-0 top-0 bottom-0 w-8 z-20 pointer-events-none"
                style={{
                  background: 'linear-gradient(to left, rgba(0,0,0,0.06), transparent)',
                }}
              />
              <button
                onClick={() => scrollBy('right')}
                className="absolute right-[0.25rem] top-1/2 -translate-y-1/2 z-30 size-8 rounded-full bg-white/90 border border-[var(--color-border-default)] shadow-sm flex items-center justify-center hover:bg-white hover:shadow-md transition-all cursor-pointer"
                aria-label="Scroll right"
              >
                <ChevronRight className="size-4 text-[var(--color-text-secondary)]" />
              </button>
            </>
          )}

          <div className="flex">
            {/* Frozen column */}
            <div className="shrink-0 w-[12.5rem] z-10 bg-[var(--color-bg-elevated)]" style={{ boxShadow: '0.125rem 0 0.25rem -0.125rem rgba(0,0,0,0.06)' }}>
              {/* Header cell */}
              <div className="h-[4.5rem] flex items-end px-4 pb-3 border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
                <span className="text-xs text-muted-foreground tracking-wide uppercase">Funnel Stage</span>
              </div>
              {/* Stage rows */}
              {FUNNEL_STAGES.map((stage) => {
                const mapping = CONFIG_FUNNEL_MAPPING.find(m => m.stage === stage.label);
                return (
                  <div
                    key={stage.id}
                    className="h-[4.5rem] flex items-center px-4 border-b border-[var(--color-border-default)] group/row hover:bg-[var(--color-bg-secondary)] transition-colors"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <div className="size-2 rounded-full shrink-0" style={{ backgroundColor: stage.color }} />
                        <span className="text-sm">{stage.label}</span>
                      </div>
                      <p className="text-[0.6875rem] text-muted-foreground ml-4 mt-0.5">
                        {mapping?.display_name || '—'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Scrollable columns */}
            <div ref={scrollRef} className="flex-1 overflow-x-auto">
              <div className="flex min-w-max">
                {/* Historic month columns */}
                {historicMonths.map((hm) => (
                  <HistoricColumn key={`${hm.month}-${hm.year}`} month={hm.month} year={hm.year} />
                ))}

                {/* Violet divider */}
                <div className="w-[2px] shrink-0 bg-[var(--color-violet-400)]" />

                {/* Future month columns */}
                {futureMonths.map((fm, i) => (
                  <FutureColumn
                    key={`${fm.month}-${fm.year}`}
                    month={fm.month}
                    year={fm.year}
                    isCurrent={i === 0}
                    goals={goals}
                    dirtyKeys={dirtyKeys}
                    onSetGoal={setGoal}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Disclaimer footer */}
      <p className="text-[0.625rem] text-muted-foreground text-center px-4">
        Goals are based on forecasted KPI values and historical trends. Actual results may vary. This tool is not intended for financial reporting or compliance purposes.
      </p>
    </div>
  );
}

/* ========== Historic Column ========== */

function HistoricColumn({ month, year }: { month: number; year: number }) {
  return (
    <div className="w-[16.25rem] shrink-0">
      {/* Header */}
      <div className="h-[4.5rem] flex flex-col justify-end px-3 pb-2 border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
        <span className="text-xs mb-1.5">{MONTHS_FULL[month]} {year}</span>
        <div className="grid grid-cols-3 gap-1">
          <span className="text-[0.625rem] text-muted-foreground">Goal</span>
          <span className="text-[0.625rem] text-muted-foreground">Actual</span>
          <span className="text-[0.625rem] text-muted-foreground">% Diff</span>
        </div>
      </div>

      {/* Data rows */}
      {FUNNEL_STAGES.map((stage) => {
        const kpiInfo = getKpiForStageMonth(stage.label, month, year);
        const actual = generateActualValue(stage.id, month, year);
        const goal = getHistoricGoal(stage.id, month, year);
        const diff = goal !== null ? ((actual - goal) / goal) * 100 : null;

        return (
          <div
            key={stage.id}
            className="h-[4.5rem] flex flex-col justify-center px-3 border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]/30 hover:bg-[var(--color-bg-secondary)] transition-colors"
          >
            <span className="text-[0.625rem] text-muted-foreground mb-1 truncate">{kpiInfo.display_name}</span>
            <div className="grid grid-cols-3 gap-1">
              <span className="text-xs tabular-nums">
                {goal !== null ? formatNumber(goal) : <span className="text-muted-foreground">—</span>}
              </span>
              <span className="text-xs tabular-nums">{formatNumber(actual)}</span>
              <span className={cn(
                "text-xs tabular-nums",
                diff === null ? "text-muted-foreground" :
                diff > 0 ? "text-green-600" :
                diff < 0 ? "text-red-500" : "text-muted-foreground"
              )}>
                {diff === null ? '—' : `${diff > 0 ? '+' : ''}${diff.toFixed(1)}%`}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ========== Future Column ========== */

function FutureColumn({
  month,
  year,
  isCurrent,
  goals,
  dirtyKeys,
  onSetGoal,
}: {
  month: number;
  year: number;
  isCurrent: boolean;
  goals: Map<string, number | null>;
  dirtyKeys: Set<string>;
  onSetGoal: (stageId: string, month: number, year: number, value: number | null) => void;
}) {
  return (
    <div className="w-[8.75rem] shrink-0">
      {/* Header */}
      <div className="h-[4.5rem] flex flex-col justify-end px-3 pb-2 border-b border-[var(--color-border-default)]">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-xs">{MONTHS_FULL[month]} {year}</span>
        </div>
        {isCurrent && (
          <div className="flex items-center gap-1 mb-1">
            <Star className="size-2.5 text-[var(--color-violet-500)] fill-[var(--color-violet-500)]" />
            <span className="text-[0.625rem] text-[var(--color-violet-600)]">Current</span>
          </div>
        )}
        <span className="text-[0.625rem] text-muted-foreground">Target</span>
      </div>

      {/* Editable cells */}
      {FUNNEL_STAGES.map((stage) => (
        <GoalInputCell
          key={stage.id}
          stageId={stage.id}
          stageLabel={stage.label}
          month={month}
          year={year}
          value={goals.get(goalKey(stage.id, month, year)) ?? null}
          isDirty={dirtyKeys.has(goalKey(stage.id, month, year))}
          onSetGoal={onSetGoal}
        />
      ))}
    </div>
  );
}

/* ========== Goal Input Cell ========== */

function GoalInputCell({
  stageId,
  stageLabel,
  month,
  year,
  value,
  isDirty,
  onSetGoal,
}: {
  stageId: string;
  stageLabel: string;
  month: number;
  year: number;
  value: number | null;
  isDirty: boolean;
  onSetGoal: (stageId: string, month: number, year: number, value: number | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFocus = () => {
    setEditing(true);
    setEditValue(value !== null ? String(value) : '');
    requestAnimationFrame(() => inputRef.current?.select());
  };

  const handleBlur = () => {
    setEditing(false);
    const parsed = parseInputValue(editValue);
    onSetGoal(stageId, month, year, parsed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  return (
    <div
      className={cn(
        "h-[4.5rem] flex items-center px-2 border-b border-[var(--color-border-default)] hover:bg-[var(--color-bg-secondary)] transition-colors",
        isDirty && "border-l-2 border-l-[var(--color-violet-400)] bg-[var(--color-violet-50)]/40"
      )}
    >
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        aria-label={`${stageLabel} target for ${MONTHS_FULL[month]} ${year}`}
        className={cn(
          "w-full h-9 px-2.5 text-xs tabular-nums rounded-[var(--radius-sm)] border transition-all outline-none",
          "bg-[var(--color-bg-elevated)]",
          value === null && !editing
            ? "border-dashed border-[var(--color-border-default)] text-muted-foreground"
            : "border-[var(--color-border-default)]",
          "focus:ring-2 focus:ring-[var(--color-violet-400)] focus:border-[var(--color-violet-400)]",
        )}
        placeholder="—"
        value={editing ? editValue : (value !== null ? formatNumber(value) : '')}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={handleKeyDown}
      />
    </div>
  );
}