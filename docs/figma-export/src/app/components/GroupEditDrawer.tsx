import { useState, useMemo } from 'react';
import {
  X,
  Check,
  ChevronDown,
  ChevronUp,
  Edit3,
  DollarSign,
  Layers,
  Eye,
  RotateCcw,
  Trash2,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  Tag,
  User,
  Clock,
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
  getUserName,
  statusStyles,
  type CalendarActivity,
  type ActivityStatus,
} from '../data/calendarData';

// ─── Helpers ───

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const ALL_STATUSES: ActivityStatus[] = ['Draft', 'Awaiting Approval', 'Approved', 'Rejected', 'Revision Requested', 'Complete'];

// Checks if all values in a field are the same across activities
function getUniformValue<T>(activities: CalendarActivity[], getter: (a: CalendarActivity) => T): { uniform: true; value: T } | { uniform: false } {
  if (activities.length === 0) return { uniform: false };
  const first = getter(activities[0]);
  const allSame = activities.every(a => {
    const v = getter(a);
    if (v === first) return true;
    if (Array.isArray(v) && Array.isArray(first)) {
      return v.length === first.length && v.every((x, i) => x === (first as unknown[])[i]);
    }
    return false;
  });
  return allSame ? { uniform: true, value: first } : { uniform: false };
}

// ═══════════════════════════════════════════════════════════

export function GroupEditDrawer({
  activities,
  onClose,
  onSave,
  onEditActivity,
  onBackToActivity,
  onDeleteActivity,
}: {
  activities: CalendarActivity[];
  onClose: () => void;
  onSave: (updated: CalendarActivity[]) => void;
  onEditActivity: (id: string) => void;
  onBackToActivity?: () => void;
  onDeleteActivity?: (id: string) => void;
}) {
  if (activities.length === 0) return null;

  const sorted = [...activities].sort((a, b) => a.launch_date.getTime() - b.launch_date.getTime());
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const pc = getPlatformColor(first.platform);
  const campaignName = getCampaignName(first.campaign_id);

  // ─── Editable state: per-activity cost overrides ───
  const [costOverrides, setCostOverrides] = useState<Map<string, number>>(() => new Map());
  const [sharedFieldsOpen, setSharedFieldsOpen] = useState(true);
  const [costToolsOpen, setCostToolsOpen] = useState(false);

  // ─── Shared field edits (applied to all) ───
  const [sharedEdits, setSharedEdits] = useState<{
    owner?: string | null;
    status?: ActivityStatus;
    launch_time_utc?: string | null;
    tags_add?: string[];
    tags_remove?: string[];
  }>({});

  const [tagInput, setTagInput] = useState('');

  // ─── Cost redistribution state ───
  const [redistMode, setRedistMode] = useState<'none' | 'even' | 'weekday-weekend'>('none');
  const [redistTotal, setRedistTotal] = useState(() =>
    sorted.reduce((sum, a) => sum + (a.cost || 0), 0)
  );
  const [weekdayCost, setWeekdayCost] = useState(200);
  const [weekendCost, setWeekendCost] = useState(100);

  // ─── Compute working copies ───
  const workingActivities = useMemo((): CalendarActivity[] => {
    return sorted.map(a => {
      const edits: Partial<CalendarActivity> = {};

      // Shared field edits
      if (sharedEdits.owner !== undefined) edits.owner = sharedEdits.owner;
      if (sharedEdits.status !== undefined) edits.status = sharedEdits.status;
      if (sharedEdits.launch_time_utc !== undefined) edits.launch_time_utc = sharedEdits.launch_time_utc;

      // Tags
      let tags = [...a.tags];
      if (sharedEdits.tags_add) {
        for (const t of sharedEdits.tags_add) {
          if (!tags.includes(t)) tags.push(t);
        }
      }
      if (sharedEdits.tags_remove) {
        tags = tags.filter(t => !sharedEdits.tags_remove!.includes(t));
      }

      // Cost overrides
      let cost = a.cost;
      if (costOverrides.has(a.activity_id)) {
        cost = costOverrides.get(a.activity_id)!;
      } else if (redistMode === 'even') {
        cost = Math.round((redistTotal / sorted.length) * 100) / 100;
      } else if (redistMode === 'weekday-weekend') {
        const dow = a.launch_date.getDay();
        cost = (dow >= 1 && dow <= 5) ? weekdayCost : weekendCost;
      }

      return { ...a, ...edits, tags, cost };
    });
  }, [sorted, sharedEdits, costOverrides, redistMode, redistTotal, weekdayCost, weekendCost]);

  const totalCost = workingActivities.reduce((sum, a) => sum + (a.cost || 0), 0);
  const owners = [...new Set(workingActivities.map(a => a.owner).filter(Boolean) as string[])];

  // ─── Detect shared field uniformity ───
  const ownerInfo = getUniformValue(workingActivities, a => a.owner);
  const statusInfo = getUniformValue(workingActivities, a => a.status);
  const timeInfo = getUniformValue(workingActivities, a => a.launch_time_utc);

  // Collect all tags across all working activities
  const allTags = [...new Set(workingActivities.flatMap(a => a.tags))].sort();

  // ─── Has changes? ───
  const hasChanges = useMemo(() => {
    return Object.keys(sharedEdits).length > 0 || costOverrides.size > 0 || redistMode !== 'none';
  }, [sharedEdits, costOverrides, redistMode]);

  const handleSave = () => {
    const now = new Date();
    const updated = workingActivities.map(a => ({
      ...a,
      last_updated_at: now,
      last_updated_by: 'sarah.chen@example.com',
    }));
    onSave(updated);
  };

  const handleTagAdd = () => {
    const tag = tagInput.trim();
    if (!tag) return;
    setSharedEdits(prev => ({
      ...prev,
      tags_add: [...(prev.tags_add || []).filter(t => t !== tag), tag],
      tags_remove: (prev.tags_remove || []).filter(t => t !== tag),
    }));
    setTagInput('');
  };

  const handleTagRemove = (tag: string) => {
    setSharedEdits(prev => ({
      ...prev,
      tags_remove: [...(prev.tags_remove || []).filter(t => t !== tag), tag],
      tags_add: (prev.tags_add || []).filter(t => t !== tag),
    }));
  };

  const fieldClass = "w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]";
  const labelClass = "text-[0.625rem] text-muted-foreground uppercase tracking-wider mb-1 block";

  return (
    <>
      <div className="fixed inset-0 z-[50] bg-black/30" onClick={onClose} />

      <div className="fixed top-0 right-0 bottom-0 z-[51] w-full max-w-lg bg-[var(--color-bg-elevated)] border-l border-[var(--color-border-default)] shadow-xl flex flex-col overflow-hidden">
        {/* Back to activity link */}
        {onBackToActivity && (
          <button
            onClick={onBackToActivity}
            className="flex items-center gap-1 px-4 py-2 text-xs text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] hover:bg-[var(--color-violet-50)] cursor-pointer border-b border-[var(--color-border-default)] transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            Back to activity
          </button>
        )}
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-[var(--color-violet-500)]" />
            <h2 className="text-sm">Edit Project</h2>
            <span className="bg-[var(--color-violet-100)] text-[var(--color-violet-600)] border border-[var(--color-violet-200)] rounded-full px-2 py-0.5 text-xs">
              {sorted.length} activities
            </span>
          </div>
          <button onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Group Summary */}
          <div className="p-4 border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] space-y-3">
            <div>
              <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Campaign</label>
              <p className="text-sm mt-0.5">{campaignName}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Platform · Channel</label>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="size-2.5 rounded-full" style={{ backgroundColor: pc.color }} />
                  <span className="text-sm">{first.platform || '—'}{first.channel ? ` · ${first.channel}` : ''}</span>
                </div>
              </div>
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Date Range</label>
                <p className="text-sm mt-0.5">{formatDate(first.launch_date)} – {formatDate(last.launch_date)}</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Total Cost</label>
                <p className="text-sm mt-0.5">${totalCost.toLocaleString()}</p>
              </div>
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Avg/Day</label>
                <p className="text-sm mt-0.5">${sorted.length > 0 ? Math.round(totalCost / sorted.length).toLocaleString() : 0}</p>
              </div>
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Owner{owners.length > 1 ? 's' : ''}</label>
                <p className="text-sm mt-0.5">{owners.map(o => getUserName(o)).join(', ') || '—'}</p>
              </div>
            </div>
          </div>

          {/* ─── Shared Fields Panel ─── */}
          <div className="border-b border-[var(--color-border-default)]">
            <button
              onClick={() => setSharedFieldsOpen(!sharedFieldsOpen)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Edit3 className="size-3.5 text-[var(--color-violet-500)]" />
                Shared Fields
                <span className="text-[0.625rem] text-muted-foreground">(apply to all activities)</span>
              </span>
              {sharedFieldsOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>

            {sharedFieldsOpen && (
              <div className="px-4 pb-4 space-y-3">
                {/* Owner */}
                <div>
                  <label className={labelClass}>
                    <span className="flex items-center gap-1">
                      <User className="size-3" /> Owner
                      {!ownerInfo.uniform && <span className="text-orange-500 ml-1">(Mixed)</span>}
                    </span>
                  </label>
                  <select
                    className={fieldClass}
                    value={
                      sharedEdits.owner !== undefined
                        ? (sharedEdits.owner || '')
                        : ownerInfo.uniform
                        ? (ownerInfo.value || '')
                        : '__mixed__'
                    }
                    onChange={e => {
                      const v = e.target.value;
                      if (v === '__mixed__') return;
                      setSharedEdits(prev => ({ ...prev, owner: v || null }));
                    }}
                  >
                    {!ownerInfo.uniform && sharedEdits.owner === undefined && (
                      <option value="__mixed__">— Mixed values —</option>
                    )}
                    <option value="">Unassigned</option>
                    {allowedUsers.map(u => (
                      <option key={u.email} value={u.email}>{u.name} ({u.email})</option>
                    ))}
                  </select>
                </div>

                {/* Status */}
                <div>
                  <label className={labelClass}>
                    <span className="flex items-center gap-1">
                      Status
                      {!statusInfo.uniform && <span className="text-orange-500 ml-1">(Mixed)</span>}
                    </span>
                  </label>
                  <select
                    className={fieldClass}
                    value={
                      sharedEdits.status !== undefined
                        ? sharedEdits.status
                        : statusInfo.uniform
                        ? statusInfo.value
                        : '__mixed__'
                    }
                    onChange={e => {
                      const v = e.target.value;
                      if (v === '__mixed__') return;
                      setSharedEdits(prev => ({ ...prev, status: v as ActivityStatus }));
                    }}
                  >
                    {!statusInfo.uniform && sharedEdits.status === undefined && (
                      <option value="__mixed__">— Mixed values —</option>
                    )}
                    {ALL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>

                {/* Launch Time */}
                <div>
                  <label className={labelClass}>
                    <span className="flex items-center gap-1">
                      <Clock className="size-3" /> Launch Time (UTC)
                      {!timeInfo.uniform && <span className="text-orange-500 ml-1">(Mixed)</span>}
                    </span>
                  </label>
                  <input
                    type="time"
                    className={fieldClass}
                    value={
                      sharedEdits.launch_time_utc !== undefined
                        ? (sharedEdits.launch_time_utc || '')
                        : timeInfo.uniform
                        ? (timeInfo.value || '')
                        : ''
                    }
                    onChange={e => setSharedEdits(prev => ({ ...prev, launch_time_utc: e.target.value || null }))}
                  />
                  {!timeInfo.uniform && sharedEdits.launch_time_utc === undefined && (
                    <p className="text-[0.625rem] text-orange-500 mt-1">Activities have different launch times</p>
                  )}
                </div>

                {/* Tags */}
                <div>
                  <label className={labelClass}>
                    <span className="flex items-center gap-1">
                      <Tag className="size-3" /> Tags
                    </span>
                  </label>
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {allTags.map(t => {
                      const isBeingRemoved = (sharedEdits.tags_remove || []).includes(t);
                      const isBeingAdded = (sharedEdits.tags_add || []).includes(t);
                      return (
                        <span
                          key={t}
                          className={cn(
                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border",
                            isBeingRemoved
                              ? "bg-red-50 text-red-400 border-red-200 line-through"
                              : isBeingAdded
                              ? "bg-green-50 text-green-600 border-green-200"
                              : "bg-[var(--color-bg-secondary)] text-muted-foreground border-[var(--color-border-default)]"
                          )}
                        >
                          {t}
                          {isBeingRemoved ? (
                            <button
                              onClick={() => setSharedEdits(prev => ({
                                ...prev,
                                tags_remove: (prev.tags_remove || []).filter(tt => tt !== t),
                              }))}
                              className="cursor-pointer text-red-400 hover:text-red-600"
                              title="Undo removal"
                            >
                              <RotateCcw className="size-2.5" />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleTagRemove(t)}
                              className="cursor-pointer hover:text-red-500"
                              title="Remove from all"
                            >
                              <X className="size-3" />
                            </button>
                          )}
                        </span>
                      );
                    })}
                  </div>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      className={cn(fieldClass, "flex-1")}
                      placeholder="Add tag to all activities"
                      list="group-edit-tag-suggestions"
                      value={tagInput}
                      onChange={e => setTagInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleTagAdd(); } }}
                    />
                    <Button variant="outline" size="sm" onClick={handleTagAdd}>Add</Button>
                  </div>
                  <datalist id="group-edit-tag-suggestions">
                    {existingTags.filter(t => !allTags.includes(t)).map(t => <option key={t} value={t} />)}
                  </datalist>
                </div>
              </div>
            )}
          </div>

          {/* ─── Cost Redistribution Tools ─── */}
          <div className="border-b border-[var(--color-border-default)]">
            <button
              onClick={() => setCostToolsOpen(!costToolsOpen)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <DollarSign className="size-3.5 text-[var(--color-violet-500)]" />
                Cost Redistribution
                {redistMode !== 'none' && (
                  <span className="bg-[var(--color-violet-100)] text-[var(--color-violet-600)] rounded-full px-1.5 py-0.5 text-[0.625rem]">
                    {redistMode === 'even' ? 'Even' : 'Weekday/Weekend'}
                  </span>
                )}
              </span>
              {costToolsOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>

            {costToolsOpen && (
              <div className="px-4 pb-4 space-y-3">
                <div className="flex gap-2">
                  {([
                    { key: 'none' as const, label: 'No Change' },
                    { key: 'even' as const, label: 'Even Split' },
                    { key: 'weekday-weekend' as const, label: 'Weekday/Weekend' },
                  ]).map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => {
                        setRedistMode(key);
                        setCostOverrides(new Map());
                      }}
                      className={cn(
                        "flex-1 px-3 py-2 text-xs rounded-[var(--radius-md)] border cursor-pointer transition-colors",
                        redistMode === key
                          ? "border-[var(--color-violet-400)] bg-[var(--color-violet-100)] text-[var(--color-violet-500)]"
                          : "border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {redistMode === 'even' && (
                  <div>
                    <label className={labelClass}>Total Budget</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                      <input
                        type="number"
                        className={cn(fieldClass, "pl-8")}
                        value={redistTotal}
                        onChange={e => { setRedistTotal(Number(e.target.value) || 0); setCostOverrides(new Map()); }}
                      />
                    </div>
                    <p className="text-[0.625rem] text-muted-foreground mt-1">
                      ${Math.round(redistTotal / sorted.length).toLocaleString()}/day across {sorted.length} activities
                    </p>
                  </div>
                )}

                {redistMode === 'weekday-weekend' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelClass}>Weekday (per day)</label>
                      <div className="relative">
                        <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                        <input
                          type="number"
                          className={cn(fieldClass, "pl-8")}
                          value={weekdayCost}
                          onChange={e => { setWeekdayCost(Number(e.target.value) || 0); setCostOverrides(new Map()); }}
                        />
                      </div>
                    </div>
                    <div>
                      <label className={labelClass}>Weekend (per day)</label>
                      <div className="relative">
                        <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                        <input
                          type="number"
                          className={cn(fieldClass, "pl-8")}
                          value={weekendCost}
                          onChange={e => { setWeekendCost(Number(e.target.value) || 0); setCostOverrides(new Map()); }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ─── Cost Breakdown Chart ─── */}
          {totalCost > 0 && (
            <div className="p-4 border-b border-[var(--color-border-default)]">
              <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Daily Cost Breakdown</label>
              <div className="mt-2 h-[8.125rem]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={workingActivities.map(a => ({
                      date: a.launch_date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                      cost: a.cost || 0,
                      id: a.activity_id,
                    }))}
                    margin={{ top: 4, right: 4, bottom: 0, left: -12 }}
                  >
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }}
                      tickLine={false}
                      axisLine={false}
                      interval={sorted.length > 10 ? Math.floor(sorted.length / 7) : 0}
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
                    <Bar dataKey="cost" radius={[3, 3, 0, 0]} maxBarSize={28}>
                      {workingActivities.map((a, i) => (
                        <Cell
                          key={`${a.activity_id ?? 'cell'}-${i}`}
                          fill={pc.color}
                          opacity={0.85}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center justify-between mt-1 text-[0.625rem] text-muted-foreground">
                <span>Total: ${totalCost.toLocaleString()}</span>
                <span>Avg: ${sorted.length > 0 ? Math.round(totalCost / sorted.length).toLocaleString() : 0}/day</span>
              </div>
            </div>
          )}

          {/* ─── Individual Activities ─── */}
          <div className="p-4 space-y-1">
            <div className="flex items-center justify-between mb-2">
              <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Individual Activities</label>
              <span className="text-[0.625rem] text-muted-foreground">Click cost to override individually</span>
            </div>

            {workingActivities.map(activity => {
              const hasOverride = costOverrides.has(activity.activity_id);
              const style = statusStyles[activity.status];
              return (
                <div
                  key={activity.activity_id}
                  className="flex items-center gap-3 p-2.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] transition-colors"
                >
                  {/* Status dot */}
                  <span
                    className="size-2 rounded-full shrink-0"
                    style={{ backgroundColor: style.text }}
                    title={activity.status}
                  />

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs truncate">{activity.name}</p>
                      {/* Editable cost */}
                      <div className="flex items-center gap-0.5 shrink-0">
                        <span className="text-xs text-muted-foreground">$</span>
                        <input
                          type="number"
                          className={cn(
                            "text-xs bg-transparent border-b border-dashed outline-none w-16 text-right",
                            hasOverride
                              ? "border-[var(--color-violet-400)] text-[var(--color-violet-600)]"
                              : "border-[var(--color-border-default)] focus:border-[var(--color-violet-400)]"
                          )}
                          value={activity.cost ?? 0}
                          onChange={e => {
                            const v = Number(e.target.value) || 0;
                            setCostOverrides(prev => {
                              const next = new Map(prev);
                              next.set(activity.activity_id, v);
                              return next;
                            });
                          }}
                        />
                      </div>
                    </div>
                    <p className="text-[0.625rem] text-muted-foreground mt-0.5">
                      {formatDate(activity.launch_date)}{activity.launch_time_utc ? ` at ${activity.launch_time_utc} UTC` : ''}
                    </p>
                  </div>

                  {/* Edit individual */}
                  <button
                    onClick={() => onEditActivity(activity.activity_id)}
                    className="text-muted-foreground hover:text-foreground cursor-pointer shrink-0"
                    title="Edit individual activity"
                  >
                    <Eye className="size-3.5" />
                  </button>
                  {onDeleteActivity && (
                    <button
                      onClick={() => onDeleteActivity(activity.activity_id)}
                      className="text-muted-foreground hover:text-red-500 cursor-pointer shrink-0"
                      title="Delete activity"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--color-border-default)] flex items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            {hasChanges ? (
              <span className="text-[var(--color-violet-500)]">Unsaved changes</span>
            ) : (
              <span>No changes</span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={!hasChanges}>
              Save {sorted.length} Activities
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}