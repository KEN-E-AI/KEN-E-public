import { useState, useMemo } from 'react';
import {
  X,
  Check,
  Plus,
  ChevronRight,
  ArrowLeft,
  DollarSign,
  Layers,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Button } from './ui/button';
import { cn } from './ui/utils';
import {
  calendarCampaigns,
  channelGuidelines,
  allowedUsers,
  knownPlatforms,
  existingTags,
  getPlatformColor,
  getCampaignName,
  getCampaignObjective,
  getCampaignsByObjective,
  addCampaign,
  type CalendarActivity,
  type ActivityStatus,
  type FunnelObjective,
} from '../data/calendarData';

// ─── Date Helpers (duplicated for isolation) ───

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function parseDateISO(s: string): Date {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

// ─── Types ───

type BudgetStrategy = 'even' | 'weekday-weekend' | 'manual';
type Frequency = 'daily' | 'weekdays' | 'custom';

const ALL_STATUSES: ActivityStatus[] = ['Draft', 'Awaiting Approval', 'Approved', 'Rejected', 'Revision Requested', 'Complete'];
const ALL_OBJECTIVES: FunnelObjective[] = ['Problem Awareness', 'Brand Awareness', 'Consideration', 'Conversion'];

interface BatchTemplate {
  namePrefix: string;
  campaign_id: string | null;
  platform: string | null;
  channel: string | null;
  task_type: string | null;
  tags: string[];
  owner: string | null;
  status: ActivityStatus;
}

interface BatchSchedule {
  startDate: string;
  endDate: string;
  frequency: Frequency;
  customDays: number[];
  launchTime: string | null;
  budgetStrategy: BudgetStrategy;
  totalBudget: number;
  weekdayBudget: number;
  weekendBudget: number;
}

interface PreviewActivity {
  id: string;
  name: string;
  date: Date;
  cost: number;
  included: boolean;
}

// ═══════════════════════════════════════════════════════════

export function BatchActivityWizard({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (activities: CalendarActivity[]) => void;
}) {
  const [step, setStep] = useState(1);
  const [tagInput, setTagInput] = useState('');
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [newCampaignName, setNewCampaignName] = useState('');

  const [template, setTemplate] = useState<BatchTemplate>({
    namePrefix: '',
    campaign_id: null,
    platform: null,
    channel: null,
    task_type: null,
    tags: [],
    owner: null,
    status: 'Draft',
  });

  const [schedule, setSchedule] = useState<BatchSchedule>({
    startDate: '2026-04-01',
    endDate: '2026-04-30',
    frequency: 'daily',
    customDays: [1, 2, 3, 4, 5],
    launchTime: null,
    budgetStrategy: 'even',
    totalBudget: 5000,
    weekdayBudget: 200,
    weekendBudget: 100,
  });

  // Generate preview activities
  const previewActivities = useMemo((): PreviewActivity[] => {
    const start = parseDateISO(schedule.startDate);
    const end = parseDateISO(schedule.endDate);
    if (start > end) return [];

    const dates: Date[] = [];
    let d = new Date(start);
    while (d <= end) {
      const dayOfWeek = d.getDay();
      let include = false;
      if (schedule.frequency === 'daily') include = true;
      else if (schedule.frequency === 'weekdays') include = dayOfWeek >= 1 && dayOfWeek <= 5;
      else include = schedule.customDays.includes(dayOfWeek);
      if (include) dates.push(new Date(d));
      d = addDays(d, 1);
    }

    if (dates.length === 0) return [];

    return dates.map((date, i) => {
      let cost = 0;
      if (schedule.budgetStrategy === 'even' || schedule.budgetStrategy === 'manual') {
        cost = Math.round((schedule.totalBudget / dates.length) * 100) / 100;
      } else if (schedule.budgetStrategy === 'weekday-weekend') {
        const dow = date.getDay();
        cost = (dow >= 1 && dow <= 5) ? schedule.weekdayBudget : schedule.weekendBudget;
      }

      const prefix = template.namePrefix || (template.platform ? `${template.platform}${template.channel ? ` ${template.channel}` : ''}` : 'Activity');
      const dateLabel = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      return {
        id: `batch-${i}`,
        name: `${prefix} - ${dateLabel}`,
        date,
        cost,
        included: true,
      };
    });
  }, [schedule, template.namePrefix, template.platform, template.channel]);

  const [overrides, setOverrides] = useState<Map<string, { name?: string; cost?: number; included?: boolean }>>(new Map());

  // Reset overrides when preview changes
  const [prevCount, setPrevCount] = useState(0);
  if (previewActivities.length !== prevCount) {
    setPrevCount(previewActivities.length);
    setOverrides(new Map());
  }

  const mergedPreview = useMemo(() => {
    return previewActivities.map(a => {
      const o = overrides.get(a.id);
      return {
        ...a,
        name: o?.name ?? a.name,
        cost: o?.cost ?? a.cost,
        included: o?.included ?? a.included,
      };
    });
  }, [previewActivities, overrides]);

  const includedPreview = mergedPreview.filter(a => a.included);
  const totalCost = includedPreview.reduce((sum, a) => sum + a.cost, 0);
  const pc = getPlatformColor(template.platform);

  const updateOverride = (id: string, patch: { name?: string; cost?: number; included?: boolean }) => {
    setOverrides(prev => {
      const next = new Map(prev);
      next.set(id, { ...next.get(id), ...patch });
      return next;
    });
  };

  const handleCampaignChange = (campaignId: string | null) => {
    setTemplate(t => ({ ...t, campaign_id: campaignId }));
  };

  const [newCampaignObjective, setNewCampaignObjective] = useState<FunnelObjective>('Problem Awareness');

  const handleCreateCampaign = (name: string) => {
    const campaign = addCampaign(name, newCampaignObjective);
    setTemplate(t => ({ ...t, campaign_id: campaign.campaign_id }));
  };

  const handleTagAdd = () => {
    const tag = tagInput.trim();
    if (tag && !template.tags.includes(tag)) {
      setTemplate(t => ({ ...t, tags: [...t.tags, tag] }));
    }
    setTagInput('');
  };

  const handleCreate = () => {
    const now = new Date();
    const newActivities: CalendarActivity[] = includedPreview.map((p, i) => ({
      activity_id: `act-batch-${Date.now()}-${i}`,
      name: p.name,
      campaign_id: template.campaign_id,
      channel: template.channel,
      platform: template.platform,
      cost: p.cost,
      launch_date: p.date,
      launch_time_utc: schedule.launchTime || null,
      category: 'task' as const,
      task_type: template.task_type,
      tags: [...template.tags],
      owner: template.owner,
      status: template.status,
      created_date: now,
      created_by: 'sarah.chen@example.com',
      last_updated_at: now,
      last_updated_by: 'sarah.chen@example.com',
    }));
    onCreate(newActivities);
  };

  const fieldClass = "w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]";
  const labelClass = "text-[0.625rem] text-muted-foreground uppercase tracking-wider mb-1 block";

  const stepValid = step === 1
    ? !!(template.campaign_id)
    : step === 2
    ? (schedule.startDate && schedule.endDate && previewActivities.length > 0)
    : includedPreview.length > 0;

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <>
      <div className="fixed inset-0 z-[50] bg-black/30" onClick={onClose} />

      <div className="fixed top-0 right-0 bottom-0 z-[51] w-full max-w-lg bg-[var(--color-bg-elevated)] border-l border-[var(--color-border-default)] shadow-xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-[var(--color-violet-500)]" />
            <h2 className="text-sm">Add Activity Group</h2>
          </div>
          <button onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-0 px-4 py-3 border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
          {[
            { n: 1, label: 'Template' },
            { n: 2, label: 'Schedule & Budget' },
            { n: 3, label: 'Preview & Confirm' },
          ].map(({ n, label }, idx) => (
            <div key={n} className="flex items-center flex-1">
              <div className="flex items-center gap-2 flex-1">
                <span
                  className={cn(
                    "size-6 rounded-full flex items-center justify-center text-xs shrink-0 transition-colors",
                    step === n
                      ? "bg-[var(--color-violet-500)] text-white"
                      : step > n
                      ? "bg-green-100 text-green-700 border border-green-300"
                      : "bg-[var(--color-bg-primary)] text-muted-foreground border border-[var(--color-border-default)]"
                  )}
                >
                  {step > n ? <Check className="size-3.5" /> : n}
                </span>
                <span className={cn("text-xs", step === n ? "text-foreground" : "text-muted-foreground")}>{label}</span>
              </div>
              {idx < 2 && <div className="w-6 h-px bg-[var(--color-border-default)] mx-1" />}
            </div>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* ─── STEP 1: TEMPLATE ─── */}
          {step === 1 && (
            <>
              <div>
                <label className={labelClass}>Name Prefix</label>
                <input
                  type="text"
                  className={fieldClass}
                  placeholder="e.g. Google Paid Search (auto-generated if blank)"
                  value={template.namePrefix}
                  onChange={e => setTemplate(t => ({ ...t, namePrefix: e.target.value }))}
                />
                <p className="text-[0.625rem] text-muted-foreground mt-1">Each activity: &quot;{template.namePrefix || '[Platform Channel]'} - [Date]&quot;</p>
              </div>

              <div>
                <label className={labelClass}>Campaign</label>
                {!showNewCampaign ? (
                  <>
                    <select className={fieldClass} value={template.campaign_id ?? ''} onChange={e => {
                      if (e.target.value === '__create_new__') {
                        setShowNewCampaign(true);
                      } else {
                        handleCampaignChange(e.target.value || null);
                      }
                    }}>
                      <option value="">No campaign</option>
                      {getCampaignsByObjective().map(c => (
                        <option key={c.campaign_id} value={c.campaign_id}>{c.name} — {c.objective}</option>
                      ))}
                      <option value="__create_new__">+ Create new campaign...</option>
                    </select>
                    <p className="text-[0.625rem] text-muted-foreground mt-1">Optional — campaign determines the objective.</p>
                  </>
                ) : (
                  <div className="space-y-2">
                    <input
                      type="text"
                      className={fieldClass}
                      placeholder="New campaign name"
                      value={newCampaignName}
                      onChange={e => setNewCampaignName(e.target.value)}
                      autoFocus
                    />
                    <select
                      className={fieldClass}
                      value={newCampaignObjective}
                      onChange={e => setNewCampaignObjective(e.target.value as FunnelObjective)}
                    >
                      {ALL_OBJECTIVES.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          if (newCampaignName.trim()) {
                            handleCreateCampaign(newCampaignName.trim());
                            setShowNewCampaign(false);
                            setNewCampaignName('');
                          }
                        }}
                        className="px-3 py-2 text-xs rounded-[var(--radius-md)] bg-[var(--color-violet-500)] text-white hover:bg-[var(--color-violet-600)] cursor-pointer shrink-0"
                      >
                        Add
                      </button>
                      <button
                        onClick={() => {
                          setShowNewCampaign(false);
                          setNewCampaignName('');
                        }}
                        className="px-3 py-2 text-xs rounded-[var(--radius-md)] border border-[var(--color-border-default)] text-muted-foreground hover:bg-[var(--color-bg-secondary)] cursor-pointer shrink-0"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className={labelClass}>Platform</label>
                <select className={fieldClass} value={template.platform || ''} onChange={e => setTemplate(t => ({ ...t, platform: e.target.value || null }))}>
                  <option value="">None</option>
                  {knownPlatforms.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div>
                <label className={labelClass}>Tags</label>
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {template.tags.map(t => (
                    <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-xs text-muted-foreground border border-[var(--color-border-default)]">
                      {t}
                      <button onClick={() => setTemplate(tp => ({ ...tp, tags: tp.tags.filter(tt => tt !== t) }))} className="cursor-pointer hover:text-red-500">
                        <X className="size-3" />
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-1.5">
                  <input
                    type="text"
                    className={cn(fieldClass, "flex-1")}
                    placeholder="Add tag"
                    list="batch-tag-suggestions"
                    value={tagInput}
                    onChange={e => setTagInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleTagAdd(); } }}
                  />
                  <Button variant="outline" size="sm" onClick={handleTagAdd}>Add</Button>
                </div>
                <datalist id="batch-tag-suggestions">
                  {existingTags.filter(t => !template.tags.includes(t)).map(t => <option key={t} value={t} />)}
                </datalist>
              </div>

              <div>
                <label className={labelClass}>Owner</label>
                <select className={fieldClass} value={template.owner || ''} onChange={e => setTemplate(t => ({ ...t, owner: e.target.value || null }))}>
                  <option value="">Unassigned</option>
                  {allowedUsers.map(u => <option key={u.email} value={u.email}>{u.name} ({u.email})</option>)}
                </select>
              </div>

              <div>
                <label className={labelClass}>Initial Status</label>
                <select className={fieldClass} value={template.status} onChange={e => setTemplate(t => ({ ...t, status: e.target.value as ActivityStatus }))}>
                  {ALL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </>
          )}

          {/* ─── STEP 2: SCHEDULE & BUDGET ─── */}
          {step === 2 && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Start Date *</label>
                  <input type="date" className={fieldClass} value={schedule.startDate} onChange={e => setSchedule(s => ({ ...s, startDate: e.target.value }))} />
                </div>
                <div>
                  <label className={labelClass}>End Date *</label>
                  <input type="date" className={fieldClass} value={schedule.endDate} onChange={e => setSchedule(s => ({ ...s, endDate: e.target.value }))} />
                </div>
              </div>

              <div>
                <label className={labelClass}>Frequency *</label>
                <div className="flex gap-2">
                  {([
                    { key: 'daily' as Frequency, label: 'Every Day' },
                    { key: 'weekdays' as Frequency, label: 'Weekdays Only' },
                    { key: 'custom' as Frequency, label: 'Custom Days' },
                  ]).map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setSchedule(s => ({ ...s, frequency: key }))}
                      className={cn(
                        "flex-1 px-3 py-2 text-xs rounded-[var(--radius-md)] border cursor-pointer transition-colors",
                        schedule.frequency === key
                          ? "border-[var(--color-violet-400)] bg-[var(--color-violet-100)] text-[var(--color-violet-500)]"
                          : "border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {schedule.frequency === 'custom' && (
                <div>
                  <label className={labelClass}>Select Days</label>
                  <div className="flex gap-1.5">
                    {dayNames.map((name, idx) => (
                      <button
                        key={name}
                        onClick={() => {
                          setSchedule(s => ({
                            ...s,
                            customDays: s.customDays.includes(idx)
                              ? s.customDays.filter(d => d !== idx)
                              : [...s.customDays, idx].sort(),
                          }));
                        }}
                        className={cn(
                          "size-9 rounded-[var(--radius-md)] text-xs border cursor-pointer transition-colors",
                          schedule.customDays.includes(idx)
                            ? "border-[var(--color-violet-400)] bg-[var(--color-violet-500)] text-white"
                            : "border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]"
                        )}
                      >
                        {name.charAt(0)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className={labelClass}>Launch Time (UTC)</label>
                <input
                  type="time"
                  className={fieldClass}
                  value={schedule.launchTime || ''}
                  onChange={e => setSchedule(s => ({ ...s, launchTime: e.target.value || null }))}
                />
                <p className="text-[0.625rem] text-muted-foreground mt-1">Applied to all activities. Leave blank if not time-scheduled.</p>
              </div>

              <div className="border-t border-[var(--color-border-default)] pt-4">
                <label className={labelClass}>Budget Strategy *</label>
                <div className="space-y-2">
                  {([
                    { key: 'even' as BudgetStrategy, label: 'Even Split', desc: 'Divide total budget equally across all days' },
                    { key: 'weekday-weekend' as BudgetStrategy, label: 'Weekday / Weekend Split', desc: 'Set different amounts for weekdays vs weekends' },
                    { key: 'manual' as BudgetStrategy, label: 'Manual', desc: 'Start with even split, then adjust individual days in preview' },
                  ]).map(({ key, label, desc }) => (
                    <button
                      key={key}
                      onClick={() => setSchedule(s => ({ ...s, budgetStrategy: key }))}
                      className={cn(
                        "w-full text-left p-3 rounded-[var(--radius-md)] border cursor-pointer transition-colors",
                        schedule.budgetStrategy === key
                          ? "border-[var(--color-violet-400)] bg-[var(--color-violet-100)]"
                          : "border-[var(--color-border-default)] hover:border-[var(--color-border-strong)]"
                      )}
                    >
                      <p className={cn("text-xs", schedule.budgetStrategy === key ? "text-[var(--color-violet-500)]" : "")}>{label}</p>
                      <p className="text-[0.625rem] text-muted-foreground mt-0.5">{desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {(schedule.budgetStrategy === 'even' || schedule.budgetStrategy === 'manual') && (
                <div>
                  <label className={labelClass}>Total Budget</label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                    <input
                      type="number"
                      className={cn(fieldClass, "pl-8")}
                      value={schedule.totalBudget}
                      onChange={e => setSchedule(s => ({ ...s, totalBudget: Number(e.target.value) || 0 }))}
                    />
                  </div>
                  {previewActivities.length > 0 && (
                    <p className="text-[0.625rem] text-muted-foreground mt-1">
                      ${Math.round(schedule.totalBudget / previewActivities.length).toLocaleString()}/day across {previewActivities.length} activities
                    </p>
                  )}
                </div>
              )}

              {schedule.budgetStrategy === 'weekday-weekend' && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}>Weekday Cost (per day)</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                      <input type="number" className={cn(fieldClass, "pl-8")} value={schedule.weekdayBudget} onChange={e => setSchedule(s => ({ ...s, weekdayBudget: Number(e.target.value) || 0 }))} />
                    </div>
                  </div>
                  <div>
                    <label className={labelClass}>Weekend Cost (per day)</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                      <input type="number" className={cn(fieldClass, "pl-8")} value={schedule.weekendBudget} onChange={e => setSchedule(s => ({ ...s, weekendBudget: Number(e.target.value) || 0 }))} />
                    </div>
                  </div>
                </div>
              )}

              {previewActivities.length > 0 && (
                <div className="rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] border border-[var(--color-border-default)] p-3 space-y-1">
                  <p className="text-xs"><span className="text-muted-foreground">Activities to create:</span> {previewActivities.length}</p>
                  <p className="text-xs"><span className="text-muted-foreground">Date range:</span> {formatDate(previewActivities[0].date)} – {formatDate(previewActivities[previewActivities.length - 1].date)}</p>
                  <p className="text-xs"><span className="text-muted-foreground">Estimated total:</span> ${previewActivities.reduce((s, a) => s + a.cost, 0).toLocaleString()}</p>
                </div>
              )}
            </>
          )}

          {/* ─── STEP 3: PREVIEW & CONFIRM ─── */}
          {step === 3 && (
            <>
              {/* Summary */}
              <div className="rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] border border-[var(--color-border-default)] p-3 space-y-2">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Campaign</label>
                    <p className="text-xs mt-0.5">{getCampaignName(template.campaign_id)}</p>
                  </div>
                  <div>
                    <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Platform / Channel</label>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="size-2.5 rounded-full" style={{ backgroundColor: pc.color }} />
                      <span className="text-xs">{template.platform || 'None'}{template.channel ? ` / ${template.channel}` : ''}</span>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Activities</label>
                    <p className="text-xs mt-0.5">{includedPreview.length} of {mergedPreview.length}</p>
                  </div>
                  <div>
                    <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Total Cost</label>
                    <p className="text-xs mt-0.5">${totalCost.toLocaleString()}</p>
                  </div>
                  <div>
                    <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Avg/Day</label>
                    <p className="text-xs mt-0.5">${includedPreview.length > 0 ? Math.round(totalCost / includedPreview.length).toLocaleString() : 0}</p>
                  </div>
                </div>
              </div>

              {/* Cost Chart */}
              {totalCost > 0 && (
                <div>
                  <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Cost Distribution</label>
                  <div className="mt-2 h-[7.5rem]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={mergedPreview.map(a => ({
                          date: a.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                          cost: a.cost,
                          excluded: !a.included,
                        }))}
                        margin={{ top: 4, right: 4, bottom: 0, left: -12 }}
                      >
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }}
                          tickLine={false}
                          axisLine={false}
                          interval={mergedPreview.length > 10 ? Math.floor(mergedPreview.length / 7) : 0}
                        />
                        <YAxis
                          tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }}
                          tickLine={false}
                          axisLine={false}
                          tickFormatter={(v: number) => `$${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`}
                          width={40}
                        />
                        <Tooltip
                          contentStyle={{
                            fontSize: 11,
                            borderRadius: 6,
                            border: '1px solid var(--color-border-default)',
                            backgroundColor: 'var(--color-bg-elevated)',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                          }}
                          formatter={(value: number) => [`$${value.toLocaleString()}`, 'Cost']}
                        />
                        <Bar dataKey="cost" radius={[3, 3, 0, 0]} maxBarSize={20}>
                          {mergedPreview.map((a) => (
                            <Cell
                              key={a.id}
                              fill={a.included ? pc.color : '#CBD5E1'}
                              opacity={a.included ? 0.85 : 0.3}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Activity List */}
              <div className="space-y-1">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Individual Activities</label>
                  <button
                    onClick={() => {
                      const allIncluded = mergedPreview.every(a => a.included);
                      mergedPreview.forEach(a => updateOverride(a.id, { included: !allIncluded }));
                    }}
                    className="text-[0.625rem] text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] cursor-pointer"
                  >
                    {mergedPreview.every(a => a.included) ? 'Deselect All' : 'Select All'}
                  </button>
                </div>

                {mergedPreview.map(activity => (
                  <div
                    key={activity.id}
                    className={cn(
                      "flex items-center gap-3 p-2.5 rounded-[var(--radius-sm)] border transition-colors",
                      activity.included
                        ? "border-[var(--color-border-default)] bg-[var(--color-bg-primary)]"
                        : "border-dashed border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] opacity-50"
                    )}
                  >
                    <button
                      onClick={() => updateOverride(activity.id, { included: !activity.included })}
                      className={cn(
                        "size-4 rounded-[3px] border flex items-center justify-center shrink-0 cursor-pointer transition-colors",
                        activity.included
                          ? "bg-[var(--color-violet-500)] border-[var(--color-violet-500)]"
                          : "border-[var(--color-border-strong)] bg-[var(--color-bg-primary)]"
                      )}
                    >
                      {activity.included && <Check className="size-3 text-white" />}
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        {schedule.budgetStrategy === 'manual' && activity.included ? (
                          <input
                            type="text"
                            className="text-xs bg-transparent border-b border-dashed border-[var(--color-border-default)] focus:border-[var(--color-violet-400)] outline-none flex-1 min-w-0 truncate"
                            value={activity.name}
                            onChange={e => updateOverride(activity.id, { name: e.target.value })}
                          />
                        ) : (
                          <p className="text-xs truncate">{activity.name}</p>
                        )}

                        {schedule.budgetStrategy === 'manual' && activity.included ? (
                          <div className="flex items-center gap-0.5 shrink-0">
                            <span className="text-xs text-muted-foreground">$</span>
                            <input
                              type="number"
                              className="text-xs bg-transparent border-b border-dashed border-[var(--color-border-default)] focus:border-[var(--color-violet-400)] outline-none w-16 text-right"
                              value={activity.cost}
                              onChange={e => updateOverride(activity.id, { cost: Number(e.target.value) || 0 })}
                            />
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground shrink-0">${activity.cost.toLocaleString()}</span>
                        )}
                      </div>
                      <p className="text-[0.625rem] text-muted-foreground mt-0.5">
                        {formatDate(activity.date)}{schedule.launchTime ? ` at ${schedule.launchTime} UTC` : ''}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--color-border-default)] flex items-center justify-between gap-2">
          <div>
            {step > 1 && (
              <Button variant="outline" size="sm" onClick={() => setStep(s => s - 1)}>
                <ArrowLeft className="size-3.5 mr-1" /> Back
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
            {step < 3 ? (
              <Button size="sm" onClick={() => setStep(s => s + 1)} disabled={!stepValid}>
                Next <ChevronRight className="size-3.5 ml-1" />
              </Button>
            ) : (
              <Button size="sm" onClick={handleCreate} disabled={!stepValid}>
                <Plus className="size-3.5 mr-1" /> Create {includedPreview.length} Activities
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}