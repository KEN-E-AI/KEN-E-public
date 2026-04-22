import type { AutomationTask, OutputFileType, OutputFile } from '../data/automationDetailsData';
import { useState, useMemo } from 'react';
import {
  X,
  Save,
  Bot,
  User,
  Calendar,
  Clock,
  DollarSign,
  Tag,
  Globe,
  FileText,
  MessageSquare,
  Activity,
  Trash2,
  Unlink,
  Paperclip,
  Package,
  ChevronDown,
  ChevronRight,
  FolderOutput,
  Pin,
  PinOff,
} from 'lucide-react';
import { Button } from './ui/button';
import { statusStyles, type ActivityStatus } from '../data/calendarData';
import { FILE_TYPE_LABELS } from '../data/automationDetailsData';
import { OutputFileViewer, OutputFileItem } from './OutputFileViewer';

const STATUSES: ActivityStatus[] = [
  'Draft',
  'Awaiting Approval',
  'Approved',
  'Rejected',
  'Revision Requested',
  'Complete',
];

const ALL_FILE_TYPES: OutputFileType[] = ['visualization', 'image', 'document', 'csv', 'json', 'text', 'html', 'video', 'audio', 'other'];

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatDate(d: Date | null): string {
  if (!d) return '';
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function displayDate(d: Date | null): string {
  if (!d) return '\u2014';
  return `${MONTH_ABBR[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

function formatTimestamp(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function Field({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-[var(--color-border-subtle)]">
      <Icon className="size-4 text-[var(--color-text-tertiary)] mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-[10px] text-[var(--color-text-tertiary)] mb-0.5">{label}</p>
        <div className="text-xs text-[var(--color-text-primary)]">{children}</div>
      </div>
    </div>
  );
}

interface AutomationTaskPanelProps {
  task: AutomationTask;
  allTasks?: AutomationTask[];
  onClose: () => void;
  onSave: (updated: AutomationTask) => void;
  onDelete?: (taskId: string) => void;
  onDetach?: (taskId: string) => void;
  selectedRunId?: string | null;
  pinnedFileTypes?: OutputFileType[];
  onPinToDashboard?: (taskId: string, fileType: OutputFileType) => void;
  onUnpinFromDashboard?: (taskId: string, fileType: OutputFileType) => void;
}

export function AutomationTaskPanel({
  task,
  allTasks,
  onClose,
  onSave,
  onDelete,
  onDetach,
  selectedRunId,
  pinnedFileTypes,
  onPinToDashboard,
  onUnpinFromDashboard,
}: AutomationTaskPanelProps) {
  const pinnedSet = useMemo(() => new Set(pinnedFileTypes ?? []), [pinnedFileTypes]);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<AutomationTask>({ ...task });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [activeTab, setActiveTab] = useState<'details' | 'outputs'>('details');
  const [viewingFile, setViewingFile] = useState<OutputFile | null>(null);
  const [expandedDeps, setExpandedDeps] = useState<Set<string>>(new Set());

  const sStyle = statusStyles[task.status as ActivityStatus] ?? statusStyles['Draft'];

  // Count output files for the badge
  const outputCount = useMemo(() => {
    const latestRun = (task.run_outputs ?? [])[0];
    return latestRun ? latestRun.outputs.length : 0;
  }, [task.run_outputs]);

  // Filtered run outputs based on selectedRunId
  const filteredRunOutputs = useMemo(() => {
    const outputs = task.run_outputs ?? [];
    if (!selectedRunId) return outputs;
    return outputs.filter((r) => r.run_id === selectedRunId);
  }, [task.run_outputs, selectedRunId]);

  // Upstream tasks (dependencies) with their outputs
  const upstreamTasks = useMemo(() => {
    if (!allTasks) return [];
    return task.depends_on
      .map((depId) => allTasks.find((t) => t.task_id === depId))
      .filter(Boolean) as AutomationTask[];
  }, [task.depends_on, allTasks]);

  const handleSave = () => {
    onSave(draft);
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({ ...task });
    setEditing(false);
  };

  const updateField = <K extends keyof AutomationTask>(key: K, value: AutomationTask[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const toggleFileType = (ft: OutputFileType) => {
    setDraft((prev) => {
      const config = prev.output_config ?? { enabled: true, expected_file_types: [], description: null };
      const has = config.expected_file_types.includes(ft);
      return {
        ...prev,
        output_config: {
          ...config,
          expected_file_types: has
            ? config.expected_file_types.filter((t) => t !== ft)
            : [...config.expected_file_types, ft],
        },
      };
    });
  };

  const toggleDepExpanded = (depId: string) => {
    setExpandedDeps((prev) => {
      const next = new Set(prev);
      if (next.has(depId)) next.delete(depId);
      else next.add(depId);
      return next;
    });
  };


  return (
    <>
      <div className="w-[360px] h-full border-l border-[var(--color-border-default)] bg-card flex flex-col shrink-0 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
          <div className="flex-1 min-w-0 mr-2">
            {editing ? (
              <input
                className="text-sm w-full bg-transparent border-b border-[var(--color-border-strong)] outline-none py-0.5"
                value={draft.title}
                onChange={(e) => updateField('title', e.target.value)}
              />
            ) : (
              <p className="text-sm truncate">{task.title}</p>
            )}
          </div>
          <div className="flex items-center gap-1">
            {editing ? (
              <>
                <Button variant="ghost" size="sm" onClick={handleCancel}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSave}>
                  <Save className="size-3.5 mr-1" />
                  Save
                </Button>
              </>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {task.output_config?.enabled &&
              onPinToDashboard &&
              task.output_config.expected_file_types.length > 0 && (
                <div className="flex items-center gap-1 pl-1 border-l border-[var(--color-border-subtle)] ml-1">
                  {task.output_config.expected_file_types.map((ft) => {
                    const pinned = pinnedSet.has(ft);
                    return (
                      <button
                        key={ft}
                        onClick={() =>
                          pinned
                            ? onUnpinFromDashboard?.(task.task_id, ft)
                            : onPinToDashboard(task.task_id, ft)
                        }
                        title={pinned ? `Unpin ${FILE_TYPE_LABELS[ft]} from dashboard` : `Pin ${FILE_TYPE_LABELS[ft]} to dashboard`}
                        className={`flex items-center gap-1 text-[10px] px-1.5 py-1 rounded-[var(--radius-sm)] border transition-colors ${
                          pinned
                            ? 'bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]'
                            : 'border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-violet-400)] hover:text-[var(--color-violet-500)]'
                        }`}
                      >
                        {pinned ? <PinOff className="size-3" /> : <Pin className="size-3" />}
                        {FILE_TYPE_LABELS[ft]}
                      </button>
                    );
                  })}
                </div>
              )}
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-[var(--color-border-default)] shrink-0">
          <button
            onClick={() => setActiveTab('details')}
            className={`flex-1 text-xs py-2.5 text-center transition-colors ${
              activeTab === 'details'
                ? 'text-[var(--color-violet-500)] border-b-2 border-[var(--color-violet-500)]'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]'
            }`}
          >
            Details
          </button>
          <button
            onClick={() => setActiveTab('outputs')}
            className={`flex-1 text-xs py-2.5 text-center transition-colors relative ${
              activeTab === 'outputs'
                ? 'text-[var(--color-violet-500)] border-b-2 border-[var(--color-violet-500)]'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]'
            }`}
          >
            Outputs
            {outputCount > 0 && (
              <span className="ml-1 text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--color-violet-100)] text-[var(--color-violet-500)]">
                {outputCount}
              </span>
            )}
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-0">
          {activeTab === 'details' && (
            <>
              {/* Status */}
              <Field icon={Activity} label="Status">
                {editing ? (
                  <select
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.status}
                    onChange={(e) => updateField('status', e.target.value as ActivityStatus)}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                ) : (
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded inline-block"
                    style={{ background: sStyle.bg, color: sStyle.text, border: `1px solid ${sStyle.border}` }}
                  >
                    {task.status}
                  </span>
                )}
              </Field>

              {/* Description */}
              <Field icon={FileText} label="Description">
                {editing ? (
                  <textarea
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full resize-none"
                    rows={3}
                    value={draft.description ?? ''}
                    onChange={(e) => updateField('description', e.target.value || null)}
                  />
                ) : (
                  <p className="text-xs">{task.description || '\u2014'}</p>
                )}
              </Field>

              {/* Assignee */}
              <Field icon={task.assignee_type === 'agent' ? Bot : User} label="Assignee">
                {editing ? (
                  <div className="space-y-1">
                    <select
                      className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                      value={draft.assignee_type}
                      onChange={(e) => updateField('assignee_type', e.target.value as 'human' | 'agent')}
                    >
                      <option value="human">Human</option>
                      <option value="agent">Agent</option>
                    </select>
                    <input
                      className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                      value={draft.assignee_name ?? ''}
                      onChange={(e) => updateField('assignee_name', e.target.value || null)}
                      placeholder="Name"
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg-secondary)]">
                      {task.assignee_type}
                    </span>
                    <span>{task.assignee_name || '\u2014'}</span>
                  </div>
                )}
              </Field>

              {/* Platform */}
              <Field icon={Globe} label="Platform">
                {editing ? (
                  <input
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.platform ?? ''}
                    onChange={(e) => updateField('platform', e.target.value || null)}
                    placeholder="e.g. Google Ads"
                  />
                ) : (
                  <span>{task.platform || '\u2014'}</span>
                )}
              </Field>

              {/* Cost */}
              <Field icon={DollarSign} label="Cost">
                {editing ? (
                  <input
                    type="number"
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.cost ?? ''}
                    onChange={(e) => updateField('cost', e.target.value ? Number(e.target.value) : null)}
                  />
                ) : (
                  <span>{task.cost != null ? `$${task.cost.toLocaleString()}` : '\u2014'}</span>
                )}
              </Field>

              {/* Due Date */}
              <Field icon={Calendar} label="Due Date">
                {editing ? (
                  <input
                    type="date"
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.due_date ? formatDate(draft.due_date) : ''}
                    onChange={(e) => updateField('due_date', e.target.value ? new Date(e.target.value) : null)}
                  />
                ) : (
                  <span>{displayDate(task.due_date)}</span>
                )}
              </Field>

              {/* Launch Time */}
              <Field icon={Clock} label="Launch Time (UTC)">
                {editing ? (
                  <input
                    type="time"
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.launch_time_utc ?? ''}
                    onChange={(e) => updateField('launch_time_utc', e.target.value || null)}
                  />
                ) : (
                  <span>{task.launch_time_utc || '\u2014'}</span>
                )}
              </Field>

              {/* Estimated Effort */}
              <Field icon={Clock} label="Estimated Effort">
                {editing ? (
                  <input
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.estimated_effort ?? ''}
                    onChange={(e) => updateField('estimated_effort', e.target.value || null)}
                    placeholder="e.g. 2h, 30m"
                  />
                ) : (
                  <span>{task.estimated_effort || '\u2014'}</span>
                )}
              </Field>

              {/* Tags */}
              <Field icon={Tag} label="Tags">
                {editing ? (
                  <input
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                    value={draft.tags.join(', ')}
                    onChange={(e) =>
                      updateField(
                        'tags',
                        e.target.value.split(',').map((t) => t.trim()).filter(Boolean)
                      )
                    }
                    placeholder="Comma-separated tags"
                  />
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {task.tags.length > 0
                      ? task.tags.map((t) => (
                          <span
                            key={t}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-violet-100)] text-[var(--color-violet-500)]"
                          >
                            {t}
                          </span>
                        ))
                      : '\u2014'}
                  </div>
                )}
              </Field>

              {/* Completion Notes */}
              <Field icon={MessageSquare} label="Completion Notes">
                {editing ? (
                  <textarea
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full resize-none"
                    rows={2}
                    value={draft.completion_notes ?? ''}
                    onChange={(e) => updateField('completion_notes', e.target.value || null)}
                  />
                ) : (
                  <p className="text-xs">{task.completion_notes || '\u2014'}</p>
                )}
              </Field>

              {/* Revision Comment */}
              <Field icon={MessageSquare} label="Revision Comment">
                {editing ? (
                  <textarea
                    className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full resize-none"
                    rows={2}
                    value={draft.revision_comment ?? ''}
                    onChange={(e) => updateField('revision_comment', e.target.value || null)}
                  />
                ) : (
                  <p className="text-xs">{task.revision_comment || '\u2014'}</p>
                )}
              </Field>

              {/* Dependencies (read-only) */}
              <Field icon={Activity} label="Depends On">
                <div className="flex flex-wrap gap-1">
                  {task.depends_on.length > 0
                    ? task.depends_on.map((d) => {
                        const depTask = allTasks?.find((t) => t.task_id === d);
                        return (
                          <span
                            key={d}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]"
                            title={d}
                          >
                            {depTask?.title ?? d}
                          </span>
                        );
                      })
                    : <span className="text-xs">None (start node)</span>}
                </div>
              </Field>
            </>
          )}

          {activeTab === 'outputs' && (
            <div className="space-y-4">
              {/* Output Configuration */}
              <div>
                <p className="text-[10px] text-[var(--color-text-tertiary)] mb-2">Output Configuration</p>
                <div className="rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] p-3 space-y-3">
                  {/* Toggle */}
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-[var(--color-text-secondary)]">Produces output files</p>
                    {editing ? (
                      <button
                        onClick={() => {
                          if (draft.output_config) {
                            updateField('output_config', { ...draft.output_config, enabled: !draft.output_config.enabled });
                          } else {
                            updateField('output_config', { enabled: true, expected_file_types: [], description: null });
                          }
                        }}
                        className={`w-8 h-5 rounded-full transition-colors relative ${
                          draft.output_config?.enabled
                            ? 'bg-[var(--color-success)]'
                            : 'bg-[var(--color-bg-secondary)] border border-[var(--color-border-default)]'
                        }`}
                      >
                        <div
                          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                            draft.output_config?.enabled ? 'translate-x-3.5' : 'translate-x-0.5'
                          }`}
                        />
                      </button>
                    ) : (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        task.output_config?.enabled
                          ? 'bg-[var(--color-success-bg)] text-[var(--color-success-text)]'
                          : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]'
                      }`}>
                        {task.output_config?.enabled ? 'Yes' : 'No'}
                      </span>
                    )}
                  </div>

                  {/* Expected file types */}
                  {(editing ? draft.output_config?.enabled : task.output_config?.enabled) && (
                    <>
                      <div>
                        <p className="text-[10px] text-[var(--color-text-tertiary)] mb-1.5">Expected File Types</p>
                        {editing ? (
                          <div className="flex flex-wrap gap-1">
                            {ALL_FILE_TYPES.map((ft) => (
                              <button
                                key={ft}
                                onClick={() => toggleFileType(ft)}
                                className={`text-[10px] px-2 py-1 rounded-[var(--radius-sm)] border transition-colors ${
                                  draft.output_config?.expected_file_types.includes(ft)
                                    ? 'bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]'
                                    : 'border-[var(--color-border-default)] text-[var(--color-text-tertiary)] hover:border-[var(--color-border-strong)]'
                                }`}
                              >
                                {FILE_TYPE_LABELS[ft]}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {(task.output_config?.expected_file_types ?? []).map((ft) => (
                              <span
                                key={ft}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-violet-100)] text-[var(--color-violet-500)]"
                              >
                                {FILE_TYPE_LABELS[ft]}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Description */}
                      <div>
                        <p className="text-[10px] text-[var(--color-text-tertiary)] mb-1">Description</p>
                        {editing ? (
                          <input
                            className="text-xs bg-transparent border border-[var(--color-border-default)] rounded px-1.5 py-1 w-full"
                            value={draft.output_config?.description ?? ''}
                            onChange={(e) => {
                              const config = draft.output_config ?? { enabled: true, expected_file_types: [], description: null };
                              updateField('output_config', { ...config, description: e.target.value || null });
                            }}
                            placeholder="What does this task output?"
                          />
                        ) : (
                          <p className="text-xs text-[var(--color-text-secondary)]">
                            {task.output_config?.description || '\u2014'}
                          </p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Available Inputs (from upstream tasks) */}
              {upstreamTasks.length > 0 && (
                <div>
                  <p className="text-[10px] text-[var(--color-text-tertiary)] mb-2">
                    <Package className="size-3 inline mr-1 -mt-0.5" />
                    Available Inputs ({upstreamTasks.length} upstream task{upstreamTasks.length !== 1 ? 's' : ''})
                  </p>
                  <div className="space-y-1.5">
                    {upstreamTasks.map((dep) => {
                      const isExpanded = expandedDeps.has(dep.task_id);
                      const latestOutputs = (dep.run_outputs ?? [])[0]?.outputs ?? [];
                      return (
                        <div key={dep.task_id} className="rounded-[var(--radius-sm)] border border-[var(--color-border-subtle)]">
                          <button
                            onClick={() => toggleDepExpanded(dep.task_id)}
                            className="w-full flex items-center gap-2 p-2 text-left hover:bg-[var(--color-bg-secondary)] transition-colors"
                          >
                            {isExpanded
                              ? <ChevronDown className="size-3 text-[var(--color-text-tertiary)] shrink-0" />
                              : <ChevronRight className="size-3 text-[var(--color-text-tertiary)] shrink-0" />
                            }
                            <span className="text-[11px] text-[var(--color-text-primary)] truncate flex-1">
                              {dep.title}
                            </span>
                            {latestOutputs.length > 0 && (
                              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--color-violet-100)] text-[var(--color-violet-500)]">
                                {latestOutputs.length} file{latestOutputs.length !== 1 ? 's' : ''}
                              </span>
                            )}
                          </button>
                          {isExpanded && (
                            <div className="px-2 pb-2 space-y-1.5">
                              {latestOutputs.length > 0 ? (
                                latestOutputs.map((f) => (
                                  <OutputFileItem
                                    key={f.file_id}
                                    file={f}
                                    onClick={() => setViewingFile(f)}
                                  />
                                ))
                              ) : (
                                <p className="text-[10px] text-[var(--color-text-tertiary)] py-2 text-center">
                                  No outputs from previous run
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Run Outputs */}
              <div>
                <p className="text-[10px] text-[var(--color-text-tertiary)] mb-2">
                  <FolderOutput className="size-3 inline mr-1 -mt-0.5" />
                  Run Outputs
                </p>
                {filteredRunOutputs.length > 0 ? (
                  <div className="space-y-3">
                    {filteredRunOutputs.map((run) => (
                      <div key={run.run_id} className="rounded-[var(--radius-md)] border border-[var(--color-border-subtle)]">
                        <div className="flex items-center gap-2 px-3 py-2 bg-[var(--color-bg-secondary)] rounded-t-[var(--radius-md)]">
                          <span className="text-[10px] text-[var(--color-text-tertiary)] font-mono">
                            {run.run_id}
                          </span>
                          <span className="text-[10px] text-[var(--color-text-tertiary)]">
                            {formatTimestamp(run.run_timestamp)}
                          </span>
                        </div>
                        <div className="p-2 space-y-1.5">
                          {run.outputs.map((f) => (
                            <OutputFileItem
                              key={f.file_id}
                              file={f}
                              onClick={() => setViewingFile(f)}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[var(--radius-md)] border border-dashed border-[var(--color-border-subtle)] p-6 text-center">
                    <Paperclip className="size-5 text-[var(--color-text-tertiary)] mx-auto mb-2" />
                    <p className="text-xs text-[var(--color-text-secondary)]">No outputs yet</p>
                    <p className="text-[10px] text-[var(--color-text-tertiary)] mt-1">
                      {task.output_config?.enabled
                        ? 'Run the automation to generate output files'
                        : 'Enable output configuration to produce files'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer: Detach (left) + Delete (right) */}
        {(onDelete || onDetach) && (
          <div className="shrink-0 p-4 border-t border-[var(--color-border-default)]">
            {confirmDelete ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-[var(--color-text-secondary)]">
                  Delete <span className="text-[var(--color-text-primary)]">"{task.title}"</span>? Dependencies referencing this task will be removed.
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => setConfirmDelete(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1 bg-[var(--color-error-bg)] text-[var(--color-error-text)] border border-[var(--color-error-text)] hover:opacity-90"
                    onClick={() => onDelete?.(task.task_id)}
                  >
                    <Trash2 className="size-3 mr-1" />
                    Confirm Delete
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                {onDetach ? (
                  <button
                    onClick={() => onDetach(task.task_id)}
                    className="flex items-center gap-1.5 text-xs text-[var(--color-violet-500)] hover:underline transition-colors"
                    title="Detach from project (move to unscheduled tasks)"
                  >
                    <Unlink className="size-3" />
                    Detach from project
                  </button>
                ) : <span />}
                {onDelete && (
                  <button
                    onClick={() => setConfirmDelete(true)}
                    className="flex items-center gap-1.5 text-xs text-[var(--color-error-text)] hover:underline transition-colors"
                  >
                    <Trash2 className="size-3" />
                    Delete Task
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* File viewer modal */}
      {viewingFile && (
        <OutputFileViewer
          file={viewingFile}
          onClose={() => setViewingFile(null)}
        />
      )}
    </>
  );
}