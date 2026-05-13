import { useState } from 'react';
import { Inbox, FolderPlus, Trash2, CalendarPlus, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from './ui/button';
import { useStandaloneTasks, updateOrphan, deleteOrphan } from '../data/standaloneTasks';
import { CURRENT_USER_EMAIL } from '../data/currentUser';
import type { CalendarActivity } from '../data/calendarData';

type Props = {
  onEdit: (taskId: string) => void;
  onMoveToProject: (taskId: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
};

function toDateInputValue(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function UnscheduledTasksPanel({ onEdit, onMoveToProject, collapsed, onToggleCollapse }: Props) {
  const all = useStandaloneTasks();
  const mine: readonly CalendarActivity[] = all.filter(
    t => t.unscheduled === true && t.owner === CURRENT_USER_EMAIL,
  );
  const [schedulingId, setSchedulingId] = useState<string | null>(null);

  const handleSchedule = (taskId: string, value: string) => {
    if (!value) return;
    const [y, m, d] = value.split('-').map(Number);
    const date = new Date(y, m - 1, d, 9, 0);
    updateOrphan(taskId, {
      launch_date: date,
      unscheduled: false,
      last_updated_by: CURRENT_USER_EMAIL,
    });
    setSchedulingId(null);
  };

  const hasWork = mine.length > 0;

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]">
      <button
        onClick={onToggleCollapse}
        className={`w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[var(--color-bg-secondary)] transition-colors ${collapsed ? '' : 'border-b border-[var(--color-border-default)]'}`}
      >
        <div className="flex items-center gap-2">
          <Inbox className={`size-4 ${hasWork ? 'text-[var(--color-warning)]' : 'text-[var(--color-violet-500)]'}`} />
          <h3 className="text-sm">Unscheduled tasks</h3>
          <span className="text-[0.625rem] text-muted-foreground">needs a due date</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs ${hasWork ? 'text-[var(--color-warning)]' : 'text-muted-foreground'}`}>
            {mine.length} task{mine.length === 1 ? '' : 's'}
          </span>
          {collapsed ? <ChevronDown className="size-4 text-muted-foreground" /> : <ChevronUp className="size-4 text-muted-foreground" />}
        </div>
      </button>

      {!collapsed && (mine.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-muted-foreground">
          You're all caught up. Tasks you detach from a project will land here until you give them a due date.
        </div>
      ) : (
        <ul className="divide-y divide-[var(--color-border-default)]">
          {mine.map(t => (
            <li key={t.activity_id} className="flex items-start gap-3 px-4 py-3">
              <div className="flex-1 min-w-0">
                <button
                  onClick={() => onEdit(t.activity_id)}
                  className="text-sm text-left truncate hover:underline cursor-pointer block w-full"
                >
                  {t.name}
                </button>
                <div className="flex items-center gap-3 mt-0.5 text-[0.6875rem] text-muted-foreground">
                  <span>{t.status}</span>
                  <span className="text-[var(--color-warning)]">No due date</span>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {schedulingId === t.activity_id ? (
                  <input
                    type="date"
                    autoFocus
                    defaultValue={toDateInputValue(new Date())}
                    onChange={e => handleSchedule(t.activity_id, e.target.value)}
                    onBlur={() => setSchedulingId(null)}
                    className="text-xs h-7 px-2 border border-[var(--color-border-default)] rounded-[var(--radius-sm)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]"
                  />
                ) : (
                  <Button
                    size="sm"
                    onClick={() => setSchedulingId(t.activity_id)}
                    className="gap-1.5 h-7 px-2"
                    title="Set a due date"
                  >
                    <CalendarPlus className="size-3" />
                    Schedule
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onMoveToProject(t.activity_id)}
                  className="gap-1.5 h-7 px-2"
                  title="Move to project"
                >
                  <FolderPlus className="size-3" />
                  Move
                </Button>
                <button
                  onClick={() => deleteOrphan(t.activity_id)}
                  className="p-1.5 rounded hover:bg-[var(--color-error-bg)] text-[var(--color-text-tertiary)] hover:text-[var(--color-error-text)] cursor-pointer"
                  title="Delete task"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      ))}
    </div>
  );
}
