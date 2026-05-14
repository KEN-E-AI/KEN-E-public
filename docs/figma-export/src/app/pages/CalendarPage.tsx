import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Calendar as CalendarIcon,
  List,
  Filter,
  X,
  ChevronDown,
  ChevronUp,
  Check,
  XCircle,
  RotateCcw,
  Megaphone,
  ArrowUp,
  ArrowDown,
  CheckCircle2,
  Edit3,
  Trash2,
  Clock,
  User,
  DollarSign,
  Tag,
  FolderOpen,
  Info,
  ArrowUpDown,
  Eye,
  Layers,
  ArrowLeft,
  ShoppingBag,
  Flag,
  Link,
  Globe,
  Repeat,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { useLocation } from 'react-router';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card } from '../components/ui/card';
import { cn } from '../components/ui/utils';
import { BatchActivityWizard } from '../components/BatchActivityWizard';
import { GroupEditDrawer } from '../components/GroupEditDrawer';
import {
  calendarCampaigns,
  channelGuidelines,
  allowedUsers,
  knownPlatforms,
  existingCategories,
  existingTags,
  getPlatformColor,
  getCampaignName,
  getCampaignObjective,
  getCampaignsForObjective,
  getGenericCampaignId,
  addCampaign,
  getUserName,
  statusStyles,
  platformColors,
  neutralPlatformColor,
  promotionTypes,
  holidayTypes,
  knownRegions,
  type CalendarActivity,
  type ActivityStatus,
  type FunnelObjective,
  type ActivityCategory,
  type PromotionType,
  type HolidayType,
} from '../data/calendarData';
import { useActivities } from '../contexts/ActivitiesContext';
import { UnscheduledTasksPanel } from '../components/UnscheduledTasksPanel';
import { ProjectsInRangePanel } from '../components/ProjectsInRangePanel';
import { MoveToProjectDialog } from '../components/MoveToProjectDialog';
import { useStandaloneTasks, attachToPlan } from '../data/standaloneTasks';
import {
  computeNextRun,
  describeSchedule,
  createDefaultSchedule,
  DAY_LABELS as SCHEDULE_DAY_LABELS,
  type AutomationSchedule,
  type ScheduleFrequency,
} from '../data/automationDetailsData';

// ─── Constants ───

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const ALL_STATUSES: ActivityStatus[] = ['Draft', 'Awaiting Approval', 'Approved', 'Rejected', 'Revision Requested', 'Complete'];
const ALL_OBJECTIVES: FunnelObjective[] = ['Problem Awareness', 'Brand Awareness', 'Consideration', 'Conversion'];
const ALL_ACTIVITY_CATEGORIES: ActivityCategory[] = ['task', 'promotion', 'holiday'];
const CATEGORY_LABELS: Record<ActivityCategory, string> = { task: 'Task', promotion: 'Promotion', holiday: 'Holiday' };

type ViewMode = 'calendar' | 'list';
type AddMode = 'task' | 'project' | 'promotion' | 'holiday';

interface Filters {
  platform: string[];
  channel: string[];
  status: ActivityStatus[];
  objective: FunnelObjective[];
  category: string[];
  activityType: ActivityCategory[];
  owner: string[];
  tags: string[];
}

const emptyFilters: Filters = {
  platform: [],
  channel: [],
  status: [],
  objective: [],
  category: [],
  activityType: [],
  owner: [],
  tags: [],
};

function hasActiveFilters(f: Filters): boolean {
  return Object.values(f).some(arr => arr.length > 0);
}

// ─── Date Helpers ───

function startOfWeek(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday start
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDateFull(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

function formatDateISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function parseDateISO(s: string): Date {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

// ─── Approval Group Helpers ───

interface ApprovalGroup {
  key: string;
  campaignId: string;
  platform: string | null;
  channel: string | null;
  month: string; // "YYYY-MM"
  activities: CalendarActivity[];
  totalCost: number;
  dateRange: { start: Date; end: Date };
  owners: string[];
}

function getGroupKey(a: CalendarActivity): string {
  const month = `${a.launch_date.getFullYear()}-${String(a.launch_date.getMonth() + 1).padStart(2, '0')}`;
  return `${a.campaign_id}|${a.platform || ''}|${a.channel || ''}|${month}`;
}

function buildApprovalGroups(items: CalendarActivity[]): { groups: ApprovalGroup[]; singles: CalendarActivity[] } {
  const map = new Map<string, CalendarActivity[]>();
  for (const item of items) {
    const key = getGroupKey(item);
    const arr = map.get(key) || [];
    arr.push(item);
    map.set(key, arr);
  }

  const groups: ApprovalGroup[] = [];
  const singles: CalendarActivity[] = [];

  for (const [key, acts] of map.entries()) {
    if (acts.length >= 2) {
      const sorted = [...acts].sort((a, b) => a.launch_date.getTime() - b.launch_date.getTime());
      const owners = [...new Set(sorted.map(a => a.owner).filter(Boolean) as string[])];
      groups.push({
        key,
        campaignId: sorted[0].campaign_id,
        platform: sorted[0].platform,
        channel: sorted[0].channel,
        month: `${sorted[0].launch_date.getFullYear()}-${String(sorted[0].launch_date.getMonth() + 1).padStart(2, '0')}`,
        activities: sorted,
        totalCost: sorted.reduce((sum, a) => sum + (a.cost || 0), 0),
        dateRange: { start: sorted[0].launch_date, end: sorted[sorted.length - 1].launch_date },
        owners,
      });
    } else {
      singles.push(acts[0]);
    }
  }

  // Sort groups by earliest date
  groups.sort((a, b) => a.dateRange.start.getTime() - b.dateRange.start.getTime());
  // Sort singles by launch date
  singles.sort((a, b) => a.launch_date.getTime() - b.launch_date.getTime());

  return { groups, singles };
}

function formatMonthYear(monthStr: string): string {
  const [y, m] = monthStr.split('-').map(Number);
  return new Date(y, m - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

// ─── Status Badge Component ───

function StatusBadge({ status }: { status: ActivityStatus }) {
  const style = statusStyles[status];
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs whitespace-nowrap"
      style={{ backgroundColor: style.bg, color: style.text, border: `1px solid ${style.border}` }}
    >
      {status === 'Complete' && <CheckCircle2 className="size-3" />}
      {status}
    </span>
  );
}

// ─── Direction Indicator ───

// ─── Multi-Select Dropdown ───

function MultiSelectDropdown({
  label,
  options,
  selected,
  onToggle,
  renderOption,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
  renderOption?: (value: string) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] border text-xs cursor-pointer transition-colors",
          selected.length > 0
            ? "border-[var(--color-violet-400)] bg-[var(--color-violet-100)] text-[var(--color-violet-500)]"
            : "border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] text-muted-foreground hover:border-[var(--color-border-strong)]"
        )}
      >
        {label}
        {selected.length > 0 && (
          <span className="bg-[var(--color-violet-500)] text-white rounded-full size-4 flex items-center justify-center text-[0.625rem]">
            {selected.length}
          </span>
        )}
        <ChevronDown className="size-3" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 z-50 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg min-w-[11.25rem] max-h-[15rem] overflow-y-auto py-1">
            {options.map(opt => (
              <button
                key={opt}
                onClick={() => onToggle(opt)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left hover:bg-[var(--color-bg-secondary)] cursor-pointer"
              >
                <span className={cn(
                  "size-4 rounded border flex items-center justify-center shrink-0",
                  selected.includes(opt)
                    ? "bg-[var(--color-violet-500)] border-[var(--color-violet-500)] text-white"
                    : "border-[var(--color-border-default)]"
                )}>
                  {selected.includes(opt) && <Check className="size-3" />}
                </span>
                {renderOption ? renderOption(opt) : <span className="truncate">{opt}</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ─── MAIN PAGE COMPONENT ───
// ═══════════════════════════════════════════════════════════

export function CalendarPage() {
  const location = useLocation();
  const { activities, setActivities } = useActivities();
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date(2026, 2, 23)));
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [showFilters, setShowFilters] = useState(false);
  const [queueCollapsed, setQueueCollapsed] = useState(true);

  // Detail/Edit drawer
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
  const [drawerMode, setDrawerMode] = useState<'view' | 'edit' | 'add'>('view');
  const [addCategory, setAddCategory] = useState<ActivityCategory>('task');

  // Standalone/orphan tasks panel
  const orphanTasks = useStandaloneTasks();
  const [unscheduledCollapsed, setUnscheduledCollapsed] = useState(true);
  const [moveTaskId, setMoveTaskId] = useState<string | null>(null);

  // Batch wizard
  const [showBatchWizard, setShowBatchWizard] = useState(false);
  const [showAddMenu, setShowAddMenu] = useState(false);

  // Group edit drawer
  const [groupEditIds, setGroupEditIds] = useState<string[] | null>(null);
  const [pendingGroupEditIds, setPendingGroupEditIds] = useState<string[] | null>(null);
  const [groupEditOriginActivityId, setGroupEditOriginActivityId] = useState<string | null>(null);

  // Group review drawer
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[] | null>(null);
  const [pendingGroupIds, setPendingGroupIds] = useState<string[] | null>(null);

  // Revision modal
  const [revisionActivityId, setRevisionActivityId] = useState<string | null>(null);
  const [revisionComment, setRevisionComment] = useState('');
  const [batchRevisionIds, setBatchRevisionIds] = useState<string[] | null>(null);

  // Sort for list view
  const [sortField, setSortField] = useState<string>('launch_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // ─── Deep-link: open activity detail from navigation state ───
  useEffect(() => {
    const state = location.state as { viewActivityId?: string } | null;
    if (state?.viewActivityId) {
      const exists = activities.some(a => a.activity_id === state.viewActivityId);
      if (exists) {
        setSelectedActivityId(state.viewActivityId);
        setDrawerMode('view');
      }
      // Clear the state so a re-render doesn't re-trigger
      window.history.replaceState({}, '');
    }
  }, [location.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Derived Data ───

  const approvalQueue = useMemo(
    () => activities.filter(a => a.status === 'Awaiting Approval' && a.category === 'task'),
    [activities]
  );

  const filteredActivities = useMemo(() => {
    return [...activities, ...orphanTasks].filter(a => {
      if (filters.platform.length > 0 && (!a.platform || !filters.platform.includes(a.platform))) return false;
      if (filters.channel.length > 0 && (!a.channel || !filters.channel.includes(a.channel))) return false;
      if (filters.status.length > 0 && !filters.status.includes(a.status)) return false;
      if (filters.objective.length > 0 && !filters.objective.includes(a.objective)) return false;
      if (filters.activityType.length > 0 && !filters.activityType.includes(a.category)) return false;
      if (filters.category.length > 0 && (!a.task_type || !filters.category.includes(a.task_type))) return false;
      if (filters.owner.length > 0 && (!a.owner || !filters.owner.includes(a.owner))) return false;
      if (filters.tags.length > 0 && !filters.tags.some(t => a.tags.includes(t))) return false;
      return true;
    });
  }, [activities, orphanTasks, filters]);

  // ─── Filter Helpers ───

  const toggleFilter = useCallback((key: keyof Filters, value: string) => {
    setFilters(prev => {
      const arr = prev[key] as string[];
      return {
        ...prev,
        [key]: arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value],
      };
    });
  }, []);

  const activeFilterChips = useMemo(() => {
    const chips: { key: keyof Filters; value: string; label: string }[] = [];
    for (const [key, values] of Object.entries(filters)) {
      for (const v of values) {
        const label = key === 'owner' ? getUserName(v) || v : key === 'activityType' ? CATEGORY_LABELS[v as ActivityCategory] : v;
        chips.push({ key: key as keyof Filters, value: v, label: `${key === 'activityType' ? 'type' : key}: ${label}` });
      }
    }
    return chips;
  }, [filters]);

  // ─── Orphan → Project Actions ───

  const handleMoveToProject = useCallback((taskId: string, planId: string) => {
    const result = attachToPlan(taskId, planId);
    if (result.ok) {
      setActivities(prev => [...prev, result.task]);
      setSelectedActivityId(result.task.activity_id);
      setDrawerMode('view');
    }
    setMoveTaskId(null);
  }, [setActivities]);

  const handleCreateProjectForTask = useCallback((taskId: string, projectName: string) => {
    const newPlanId = `wf-new-${Date.now()}`;
    const result = attachToPlan(taskId, newPlanId);
    if (result.ok) {
      setActivities(prev => [...prev, result.task]);
      setSelectedActivityId(result.task.activity_id);
      setDrawerMode('view');
    }
    setMoveTaskId(null);
    console.info(`[stub] Created project "${projectName}" with id ${newPlanId}`);
  }, [setActivities]);

  // ─── Approval Actions ───

  const handleApprove = useCallback((id: string) => {
    setActivities(prev => prev.map(a => a.activity_id === id ? { ...a, status: 'Approved' as ActivityStatus, last_updated_at: new Date() } : a));
  }, []);

  const handleReject = useCallback((id: string) => {
    setActivities(prev => prev.map(a => a.activity_id === id ? { ...a, status: 'Rejected' as ActivityStatus, last_updated_at: new Date() } : a));
  }, []);

  const handleRevisionRequest = useCallback(() => {
    if (!revisionComment.trim()) return;
    const idsToRevise = batchRevisionIds || (revisionActivityId ? [revisionActivityId] : []);
    if (idsToRevise.length === 0) return;
    setActivities(prev => prev.map(a =>
      idsToRevise.includes(a.activity_id)
        ? { ...a, status: 'Revision Requested' as ActivityStatus, revision_comment: revisionComment.trim(), last_updated_at: new Date() }
        : a
    ));
    setRevisionActivityId(null);
    setRevisionComment('');
    setBatchRevisionIds(null);
  }, [revisionActivityId, revisionComment, batchRevisionIds]);

  // ─── Batch Approval Actions ───

  const handleBatchApprove = useCallback((ids: string[]) => {
    setActivities(prev => prev.map(a =>
      ids.includes(a.activity_id) ? { ...a, status: 'Approved' as ActivityStatus, last_updated_at: new Date() } : a
    ));
    setSelectedGroupIds(null);
  }, []);

  const handleBatchReject = useCallback((ids: string[]) => {
    setActivities(prev => prev.map(a =>
      ids.includes(a.activity_id) ? { ...a, status: 'Rejected' as ActivityStatus, last_updated_at: new Date() } : a
    ));
    setSelectedGroupIds(null);
  }, []);

  // ─── Activity CRUD ───

  const handleSaveActivity = useCallback((activity: CalendarActivity) => {
    setActivities(prev => {
      const exists = prev.find(a => a.activity_id === activity.activity_id);
      if (exists) {
        return prev.map(a => a.activity_id === activity.activity_id ? activity : a);
      }
      return [...prev, activity];
    });
    setSelectedActivityId(activity.activity_id);
    setDrawerMode('view');
  }, []);

  const handleDeleteActivity = useCallback((id: string) => {
    setActivities(prev => prev.filter(a => a.activity_id !== id));
    setSelectedActivityId(null);
    setDrawerMode('view');
  }, []);

  const handleBatchCreate = useCallback((newActivities: CalendarActivity[]) => {
    setActivities(prev => [...prev, ...newActivities]);
    setShowBatchWizard(false);
  }, []);

  const handleGroupSave = useCallback((updated: CalendarActivity[]) => {
    const idSet = new Set(updated.map(a => a.activity_id));
    setActivities(prev => prev.map(a => {
      if (idSet.has(a.activity_id)) {
        return updated.find(u => u.activity_id === a.activity_id)!;
      }
      return a;
    }));
    setGroupEditIds(null);
  }, []);

  // Find group siblings for any activity (all statuses)
  const getGroupSiblings = useCallback((activity: CalendarActivity): CalendarActivity[] => {
    const key = getGroupKey(activity);
    return activities.filter(a => getGroupKey(a) === key);
  }, [activities]);

  // ─── Navigation ─���─

  const goToday = () => setWeekStart(startOfWeek(new Date(2026, 2, 23)));
  const goPrev = () => setWeekStart(prev => addDays(prev, -7));
  const goNext = () => setWeekStart(prev => addDays(prev, 7));

  // ─── Distinct values for filters ───

  const distinctPlatforms = useMemo(() => [...new Set(activities.map(a => a.platform).filter(Boolean) as string[])].sort(), [activities]);
  const distinctTags = useMemo(() => [...new Set(activities.flatMap(a => a.tags))].sort(), [activities]);

  const selectedActivity = selectedActivityId ? activities.find(a => a.activity_id === selectedActivityId) : null;
  const selectedGroupSiblings = selectedActivity ? getGroupSiblings(selectedActivity) : [];
  const selectedGroupSiblingCount = selectedGroupSiblings.length;

  return (
    <div className="flex flex-col h-full relative">
      {/* ─── Page Header ─── */}
      <div className="px-6 pt-6 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center"
            style={{ boxShadow: 'var(--shadow-color-violet)' }}
          >
            <CalendarIcon className="size-4 text-[var(--color-text-inverse)]" />
          </div>
          <div>
            <h1>Calendar</h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Plan and manage your marketing campaign activities.
            </p>
          </div>
        </div>
        <div className="relative">
          <div className="flex">
            <Button
              size="sm"
              className="rounded-r-none"
              onClick={() => {
                setSelectedActivityId(null);
                setAddCategory('task');
                setDrawerMode('add');
              }}
            >
              <Plus className="size-4 mr-1.5" /> Add Task
            </Button>
            <Button
              size="sm"
              className="rounded-l-none border-l border-white/20 px-1.5"
              onClick={() => setShowAddMenu(prev => !prev)}
            >
              <ChevronDown className="size-3.5" />
            </Button>
          </div>
          {showAddMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowAddMenu(false)} />
              <div className="absolute top-full right-0 mt-1 z-50 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg min-w-[15rem] py-1">
                <button
                  onClick={() => {
                    setShowAddMenu(false);
                    setSelectedActivityId(null);
                    setAddCategory('task');
                    setDrawerMode('add');
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[var(--color-bg-secondary)] cursor-pointer text-left"
                >
                  <Megaphone className="size-3.5" />
                  Add Task
                </button>
                <button
                  onClick={() => {
                    setShowAddMenu(false);
                    setShowBatchWizard(true);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[var(--color-bg-secondary)] cursor-pointer text-left"
                >
                  <Layers className="size-3.5" />
                  Add Project
                </button>
                <div className="border-t border-[var(--color-border-default)] my-1" />
                <button
                  onClick={() => {
                    setShowAddMenu(false);
                    setSelectedActivityId(null);
                    setAddCategory('promotion');
                    setDrawerMode('add');
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[var(--color-bg-secondary)] cursor-pointer text-left"
                >
                  <ShoppingBag className="size-3.5" />
                  Add Product/Service Promotion
                </button>
                <button
                  onClick={() => {
                    setShowAddMenu(false);
                    setSelectedActivityId(null);
                    setAddCategory('holiday');
                    setDrawerMode('add');
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[var(--color-bg-secondary)] cursor-pointer text-left"
                >
                  <Flag className="size-3.5" />
                  Add Holiday
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ─── Scrollable Content ─── */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-4">

        {/* ─── Approval Queue ─── */}
        <ApprovalQueue
          items={approvalQueue}
          collapsed={queueCollapsed}
          onToggleCollapse={() => setQueueCollapsed(!queueCollapsed)}
          onViewActivity={(id) => { setSelectedActivityId(id); setDrawerMode('view'); }}
          onViewGroup={(ids) => { setSelectedGroupIds(ids); }}
        />

        {/* ─── Unscheduled tasks (orphan) ─── */}
        <UnscheduledTasksPanel
          onEdit={(taskId) => { setSelectedActivityId(taskId); setDrawerMode('view'); }}
          onMoveToProject={(taskId) => setMoveTaskId(taskId)}
          collapsed={unscheduledCollapsed}
          onToggleCollapse={() => setUnscheduledCollapsed(v => !v)}
        />

        {/* ─── Toolbar ─── */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={goPrev}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={goToday}>
              Today
            </Button>
            <Button variant="outline" size="sm" onClick={goNext}>
              <ChevronRight className="size-4" />
            </Button>
            <span className="text-sm text-muted-foreground ml-2">
              {formatDate(weekStart)} &ndash; {formatDate(addDays(weekStart, 27))}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className={cn(hasActiveFilters(filters) && "border-[var(--color-violet-400)] text-[var(--color-violet-500)]")}
            >
              <Filter className="size-3.5 mr-1.5" />
              Filters
              {hasActiveFilters(filters) && (
                <span className="bg-[var(--color-violet-500)] text-white rounded-full size-4 flex items-center justify-center text-[0.625rem] ml-1">
                  {activeFilterChips.length}
                </span>
              )}
            </Button>

            <div className="flex items-center gap-0.5 p-0.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)]">
              <button
                onClick={() => setViewMode('calendar')}
                className={cn(
                  "flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-xs)] text-xs transition-all cursor-pointer",
                  viewMode === 'calendar'
                    ? "bg-[var(--color-violet-500)] text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <CalendarIcon className="size-3.5" /> Calendar
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  "flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-xs)] text-xs transition-all cursor-pointer",
                  viewMode === 'list'
                    ? "bg-[var(--color-violet-500)] text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <List className="size-3.5" /> List
              </button>
            </div>
          </div>
        </div>

        {/* ─── Filter Bar ─── */}
        {showFilters && (
          <div className="flex flex-wrap items-center gap-2 p-3 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] border border-[var(--color-border-default)]">
            <MultiSelectDropdown
              label="Platform"
              options={distinctPlatforms}
              selected={filters.platform}
              onToggle={(v) => toggleFilter('platform', v)}
              renderOption={(v) => {
                const pc = getPlatformColor(v);
                return (
                  <span className="flex items-center gap-2">
                    <span className="size-2.5 rounded-full shrink-0" style={{ backgroundColor: pc.color }} />
                    {v}
                  </span>
                );
              }}
            />
            <MultiSelectDropdown
              label="Channel"
              options={channelGuidelines.map(c => c.channel)}
              selected={filters.channel}
              onToggle={(v) => toggleFilter('channel', v)}
            />
            <MultiSelectDropdown
              label="Status"
              options={ALL_STATUSES}
              selected={filters.status}
              onToggle={(v) => toggleFilter('status', v as ActivityStatus)}
            />
            <MultiSelectDropdown
              label="Objective"
              options={ALL_OBJECTIVES}
              selected={filters.objective}
              onToggle={(v) => toggleFilter('objective', v as FunnelObjective)}
            />
            <MultiSelectDropdown
              label="Type"
              options={ALL_ACTIVITY_CATEGORIES}
              selected={filters.activityType}
              onToggle={(v) => toggleFilter('activityType', v)}
              renderOption={(v) => <span>{CATEGORY_LABELS[v as ActivityCategory]}</span>}
            />
            <MultiSelectDropdown
              label="Owner"
              options={allowedUsers.map(u => u.email)}
              selected={filters.owner}
              onToggle={(v) => toggleFilter('owner', v)}
              renderOption={(v) => (
                <span>{getUserName(v)}</span>
              )}
            />
            <MultiSelectDropdown
              label="Tags"
              options={distinctTags}
              selected={filters.tags}
              onToggle={(v) => toggleFilter('tags', v)}
            />
            {hasActiveFilters(filters) && (
              <button
                onClick={() => setFilters(emptyFilters)}
                className="text-xs text-red-500 hover:text-red-700 cursor-pointer flex items-center gap-1 ml-2"
              >
                <X className="size-3" /> Clear All
              </button>
            )}
          </div>
        )}

        {/* ─── Active Filter Chips ─── */}
        {activeFilterChips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {activeFilterChips.map(chip => (
              <span
                key={`${chip.key}-${chip.value}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-[var(--color-violet-100)] text-[var(--color-violet-500)] border border-[var(--color-violet-200)]"
              >
                {chip.label}
                <button onClick={() => toggleFilter(chip.key, chip.value)} className="cursor-pointer hover:text-red-500">
                  <X className="size-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* ─── Main Content ─── */}
        {viewMode === 'calendar' ? (
          <WeeklyCalendarGrid
            weekStart={weekStart}
            activities={filteredActivities}
            onActivityClick={(id) => { setSelectedActivityId(id); setDrawerMode('view'); }}
          />
        ) : (
          <ActivityListView
            activities={filteredActivities}
            sortField={sortField}
            sortDir={sortDir}
            onSort={(field) => {
              if (sortField === field) {
                setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
              } else {
                setSortField(field);
                setSortDir('asc');
              }
            }}
            onActivityClick={(id) => { setSelectedActivityId(id); setDrawerMode('view'); }}
          />
        )}

        {/* ─── Projects in view ─── */}
        <ProjectsInRangePanel
          rangeStart={weekStart}
          rangeEnd={addDays(weekStart, 27)}
        />

        {/* ─── Color Legend ─── */}
        <PlatformLegend />
      </div>

      {/* ─── Activity Detail/Edit Drawer ─── */}
      {(selectedActivity || drawerMode === 'add') && (
        <ActivityDrawer
          activity={selectedActivity || null}
          mode={drawerMode}
          addCategory={addCategory}
          onClose={() => { setSelectedActivityId(null); setDrawerMode('view'); setPendingGroupIds(null); setPendingGroupEditIds(null); }}
          onSave={handleSaveActivity}
          onDelete={handleDeleteActivity}
          onEdit={() => setDrawerMode('edit')}
          onCancelEdit={() => setDrawerMode('view')}
          groupSiblingCount={selectedGroupSiblingCount}
          onEditAsGroup={selectedGroupSiblingCount >= 2 && selectedActivity?.category === 'task' ? () => {
            const ids = selectedGroupSiblings.map(a => a.activity_id);
            setSelectedActivityId(null);
            setDrawerMode('view');
            setGroupEditIds(ids);
            setGroupEditOriginActivityId(selectedActivityId);
          } : undefined}
          onApprove={handleApprove}
          onReject={handleReject}
          onRevisionRequest={(id) => { setRevisionActivityId(id); setRevisionComment(''); }}
          onBackToGroup={pendingGroupIds ? () => {
            setSelectedActivityId(null);
            setDrawerMode('view');
            setSelectedGroupIds(pendingGroupIds);
            setPendingGroupIds(null);
          } : pendingGroupEditIds ? () => {
            setSelectedActivityId(null);
            setDrawerMode('view');
            setGroupEditIds(pendingGroupEditIds);
            setPendingGroupEditIds(null);
          } : undefined}
          backToGroupLabel={pendingGroupEditIds ? 'Back to project edit' : undefined}
        />
      )}

      {/* ─── Move-to-Project Dialog ─── */}
      {moveTaskId && (() => {
        const task = orphanTasks.find(t => t.activity_id === moveTaskId);
        if (!task) return null;
        return (
          <MoveToProjectDialog
            taskName={task.name}
            onClose={() => setMoveTaskId(null)}
            onAttach={(planId) => handleMoveToProject(moveTaskId, planId)}
            onCreateNewProject={(name) => handleCreateProjectForTask(moveTaskId, name)}
          />
        );
      })()}

      {/* ─── Group Review Drawer ─── */}
      {selectedGroupIds && selectedGroupIds.length > 0 && (
        <GroupReviewDrawer
          activities={activities.filter(a => selectedGroupIds.includes(a.activity_id))}
          onClose={() => setSelectedGroupIds(null)}
          onBatchApprove={handleBatchApprove}
          onBatchReject={handleBatchReject}
          onBatchRevisionRequest={(ids) => {
            setSelectedGroupIds(null);
            setRevisionActivityId(ids[0]);
            setRevisionComment('');
            // Store all IDs for batch revision
            setBatchRevisionIds(ids);
          }}
          onViewActivity={(id) => {
            setPendingGroupIds(selectedGroupIds);
            setSelectedGroupIds(null);
            setSelectedActivityId(id);
            setDrawerMode('view');
          }}
        />
      )}

      {/* ─── Project Edit Drawer ─── */}
      {groupEditIds && groupEditIds.length > 0 && (
        <GroupEditDrawer
          activities={activities.filter(a => groupEditIds.includes(a.activity_id))}
          onClose={() => { setGroupEditIds(null); setGroupEditOriginActivityId(null); }}
          onSave={handleGroupSave}
          onBackToActivity={groupEditOriginActivityId ? () => {
            const id = groupEditOriginActivityId;
            setGroupEditIds(null);
            setGroupEditOriginActivityId(null);
            setSelectedActivityId(id);
            setDrawerMode('view');
          } : undefined}
          onEditActivity={(id) => {
            setPendingGroupEditIds(groupEditIds);
            setGroupEditIds(null);
            setSelectedActivityId(id);
            setDrawerMode('view');
          }}
          onDeleteActivity={(id) => {
            setActivities(prev => prev.filter(a => a.activity_id !== id));
            const remaining = groupEditIds!.filter(gid => gid !== id);
            if (remaining.length === 0) {
              setGroupEditIds(null);
              setGroupEditOriginActivityId(null);
            } else {
              setGroupEditIds(remaining);
            }
            if (groupEditOriginActivityId === id) {
              setGroupEditOriginActivityId(null);
            }
          }}
        />
      )}

      {/* ─── Batch Activity Wizard ─── */}
      {showBatchWizard && (
        <BatchActivityWizard
          onClose={() => setShowBatchWizard(false)}
          onCreate={handleBatchCreate}
        />
      )}

      {/* ─── Revision Comment Modal ─── */}
      {revisionActivityId && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40">
          <Card className="w-full max-w-md p-6 space-y-4 mx-4">
            <h3 className="text-sm">Request Revision</h3>
            <p className="text-xs text-muted-foreground">
              {batchRevisionIds && batchRevisionIds.length > 1
                ? `Provide a reason for requesting revisions on ${batchRevisionIds.length} activities.`
                : 'Provide a reason or comment for requesting revisions on this activity.'}
            </p>
            <textarea
              className="w-full h-24 p-3 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] resize-none focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]"
              placeholder="Describe what needs to be revised..."
              value={revisionComment}
              onChange={e => setRevisionComment(e.target.value)}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => { setRevisionActivityId(null); setRevisionComment(''); setBatchRevisionIds(null); }}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleRevisionRequest} disabled={!revisionComment.trim()}>
                Submit
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

// ��══════════════════════════════════════════════════════════
// ─── APPROVAL QUEUE ───
// ═══════════════════════════════════════════════════════════

function ApprovalQueue({
  items,
  collapsed,
  onToggleCollapse,
  onViewActivity,
  onViewGroup,
}: {
  items: CalendarActivity[];
  collapsed: boolean;
  onToggleCollapse: () => void;
  onViewActivity: (id: string) => void;
  onViewGroup: (ids: string[]) => void;
}) {
  const { groups, singles } = useMemo(() => buildApprovalGroups(items), [items]);

  if (items.length === 0) {
    return (
      <div className="flex items-center gap-2 px-4 py-2.5 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] border border-[var(--color-border-default)]">
        <CheckCircle2 className="size-4 text-green-500" />
        <span className="text-xs text-muted-foreground">No items awaiting approval.</span>
      </div>
    );
  }

  const totalItems = items.length;
  const groupCount = groups.length;

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] overflow-hidden">
      <button
        onClick={onToggleCollapse}
        className="w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[var(--color-bg-secondary)] transition-colors"
      >
        <div className="flex items-center gap-2">
          <Clock className="size-4 text-amber-500" />
          <span className="text-sm">Approval Queue</span>
          <span className="bg-amber-100 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5 text-xs">
            {totalItems}
          </span>
          {groupCount > 0 && (
            <span className="text-[0.625rem] text-muted-foreground">
              · {groupCount} group{groupCount > 1 ? 's' : ''}, {singles.length} individual
            </span>
          )}
        </div>
        {collapsed ? <ChevronDown className="size-4 text-muted-foreground" /> : <ChevronUp className="size-4 text-muted-foreground" />}
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 overflow-x-auto">
          <div className="flex gap-3" style={{ minWidth: 'min-content' }}>
            {groups.map(group => (
              <ApprovalGroupCard
                key={group.key}
                group={group}
                onView={() => onViewGroup(group.activities.map(a => a.activity_id))}
              />
            ))}
            {singles.map(item => (
              <ApprovalCard
                key={item.activity_id}
                activity={item}
                onView={() => onViewActivity(item.activity_id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ApprovalGroupCard({
  group,
  onView,
}: {
  group: ApprovalGroup;
  onView: () => void;
}) {
  const pc = getPlatformColor(group.platform);

  return (
    <div className="min-w-[17.5rem] max-w-[20rem] p-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50/40 flex flex-col gap-2.5 shrink-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <Layers className="size-3.5 text-amber-600 shrink-0" />
            <span className="text-xs text-amber-700 bg-amber-100 border border-amber-200 rounded-full px-2 py-0.5">
              {group.activities.length} activities
            </span>
          </div>
          <p className="text-sm truncate mt-1.5">{getCampaignName(group.campaignId)}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: pc.color }} />
            <span className="text-xs text-muted-foreground truncate">
              {group.platform || 'No platform'}{group.channel ? ` · ${group.channel}` : ''}
            </span>
          </div>
        </div>
      </div>

      <div className="text-xs text-muted-foreground space-y-1">
        <div className="flex items-center gap-1.5">
          <CalendarIcon className="size-3" />
          <span>{formatMonthYear(group.month)} · {formatDate(group.dateRange.start)} – {formatDate(group.dateRange.end)}</span>
        </div>
        {group.totalCost > 0 && (
          <div className="flex items-center gap-1.5">
            <DollarSign className="size-3" />
            <span>Total: ${group.totalCost.toLocaleString()}</span>
          </div>
        )}
        {group.owners.length > 0 && (
          <div className="flex items-center gap-1.5">
            <User className="size-3" />
            <span>{group.owners.map(o => getUserName(o)).join(', ')}</span>
          </div>
        )}
      </div>

      <div className="mt-auto pt-1">
        <button
          onClick={onView}
          className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs rounded-[var(--radius-sm)] bg-amber-100 text-amber-800 border border-amber-200 hover:bg-amber-200 cursor-pointer transition-colors"
        >
          <Eye className="size-3" /> Review Group
        </button>
      </div>
    </div>
  );
}

function ApprovalCard({
  activity,
  onView,
}: {
  activity: CalendarActivity;
  onView: () => void;
}) {
  const pc = getPlatformColor(activity.platform);

  return (
    <div className="min-w-[16.25rem] max-w-[18.75rem] p-4 rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] flex flex-col gap-2.5 shrink-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm truncate">{activity.name}</p>
          <p className="text-xs text-muted-foreground truncate mt-0.5">{getCampaignName(activity.campaign_id)}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: pc.color }} />
            <span className="text-xs text-muted-foreground truncate">
              {activity.platform || 'No platform'}{activity.channel ? ` · ${activity.channel}` : ''}
            </span>
          </div>
        </div>
      </div>

      <div className="text-xs text-muted-foreground space-y-1">
        {activity.owner && (
          <div className="flex items-center gap-1.5">
            <User className="size-3" />
            <span>{getUserName(activity.owner)}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <CalendarIcon className="size-3" />
          <span>{formatDate(activity.launch_date)}{activity.launch_time_utc ? ` at ${activity.launch_time_utc} UTC` : ''}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="size-3" />
          <span>Submitted {formatDate(activity.last_updated_at)}</span>
        </div>
      </div>

      <div className="mt-auto pt-1">
        <button
          onClick={onView}
          className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--color-bg-secondary)] text-foreground border border-[var(--color-border-default)] hover:bg-[var(--color-bg-tertiary)] cursor-pointer transition-colors"
        >
          <Eye className="size-3" /> View
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ─── GROUP REVIEW DRAWER ───
// ═══════════════════════════════════════════════════════════

function GroupReviewDrawer({
  activities,
  onClose,
  onBatchApprove,
  onBatchReject,
  onBatchRevisionRequest,
  onViewActivity,
}: {
  activities: CalendarActivity[];
  onClose: () => void;
  onBatchApprove: (ids: string[]) => void;
  onBatchReject: (ids: string[]) => void;
  onBatchRevisionRequest: (ids: string[]) => void;
  onViewActivity: (id: string) => void;
}) {
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());

  if (activities.length === 0) return null;

  const sorted = [...activities].sort((a, b) => a.launch_date.getTime() - b.launch_date.getTime());
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const pc = getPlatformColor(first.platform);
  const campaignName = getCampaignName(first.campaign_id);
  const totalCost = sorted.reduce((sum, a) => sum + (a.cost || 0), 0);
  const owners = [...new Set(sorted.map(a => a.owner).filter(Boolean) as string[])];
  const includedIds = sorted.filter(a => !excludedIds.has(a.activity_id)).map(a => a.activity_id);
  const allSelected = excludedIds.size === 0;
  const noneSelected = includedIds.length === 0;
  const includedCost = sorted.filter(a => !excludedIds.has(a.activity_id)).reduce((sum, a) => sum + (a.cost || 0), 0);

  const toggleExclude = (id: string) => {
    setExcludedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) {
      setExcludedIds(new Set(sorted.map(a => a.activity_id)));
    } else {
      setExcludedIds(new Set());
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-[50] bg-black/30" onClick={onClose} />

      <div className="fixed top-0 right-0 bottom-0 z-[51] w-full max-w-lg bg-[var(--color-bg-elevated)] border-l border-[var(--color-border-default)] shadow-xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-amber-600" />
            <h2 className="text-sm">Group Review</h2>
            <span className="bg-amber-100 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5 text-xs">
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
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Total Cost</label>
                <p className="text-sm mt-0.5">${totalCost.toLocaleString()}</p>
              </div>
              <div>
                <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Owner{owners.length > 1 ? 's' : ''}</label>
                <p className="text-sm mt-0.5">{owners.map(o => getUserName(o)).join(', ') || '—'}</p>
              </div>
            </div>
          </div>

          {/* Cost Breakdown Chart */}
          {totalCost > 0 && (
            <div className="p-4 border-b border-[var(--color-border-default)]">
              <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Daily Cost Breakdown</label>
              <div className="mt-2 h-[8.75rem]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={sorted.map(a => ({
                      date: a.launch_date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                      cost: a.cost || 0,
                      id: a.activity_id,
                      excluded: excludedIds.has(a.activity_id),
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
                      {sorted.map((a) => (
                        <Cell
                          key={a.activity_id}
                          fill={excludedIds.has(a.activity_id) ? '#CBD5E1' : pc.color}
                          opacity={excludedIds.has(a.activity_id) ? 0.4 : 0.85}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center justify-between mt-1 text-[0.625rem] text-muted-foreground">
                <span>Avg: ${sorted.length > 0 ? Math.round(totalCost / sorted.length).toLocaleString() : 0}/day</span>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <span className="size-2 rounded-sm" style={{ backgroundColor: pc.color, opacity: 0.85 }} /> Selected
                  </span>
                  {excludedIds.size > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="size-2 rounded-sm bg-slate-300 opacity-40" /> Excluded
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Activity List */}
          <div className="p-4 space-y-1">
            <div className="flex items-center justify-between mb-2">
              <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Individual Activities</label>
              <button
                onClick={toggleAll}
                className="text-[0.625rem] text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] cursor-pointer"
              >
                {allSelected ? 'Deselect All' : 'Select All'}
              </button>
            </div>

            {sorted.map(activity => {
              const included = !excludedIds.has(activity.activity_id);
              return (
                <div
                  key={activity.activity_id}
                  className={cn(
                    "flex items-center gap-3 p-2.5 rounded-[var(--radius-sm)] border transition-colors",
                    included
                      ? "border-[var(--color-border-default)] bg-[var(--color-bg-primary)]"
                      : "border-dashed border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] opacity-50"
                  )}
                >
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleExclude(activity.activity_id)}
                    className={cn(
                      "size-4 rounded-[3px] border flex items-center justify-center shrink-0 cursor-pointer transition-colors",
                      included
                        ? "bg-[var(--color-violet-500)] border-[var(--color-violet-500)]"
                        : "border-[var(--color-border-strong)] bg-[var(--color-bg-primary)]"
                    )}
                  >
                    {included && <Check className="size-3 text-white" />}
                  </button>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs truncate">{activity.name}</p>
                      {activity.cost != null && (
                        <span className="text-xs text-muted-foreground shrink-0">${activity.cost.toLocaleString()}</span>
                      )}
                    </div>
                    <p className="text-[0.625rem] text-muted-foreground mt-0.5">
                      {formatDate(activity.launch_date)}{activity.launch_time_utc ? ` at ${activity.launch_time_utc} UTC` : ''}
                    </p>
                  </div>

                  {/* View individual */}
                  <button
                    onClick={() => onViewActivity(activity.activity_id)}
                    className="text-muted-foreground hover:text-foreground cursor-pointer shrink-0"
                    title="View details"
                  >
                    <Eye className="size-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer with batch actions */}
        <div className="p-4 border-t border-[var(--color-border-default)] space-y-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{includedIds.length} of {sorted.length} selected</span>
            {includedIds.length > 0 && (
              <span>Selected cost: ${includedCost.toLocaleString()}</span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onBatchApprove(includedIds)}
              disabled={noneSelected}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs rounded-[var(--radius-sm)] bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Check className="size-3.5" /> Approve {includedIds.length > 1 ? `All (${includedIds.length})` : ''}
            </button>
            <button
              onClick={() => onBatchReject(includedIds)}
              disabled={noneSelected}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs rounded-[var(--radius-sm)] bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <XCircle className="size-3.5" /> Reject {includedIds.length > 1 ? `All` : ''}
            </button>
            <button
              onClick={() => onBatchRevisionRequest(includedIds)}
              disabled={noneSelected}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs rounded-[var(--radius-sm)] bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100 cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <RotateCcw className="size-3.5" /> Revise
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════
// ─── WEEKLY CALENDAR GRID ───
// ═══════════════════════════════════════════════════════════

function WeeklyCalendarGrid({
  weekStart,
  activities,
  onActivityClick,
}: {
  weekStart: Date;
  activities: CalendarActivity[];
  onActivityClick: (id: string) => void;
}) {
  const today = new Date(2026, 2, 24);
  const MAX_PILLS = 5;

  // 4 weeks of data
  const weeks: Date[][] = [];
  for (let w = 0; w < 4; w++) {
    const row: Date[] = [];
    for (let d = 0; d < 7; d++) {
      row.push(addDays(weekStart, w * 7 + d));
    }
    weeks.push(row);
  }

  const windowStart = weekStart;
  const windowEnd = addDays(weekStart, 27);

  // Filter activities within the visible window, expanding recurring schedules.
  const visibleActivities = useMemo<CalendarActivity[]>(() => {
    const out: CalendarActivity[] = [];
    for (const a of activities) {
      if (a.schedule?.enabled) {
        let cursor = new Date(windowStart.getTime() - 1);
        const cap = 64;
        for (let i = 0; i < cap; i++) {
          const next = computeNextRun(a.schedule!, cursor);
          if (!next || next > windowEnd) break;
          out.push({
            ...a,
            activity_id: `${a.activity_id}@${next.toISOString()}`,
            launch_date: next,
            launch_time_utc: a.schedule!.time_utc,
          });
          cursor = next;
        }
      } else if (!a.unscheduled && a.launch_date >= windowStart && a.launch_date <= windowEnd) {
        out.push(a);
      }
    }
    return out;
  }, [activities, windowStart, windowEnd]);

  // Build a map: dateKey → activities for that day
  const dayMap = useMemo(() => {
    const map = new Map<string, CalendarActivity[]>();
    for (const a of visibleActivities) {
      // Multi-day holidays span from launch_date to end_date
      if (a.category === 'holiday' && a.end_date) {
        const start = new Date(a.launch_date);
        const end = new Date(a.end_date);
        for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
          const key = formatDateISO(new Date(d));
          const arr = map.get(key) || [];
          arr.push(a);
          map.set(key, arr);
        }
      } else {
        const key = formatDateISO(a.launch_date);
        const arr = map.get(key) || [];
        arr.push(a);
        map.set(key, arr);
      }
    }
    // Sort each day's activities by launch_time_utc (nulls last)
    for (const [, arr] of map) {
      arr.sort((a, b) => {
        if (a.launch_time_utc && b.launch_time_utc) return a.launch_time_utc.localeCompare(b.launch_time_utc);
        if (a.launch_time_utc) return -1;
        if (b.launch_time_utc) return 1;
        return 0;
      });
    }
    return map;
  }, [visibleActivities]);

  if (activities.length === 0) {
    return (
      <div className="text-center py-16 border-2 border-dashed border-[var(--color-border-default)] rounded-[var(--radius-md)]">
        <CalendarIcon className="size-8 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm text-muted-foreground mb-1">No activities match your filters.</p>
        <p className="text-xs text-muted-foreground">Try adjusting your filter criteria.</p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--color-border-default)] rounded-[var(--radius-md)] overflow-hidden bg-[var(--color-bg-elevated)]">
      {/* Header row */}
      <div className="grid grid-cols-7 border-b border-[var(--color-border-default)]">
        {DAY_NAMES.map((d) => (
          <div key={d} className="p-2 text-center text-xs text-muted-foreground border-l border-[var(--color-border-default)] first:border-l-0">
            {d}
          </div>
        ))}
      </div>

      {/* Week rows */}
      {weeks.map((weekDays, wi) => (
        <div
          key={wi}
          className="grid grid-cols-7 border-b border-[var(--color-border-default)] last:border-b-0"
        >
          {/* Day cells with pills */}
          {weekDays.map((day, di) => {
            const isToday = isSameDay(day, today);
            const dateKey = formatDateISO(day);
            const dayActivities = dayMap.get(dateKey) || [];
            const displayActivities = dayActivities.slice(0, MAX_PILLS);
            const overflowCount = dayActivities.length - MAX_PILLS;

            return (
              <div
                key={di}
                className={cn(
                  "border-l border-[var(--color-border-default)] min-h-[9.25rem] p-1 flex flex-col",
                  isToday && "bg-[var(--color-violet-100)]/40"
                )}
              >
                {/* Date number */}
                <span className={cn(
                  "text-[0.6875rem] leading-none mb-1 shrink-0",
                  isToday
                    ? "bg-[var(--color-violet-500)] text-white rounded-full h-5 px-1.5 flex items-center justify-center"
                    : "text-muted-foreground"
                )}>
                  {day.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()} {day.getDate()}
                </span>

                {/* Activity pills */}
                <div className="flex flex-col gap-0.5 min-w-0 overflow-hidden">
                  {displayActivities.map(a => {
                    if (a.category === 'holiday') {
                      return (
                        <button
                          key={a.activity_id}
                          className={cn(
                            "w-full text-left truncate px-1.5 py-[3px] text-[0.625rem] rounded-[3px] cursor-pointer hover:opacity-80 transition-opacity leading-tight bg-amber-100 text-amber-800 border border-amber-300 flex items-center gap-0.5",
                            a.end_date && "border-dashed border-amber-400"
                          )}
                          onClick={() => onActivityClick(a.activity_id)}
                          title={`${a.name}${a.end_date ? ` · ${formatDate(a.launch_date)} – ${formatDate(a.end_date)}` : ''}`}
                        >
                          <Flag className="size-2.5 shrink-0" />
                          {a.name}
                        </button>
                      );
                    }
                    if (a.category === 'promotion') {
                      return (
                        <button
                          key={a.activity_id}
                          className="w-full text-left truncate px-1.5 py-[3px] text-[0.625rem] rounded-[3px] cursor-pointer hover:opacity-80 transition-opacity leading-tight bg-gradient-to-r from-pink-100 to-rose-100 text-rose-800 border border-rose-300 flex items-center gap-0.5"
                          onClick={() => onActivityClick(a.activity_id)}
                          title={`${a.name}${a.end_date ? ` · ends ${a.end_date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}` : ''}`}
                        >
                          <ShoppingBag className="size-2.5 shrink-0" />
                          {a.name}
                        </button>
                      );
                    }
                    const pc = getPlatformColor(a.platform);
                    return (
                      <button
                        key={a.activity_id}
                        className="w-full text-left truncate px-1.5 py-[3px] text-[0.625rem] rounded-[3px] cursor-pointer hover:opacity-80 transition-opacity leading-tight"
                        style={{ backgroundColor: pc.color, color: pc.textColor }}
                        onClick={() => onActivityClick(a.activity_id)}
                        title={`${a.name}${a.launch_time_utc ? ` · ${a.launch_time_utc} UTC` : ''}`}
                      >
                        {a.launch_time_utc && (
                          <span className="opacity-75 mr-0.5">{a.launch_time_utc}</span>
                        )}
                        {a.name}
                      </button>
                    );
                  })}
                  {overflowCount > 0 && (
                    <span className="text-[0.625rem] text-muted-foreground px-1 cursor-default">
                      +{overflowCount} more
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ─── LIST VIEW ───
// ═══════════════════════════════════════════════════════════

function ActivityListView({
  activities,
  sortField,
  sortDir,
  onSort,
  onActivityClick,
}: {
  activities: CalendarActivity[];
  sortField: string;
  sortDir: 'asc' | 'desc';
  onSort: (field: string) => void;
  onActivityClick: (id: string) => void;
}) {
  const sorted = useMemo(() => {
    const arr = [...activities];
    arr.sort((a, b) => {
      let va: any, vb: any;
      switch (sortField) {
        case 'launch_date': va = a.launch_date.getTime(); vb = b.launch_date.getTime(); break;
        case 'launch_time': va = a.launch_time_utc || 'zzz'; vb = b.launch_time_utc || 'zzz'; break;
        case 'campaign': va = getCampaignName(a.campaign_id); vb = getCampaignName(b.campaign_id); break;
        case 'platform': va = a.platform || ''; vb = b.platform || ''; break;
        case 'status': va = a.status; vb = b.status; break;
        case 'cost': va = a.cost || 0; vb = b.cost || 0; break;
        case 'owner': va = getUserName(a.owner) || ''; vb = getUserName(b.owner) || ''; break;
        default: va = a.launch_date.getTime(); vb = b.launch_date.getTime();
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return arr;
  }, [activities, sortField, sortDir]);

  if (activities.length === 0) {
    return (
      <div className="text-center py-16 border-2 border-dashed border-[var(--color-border-default)] rounded-[var(--radius-md)]">
        <List className="size-8 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm text-muted-foreground mb-1">No activities match your filters.</p>
        <p className="text-xs text-muted-foreground">Try adjusting your filter criteria.</p>
      </div>
    );
  }

  const SortHeader = ({ field, children }: { field: string; children: React.ReactNode }) => (
    <button
      onClick={() => onSort(field)}
      className="flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors"
    >
      {children}
      {sortField === field ? (
        sortDir === 'asc' ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />
      ) : (
        <ArrowUpDown className="size-3 opacity-40" />
      )}
    </button>
  );

  return (
    <div className="border border-[var(--color-border-default)] rounded-[var(--radius-md)] overflow-hidden bg-[var(--color-bg-elevated)]">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
              <th className="text-left p-3 text-muted-foreground"><SortHeader field="launch_date">Launch Date</SortHeader></th>
              <th className="text-left p-3 text-muted-foreground">Name</th>
              <th className="text-left p-3 text-muted-foreground">Type</th>
              <th className="text-left p-3 text-muted-foreground"><SortHeader field="platform">Platform</SortHeader></th>
              <th className="text-left p-3 text-muted-foreground">Channel</th>
              <th className="text-left p-3 text-muted-foreground"><SortHeader field="launch_time">Launch Time</SortHeader></th>
              <th className="text-left p-3 text-muted-foreground"><SortHeader field="status">Status</SortHeader></th>
              <th className="text-right p-3 text-muted-foreground"><SortHeader field="cost">Cost</SortHeader></th>
              <th className="text-left p-3 text-muted-foreground">Tags</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(a => {
              const pc = getPlatformColor(a.platform);
              return (
                <tr
                  key={a.activity_id}
                  className="border-b border-[var(--color-border-subtle)] hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
                  onClick={() => onActivityClick(a.activity_id)}
                >
                  <td className="p-3 whitespace-nowrap">{formatDate(a.launch_date)}{a.category === 'holiday' && a.end_date ? ` – ${formatDate(a.end_date)}` : ''}</td>
                  <td className="p-3 max-w-[12.5rem] truncate">{a.name}</td>
                  <td className="p-3 whitespace-nowrap">
                    <span className={cn(
                      "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[0.625rem]",
                      a.category === 'promotion' && "bg-rose-100 text-rose-700",
                      a.category === 'holiday' && "bg-amber-100 text-amber-700",
                      a.category === 'task' && "bg-[var(--color-violet-100)] text-[var(--color-violet-600)]",
                    )}>
                      {a.category === 'promotion' && <ShoppingBag className="size-2.5" />}
                      {a.category === 'holiday' && <Flag className="size-2.5" />}
                      {a.category === 'task' && <Megaphone className="size-2.5" />}
                      {CATEGORY_LABELS[a.category]}
                    </span>
                  </td>
                  <td className="p-3 whitespace-nowrap">
                    <span className="flex items-center gap-1.5">
                      <span className="size-2.5 rounded-full shrink-0" style={{ backgroundColor: pc.color }} />
                      {a.platform || <span className="text-muted-foreground">—</span>}
                    </span>
                  </td>
                  <td className="p-3 text-muted-foreground whitespace-nowrap">{a.channel || '—'}</td>
                  <td className="p-3 whitespace-nowrap">{a.launch_time_utc ? <span className="flex items-center gap-1"><Clock className="size-3 text-muted-foreground" />{a.launch_time_utc} UTC</span> : <span className="text-muted-foreground">—</span>}</td>
                  <td className="p-3"><StatusBadge status={a.status} /></td>
                  <td className="p-3 text-right whitespace-nowrap">{a.cost != null ? `$${a.cost.toLocaleString()}` : '—'}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1 max-w-[9.375rem]">
                      {a.tags.slice(0, 2).map(t => (
                        <span key={t} className="px-1.5 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground text-[0.625rem]">{t}</span>
                      ))}
                      {a.tags.length > 2 && <span className="text-[0.625rem] text-muted-foreground">+{a.tags.length - 2}</span>}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ─── PLATFORM LEGEND ───
// ═══════════════════════════════════════════════════════════

function PlatformLegend() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      >
        <Info className="size-3.5" />
        Platform Color Legend
        {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
      </button>
      {expanded && (
        <div className="mt-2 p-3 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] border border-[var(--color-border-default)]">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {platformColors.map(pc => (
              <div key={pc.platform} className="flex items-center gap-2 text-xs">
                <span className="size-3 rounded-sm shrink-0" style={{ backgroundColor: pc.color }} />
                <span>{pc.platform}</span>
                <span className="text-muted-foreground">({pc.channel})</span>
              </div>
            ))}
            <div className="flex items-center gap-2 text-xs">
              <span className="size-3 rounded-sm shrink-0" style={{ backgroundColor: neutralPlatformColor.color }} />
              <span>No Platform</span>
            </div>
          </div>
          <div className="border-t border-[var(--color-border-default)] mt-2 pt-2">
            <p className="text-[0.625rem] text-muted-foreground uppercase tracking-wider mb-1.5">Activity Types</p>
            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-1.5 text-xs">
                <span className="size-3 rounded-sm shrink-0 bg-gradient-to-r from-pink-100 to-rose-100 border border-rose-300" />
                <ShoppingBag className="size-3 text-rose-700" />
                <span>Promotion</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs">
                <span className="size-3 rounded-sm shrink-0 bg-amber-100 border border-amber-300" />
                <Flag className="size-3 text-amber-700" />
                <span>Holiday</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ─── ACTIVITY DRAWER (Detail / Edit / Add) ───
// ═══════════════════════════════════════════════════════════

function ActivityDrawer({
  activity,
  mode,
  addCategory,
  onClose,
  onSave,
  onDelete,
  onEdit,
  onCancelEdit,
  onApprove,
  onReject,
  onRevisionRequest,
  onBackToGroup,
  backToGroupLabel,
  groupSiblingCount,
  onEditAsGroup,
}: {
  activity: CalendarActivity | null;
  mode: 'view' | 'edit' | 'add';
  addCategory?: ActivityCategory;
  onClose: () => void;
  onSave: (a: CalendarActivity) => void;
  onDelete: (id: string) => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onRevisionRequest: (id: string) => void;
  onBackToGroup?: () => void;
  backToGroupLabel?: string;
  groupSiblingCount?: number;
  onEditAsGroup?: () => void;
}) {
  const isAdd = mode === 'add';
  const isEdit = mode === 'edit';
  const isView = mode === 'view';

  const effectiveCategory: ActivityCategory = activity?.category || addCategory || 'task';

  const defaultActivity: CalendarActivity = {
    activity_id: `act-new-${Date.now()}`,
    name: '',
    objective: effectiveCategory === 'holiday' ? 'Problem Awareness' : 'Problem Awareness',
    expected_direction: effectiveCategory === 'holiday' ? 'Decrease' : 'Increase',
    campaign_id: '',
    channel: null,
    platform: null,
    cost: null,
    launch_date: new Date(2026, 2, 24),
    launch_time_utc: null,
    category: effectiveCategory,
    task_type: null,
    tags: [],
    owner: null,
    status: effectiveCategory === 'task' ? 'Draft' : 'Approved',
    created_date: new Date(),
    created_by: 'sarah.chen@example.com',
    last_updated_at: new Date(),
    last_updated_by: 'sarah.chen@example.com',
    // Promotion defaults
    ...(effectiveCategory === 'promotion' ? { product_service: null, promotion_type: null, discount_details: null, end_date: null, promo_url: null, region: null } : {}),
    // Holiday defaults
    ...(effectiveCategory === 'holiday' ? { holiday_type: null, recurring: false, region: null } : {}),
  };

  const [form, setForm] = useState<CalendarActivity>(activity || defaultActivity);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [tagInput, setTagInput] = useState('');

  // Reset form when activity changes
  const activityId = activity?.activity_id;
  const [prevId, setPrevId] = useState(activityId);
  if (activityId !== prevId) {
    setPrevId(activityId);
    if (activity) setForm(activity);
  }

  const handleObjectiveChange = (objective: FunnelObjective) => {
    setForm(f => ({ ...f, objective, campaign_id: '' }));
  };

  const handleCampaignChange = (campaignId: string) => {
    setForm(f => ({ ...f, campaign_id: campaignId }));
  };

  const handleCreateCampaign = (name: string) => {
    const campaign = addCampaign(name, form.objective);
    setForm(f => ({ ...f, campaign_id: campaign.campaign_id }));
  };

  const handleTagAdd = () => {
    const tag = tagInput.trim();
    if (tag && !form.tags.includes(tag)) {
      setForm(f => ({ ...f, tags: [...f.tags, tag] }));
    }
    setTagInput('');
  };

  const handleSubmit = () => {
    const now = new Date();
    const updated: CalendarActivity = {
      ...form,
      campaign_id: form.campaign_id || getGenericCampaignId(form.objective),
      last_updated_at: now,
      last_updated_by: 'sarah.chen@example.com',
      ...(isAdd ? { created_date: now, created_by: 'sarah.chen@example.com' } : {}),
    };
    onSave(updated);
  };

  const pc = getPlatformColor(form.platform);

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-[50] bg-black/30" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed top-0 right-0 bottom-0 z-[51] w-full max-w-lg bg-[var(--color-bg-elevated)] border-l border-[var(--color-border-default)] shadow-xl flex flex-col overflow-hidden">
        {/* Back to project link */}
        {onBackToGroup && isView && (
          <button
            onClick={onBackToGroup}
            className="flex items-center gap-1.5 px-4 py-2 text-xs text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] hover:bg-[var(--color-violet-100)]/50 cursor-pointer transition-colors border-b border-[var(--color-border-default)]"
          >
            <ArrowLeft className="size-3.5" />
            {backToGroupLabel || 'Back to project review'}
          </button>
        )}

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-2 min-w-0 shrink-0">
            <h2 className="text-sm shrink-0">
              {isAdd
                ? `Add ${CATEGORY_LABELS[effectiveCategory]}`
                : isEdit
                ? `Edit ${CATEGORY_LABELS[effectiveCategory]}`
                : `${CATEGORY_LABELS[effectiveCategory]} Details`}
            </h2>
            {isView && activity && groupSiblingCount && groupSiblingCount >= 2 && (
              <span
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.625rem] bg-[var(--color-violet-100)] text-[var(--color-violet-600)] border border-[var(--color-violet-200)] shrink-0 whitespace-nowrap"
              >
                <Layers className="size-3" />
                Part of {groupSiblingCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isView && activity && (
              <>
                {onEditAsGroup && groupSiblingCount && groupSiblingCount >= 2 && (
                  <Button variant="outline" size="sm" onClick={onEditAsGroup} className="text-[var(--color-violet-500)]">
                    <Layers className="size-3.5 mr-1" /> Edit Project
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={onEdit}>
                  <Edit3 className="size-3.5 mr-1" /> Edit
                </Button>
                <Button variant="outline" size="sm" className="text-red-500 hover:text-red-700" onClick={() => setShowDeleteConfirm(true)}>
                  <Trash2 className="size-3.5" />
                </Button>
              </>
            )}
            <button onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground">
              <X className="size-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {isView && activity ? (
            <ActivityDetailView activity={activity} />
          ) : effectiveCategory === 'promotion' ? (
            <PromotionForm
              form={form}
              onChange={setForm}
              tagInput={tagInput}
              onTagInputChange={setTagInput}
              onTagAdd={handleTagAdd}
            />
          ) : effectiveCategory === 'holiday' ? (
            <HolidayForm
              form={form}
              onChange={setForm}
            />
          ) : (
            <ActivityForm
              form={form}
              onChange={setForm}
              onObjectiveChange={handleObjectiveChange}
              onCampaignChange={handleCampaignChange}
              onCreateCampaign={handleCreateCampaign}
              tagInput={tagInput}
              onTagInputChange={setTagInput}
              onTagAdd={handleTagAdd}
            />
          )}
        </div>

        {/* Footer */}
        {(isEdit || isAdd) && (
          <div className="p-4 border-t border-[var(--color-border-default)] flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={isAdd ? onClose : onCancelEdit}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSubmit}>
              {isAdd ? `Create ${CATEGORY_LABELS[effectiveCategory]}` : 'Save Changes'}
            </Button>
          </div>
        )}

        {/* Approval actions footer */}
        {isView && activity && activity.status === 'Awaiting Approval' && (
          <div className="p-4 border-t border-[var(--color-border-default)] space-y-2">
            <p className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Approval Actions</p>
            <div className="flex gap-2">
              <button
                onClick={() => { onApprove(activity.activity_id); onClose(); }}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs rounded-[var(--radius-sm)] bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 cursor-pointer transition-colors"
              >
                <Check className="size-3.5" /> Approve
              </button>
              <button
                onClick={() => { onReject(activity.activity_id); onClose(); }}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs rounded-[var(--radius-sm)] bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 cursor-pointer transition-colors"
              >
                <XCircle className="size-3.5" /> Reject
              </button>
              <button
                onClick={() => { onRevisionRequest(activity.activity_id); onClose(); }}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs rounded-[var(--radius-sm)] bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100 cursor-pointer transition-colors"
              >
                <RotateCcw className="size-3.5" /> Revise
              </button>
            </div>
          </div>
        )}

        {/* Delete confirmation */}
        {showDeleteConfirm && activity && (
          <div className="absolute inset-0 z-10 bg-black/30 flex items-center justify-center p-6">
            <Card className="p-5 space-y-3 w-full max-w-sm">
              <h3 className="text-sm">Delete Activity?</h3>
              <p className="text-xs text-muted-foreground">
                Are you sure you want to delete this activity? This action cannot be undone.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
                <Button size="sm" variant="destructive" onClick={() => onDelete(activity.activity_id)}>Delete</Button>
              </div>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}

// ─── Detail View ───

function ActivityDetailView({ activity }: { activity: CalendarActivity }) {
  const pc = getPlatformColor(activity.platform);
  const labelClass = "text-[0.625rem] text-muted-foreground uppercase tracking-wider";

  return (
    <div className="space-y-5">
      {/* Type badge */}
      <span className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.625rem]",
        activity.category === 'promotion' && "bg-rose-100 text-rose-700 border border-rose-200",
        activity.category === 'holiday' && "bg-amber-100 text-amber-700 border border-amber-200",
        activity.category === 'task' && "bg-[var(--color-violet-100)] text-[var(--color-violet-600)] border border-[var(--color-violet-200)]",
      )}>
        {activity.category === 'promotion' && <ShoppingBag className="size-3" />}
        {activity.category === 'holiday' && <Flag className="size-3" />}
        {activity.category === 'task' && <Megaphone className="size-3" />}
        {CATEGORY_LABELS[activity.category]}
      </span>

      {/* Name */}
      <div>
        <label className={labelClass}>Name</label>
        <p className="text-sm mt-0.5">{activity.name}</p>
      </div>

      {/* ── Promotion-specific ── */}
      {activity.category === 'promotion' && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Product / Service</label>
              <p className="text-sm mt-0.5">{activity.product_service || '—'}</p>
            </div>
            <div>
              <label className={labelClass}>Promotion Type</label>
              <p className="text-sm mt-0.5">{activity.promotion_type || '—'}</p>
            </div>
          </div>
          <div>
            <label className={labelClass}>Discount Details</label>
            <p className="text-sm mt-0.5">{activity.discount_details || '—'}</p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Start Date</label>
              <p className="text-sm mt-0.5">{formatDateFull(activity.launch_date)}</p>
            </div>
            <div>
              <label className={labelClass}>End Date</label>
              <p className="text-sm mt-0.5">{activity.end_date ? formatDateFull(activity.end_date) : '—'}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Region</label>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Globe className="size-3.5 text-muted-foreground" />
                <span className="text-sm">{activity.region || '—'}</span>
              </div>
            </div>
            <div>
              <label className={labelClass}>Owner</label>
              <p className="text-sm mt-0.5">{activity.owner ? getUserName(activity.owner) : '—'}</p>
            </div>
          </div>
          {activity.promo_url && (
            <div>
              <label className={labelClass}>URL</label>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Link className="size-3.5 text-[var(--color-violet-500)]" />
                <span className="text-sm text-[var(--color-violet-500)] truncate">{activity.promo_url}</span>
              </div>
            </div>
          )}
          {activity.tags.length > 0 && (
            <div>
              <label className={labelClass}>Tags</label>
              <div className="flex flex-wrap gap-1 mt-1">
                {activity.tags.map(t => (
                  <span key={t} className="px-2 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-xs text-muted-foreground border border-[var(--color-border-default)]">{t}</span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Holiday-specific ── */}
      {activity.category === 'holiday' && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>{activity.end_date ? 'Start Date' : 'Date'}</label>
              <p className="text-sm mt-0.5">{formatDateFull(activity.launch_date)}</p>
            </div>
            {activity.end_date ? (
              <div>
                <label className={labelClass}>End Date</label>
                <p className="text-sm mt-0.5">{formatDateFull(activity.end_date)}</p>
              </div>
            ) : (
              <div>
                <label className={labelClass}>Holiday Type</label>
                <p className="text-sm mt-0.5">{activity.holiday_type || '—'}</p>
              </div>
            )}
          </div>
          {activity.end_date && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Holiday Type</label>
                <p className="text-sm mt-0.5">{activity.holiday_type || '—'}</p>
              </div>
              <div>
                <label className={labelClass}>Duration</label>
                <p className="text-sm mt-0.5">{Math.round((activity.end_date.getTime() - activity.launch_date.getTime()) / (1000 * 60 * 60 * 24)) + 1} days</p>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Region</label>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Globe className="size-3.5 text-muted-foreground" />
                <span className="text-sm">{activity.region || '—'}</span>
              </div>
            </div>
            <div>
              <label className={labelClass}>Recurring</label>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Repeat className="size-3.5 text-muted-foreground" />
                <span className="text-sm">{activity.recurring ? 'Yes (annual)' : 'No'}</span>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Task-specific ── */}
      {activity.category === 'task' && (
        <>
          <div>
            <label className={labelClass}>Campaign</label>
            <p className="text-sm mt-0.5">{getCampaignName(activity.campaign_id)}</p>
          </div>
          <div>
            <label className={labelClass}>Objective</label>
            <p className="text-sm mt-0.5">{activity.objective}</p>
          </div>
          <div>
            <label className={labelClass}>Platform</label>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="size-2.5 rounded-full" style={{ backgroundColor: pc.color }} />
              <span className="text-sm">{activity.platform || '—'}</span>
            </div>
          </div>
          <div>
            <label className={labelClass}>Cost</label>
            <p className="text-sm mt-0.5">{activity.cost != null ? `$${activity.cost.toLocaleString()}` : '—'}</p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Launch Date</label>
              <p className="text-sm mt-0.5">{formatDateFull(activity.launch_date)}</p>
            </div>
            <div>
              <label className={labelClass}>Launch Time (UTC)</label>
              {activity.launch_time_utc ? (
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Clock className="size-3.5 text-[var(--color-violet-500)]" />
                  <span className="text-sm">{activity.launch_time_utc} UTC</span>
                </div>
              ) : (
                <p className="text-sm mt-0.5 text-muted-foreground">Not scheduled</p>
              )}
            </div>
          </div>
          {activity.launch_time_utc && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] bg-[var(--color-violet-100)]/60 border border-[var(--color-violet-200)]">
              <Clock className="size-3.5 text-[var(--color-violet-500)] shrink-0" />
              <span className="text-xs text-[var(--color-violet-600)]">Scheduled for programmatic launch at {activity.launch_time_utc} UTC</span>
            </div>
          )}
          <div>
            <label className={labelClass}>Owner</label>
            <p className="text-sm mt-0.5">{activity.owner ? getUserName(activity.owner) : '—'}</p>
            {activity.owner && <p className="text-[0.625rem] text-muted-foreground">{activity.owner}</p>}
          </div>
          <div>
            <label className={labelClass}>Tags</label>
            <div className="flex flex-wrap gap-1 mt-1">
              {activity.tags.length > 0 ? activity.tags.map(t => (
                <span key={t} className="px-2 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-xs text-muted-foreground border border-[var(--color-border-default)]">{t}</span>
              )) : <span className="text-xs text-muted-foreground">—</span>}
            </div>
          </div>
        </>
      )}

      {/* Status */}
      <div>
        <label className={labelClass}>Status</label>
        <div className="mt-1"><StatusBadge status={activity.status} /></div>
      </div>

      {activity.revision_comment && (
        <div className="p-3 rounded-[var(--radius-md)] bg-orange-50 border border-orange-200">
          <div className="flex items-center gap-1.5 mb-1">
            <RotateCcw className="size-3.5 text-orange-500" />
            <span className="text-xs text-orange-700">Revision Requested</span>
          </div>
          <p className="text-xs text-orange-800">{activity.revision_comment}</p>
          <p className="text-[0.625rem] text-orange-500 mt-1">By {getUserName(activity.last_updated_by)} on {formatDateFull(activity.last_updated_at)}</p>
        </div>
      )}

      <div className="pt-4 border-t border-[var(--color-border-default)] space-y-1.5">
        <p className="text-[0.625rem] text-muted-foreground">Created by {getUserName(activity.created_by)} on {formatDateFull(activity.created_date)}</p>
        <p className="text-[0.625rem] text-muted-foreground">Last updated by {getUserName(activity.last_updated_by)} on {formatDateFull(activity.last_updated_at)}</p>
      </div>
    </div>
  );
}

// ─── Form (Add / Edit) ───

function ActivityForm({
  form,
  onChange,
  onObjectiveChange,
  onCampaignChange,
  onCreateCampaign,
  tagInput,
  onTagInputChange,
  onTagAdd,
}: {
  form: CalendarActivity;
  onChange: (f: CalendarActivity) => void;
  onObjectiveChange: (obj: FunnelObjective) => void;
  onCampaignChange: (id: string) => void;
  onCreateCampaign: (name: string) => void;
  tagInput: string;
  onTagInputChange: (v: string) => void;
  onTagAdd: () => void;
}) {
  const fieldClass = "w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]";
  const labelClass = "text-[0.625rem] text-muted-foreground uppercase tracking-wider mb-1 block";
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [newCampaignName, setNewCampaignName] = useState('');

  const campaignsForObjective = getCampaignsForObjective(form.objective);
  const genericId = getGenericCampaignId(form.objective);

  return (
    <div className="space-y-4">
      {/* Activity Name */}
      <div>
        <label className={labelClass}>Activity Name *</label>
        <input
          type="text"
          className={fieldClass}
          placeholder="e.g. Google Ads Spring Promo"
          value={form.name}
          onChange={e => onChange({ ...form, name: e.target.value })}
        />
      </div>

      {/* Objective */}
      <div>
        <label className={labelClass}>Objective *</label>
        <select
          className={fieldClass}
          value={form.objective}
          onChange={e => {
            onObjectiveChange(e.target.value as FunnelObjective);
            setShowNewCampaign(false);
            setNewCampaignName('');
          }}
        >
          {ALL_OBJECTIVES.map(o => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      </div>

      {/* Campaign (optional, filtered by objective) */}
      <div>
        <label className={labelClass}>Campaign</label>
        {!showNewCampaign ? (
          <>
            <select
              className={fieldClass}
              value={form.campaign_id}
              onChange={e => {
                if (e.target.value === '__create_new__') {
                  setShowNewCampaign(true);
                } else {
                  onCampaignChange(e.target.value);
                }
              }}
            >
              <option value="">(not set)</option>
              {campaignsForObjective.filter(c => c.campaign_id !== genericId).map(c => (
                <option key={c.campaign_id} value={c.campaign_id}>{c.name}</option>
              ))}
              <option value="__create_new__">+ Create new campaign...</option>
            </select>
            <p className="text-[0.625rem] text-muted-foreground mt-1">
              Optional — leave blank to auto-assign the generic campaign for this objective.
            </p>
          </>
        ) : (
          <div className="flex gap-2">
            <input
              type="text"
              className={fieldClass}
              placeholder="New campaign name"
              value={newCampaignName}
              onChange={e => setNewCampaignName(e.target.value)}
              autoFocus
            />
            <button
              onClick={() => {
                if (newCampaignName.trim()) {
                  onCreateCampaign(newCampaignName.trim());
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
                onCampaignChange('');
              }}
              className="px-3 py-2 text-xs rounded-[var(--radius-md)] border border-[var(--color-border-default)] text-muted-foreground hover:bg-[var(--color-bg-secondary)] cursor-pointer shrink-0"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Platform */}
      <div>
        <label className={labelClass}>Platform</label>
        <select
          className={fieldClass}
          value={form.platform || ''}
          onChange={e => onChange({ ...form, platform: e.target.value || null })}
        >
          <option value="">None</option>
          {knownPlatforms.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      {/* Cost */}
      <div>
        <label className={labelClass}>Cost</label>
        <div className="relative">
          <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <input
            type="number"
            className={cn(fieldClass, "pl-8")}
            placeholder="0.00"
            value={form.cost ?? ''}
            onChange={e => onChange({ ...form, cost: e.target.value ? Number(e.target.value) : null })}
          />
        </div>
      </div>

      {/* Launch Date & Time */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Launch Date *</label>
          <input
            type="date"
            className={fieldClass}
            value={formatDateISO(form.launch_date)}
            onChange={e => onChange({ ...form, launch_date: parseDateISO(e.target.value) })}
          />
        </div>
        <div>
          <label className={labelClass}>Launch Time (UTC)</label>
          <input
            type="time"
            className={fieldClass}
            value={form.launch_time_utc || ''}
            onChange={e => onChange({ ...form, launch_time_utc: e.target.value || null })}
          />
          <p className="text-[0.625rem] text-muted-foreground mt-1">Leave blank if not time-scheduled.</p>
        </div>
      </div>

      {/* Repeat (tasks only) */}
      {form.category === 'task' && (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Repeat className="size-3.5 text-[var(--color-violet-500)]" />
              <span className="text-xs">Repeat</span>
            </div>
            <button
              type="button"
              onClick={() => {
                if (form.schedule?.enabled) {
                  onChange({ ...form, schedule: { ...form.schedule, enabled: false } });
                } else {
                  const base = form.schedule ?? createDefaultSchedule();
                  const time = form.launch_time_utc || base.time_utc || '09:00';
                  onChange({
                    ...form,
                    schedule: { ...base, enabled: true, frequency: 'weekly', days_of_week: base.days_of_week.length ? base.days_of_week : [1], time_utc: time },
                    launch_time_utc: time,
                  });
                }
              }}
              className={`text-[0.625rem] px-2 py-0.5 rounded-full border transition-colors ${
                form.schedule?.enabled
                  ? 'bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]'
                  : 'border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]'
              }`}
            >
              {form.schedule?.enabled ? 'On' : 'Off'}
            </button>
          </div>

          {form.schedule?.enabled && (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className={labelClass}>Frequency</label>
                  <select
                    className={fieldClass}
                    value={form.schedule.frequency}
                    onChange={e => onChange({ ...form, schedule: { ...form.schedule!, frequency: e.target.value as ScheduleFrequency } })}
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Time (UTC)</label>
                  <input
                    type="time"
                    className={fieldClass}
                    value={form.schedule.time_utc}
                    onChange={e => onChange({ ...form, schedule: { ...form.schedule!, time_utc: e.target.value }, launch_time_utc: e.target.value })}
                  />
                </div>
              </div>

              {form.schedule.frequency === 'weekly' && (
                <div>
                  <label className={labelClass}>Days</label>
                  <div className="flex gap-1">
                    {SCHEDULE_DAY_LABELS.map((lab, idx) => {
                      const selected = form.schedule!.days_of_week.includes(idx);
                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            const cur = form.schedule!.days_of_week;
                            const next = selected ? cur.filter(d => d !== idx) : [...cur, idx].sort((a, b) => a - b);
                            onChange({ ...form, schedule: { ...form.schedule!, days_of_week: next } });
                          }}
                          className={`flex-1 text-[0.625rem] py-1.5 rounded-[var(--radius-sm)] border transition-colors ${
                            selected
                              ? 'bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]'
                              : 'border-[var(--color-border-default)] text-muted-foreground hover:border-[var(--color-border-strong)]'
                          }`}
                        >
                          {lab}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {form.schedule.frequency === 'monthly' && (
                <div>
                  <label className={labelClass}>Day of Month</label>
                  <input
                    type="number"
                    min={1}
                    max={31}
                    className={fieldClass}
                    value={form.schedule.day_of_month ?? ''}
                    onChange={e => onChange({ ...form, schedule: { ...form.schedule!, day_of_month: e.target.value ? Math.min(31, Math.max(1, Number(e.target.value))) : null } })}
                    placeholder="1–31"
                  />
                </div>
              )}

              <p className="text-[0.625rem] text-[var(--color-violet-600)]">
                {describeSchedule(form.schedule)}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Tags */}
      <div>
        <label className={labelClass}>Tags</label>
        <div className="flex flex-wrap gap-1 mb-1.5">
          {form.tags.map(t => (
            <span
              key={t}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-xs text-muted-foreground border border-[var(--color-border-default)]"
            >
              {t}
              <button
                onClick={() => onChange({ ...form, tags: form.tags.filter(tt => tt !== t) })}
                className="cursor-pointer hover:text-red-500"
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-1.5">
          <input
            type="text"
            className={cn(fieldClass, "flex-1")}
            placeholder="Add tag and press Enter"
            list="tag-suggestions"
            value={tagInput}
            onChange={e => onTagInputChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); onTagAdd(); } }}
          />
          <Button variant="outline" size="sm" onClick={onTagAdd} type="button">Add</Button>
        </div>
        <datalist id="tag-suggestions">
          {existingTags.filter(t => !form.tags.includes(t)).map(t => <option key={t} value={t} />)}
        </datalist>
      </div>

      {/* Owner */}
      <div>
        <label className={labelClass}>Owner</label>
        <select
          className={fieldClass}
          value={form.owner || ''}
          onChange={e => onChange({ ...form, owner: e.target.value || null })}
        >
          <option value="">Unassigned</option>
          {allowedUsers.map(u => (
            <option key={u.email} value={u.email}>{u.name} ({u.email})</option>
          ))}
        </select>
      </div>

      {/* Status */}
      <div>
        <label className={labelClass}>Status *</label>
        <select
          className={fieldClass}
          value={form.status}
          onChange={e => onChange({ ...form, status: e.target.value as ActivityStatus })}
        >
          {ALL_STATUSES.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ─── Promotion Form ───

function PromotionForm({
  form,
  onChange,
  tagInput,
  onTagInputChange,
  onTagAdd,
}: {
  form: CalendarActivity;
  onChange: (f: CalendarActivity) => void;
  tagInput: string;
  onTagInputChange: (v: string) => void;
  onTagAdd: () => void;
}) {
  const fieldClass = "w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]";
  const labelClass = "text-[0.625rem] text-muted-foreground uppercase tracking-wider mb-1 block";

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Promotion Name *</label>
        <input type="text" className={fieldClass} placeholder="e.g. Summer Sale — Widget Pro 30% off" value={form.name} onChange={e => onChange({ ...form, name: e.target.value })} />
      </div>
      <div>
        <label className={labelClass}>Product / Service *</label>
        <input type="text" className={fieldClass} placeholder="e.g. Widget Pro, Enterprise Suite" value={form.product_service || ''} onChange={e => onChange({ ...form, product_service: e.target.value || null })} />
      </div>
      <div>
        <label className={labelClass}>Promotion Type *</label>
        <select className={fieldClass} value={form.promotion_type || ''} onChange={e => onChange({ ...form, promotion_type: (e.target.value || null) as PromotionType | null })}>
          <option value="">Select type...</option>
          {promotionTypes.map(pt => (<option key={pt} value={pt}>{pt}</option>))}
        </select>
      </div>
      <div>
        <label className={labelClass}>Discount Details</label>
        <input type="text" className={fieldClass} placeholder='e.g. "30% off", "Buy 2 Get 1 Free"' value={form.discount_details || ''} onChange={e => onChange({ ...form, discount_details: e.target.value || null })} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Start Date *</label>
          <input type="date" className={fieldClass} value={formatDateISO(form.launch_date)} onChange={e => onChange({ ...form, launch_date: parseDateISO(e.target.value) })} />
        </div>
        <div>
          <label className={labelClass}>End Date</label>
          <input type="date" className={fieldClass} value={form.end_date ? formatDateISO(form.end_date) : ''} onChange={e => onChange({ ...form, end_date: e.target.value ? parseDateISO(e.target.value) : null })} />
        </div>
      </div>
      <div>
        <label className={labelClass}>Region</label>
        <select className={fieldClass} value={form.region || ''} onChange={e => onChange({ ...form, region: e.target.value || null })}>
          <option value="">Select region...</option>
          {knownRegions.map(r => (<option key={r} value={r}>{r}</option>))}
        </select>
      </div>
      <div>
        <label className={labelClass}>URL</label>
        <input type="url" className={fieldClass} placeholder="https://example.com/promotion" value={form.promo_url || ''} onChange={e => onChange({ ...form, promo_url: e.target.value || null })} />
      </div>
      <div>
        <label className={labelClass}>Tags</label>
        <div className="flex flex-wrap gap-1 mb-1.5">
          {form.tags.map(t => (
            <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-xs text-muted-foreground border border-[var(--color-border-default)]">
              {t}
              <button onClick={() => onChange({ ...form, tags: form.tags.filter(tt => tt !== t) })} className="cursor-pointer hover:text-red-500"><X className="size-3" /></button>
            </span>
          ))}
        </div>
        <div className="flex gap-1.5">
          <input type="text" className={cn(fieldClass, "flex-1")} placeholder="Add tag" value={tagInput} onChange={e => onTagInputChange(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); onTagAdd(); } }} />
          <Button variant="outline" size="sm" onClick={onTagAdd} type="button">Add</Button>
        </div>
      </div>
      <div>
        <label className={labelClass}>Owner</label>
        <select className={fieldClass} value={form.owner || ''} onChange={e => onChange({ ...form, owner: e.target.value || null })}>
          <option value="">Unassigned</option>
          {allowedUsers.map(u => (<option key={u.email} value={u.email}>{u.name} ({u.email})</option>))}
        </select>
      </div>
    </div>
  );
}

// ─── Holiday Form ───

function HolidayForm({
  form,
  onChange,
}: {
  form: CalendarActivity;
  onChange: (f: CalendarActivity) => void;
}) {
  const fieldClass = "w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]";
  const labelClass = "text-[0.625rem] text-muted-foreground uppercase tracking-wider mb-1 block";

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Holiday Name *</label>
        <input type="text" className={fieldClass} placeholder="e.g. Chinese New Year, Christmas Day" value={form.name} onChange={e => onChange({ ...form, name: e.target.value })} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Start Date *</label>
          <input type="date" className={fieldClass} value={formatDateISO(form.launch_date)} onChange={e => onChange({ ...form, launch_date: parseDateISO(e.target.value) })} />
        </div>
        <div>
          <label className={labelClass}>End Date</label>
          <input type="date" className={fieldClass} value={form.end_date ? formatDateISO(form.end_date) : ''} onChange={e => onChange({ ...form, end_date: e.target.value ? parseDateISO(e.target.value) : null })} />
          <p className="text-[0.5625rem] text-muted-foreground mt-0.5">Leave blank for single-day holidays</p>
        </div>
      </div>
      <div>
        <label className={labelClass}>Region *</label>
        <select className={fieldClass} value={form.region || ''} onChange={e => onChange({ ...form, region: e.target.value || null })}>
          <option value="">Select region...</option>
          {knownRegions.map(r => (<option key={r} value={r}>{r}</option>))}
        </select>
      </div>
      <div>
        <label className={labelClass}>Holiday Type *</label>
        <select className={fieldClass} value={form.holiday_type || ''} onChange={e => onChange({ ...form, holiday_type: (e.target.value || null) as HolidayType | null })}>
          <option value="">Select type...</option>
          {holidayTypes.map(ht => (<option key={ht} value={ht}>{ht}</option>))}
        </select>
      </div>
      <div>
        <label className={labelClass}>Recurring</label>
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={() => onChange({ ...form, recurring: !form.recurring })}
            className={cn("w-10 h-5 rounded-full transition-colors cursor-pointer relative", form.recurring ? "bg-[var(--color-violet-500)]" : "bg-[var(--color-border-default)]")}
          >
            <span className={cn("absolute top-0.5 size-4 rounded-full bg-white transition-transform shadow-sm", form.recurring ? "translate-x-5" : "translate-x-0.5")} />
          </button>
          <span className="text-xs text-muted-foreground">{form.recurring ? 'Yes — repeats every year' : 'No — one-time event'}</span>
        </div>
      </div>
      <div>
        <label className={labelClass}>Notes</label>
        <textarea className={cn(fieldClass, "min-h-[3.75rem] resize-y")} placeholder="Optional notes..." value={form.revision_comment || ''} onChange={e => onChange({ ...form, revision_comment: e.target.value || null })} />
      </div>
    </div>
  );
}
