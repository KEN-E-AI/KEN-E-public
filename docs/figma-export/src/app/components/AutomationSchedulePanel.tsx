import { useState, useMemo, useEffect } from 'react';
import {
  X,
  Save,
  CalendarClock,
  AlertTriangle,
  Timer,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { Button } from './ui/button';
import {
  type AutomationSchedule,
  type ScheduleFrequency,
  DAY_LABELS,
  computeNextRun,
  describeSchedule,
} from '../data/automationDetailsData';

const FREQUENCIES: { value: ScheduleFrequency; label: string }[] = [
  { value: 'once', label: 'Once' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'custom_cron', label: 'Custom Cron' },
];

interface AutomationSchedulePanelProps {
  schedule: AutomationSchedule;
  onSave: (updated: AutomationSchedule) => void;
  onClose: () => void;
  hasRootTasks: boolean;
  rootTaskCount: number;
  isRunning: boolean;
}

export function AutomationSchedulePanel({
  schedule,
  onSave,
  onClose,
  hasRootTasks,
  rootTaskCount,
  isRunning,
}: AutomationSchedulePanelProps) {
  const [draft, setDraft] = useState<AutomationSchedule>({ ...schedule });

  const update = <K extends keyof AutomationSchedule>(key: K, value: AutomationSchedule[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const toggleDay = (day: number) => {
    setDraft((prev) => {
      const has = prev.days_of_week.includes(day);
      return {
        ...prev,
        days_of_week: has
          ? prev.days_of_week.filter((d) => d !== day)
          : [...prev.days_of_week, day].sort((a, b) => a - b),
      };
    });
  };

  const previewNextRun = useMemo(() => computeNextRun(draft), [draft]);

  const previewDescription = useMemo(() => describeSchedule(draft), [draft]);

  const isDirty = useMemo(() => {
    return JSON.stringify(draft) !== JSON.stringify(schedule);
  }, [draft, schedule]);

  const handleSave = () => {
    const withNextRun = { ...draft, next_run: computeNextRun(draft) };
    onSave(withNextRun);
  };

  const handleCancel = () => {
    setDraft({ ...schedule });
  };

  const formatNextRun = (d: Date | null) => {
    if (!d) return '—';
    return d.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }) + ' at ' + d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short',
    });
  };

  return (
    <div className="w-[23.75rem] h-full border-l border-[var(--color-border-default)] bg-card flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
        <div className="flex items-center gap-2">
          <CalendarClock className="size-4 text-[var(--color-violet-500)]" />
          <p className="text-sm">Schedule Automation</p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]"
        >
          <X className="size-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Enable / Disable toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--color-text-primary)]">Schedule Enabled</p>
            <p className="text-[0.625rem] text-[var(--color-text-tertiary)] mt-0.5">
              When enabled, this automation will run on its configured schedule
            </p>
          </div>
          <button
            onClick={() => update('enabled', !draft.enabled)}
            disabled={isRunning}
            className="flex items-center transition-colors disabled:opacity-50"
            title={draft.enabled ? 'Disable schedule' : 'Enable schedule'}
          >
            {draft.enabled ? (
              <ToggleRight className="size-7 text-[var(--color-success)]" />
            ) : (
              <ToggleLeft className="size-7 text-[var(--color-text-tertiary)]" />
            )}
          </button>
        </div>

        {/* No root tasks warning */}
        {!hasRootTasks && draft.enabled && (
          <div className="flex items-start gap-2 p-2.5 rounded-[var(--radius-md)] bg-[var(--color-warning-bg)] border border-[var(--color-warning)]">
            <AlertTriangle className="size-3.5 text-[var(--color-warning)] mt-0.5 shrink-0" />
            <p className="text-[0.625rem] text-[var(--color-warning-text)]">
              No start tasks found. The schedule needs at least one task with no dependencies to begin execution.
            </p>
          </div>
        )}

        {/* Root tasks info */}
        {hasRootTasks && draft.enabled && (
          <div className="flex items-start gap-2 p-2.5 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] border border-[var(--color-border-subtle)]">
            <Timer className="size-3.5 text-[var(--color-violet-500)] mt-0.5 shrink-0" />
            <p className="text-[0.625rem] text-[var(--color-text-secondary)]">
              When triggered, <strong>{rootTaskCount} root task{rootTaskCount !== 1 ? 's' : ''}</strong> with no dependencies will start running simultaneously.
            </p>
          </div>
        )}

        {/* Frequency */}
        <div>
          <label className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1.5 block">Frequency</label>
          <div className="flex flex-wrap gap-1.5">
            {FREQUENCIES.map((f) => (
              <button
                key={f.value}
                onClick={() => update('frequency', f.value)}
                disabled={!draft.enabled || isRunning}
                className={`text-[0.6875rem] px-2.5 py-1.5 rounded-[var(--radius-sm)] border transition-colors disabled:opacity-50 ${
                  draft.frequency === f.value
                    ? 'bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]'
                    : 'border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Once: date picker */}
        {draft.frequency === 'once' && (
          <div>
            <label className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1.5 block">
              Run date
            </label>
            <input
              type="date"
              disabled={!draft.enabled || isRunning}
              value={draft.run_date ? `${draft.run_date.getFullYear()}-${String(draft.run_date.getMonth() + 1).padStart(2, '0')}-${String(draft.run_date.getDate()).padStart(2, '0')}` : ''}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) { update('run_date', null); return; }
                const [y, m, d] = v.split('-').map(Number);
                update('run_date', new Date(y, m - 1, d));
              }}
              className="w-full text-xs px-3 py-2 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)] disabled:opacity-50"
            />
            {!draft.run_date && draft.enabled && (
              <p className="text-[0.625rem] text-[var(--color-error-text)] mt-1">Pick a date</p>
            )}
          </div>
        )}

        {/* Weekly: day picker */}
        {draft.frequency === 'weekly' && (
          <div>
            <label className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1.5 block">
              Days of Week
            </label>
            <div className="flex gap-1">
              {DAY_LABELS.map((label, idx) => (
                <button
                  key={idx}
                  onClick={() => toggleDay(idx)}
                  disabled={!draft.enabled || isRunning}
                  className={`flex-1 text-[0.625rem] py-2 rounded-[var(--radius-sm)] border transition-colors disabled:opacity-50 ${
                    draft.days_of_week.includes(idx)
                      ? 'bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]'
                      : 'border-[var(--color-border-default)] text-[var(--color-text-tertiary)] hover:border-[var(--color-border-strong)]'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {draft.days_of_week.length === 0 && draft.enabled && (
              <p className="text-[0.625rem] text-[var(--color-error-text)] mt-1">
                Select at least one day
              </p>
            )}
          </div>
        )}

        {/* Monthly: day of month */}
        {draft.frequency === 'monthly' && (
          <div>
            <label className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1.5 block">
              Day of Month
            </label>
            <input
              type="number"
              min={1}
              max={31}
              disabled={!draft.enabled || isRunning}
              className="text-xs bg-transparent border border-[var(--color-border-default)] rounded-[var(--radius-sm)] px-2.5 py-1.5 w-full disabled:opacity-50"
              value={draft.day_of_month ?? ''}
              onChange={(e) => update('day_of_month', e.target.value ? Math.min(31, Math.max(1, Number(e.target.value))) : null)}
              placeholder="1–31"
            />
          </div>
        )}

        {/* Custom cron */}
        {draft.frequency === 'custom_cron' && (
          <div>
            <label className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1.5 block">
              Cron Expression
            </label>
            <input
              type="text"
              disabled={!draft.enabled || isRunning}
              className="text-xs bg-transparent border border-[var(--color-border-default)] rounded-[var(--radius-sm)] px-2.5 py-1.5 w-full font-mono disabled:opacity-50"
              value={draft.cron_expression ?? ''}
              onChange={(e) => update('cron_expression', e.target.value || null)}
              placeholder="0 14 * * 1  (min hour day month weekday)"
            />
            <p className="text-[0.625rem] text-[var(--color-text-tertiary)] mt-1">
              Standard 5-field cron syntax. Time is interpreted as UTC.
            </p>
          </div>
        )}

        {/* Time */}
        <div>
          <label className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1.5 block">
            Trigger Time (UTC)
          </label>
          <input
            type="time"
            disabled={!draft.enabled || isRunning}
            className="text-xs bg-transparent border border-[var(--color-border-default)] rounded-[var(--radius-sm)] px-2.5 py-1.5 w-full disabled:opacity-50"
            value={draft.time_utc}
            onChange={(e) => update('time_utc', e.target.value)}
          />
        </div>

        {/* Preview section */}
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg-secondary)] p-3 space-y-2">
          <p className="text-[0.625rem] text-[var(--color-text-tertiary)]">Schedule Preview</p>
          <p className="text-xs text-[var(--color-text-primary)]">
            {previewDescription}
          </p>
          {draft.enabled && previewNextRun && (
            <div className="pt-1.5 border-t border-[var(--color-border-subtle)]">
              <p className="text-[0.625rem] text-[var(--color-text-tertiary)]">Next Run</p>
              <p className="text-xs text-[var(--color-violet-500)]">
                {formatNextRun(previewNextRun)}
              </p>
            </div>
          )}
          {schedule.last_run && (
            <div className="pt-1.5 border-t border-[var(--color-border-subtle)]">
              <p className="text-[0.625rem] text-[var(--color-text-tertiary)]">Last Run</p>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {formatNextRun(schedule.last_run)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 p-4 border-t border-[var(--color-border-default)] flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          onClick={handleCancel}
          disabled={!isDirty}
        >
          Reset
        </Button>
        <Button
          size="sm"
          className="flex-1 gap-1.5"
          onClick={handleSave}
          disabled={!isDirty || isRunning}
        >
          <Save className="size-3.5" />
          Save Schedule
        </Button>
      </div>
    </div>
  );
}
