import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Settings,
  Pencil,
  Save,
  X,
  Info,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  Plus,
  ChevronRight,
  ChevronDown,
  RotateCcw,
} from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip';
import { cn } from './ui/utils';
import {
  MOCK_CLV,
  MOCK_FUNNEL_MAPPING,
  AVAILABLE_KPIS,
  MOCK_EVENTS,
  MOCK_CATEGORY_STATUS,
  KNOWN_CATEGORIES,
  MOCK_THRESHOLDS,
  MOCK_CHANNEL_COVERAGE,
  TRAINING_MONTHS,
  MIN_MONTHLY_OBS,
  FUNNEL_STAGES,
  type ClvConfig,
  type FunnelStageRow,
  type KpiOption,
  type ExogenousEvent,
  type ExpectedDirection,
  type CategoryStatus,
  type ThresholdRow,
  type MethodLabel,
  type ChannelCoverageRow,
} from '../data/configData';

/* ========== Helpers ========== */

function formatDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatCurrency(v: number): string {
  return `$${v.toLocaleString()}`;
}

let _uid = 200;
function uid() { return `gen-${_uid++}`; }

/* ========== Main Component ========== */

export function ConfigSection() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Settings className="size-5 text-[var(--color-violet-500)]" />
        <div>
          <h2>Configuration</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage model inputs — funnel mappings, lifetime value, exogenous events, and channel settings.
          </p>
        </div>
      </div>

      <ClvSection />
      <FunnelMappingSection />
      <ExogenousEventsSection />
      <ThresholdsSection />
      <ChannelCoverageSection />
    </div>
  );
}

/* ================================================================
   2. CLV Section
   ================================================================ */

function ClvSection() {
  const [value, setValue] = useState<number | null>(MOCK_CLV.value);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = () => {
    setDraft(value != null ? String(value) : '');
    setError('');
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const cancel = () => { setEditing(false); setError(''); };

  const save = async () => {
    const n = Number(draft);
    if (!draft || isNaN(n) || n <= 0) { setError('Value must be a positive number.'); return; }
    setSaving(true);
    await new Promise((r) => setTimeout(r, 600));
    setValue(n);
    setSaving(false);
    setEditing(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') save();
    if (e.key === 'Escape') cancel();
  };

  return (
    <Card className="p-5">
      <h3 className="text-sm mb-3">Average Customer Lifetime Value</h3>
      {editing ? (
        <div className="flex items-center gap-3">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
            <input
              ref={inputRef}
              type="number"
              className="pl-7 pr-3 py-1.5 text-sm rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500 w-40"
              value={draft}
              onChange={(e) => { setDraft(e.target.value); setError(''); }}
              onKeyDown={onKeyDown}
            />
          </div>
          <Button size="sm" onClick={save} disabled={saving}>
            <Save className="size-3 mr-1" />
            {saving ? 'Saving…' : 'Save'}
          </Button>
          <Button size="sm" variant="outline" onClick={cancel} disabled={saving}>
            <X className="size-3 mr-1" /> Cancel
          </Button>
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <span className="text-lg">{value != null ? formatCurrency(value) : 'Not configured'}</span>
          <Button size="sm" variant="outline" onClick={startEdit}>
            <Pencil className="size-3 mr-1" /> Edit
          </Button>
        </div>
      )}
    </Card>
  );
}

/* ================================================================
   3. Funnel Stage Mapping
   ================================================================ */

function FunnelMappingSection() {
  const [rows, setRows] = useState<FunnelStageRow[]>(MOCK_FUNNEL_MAPPING);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState<FunnelStageRow[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const startEdit = () => { setSaved(JSON.parse(JSON.stringify(rows))); setEditing(true); setError(''); };
  const cancel = () => { if (saved) setRows(saved); setSaved(null); setEditing(false); setError(''); };

  const save = async () => {
    // Validate all assigned
    if (rows.some((r) => !r.kpiId)) { setError('All stages must have a KPI assigned.'); return; }
    const ids = rows.map((r) => r.kpiId);
    if (new Set(ids).size !== ids.length) { setError('Each stage must have a unique KPI.'); return; }
    setSaving(true);
    await new Promise((r) => setTimeout(r, 600));
    setSaving(false);
    setSaved(null);
    setEditing(false);
    setError('');
  };

  const assignedKpiIds = rows.map((r) => r.kpiId);

  const getKpi = (id: string) => AVAILABLE_KPIS.find((k) => k.id === id);

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm">Funnel Stage Mapping</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Configure which KPI is assigned to each funnel stage.</p>
        </div>
        {!editing && (
          <Button size="sm" variant="outline" onClick={startEdit}>
            <Pencil className="size-3 mr-1" /> Edit
          </Button>
        )}
      </div>

      {editing && (
        <div className="flex items-start gap-2 p-3 mb-3 rounded-[var(--radius-sm)] bg-amber-50 border border-amber-200 text-xs text-amber-800">
          <AlertTriangle className="size-3.5 shrink-0 mt-0.5 text-amber-500" />
          Changing KPI assignments requires model re-estimation for accurate forecasts. Use the Re-estimate Model button after saving.
        </div>
      )}

      <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border-default)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Funnel Stage</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">KPI</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Data Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const kpi = getKpi(row.kpiId);
              return (
                <tr key={row.stage} className="border-b border-[var(--color-border-default)] last:border-b-0">
                  <td className="px-4 py-2.5 text-sm">{row.stage}</td>
                  <td className="px-4 py-2.5">
                    {editing ? (
                      <select
                        value={row.kpiId}
                        onChange={(e) => {
                          const next = [...rows];
                          next[idx] = { ...next[idx], kpiId: e.target.value };
                          setRows(next);
                          setError('');
                        }}
                        className="text-sm px-2 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500 w-full max-w-[260px]"
                      >
                        <option value="">Select KPI…</option>
                        {AVAILABLE_KPIS.map((k) => {
                          const taken = assignedKpiIds.includes(k.id) && k.id !== row.kpiId;
                          const disabled = taken || k.noData;
                          return (
                            <option key={k.id} value={k.id} disabled={disabled}>
                              {k.name}{k.noData ? ' (no data)' : ''}{taken ? ' (assigned)' : ''}
                            </option>
                          );
                        })}
                      </select>
                    ) : (
                      <span className="text-sm">{kpi?.name ?? '—'}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <code className="text-xs text-muted-foreground bg-[var(--color-bg-secondary)] px-1.5 py-0.5 rounded">
                      {kpi?.dataSource ?? '—'}
                    </code>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="flex items-center gap-3 mt-3">
          <Button size="sm" onClick={save} disabled={saving}>
            <Save className="size-3 mr-1" /> {saving ? 'Saving…' : 'Save'}
          </Button>
          <Button size="sm" variant="outline" onClick={cancel} disabled={saving}>
            <X className="size-3 mr-1" /> Cancel
          </Button>
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
      )}
    </Card>
  );
}

/* ================================================================
   4. Exogenous Events
   ================================================================ */

function ExogenousEventsSection() {
  const [events, setEvents] = useState<ExogenousEvent[]>(MOCK_EVENTS);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState<ExogenousEvent[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Record<string, string[]>>({});

  const startEdit = () => { setSaved(JSON.parse(JSON.stringify(events))); setEditing(true); setValidationErrors({}); };
  const cancel = () => { if (saved) setEvents(saved); setSaved(null); setEditing(false); setValidationErrors({}); };

  const validate = (): boolean => {
    const errs: Record<string, string[]> = {};
    let valid = true;
    events.forEach((ev) => {
      const rowErrs: string[] = [];
      if (!ev.startDate) rowErrs.push('Start date is required');
      if (!ev.endDate) rowErrs.push('End date is required');
      if (!ev.label.trim()) rowErrs.push('Label is required');
      if (!ev.category.trim()) rowErrs.push('Category is required');
      if (ev.startDate && ev.endDate && ev.startDate > ev.endDate) rowErrs.push('Start date must be on or before end date');
      if (rowErrs.length) { errs[ev.id] = rowErrs; valid = false; }
    });
    setValidationErrors(errs);
    return valid;
  };

  const save = async () => {
    if (!validate()) return;
    setSaving(true);
    await new Promise((r) => setTimeout(r, 600));
    setSaving(false);
    setSaved(null);
    setEditing(false);
  };

  const addRow = () => {
    const newEv: ExogenousEvent = { id: uid(), startDate: '', endDate: '', label: '', category: '', expectedDirection: 'none' };
    setEvents([...events, newEv]);
  };

  const deleteRow = (id: string) => setEvents(events.filter((e) => e.id !== id));

  const updateEvent = (id: string, patch: Partial<ExogenousEvent>) => {
    setEvents(events.map((e) => (e.id === id ? { ...e, ...patch } : e)));
    if (validationErrors[id]) {
      const next = { ...validationErrors };
      delete next[id];
      setValidationErrors(next);
    }
  };

  // Derive categories from events for autocomplete
  const allCategories = [...new Set([...KNOWN_CATEGORIES, ...events.map((e) => e.category).filter(Boolean)])];

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm">Exogenous Events</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage competitor activity, seasonal events, and other external factors that may influence funnel metrics.
          </p>
        </div>
        {!editing && (
          <Button size="sm" variant="outline" onClick={startEdit}>
            <Pencil className="size-3 mr-1" /> Edit
          </Button>
        )}
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-2.5 p-3 mb-4 rounded-[var(--radius-sm)] bg-blue-50 border border-blue-200 text-xs text-blue-800">
        <Info className="size-3.5 shrink-0 mt-0.5 text-blue-500" />
        <span>
          Events help the model separate external factors from organic trends, preventing interventions from inflating the forecast baseline.
          Calendar activities are included automatically. Use this page for non-campaign events like competitor launches, seasonal shifts, or market disruptions.
        </span>
      </div>

      {/* Category Status */}
      <CategoryStatusPanel categories={MOCK_CATEGORY_STATUS} />

      {/* Table or empty state */}
      {events.length === 0 && !editing ? (
        <div className="text-center py-8 text-xs text-muted-foreground italic">
          No events configured. Add events to help the model account for competitor activity, seasonal patterns, and other external factors.
          Note: campaigns are automatically included as exogenous controls — you do not need to add them here.
        </div>
      ) : (
        <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border-default)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
                <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Start Date</th>
                <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">End Date</th>
                <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Label</th>
                <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Category</th>
                <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">
                  Expected Direction
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="size-3 text-muted-foreground/60 cursor-help inline-block ml-1" />
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-[260px]">
                      Select 'positive' if this event type is expected to increase funnel metrics, 'negative' if expected to decrease, or leave blank if unknown. This is for documentation only and does not constrain the model.
                    </TooltipContent>
                  </Tooltip>
                </th>
                {editing && <th className="w-10" />}
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <EventRow
                  key={ev.id}
                  event={ev}
                  editing={editing}
                  errors={validationErrors[ev.id]}
                  allCategories={allCategories}
                  onUpdate={(patch) => updateEvent(ev.id, patch)}
                  onDelete={() => deleteRow(ev.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <div className="flex items-center gap-3 mt-3">
          <Button size="sm" variant="outline" onClick={addRow}>
            <Plus className="size-3 mr-1" /> Add Row
          </Button>
          <div className="flex-1" />
          <Button size="sm" onClick={save} disabled={saving}>
            <Save className="size-3 mr-1" /> {saving ? 'Saving…' : 'Save'}
          </Button>
          <Button size="sm" variant="outline" onClick={cancel} disabled={saving}>
            <X className="size-3 mr-1" /> Cancel
          </Button>
        </div>
      )}
    </Card>
  );
}

function CategoryStatusPanel({ categories }: { categories: CategoryStatus[] }) {
  if (categories.length === 0) return null;
  return (
    <div className="mb-4 space-y-2">
      {categories.map((cat) => {
        const needed = 5 - cat.eventCount;
        return (
          <div key={cat.category} className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-xs capitalize">{cat.category}</span>
              {cat.isActive ? (
                <Badge variant="success" className="text-[10px] px-2 py-0 gap-1">
                  <CheckCircle2 className="size-2.5" />
                  Active in model ({cat.eventCount} events)
                </Badge>
              ) : (
                <Badge variant="warning" className="text-[10px] px-2 py-0 gap-1">
                  <AlertTriangle className="size-2.5" />
                  Not yet active — needs {needed} more event{needed !== 1 ? 's' : ''} ({cat.eventCount}/5)
                </Badge>
              )}
            </div>
            {cat.isCampaign && (
              <p className="text-[10px] text-muted-foreground ml-0.5">
                Automatically included from Calendar. Events from the Calendar page are merged into this category.
              </p>
            )}
            {cat.coversFullTrainingPeriod && cat.isActive && (
              <div className="flex items-start gap-1.5 text-[10px] text-amber-700 ml-0.5">
                <AlertTriangle className="size-3 shrink-0 mt-0.5" />
                This category covers the entire training period. The model needs some periods without events in this category to estimate its effect. Consider scheduling holdout periods.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EventRow({
  event: ev,
  editing,
  errors,
  allCategories,
  onUpdate,
  onDelete,
}: {
  event: ExogenousEvent;
  editing: boolean;
  errors?: string[];
  allCategories: string[];
  onUpdate: (patch: Partial<ExogenousEvent>) => void;
  onDelete: () => void;
}) {
  const directionLabel = (d: ExpectedDirection) => {
    if (d === 'positive') return 'Positive';
    if (d === 'negative') return 'Negative';
    return '—';
  };

  return (
    <>
      <tr className={cn('border-b border-[var(--color-border-default)] last:border-b-0', errors?.length && 'bg-red-50/40')}>
        <td className="px-4 py-2">
          {editing ? (
            <input
              type="date"
              className="text-xs px-2 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
              value={ev.startDate}
              onChange={(e) => onUpdate({ startDate: e.target.value })}
            />
          ) : (
            <span className="text-sm">{formatDate(ev.startDate)}</span>
          )}
        </td>
        <td className="px-4 py-2">
          {editing ? (
            <input
              type="date"
              className="text-xs px-2 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
              value={ev.endDate}
              onChange={(e) => onUpdate({ endDate: e.target.value })}
            />
          ) : (
            <span className="text-sm">{formatDate(ev.endDate)}</span>
          )}
        </td>
        <td className="px-4 py-2">
          {editing ? (
            <input
              type="text"
              className="text-xs px-2 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500 w-full max-w-[180px]"
              placeholder="e.g. Black Friday"
              value={ev.label}
              onChange={(e) => onUpdate({ label: e.target.value })}
            />
          ) : (
            <span className="text-sm">{ev.label}</span>
          )}
        </td>
        <td className="px-4 py-2">
          {editing ? (
            <input
              type="text"
              list={`cat-list-${ev.id}`}
              className="text-xs px-2 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500 w-full max-w-[140px]"
              placeholder="e.g. seasonal"
              value={ev.category}
              onChange={(e) => onUpdate({ category: e.target.value })}
            />
          ) : (
            <span className="text-sm">{ev.category}</span>
          )}
          {editing && (
            <datalist id={`cat-list-${ev.id}`}>
              {allCategories.map((c) => <option key={c} value={c} />)}
            </datalist>
          )}
        </td>
        <td className="px-4 py-2">
          {editing ? (
            <select
              className="text-xs px-2 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
              value={ev.expectedDirection}
              onChange={(e) => onUpdate({ expectedDirection: e.target.value as ExpectedDirection })}
            >
              <option value="none">None</option>
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
            </select>
          ) : (
            <span className="text-sm">{directionLabel(ev.expectedDirection)}</span>
          )}
        </td>
        {editing && (
          <td className="px-2 py-2">
            <button onClick={onDelete} className="text-red-400 hover:text-red-500 cursor-pointer">
              <Trash2 className="size-3.5" />
            </button>
          </td>
        )}
      </tr>
      {errors && errors.length > 0 && (
        <tr className="bg-red-50/40">
          <td colSpan={editing ? 6 : 5} className="px-4 py-1.5">
            <div className="flex flex-wrap gap-2">
              {errors.map((err) => (
                <span key={err} className="text-[10px] text-red-600">{err}</span>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ================================================================
   5. Auto-Detected Thresholds
   ================================================================ */

function ThresholdsSection() {
  const [rows, setRows] = useState<ThresholdRow[]>(MOCK_THRESHOLDS);
  const [expandedId, setExpandedId] = useState<string | null>(() => {
    const preExpanded = MOCK_THRESHOLDS.find((r) => r.overrideEnabled);
    return preExpanded?.id ?? null;
  });

  const toggleOverride = (id: string) => {
    setRows(rows.map((r) => {
      if (r.id !== id) return r;
      const next = { ...r, overrideEnabled: !r.overrideEnabled };
      if (!next.overrideEnabled) {
        next.override = undefined;
        setExpandedId(null);
      } else {
        next.override = {
          method: '% Above Median',
          thresholdPct: r.autoDetected.thresholdPct,
          rollingMedian: r.autoDetected.rolling === 'Static' ? 'Static' : 'Rolling',
          windowMonths: 12,
        };
        setExpandedId(id);
      }
      return next;
    }));
  };

  const updateOverride = (id: string, patch: Partial<NonNullable<ThresholdRow['override']>>) => {
    setRows(rows.map((r) => r.id === id && r.override ? { ...r, override: { ...r.override, ...patch } } : r));
  };

  const resetToAuto = (id: string) => {
    setRows(rows.map((r) => {
      if (r.id !== id) return r;
      return {
        ...r,
        overrideEnabled: false,
        override: undefined,
      };
    }));
    setExpandedId(null);
  };

  // Group by funnel step
  const groups: { step: string; items: ThresholdRow[] }[] = [];
  rows.forEach((r) => {
    const last = groups[groups.length - 1];
    if (last && last.step === r.funnelStep) {
      last.items.push(r);
    } else {
      groups.push({ step: r.funnelStep, items: [r] });
    }
  });

  const coverageBadge = (coverage: number | null) => {
    if (coverage == null) return <span className="text-xs text-muted-foreground">N/A</span>;
    let variant: 'success' | 'warning' | 'error' = 'success';
    if (coverage < 20 || coverage > 50) variant = 'error';
    else if (coverage < 30 || coverage > 40) variant = 'warning';
    return <Badge variant={variant} className="text-[10px] px-2 py-0">{coverage.toFixed(1)}%</Badge>;
  };

  return (
    <Card className="p-5">
      <div className="mb-3">
        <h3 className="text-sm">Auto-Detected Thresholds</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Automatically computed from per-channel pulse spend data (Path C). Thresholds are recalculated at each model estimation.
        </p>
      </div>

      <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border-default)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
              <th className="w-8" />
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Funnel Step</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Channel</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Method</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Threshold %</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Rolling</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Last Value</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Flag0 Coverage</th>
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Override</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group, gi) =>
              group.items.map((row, ri) => {
                const isExpanded = expandedId === row.id && row.overrideEnabled;
                const showStep = ri === 0;
                const isLastGroup = gi === groups.length - 1;
                const isLastInGroup = ri === group.items.length - 1;
                const groupBorder = isLastInGroup && !isLastGroup && !isExpanded;

                return (
                  <ThresholdRowView
                    key={row.id}
                    row={row}
                    showStep={showStep}
                    groupSpan={showStep ? group.items.length : 0}
                    groupBorder={groupBorder}
                    isExpanded={isExpanded}
                    coverageBadge={coverageBadge}
                    onToggleExpand={() => setExpandedId(isExpanded ? null : row.id)}
                    onToggleOverride={() => toggleOverride(row.id)}
                    onUpdateOverride={(patch) => updateOverride(row.id, patch)}
                    onResetToAuto={() => resetToAuto(row.id)}
                  />
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ThresholdRowView({
  row,
  showStep,
  groupSpan,
  groupBorder,
  isExpanded,
  coverageBadge,
  onToggleExpand,
  onToggleOverride,
  onUpdateOverride,
  onResetToAuto,
}: {
  row: ThresholdRow;
  showStep: boolean;
  groupSpan: number;
  groupBorder: boolean;
  isExpanded: boolean;
  coverageBadge: (v: number | null) => React.ReactNode;
  onToggleExpand: () => void;
  onToggleOverride: () => void;
  onUpdateOverride: (patch: Partial<NonNullable<ThresholdRow['override']>>) => void;
  onResetToAuto: () => void;
}) {
  return (
    <>
      <tr
        className={cn(
          'border-b border-[var(--color-border-default)]',
          groupBorder && 'border-b-2 border-b-[var(--color-border-strong)]',
          row.overrideEnabled && 'cursor-pointer hover:bg-[var(--color-bg-secondary)]',
        )}
        onClick={row.overrideEnabled ? onToggleExpand : undefined}
      >
        <td className="px-2 py-2 text-center">
          {row.overrideEnabled ? (
            isExpanded ? <ChevronDown className="size-3.5 text-muted-foreground" /> : <ChevronRight className="size-3.5 text-muted-foreground" />
          ) : null}
        </td>
        <td className="px-4 py-2.5 text-sm">
          {showStep ? row.funnelStep : ''}
        </td>
        <td className="px-4 py-2.5">
          <span className="text-sm">{row.channelName}</span>{' '}
          <code className="text-[10px] text-muted-foreground bg-[var(--color-bg-secondary)] px-1 py-0.5 rounded">{row.channelSlug}</code>
        </td>
        <td className="px-4 py-2.5 text-sm">{row.method}</td>
        <td className="px-4 py-2.5 text-sm tabular-nums">{row.thresholdPct.toFixed(1)}%</td>
        <td className="px-4 py-2.5 text-sm">{row.rolling}</td>
        <td className="px-4 py-2.5 text-sm tabular-nums">{row.lastValue != null ? formatCurrency(row.lastValue) : '—'}</td>
        <td className="px-4 py-2.5">{coverageBadge(row.flag0Coverage)}</td>
        <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={row.overrideEnabled}
              onChange={onToggleOverride}
              className="accent-[var(--color-violet-500)] cursor-pointer"
            />
            {row.overrideEnabled && (
              <Badge variant="info" className="text-[10px] px-2 py-0">Manual</Badge>
            )}
          </div>
        </td>
      </tr>
      {isExpanded && row.override && (
        <tr className="bg-[var(--color-bg-secondary)]">
          <td colSpan={9} className="px-6 py-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground tracking-wide uppercase">Manual Override Values</span>
                <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); onResetToAuto(); }}>
                  <RotateCcw className="size-3 mr-1" /> Reset to Auto
                </Button>
              </div>

              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">Method</label>
                  <select
                    value={row.override.method}
                    onChange={(e) => onUpdateOverride({ method: e.target.value as MethodLabel })}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full text-xs px-2 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
                  >
                    <option value="% Above Median">% Above Median</option>
                    <option value="SD Bands">SD Bands</option>
                    <option value="IQR">IQR</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">Threshold %</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    step={0.5}
                    value={row.override.thresholdPct}
                    onChange={(e) => onUpdateOverride({ thresholdPct: Number(e.target.value) })}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full text-xs px-2 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500 tabular-nums"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">Rolling Median</label>
                  <select
                    value={row.override.rollingMedian}
                    onChange={(e) => onUpdateOverride({ rollingMedian: e.target.value as 'Static' | 'Rolling' })}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full text-xs px-2 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500"
                  >
                    <option value="Static">Static</option>
                    <option value="Rolling">Rolling</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground block mb-1">Window (months)</label>
                  <input
                    type="number"
                    min={3}
                    max={36}
                    step={1}
                    value={row.override.windowMonths}
                    disabled={row.override.rollingMedian === 'Static'}
                    onChange={(e) => onUpdateOverride({ windowMonths: Number(e.target.value) })}
                    onClick={(e) => e.stopPropagation()}
                    className={cn(
                      'w-full text-xs px-2 py-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-1 focus:ring-violet-500 tabular-nums',
                      row.override.rollingMedian === 'Static' && 'opacity-40 cursor-not-allowed',
                    )}
                  />
                </div>
              </div>

              <div className="text-[10px] text-muted-foreground bg-[var(--color-bg-primary)] px-3 py-2 rounded-[var(--radius-sm)] border border-[var(--color-border-default)]">
                Auto-detected values: Method: {row.autoDetected.method}, Threshold: {row.autoDetected.thresholdPct.toFixed(1)}%,
                Rolling: {row.autoDetected.rolling === 'Static' ? 'No' : 'Yes'}, Coverage: {row.autoDetected.coverage.toFixed(1)}%
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ================================================================
   6. Marketing Channels
   ================================================================ */

function ChannelCoverageSection() {
  const [channels, setChannels] = useState<ChannelCoverageRow[]>(MOCK_CHANNEL_COVERAGE);

  const toggleExclude = (id: string) => {
    setChannels(channels.map((c) => (c.id === id ? { ...c, excluded: !c.excluded } : c)));
  };

  return (
    <Card className="p-5">
      <div className="mb-3">
        <h3 className="text-sm">Marketing Channels</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Channels are automatically discovered from pulse data. Coverage across {TRAINING_MONTHS} months of training data ({MIN_MONTHLY_OBS} monthly observations required).
          Excluded channels are hidden from pulse suggestions and omitted from the model.
        </p>
      </div>

      <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border-default)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
              <th className="text-left px-4 py-2.5 text-xs text-muted-foreground tracking-wide">Channel</th>
              {FUNNEL_STAGES.map((stage) => (
                <th key={stage} className="text-left px-3 py-2.5 text-xs text-muted-foreground tracking-wide">{stage}</th>
              ))}
              <th className="text-left px-3 py-2.5 text-xs text-muted-foreground tracking-wide">Overall</th>
              <th className="text-left px-3 py-2.5 text-xs text-muted-foreground tracking-wide">Exclude</th>
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => (
              <tr
                key={ch.id}
                className={cn(
                  'border-b border-[var(--color-border-default)] last:border-b-0 transition-opacity',
                  ch.excluded && 'opacity-40',
                )}
              >
                <td className="px-4 py-2.5">
                  <span className="text-sm">{ch.channelName}</span>{' '}
                  <code className="text-[10px] text-muted-foreground bg-[var(--color-bg-secondary)] px-1 py-0.5 rounded">{ch.channelSlug}</code>
                </td>
                {FUNNEL_STAGES.map((stage) => {
                  const cov = ch.coverage[stage];
                  if (!cov) return <td key={stage} className="px-3 py-2.5 text-xs text-muted-foreground">—</td>;
                  const pass = cov.observed >= cov.required;
                  return (
                    <td key={stage} className="px-3 py-2.5">
                      <Badge variant={pass ? 'success' : 'warning'} className="text-[10px] px-2 py-0">
                        {cov.observed}/{cov.required}
                      </Badge>
                    </td>
                  );
                })}
                <td className="px-3 py-2.5">
                  <Badge variant={ch.overall === 'Pass' ? 'success' : 'warning'} className="text-[10px] px-2 py-0">
                    {ch.overall}
                  </Badge>
                </td>
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={ch.excluded}
                    onChange={() => toggleExclude(ch.id)}
                    className="accent-[var(--color-violet-500)] cursor-pointer"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
