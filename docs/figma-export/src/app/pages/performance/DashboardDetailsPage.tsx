import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  ArrowLeft,
  Clock,
  RefreshCw,
  CheckCircle2,
  DollarSign,
  ListTodo,
  Play,
  Square,
  Loader2,
  CalendarClock,
  Timer,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { AutomationGraph, topoSort } from '../../components/AutomationGraph';
import { AutomationTaskPanel } from '../../components/AutomationTaskPanel';
import { AutomationSchedulePanel } from '../../components/AutomationSchedulePanel';
import { DashboardCanvas, type Placement } from '../../components/DashboardCanvas';
import {
  getAutomationDetail,
  type AutomationTask,
  type AutomationSchedule,
  type OutputFile,
  type TaskRunOutput,
  computeNextRun,
  describeSchedule,
} from '../../data/automationDetailsData';
import { mockWorkflows } from '../../data/mockData';

let taskCounter = 5000;
let runCounter = 0;

function generateMockOutputs(task: AutomationTask, runId: string): OutputFile[] {
  if (!task.output_config?.enabled) return [];
  const now = new Date();
  const types = task.output_config.expected_file_types;
  if (types.length === 0) return [];

  const vegaSpec = {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    title: task.title,
    data: {
      values: Array.from({ length: 7 }, (_, i) => ({
        day: `Day ${i + 1}`,
        value: Math.round(40 + Math.random() * 80),
      })),
    },
    mark: 'bar',
    encoding: {
      x: { field: 'day', type: 'ordinal', title: null },
      y: { field: 'value', type: 'quantitative', title: 'Value' },
    },
  };

  const MOCK: Record<string, { filename: string; mime: string; size: number; content: string | null }> = {
    json: { filename: `${task.task_id}-output.json`, mime: 'application/json', size: 1200 + Math.floor(Math.random() * 3000), content: `{"task":"${task.title}","status":"completed"}` },
    csv: { filename: `${task.task_id}-output.csv`, mime: 'text/csv', size: 800, content: 'id,name,value\n1,A,10' },
    text: { filename: `${task.task_id}-output.txt`, mime: 'text/plain', size: 500, content: `Task ${task.title} completed.` },
    html: { filename: `${task.task_id}-report.html`, mime: 'text/html', size: 2000, content: `<h1>${task.title}</h1>` },
    image: { filename: `${task.task_id}-visual.png`, mime: 'image/png', size: 150000, content: null },
    document: { filename: `${task.task_id}-doc.pdf`, mime: 'application/pdf', size: 50000, content: null },
    visualization: { filename: `${task.task_id}-chart.vl.json`, mime: 'application/vnd.vega-lite+json', size: 1500, content: JSON.stringify(vegaSpec) },
    other: { filename: `${task.task_id}-output.bin`, mime: 'application/octet-stream', size: 10000, content: null },
  };

  return types.map((ft) => {
    const mock = MOCK[ft] ?? MOCK.other;
    return {
      file_id: `${runId}-${task.task_id}-${ft}`,
      filename: mock.filename,
      file_type: ft,
      mime_type: mock.mime,
      size_bytes: mock.size,
      preview_url: null,
      content_preview: mock.content,
      created_at: new Date(),
    };
  });
}

export function DashboardDetailsPage() {
  const { dashboardId } = useParams<{ dashboardId: string }>();
  const navigate = useNavigate();

  const workflow = useMemo(
    () => mockWorkflows.find((w) => w.id === dashboardId && w.type === 'dashboard'),
    [dashboardId]
  );

  const automationDetail = useMemo(() => {
    if (!dashboardId) return null;
    return getAutomationDetail(dashboardId);
  }, [dashboardId]);

  const [tasks, setTasks] = useState<AutomationTask[]>(() => automationDetail?.tasks ?? []);
  const [schedule, setSchedule] = useState<AutomationSchedule>(
    () => automationDetail?.schedule ?? {
      enabled: false, frequency: 'weekly', days_of_week: [1], day_of_month: null,
      time_utc: '14:00', cron_expression: null, next_run: null, last_run: null,
    }
  );

  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [showSchedulePanel, setShowSchedulePanel] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runState, setRunState] = useState<Record<string, 'pending' | 'running' | 'complete'>>({});
  const runAbortRef = useRef(false);
  const scheduledTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [countdown, setCountdown] = useState<string | null>(null);
  const [placements, setPlacementsState] = useState<Placement[]>(
    () => workflow?.dashboardPlacements ?? []
  );
  const [lastRunAt, setLastRunAt] = useState<Date | null>(null);

  const setPlacements = useCallback(
    (next: Placement[]) => {
      setPlacementsState(next);
      if (workflow) {
        // Persist to the workflow record so layouts survive navigation
        workflow.dashboardPlacements = next;
      }
    },
    [workflow]
  );

  const handlePinToDashboard = useCallback(
    (taskId: string, fileType: string) => {
      if (placements.some((p) => p.nodeId === taskId && p.fileType === fileType)) return;
      const existing = placements.length;
      const id = `pl-${taskId}-${fileType}-${Date.now()}`;
      setPlacements([
        ...placements,
        {
          id,
          nodeId: taskId,
          fileType: fileType as Placement['fileType'],
          x: 16 + (existing % 3) * 280,
          y: 16 + Math.floor(existing / 3) * 220,
          w: 260,
          h: 200,
        },
      ]);
    },
    [placements, setPlacements]
  );

  const handleUnpinFromDashboard = useCallback(
    (taskId: string, fileType: string) => {
      setPlacements(placements.filter((p) => !(p.nodeId === taskId && p.fileType === fileType)));
    },
    [placements, setPlacements]
  );

  const selectedTask = useMemo(
    () => tasks.find((t) => t.task_id === selectedTaskId) ?? null,
    [tasks, selectedTaskId]
  );

  const rootTasks = useMemo(() => tasks.filter((t) => t.depends_on.length === 0), [tasks]);

  const stats = useMemo(() => {
    const total = tasks.length;
    const completed = tasks.filter((t) => t.status === 'Complete').length;
    const totalCost = tasks.reduce((sum, t) => sum + (t.cost ?? 0), 0);
    return { total, completed, totalCost };
  }, [tasks]);

  const scheduleDescription = useMemo(() => describeSchedule(schedule), [schedule]);

  const handleSaveTask = (updated: AutomationTask) => {
    setTasks((prev) => prev.map((t) => (t.task_id === updated.task_id ? updated : t)));
  };

  const handleAddTask = useCallback(() => {
    const newId = `t-new-${++taskCounter}`;
    const newTask: AutomationTask = {
      task_id: newId,
      title: 'New Task',
      description: null,
      assignee_type: 'human',
      assignee_name: null,
      status: 'Draft',
      depends_on: [],
      cost: null,
      due_date: null,
      launch_time_utc: null,
      platform: null,
      tags: [],
      estimated_effort: null,
      completion_notes: null,
      revision_comment: null,
      output_config: null,
      run_outputs: [],
    };
    setTasks((prev) => [...prev, newTask]);
    setSelectedTaskId(newId);
    setShowSchedulePanel(false);
  }, []);

  const handleDeleteTask = useCallback(
    (taskId: string) => {
      setTasks((prev) => {
        const filtered = prev.filter((t) => t.task_id !== taskId);
        return filtered.map((t) => ({ ...t, depends_on: t.depends_on.filter((d) => d !== taskId) }));
      });
      if (selectedTaskId === taskId) setSelectedTaskId(null);
    },
    [selectedTaskId]
  );

  const handleConnect = useCallback((sourceId: string, targetId: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.task_id === targetId && !t.depends_on.includes(sourceId)) {
          return { ...t, depends_on: [...t.depends_on, sourceId] };
        }
        return t;
      })
    );
  }, []);

  const handleDeleteEdge = useCallback((sourceId: string, targetId: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.task_id === targetId) {
          return { ...t, depends_on: t.depends_on.filter((d) => d !== sourceId) };
        }
        return t;
      })
    );
  }, []);

  const handleRun = useCallback(async () => {
    if (tasks.length === 0) return;
    runAbortRef.current = false;
    setIsRunning(true);
    setSelectedTaskId(null);
    setShowSchedulePanel(false);

    const runId = `run-${Date.now()}-${++runCounter}`;

    if (scheduledTimerRef.current) {
      clearTimeout(scheduledTimerRef.current);
      scheduledTimerRef.current = null;
    }

    const initial: Record<string, 'pending' | 'running' | 'complete'> = {};
    tasks.forEach((t) => (initial[t.task_id] = 'pending'));
    setRunState(initial);

    const layers = topoSort(tasks);
    const state = { ...initial };

    for (const layer of layers) {
      if (runAbortRef.current) break;
      layer.forEach((id) => (state[id] = 'running'));
      setRunState({ ...state });
      await new Promise((r) => setTimeout(r, 1200 + Math.random() * 600));
      if (runAbortRef.current) break;
      layer.forEach((id) => (state[id] = 'complete'));
      setRunState({ ...state });

      setTasks((prev) =>
        prev.map((t) => {
          if (layer.includes(t.task_id) && t.output_config?.enabled) {
            const outputs = generateMockOutputs(t, runId);
            if (outputs.length > 0) {
              return { ...t, run_outputs: [{ run_id: runId, run_timestamp: new Date(), outputs }, ...t.run_outputs].slice(0, 5) };
            }
          }
          return t;
        })
      );

      await new Promise((r) => setTimeout(r, 400));
    }

    if (!runAbortRef.current) {
      setTasks((prev) => prev.map((t) => ({ ...t, status: 'Complete' as const })));
      setSchedule((prev) => ({ ...prev, last_run: new Date(), next_run: computeNextRun(prev) }));
      setLastRunAt(new Date());
    }

    await new Promise((r) => setTimeout(r, 800));
    setIsRunning(false);
    setRunState({});
  }, [tasks]);

  const handleStopRun = useCallback(() => {
    runAbortRef.current = true;
    setIsRunning(false);
    setRunState({});
  }, []);

  const handleSaveSchedule = useCallback((updated: AutomationSchedule) => {
    setSchedule(updated);
  }, []);

  useEffect(() => {
    if (scheduledTimerRef.current) {
      clearTimeout(scheduledTimerRef.current);
      scheduledTimerRef.current = null;
    }

    if (!schedule.enabled || isRunning) {
      setCountdown(null);
      return;
    }

    const nextRun = schedule.next_run ?? computeNextRun(schedule);
    if (!nextRun) { setCountdown(null); return; }

    const msUntil = nextRun.getTime() - Date.now();
    if (msUntil > 0 && msUntil <= 5 * 60 * 1000) {
      scheduledTimerRef.current = setTimeout(() => { handleRun(); }, msUntil);
    }

    const countdownInterval = setInterval(() => {
      const remaining = nextRun.getTime() - Date.now();
      if (remaining <= 0) { setCountdown('Now'); clearInterval(countdownInterval); return; }
      const totalSec = Math.floor(remaining / 1000);
      const days = Math.floor(totalSec / 86400);
      const hrs = Math.floor((totalSec % 86400) / 3600);
      const mins = Math.floor((totalSec % 3600) / 60);
      const secs = totalSec % 60;
      if (days > 0) setCountdown(`${days}d ${hrs}h ${mins}m`);
      else if (hrs > 0) setCountdown(`${hrs}h ${mins}m ${secs}s`);
      else setCountdown(`${mins}m ${secs}s`);
    }, 1000);

    return () => {
      clearInterval(countdownInterval);
      if (scheduledTimerRef.current) {
        clearTimeout(scheduledTimerRef.current);
        scheduledTimerRef.current = null;
      }
    };
  }, [schedule, isRunning, handleRun]);

  if (!workflow) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-sm text-[var(--color-text-secondary)]">Dashboard not found.</p>
        <Button variant="outline" onClick={() => navigate('/performance')}>
          <ArrowLeft className="size-4 mr-1" /> Back to Performance
        </Button>
      </div>
    );
  }

  const progressPct = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-[var(--color-border-default)] bg-card">
        <div className="flex items-center gap-3 mb-3">
          <button
            onClick={() => navigate('/performance')}
            className="p-1.5 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] transition-colors"
          >
            <ArrowLeft className="size-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-lg truncate">{workflow.name}</h1>
              {workflow.isActive === false ? (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-error-bg)] text-[var(--color-error-text)]">Inactive</span>
              ) : (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-success-bg)] text-[var(--color-success-text)]">Active</span>
              )}
            </div>
            <div className="flex items-center gap-4 mt-1">
              <span className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                <Clock className="size-3" /> {workflow.schedule}
              </span>
              <span className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                <RefreshCw className="size-3" /> Last run:{' '}
                {(schedule.last_run ?? workflow.lastRun).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
            </div>
          </div>

          <button
            onClick={() => { setShowSchedulePanel(!showSchedulePanel); setSelectedTaskId(null); }}
            disabled={isRunning}
            className={`flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] border text-xs transition-colors disabled:opacity-50 ${
              schedule.enabled
                ? 'border-[var(--color-violet-400)] bg-[var(--color-violet-100)] text-[var(--color-violet-500)]'
                : 'border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]'
            } ${showSchedulePanel ? 'ring-2 ring-[var(--color-violet-400)]/30' : ''}`}
          >
            <CalendarClock className="size-3.5" />
            <span className="hidden sm:inline">{schedule.enabled ? scheduleDescription : 'Schedule'}</span>
            {schedule.enabled && countdown && (
              <span className="flex items-center gap-1 text-[10px] bg-[var(--color-bg-elevated)] px-1.5 py-0.5 rounded text-[var(--color-violet-500)]">
                <Timer className="size-2.5" />{countdown}
              </span>
            )}
          </button>

          {isRunning ? (
            <Button variant="outline" onClick={handleStopRun} className="gap-2 border-[var(--color-error-text)] text-[var(--color-error-text)] hover:bg-[var(--color-error-bg)]">
              <Square className="size-3.5" /> Stop
            </Button>
          ) : (
            <Button onClick={handleRun} disabled={tasks.length === 0} className="gap-2" style={{ boxShadow: 'var(--shadow-color-violet)' }}>
              <Play className="size-3.5" /> Run
            </Button>
          )}
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <ListTodo className="size-3.5" /><span>{stats.total} tasks</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <CheckCircle2 className="size-3.5 text-[var(--color-success)]" /><span>{stats.completed} complete</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <DollarSign className="size-3.5" /><span>${stats.totalCost.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-2 flex-1 max-w-[200px]">
            <div className="flex-1 h-1.5 rounded-full bg-[var(--color-bg-secondary)] overflow-hidden">
              <div className="h-full rounded-full bg-[var(--color-success)] transition-all" style={{ width: `${progressPct}%` }} />
            </div>
            <span className="text-[10px] text-[var(--color-text-tertiary)]">{progressPct}%</span>
          </div>
          {schedule.enabled && !isRunning && (
            <div className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-tertiary)]">
              <Timer className="size-3" />{rootTasks.length} root task{rootTasks.length !== 1 ? 's' : ''}
            </div>
          )}
          {isRunning && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--color-warning)] ml-auto">
              <Loader2 className="size-3.5 animate-spin" />
              <span>{Object.values(runState).filter((s) => s === 'complete').length}/{tasks.length} complete</span>
            </div>
          )}
        </div>
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        <SplitPane
          graph={
            <AutomationGraph
              tasks={tasks}
              selectedTaskId={selectedTaskId}
              onSelectTask={(id) => { setSelectedTaskId(id); if (id) setShowSchedulePanel(false); }}
              onAddTask={handleAddTask}
              onDeleteTask={handleDeleteTask}
              onConnect={handleConnect}
              onDeleteEdge={handleDeleteEdge}
              runState={runState}
              isRunning={isRunning}
            />
          }
          canvas={
            <DashboardCanvas
              tasks={tasks}
              placements={placements}
              onPlacementsChange={setPlacements}
              lastRunAt={lastRunAt}
            />
          }
        />

        {selectedTask && !isRunning && !showSchedulePanel && (
          <AutomationTaskPanel
            key={selectedTask.task_id}
            task={selectedTask}
            allTasks={tasks}
            onClose={() => setSelectedTaskId(null)}
            onSave={handleSaveTask}
            onDelete={handleDeleteTask}
            pinnedFileTypes={placements
              .filter((p) => p.nodeId === selectedTask.task_id)
              .map((p) => p.fileType)}
            onPinToDashboard={handlePinToDashboard}
            onUnpinFromDashboard={handleUnpinFromDashboard}
          />
        )}

        {showSchedulePanel && !isRunning && (
          <AutomationSchedulePanel
            schedule={schedule}
            onSave={handleSaveSchedule}
            onClose={() => setShowSchedulePanel(false)}
            hasRootTasks={rootTasks.length > 0}
            rootTaskCount={rootTasks.length}
            isRunning={isRunning}
          />
        )}
      </div>
    </div>
  );
}

const SPLIT_STORAGE_KEY = 'dashboard-split-graph-pct';
const MIN_PCT = 15;
const MAX_PCT = 85;

function SplitPane({ graph, canvas }: { graph: React.ReactNode; canvas: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [graphPct, setGraphPct] = useState<number>(() => {
    const saved = typeof window !== 'undefined' ? window.localStorage.getItem(SPLIT_STORAGE_KEY) : null;
    const parsed = saved ? Number(saved) : NaN;
    return Number.isFinite(parsed) && parsed >= MIN_PCT && parsed <= MAX_PCT ? parsed : 60;
  });
  const draggingRef = useRef(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientY - rect.top) / rect.height) * 100;
      const clamped = Math.max(MIN_PCT, Math.min(MAX_PCT, pct));
      setGraphPct(clamped);
    };
    const onUp = () => {
      if (draggingRef.current) {
        draggingRef.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SPLIT_STORAGE_KEY, String(graphPct));
    }
  }, [graphPct]);

  const startDrag = (e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  };

  return (
    <div ref={containerRef} className="flex-1 min-w-0 h-full flex flex-col min-h-0">
      <div className="min-h-0" style={{ height: `${graphPct}%` }}>
        {graph}
      </div>
      <div
        role="separator"
        aria-orientation="horizontal"
        onMouseDown={startDrag}
        onDoubleClick={() => setGraphPct(60)}
        className="shrink-0 h-1.5 bg-[var(--color-border-default)] hover:bg-[var(--color-violet-400)] cursor-row-resize transition-colors relative group"
        title="Drag to resize · double-click to reset"
      >
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-0.5 rounded bg-[var(--color-text-tertiary)] opacity-50 group-hover:opacity-100" />
      </div>
      <div className="min-h-0 flex-1">
        {canvas}
      </div>
    </div>
  );
}
