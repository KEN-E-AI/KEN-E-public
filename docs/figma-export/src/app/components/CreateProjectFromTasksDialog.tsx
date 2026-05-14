import { useState } from 'react';
import { X, Layers } from 'lucide-react';
import { Button } from './ui/button';

type Props = {
  taskCount: number;
  onClose: () => void;
  onConfirm: (title: string, goal: string) => void;
};

export function CreateProjectFromTasksDialog({ taskCount, onClose, onConfirm }: Props) {
  const [title, setTitle] = useState('');
  const [goal, setGoal] = useState('');

  const canSubmit = title.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onConfirm(title.trim(), goal.trim());
  };

  return (
    <>
      <div className="fixed inset-0 z-[70] bg-black/40" onClick={onClose} />
      <div className="fixed left-1/2 top-1/2 z-[71] -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-lg)] shadow-xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-[var(--color-violet-500)]" />
            <h2 className="text-sm">Create project from selection</h2>
          </div>
          <button onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>

        <div className="px-4 py-3 border-b border-[var(--color-border-default)]">
          <p className="text-xs text-muted-foreground">
            Bundling <span className="text-foreground">{taskCount}</span> unfiled task{taskCount === 1 ? '' : 's'} into a new project.
          </p>
        </div>

        <div className="p-4 space-y-4">
          <div className="space-y-1.5">
            <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Project title</label>
            <input
              type="text"
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
              placeholder="e.g. Q2 Launch Readiness"
              className="w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[0.625rem] text-muted-foreground uppercase tracking-wider">Goal (optional)</label>
            <textarea
              value={goal}
              onChange={e => setGoal(e.target.value)}
              rows={3}
              placeholder="What's the outcome this project should drive?"
              className="w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)] resize-none"
            />
          </div>
          <p className="text-[0.6875rem] text-muted-foreground">
            Tasks move into the new project as unlinked nodes. You can wire dependencies from the DAG editor.
          </p>
        </div>

        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[var(--color-border-default)]">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={handleSubmit} disabled={!canSubmit}>
            Create project
          </Button>
        </div>
      </div>
    </>
  );
}
