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
import { createOrphan } from '../../data/standaloneTasks';
import { CURRENT_USER_EMAIL } from '../../data/currentUser';

let taskCounter = 1000;
let runCounter = 0;

// ─── Generate mock output files for a task during a run ───
function generateMockOutputs(task: AutomationTask, runId: string): OutputFile[] {
  if (!task.output_config?.enabled) return [];
  const now = new Date();
  const types = task.output_config.expected_file_types;
  if (types.length === 0) return [];

  const MOCK_CONTENT: Record<string, { filename: string; mime: string; size: number; content: string | null }> = {
    json: { filename: `${task.task_id}-output.json`, mime: 'application/json', size: 1200 + Math.floor(Math.random() * 3000), content: `{\n  "task": "${task.title}",\n  "status": "completed",\n  "generated_at": "${now.toISOString()}",\n  "result": {\n    "success": true,\n    "items_processed": ${Math.floor(Math.random() * 100) + 10},\n    "duration_ms": ${Math.floor(Math.random() * 5000) + 500}\n  }\n}` },
    csv: { filename: `${task.task_id}-output.csv`, mime: 'text/csv', size: 800 + Math.floor(Math.random() * 2000), content: `id,name,value,status\n1,"Item A",${Math.floor(Math.random() * 100)},pass\n2,"Item B",${Math.floor(Math.random() * 100)},warning\n3,"Item C",${Math.floor(Math.random() * 100)},pass\n4,"Item D",${Math.floor(Math.random() * 100)},fail\n5,"Item E",${Math.floor(Math.random() * 100)},pass` },
    text: { filename: `${task.task_id}-output.txt`, mime: 'text/plain', size: 500 + Math.floor(Math.random() * 1500), content: `Task: ${task.title}\nCompleted at: ${now.toLocaleString()}\n\nSummary:\nThe task completed successfully. ${Math.floor(Math.random() * 50) + 5} items were processed with a ${(90 + Math.random() * 10).toFixed(1)}% success rate.\n\nNext steps: Review the output and proceed to downstream tasks.` },
    html: { filename: `${task.task_id}-report.html`, mime: 'text/html', size: 2000 + Math.floor(Math.random() * 5000), content: `<!DOCTYPE html>\n<html>\n<head><title>${task.title} - Report</title></head>\n<body>\n  <h1>${task.title}</h1>\n  <p>Generated: ${now.toLocaleString()}</p>\n  <table>\n    <tr><th>Metric</th><th>Value</th></tr>\n    <tr><td>Items Processed</td><td>${Math.floor(Math.random() * 100)}</td></tr>\n    <tr><td>Success Rate</td><td>${(90 + Math.random() * 10).toFixed(1)}%</td></tr>\n  </table>\n</body>\n</html>` },
    image: { filename: `${task.task_id}-visual.png`, mime: 'image/png', size: 150000 + Math.floor(Math.random() * 200000), content: null },
    document: { filename: `${task.task_id}-doc.pdf`, mime: 'application/pdf', size: 50000 + Math.floor(Math.random() * 100000), content: null },
    video: { filename: `${task.task_id}-clip.mp4`, mime: 'video/mp4', size: 500000, content: null },
    audio: { filename: `${task.task_id}-audio.mp3`, mime: 'audio/mpeg', size: 200000, content: null },
    other: { filename: `${task.task_id}-output.bin`, mime: 'application/octet-stream', size: 10000, content: null },
  };

  return types.map((ft) => {
    const mock = MOCK_CONTENT[ft] ?? MOCK_CONTENT.other;
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

export function AutomationDetailsPage() {
  const { automationId } = useParams<{ automationId: string }>();
  const navigate = useNavigate();

  const workflow = useMemo(
    () => mockWorkflows.find((w) => w.id === automationId),
    [automationId]
  );

  const automationDetail = useMemo(() => {
    if (!automationId) return null;
    return getAutomationDetail(automationId);
  }, [automationId]);

  const [tasks, setTasks] = useState<AutomationTask[]>(() => automationDetail?.tasks ?? []);
  const [schedule, setSchedule] = useState<AutomationSchedule>(
    () => automationDetail?.schedule ?? {
      enabled: false, frequency: 'weekly', days_of_week: [1], day_of_month: null,
      time_utc: '14:00', cron_expression: null, next_run: null, last_run: null,
    }
  );

  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [showSchedulePanel, setShowSchedulePanel] = useState(false);

  // ─── Run animation state ───
  const [isRunning, setIsRunning] = useState(false);
  const [runState, setRunState] = useState<Record<string, 'pending' | 'running' | 'complete'>>({});
  const runAbortRef = useRef(false);

  // ─── Scheduled run timer ───
  const scheduledTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [countdown, setCountdown] = useState<string | null>(null);

  const selectedTask = useMemo(
    () => tasks.find((t) => t.task_id === selectedTaskId) ?? null,
    [tasks, selectedTaskId]
  );

  // Root tasks (no dependencies) - these fire on scheduled trigger
  const rootTasks = useMemo(() => tasks.filter((t) => t.depends_on.length === 0), [tasks]);

  // ─── Summary stats ───
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

  // ─── Add task ───
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

  // ─── Delete task ───
  const handleDeleteTask = useCallback(
    (taskId: string) => {
      setTasks((prev) => {
        const filtered = prev.filter((t) => t.task_id !== taskId);
        return filtered.map((t) => ({
          ...t,
          depends_on: t.depends_on.filter((d) => d !== taskId),
        }));
      });
      if (selectedTaskId === taskId) setSelectedTaskId(null);
    },
    [selectedTaskId]
  );

  // ─── Detach task (move to standalone orphan) ───
  const handleDetachTask = useCallback(
    (taskId: string) => {
      setTasks((prev) => {
        const task = prev.find((t) => t.task_id === taskId);
        if (!task) return prev;
        const now = new Date();
        createOrphan({
          name: task.title,
          campaign_id: null,
          channel: null,
          platform: null,
          cost: 0,
          launch_date: now,
          launch_time_utc: null,
          category: 'task',
          task_type: null,
          tags: [],
          owner: CURRENT_USER_EMAIL,
          status: (task.status as any) ?? 'Draft',
          unscheduled: true,
          created_by: CURRENT_USER_EMAIL,
        });
        const filtered = prev.filter((t) => t.task_id !== taskId);
        return filtered.map((t) => ({
          ...t,
          depends_on: t.depends_on.filter((d) => d !== taskId),
        }));
      });
      if (selectedTaskId === taskId) setSelectedTaskId(null);
    },
    [selectedTaskId]
  );

  // ─── Connect (add dependency) ───
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

  // ─── Delete edge ───
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

  // ─── Run animation ───
  const handleRun = useCallback(async () => {
    if (tasks.length === 0) return;
    runAbortRef.current = false;
    setIsRunning(true);
    setSelectedTaskId(null);
    setShowSchedulePanel(false);

    // Generate a unique run ID for this execution
    const runId = `run-${Date.now()}-${++runCounter}`;

    // Clear any pending scheduled timer since we're running now
    if (scheduledTimerRef.current) {
      clearTimeout(scheduledTimerRef.current);
      scheduledTimerRef.current = null;
    }

    const initial: Record<string, 'pending' | 'running' | 'complete'> = {};
    tasks.forEach((t) => (initial[t.task_id] = 'pending'));
    setRunState(initial);

    const layers = topoSort(tasks);
    const state = { ...initial };
    const completedTaskIds: string[] = [];

    for (const layer of layers) {
      if (runAbortRef.current) break;

      layer.forEach((id) => (state[id] = 'running'));
      setRunState({ ...state });

      await new Promise((r) => setTimeout(r, 1200 + Math.random() * 600));
      if (runAbortRef.current) break;

      layer.forEach((id) => {
        state[id] = 'complete';
        completedTaskIds.push(id);
      });
      setRunState({ ...state });

      // Generate mock outputs for completed tasks in this layer
      setTasks((prev) =>
        prev.map((t) => {
          if (layer.includes(t.task_id) && t.output_config?.enabled) {
            const outputs = generateMockOutputs(t, runId);
            if (outputs.length > 0) {
              const newRunOutput: TaskRunOutput = {
                run_id: runId,
                run_timestamp: new Date(),
                outputs,
              };
              return {
                ...t,
                run_outputs: [newRunOutput, ...t.run_outputs].slice(0, 5), // cap at 5 runs
              };
            }
          }
          return t;
        })
      );

      await new Promise((r) => setTimeout(r, 400));
    }

    if (!runAbortRef.current) {
      setTasks((prev) => prev.map((t) => ({ ...t, status: 'Complete' as const })));
      // Update schedule last_run
      setSchedule((prev) => {
        const nextRun = computeNextRun(prev);
        const wf = mockWorkflows.find((w) => w.id === automationId);
        if (wf) {
          wf.nextRun = nextRun ?? undefined;
          wf.isActive = !!(prev.enabled && nextRun && nextRun.getTime() > Date.now());
          wf.lastRun = new Date();
        }
        return { ...prev, last_run: new Date(), next_run: nextRun };
      });
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

  // ─── Save schedule ────
  const handleSaveSchedule = useCallback((updated: AutomationSchedule) => {
    setSchedule(updated);
    const wf = mockWorkflows.find((w) => w.id === automationId);
    if (wf) {
      const nextRun = updated.next_run ?? computeNextRun(updated);
      wf.nextRun = nextRun ?? undefined;
      wf.isActive = !!(updated.enabled && nextRun && nextRun.getTime() > Date.now());
    }
  }, [automationId]);

  // ─── Schedule timer: set up setTimeout for next_run ───
  useEffect(() => {
    // Clean up old timer
    if (scheduledTimerRef.current) {
      clearTimeout(scheduledTimerRef.current);
      scheduledTimerRef.current = null;
    }

    if (!schedule.enabled || isRunning) {
      setCountdown(null);
      return;
    }

    const nextRun = schedule.next_run ?? computeNextRun(schedule);
    if (!nextRun) {
      setCountdown(null);
      return;
    }

    const msUntil = nextRun.getTime() - Date.now();

    // Only auto-trigger if within 5 minutes (for demo purposes we'll show countdown regardless)
    if (msUntil > 0 && msUntil <= 5 * 60 * 1000) {
      scheduledTimerRef.current = setTimeout(() => {
        handleRun();
      }, msUntil);
    }

    // Update countdown every second
    const countdownInterval = setInterval(() => {
      const remaining = nextRun.getTime() - Date.now();
      if (remaining <= 0) {
        setCountdown('Now');
        clearInterval(countdownInterval);
        return;
      }
      const totalSec = Math.floor(remaining / 1000);
      const days = Math.floor(totalSec / 86400);
      const hrs = Math.floor((totalSec % 86400) / 3600);
      const mins = Math.floor((totalSec % 3600) / 60);
      const secs = totalSec % 60;
      if (days > 0) {
        setCountdown(`${days}d ${hrs}h ${mins}m`);
      } else if (hrs > 0) {
        setCountdown(`${hrs}h ${mins}m ${secs}s`);
      } else {
        setCountdown(`${mins}m ${secs}s`);
      }
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
        <p className="text-sm text-[var(--color-text-secondary)]">Automation not found.</p>
        <Button variant="outline" onClick={() => navigate('/workflows/automations')}>
          <ArrowLeft className="size-4 mr-1" /> Back to Automations
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
            onClick={() => navigate('/workflows/automations')}
            className="p-1.5 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] transition-colors"
          >
            <ArrowLeft className="size-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-lg truncate">{workflow.name}</h1>
              {workflow.isActive === false ? (
                <span className="text-[0.625rem] px-1.5 py-0.5 rounded bg-[var(--color-error-bg)] text-[var(--color-error-text)]">
                  Inactive
                </span>
              ) : (
                <span className="text-[0.625rem] px-1.5 py-0.5 rounded bg-[var(--color-success-bg)] text-[var(--color-success-text)]">
                  Active
                </span>
              )}
            </div>
            <div className="flex items-center gap-4 mt-1">
              <span className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                <Clock className="size-3" /> {workflow.schedule}
              </span>
              <span className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                <RefreshCw className="size-3" /> Last run:{' '}
                {(schedule.last_run ?? workflow.lastRun).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            </div>
          </div>

          {/* Schedule badge + button */}
          <button
            onClick={() => {
              setShowSchedulePanel(!showSchedulePanel);
              setSelectedTaskId(null);
            }}
            disabled={isRunning}
            className={`flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] border text-xs transition-colors disabled:opacity-50 ${
              schedule.enabled
                ? 'border-[var(--color-violet-400)] bg-[var(--color-violet-100)] text-[var(--color-violet-500)]'
                : 'border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]'
            } ${showSchedulePanel ? 'ring-2 ring-[var(--color-violet-400)]/30' : ''}`}
          >
            <CalendarClock className="size-3.5" />
            <span className="hidden sm:inline">
              {schedule.enabled ? scheduleDescription : 'Schedule'}
            </span>
            {schedule.enabled && countdown && (
              <span className="flex items-center gap-1 text-[0.625rem] bg-[var(--color-bg-elevated)] px-1.5 py-0.5 rounded text-[var(--color-violet-500)]">
                <Timer className="size-2.5" />
                {countdown}
              </span>
            )}
          </button>

          {/* Run / Stop button */}
          {isRunning ? (
            <Button
              variant="outline"
              onClick={handleStopRun}
              className="gap-2 border-[var(--color-error-text)] text-[var(--color-error-text)] hover:bg-[var(--color-error-bg)]"
            >
              <Square className="size-3.5" />
              Stop
            </Button>
          ) : (
            <Button
              onClick={handleRun}
              disabled={tasks.length === 0}
              className="gap-2"
              style={{ boxShadow: 'var(--shadow-color-violet)' }}
            >
              <Play className="size-3.5" />
              Run
            </Button>
          )}
        </div>

        {/* Summary bar */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <ListTodo className="size-3.5" />
            <span>{stats.total} tasks</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <CheckCircle2 className="size-3.5 text-[var(--color-success)]" />
            <span>{stats.completed} complete</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <DollarSign className="size-3.5" />
            <span>${stats.totalCost.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-2 flex-1 max-w-[12.5rem]">
            <div className="flex-1 h-1.5 rounded-full bg-[var(--color-bg-secondary)] overflow-hidden">
              <div
                className="h-full rounded-full bg-[var(--color-success)] transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-[0.625rem] text-[var(--color-text-tertiary)]">{progressPct}%</span>
          </div>

          {/* Root tasks indicator */}
          {schedule.enabled && !isRunning && (
            <div className="flex items-center gap-1.5 text-[0.625rem] text-[var(--color-text-tertiary)]">
              <Timer className="size-3" />
              {rootTasks.length} root task{rootTasks.length !== 1 ? 's' : ''}
            </div>
          )}

          {/* Run progress indicator */}
          {isRunning && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--color-warning)] ml-auto">
              <Loader2 className="size-3.5 animate-spin" />
              <span>
                {Object.values(runState).filter((s) => s === 'complete').length}/{tasks.length} complete
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Main area: graph + optional side panels */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        <div className="flex-1 min-w-0 h-full">
          <AutomationGraph
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            onSelectTask={(id) => {
              setSelectedTaskId(id);
              if (id) setShowSchedulePanel(false);
            }}
            onAddTask={handleAddTask}
            onDeleteTask={handleDeleteTask}
            onDetachTask={handleDetachTask}
            onConnect={handleConnect}
            onDeleteEdge={handleDeleteEdge}
            runState={runState}
            isRunning={isRunning}
          />
        </div>

        {/* Task detail panel */}
        {selectedTask && !isRunning && !showSchedulePanel && (
          <AutomationTaskPanel
            key={selectedTask.task_id}
            task={selectedTask}
            allTasks={tasks}
            onClose={() => setSelectedTaskId(null)}
            onSave={handleSaveTask}
            onDelete={handleDeleteTask}
            onDetach={handleDetachTask}
          />
        )}

        {/* Schedule panel */}
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