import { useState } from 'react';
import { X, FolderOpen, Plus, Search } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from './ui/utils';
import { mockWorkflows } from '../data/mockData';

type Props = {
  taskName: string;
  onClose: () => void;
  onAttach: (planId: string) => void;
  onCreateNewProject: (name: string) => void;
};

export function MoveToProjectDialog({ taskName, onClose, onAttach, onCreateNewProject }: Props) {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');

  const projects = mockWorkflows.filter(w => w.type === 'freeform');
  const filtered = projects.filter(p =>
    p.name.toLowerCase().includes(query.trim().toLowerCase()),
  );

  const handleConfirm = () => {
    if (creating) {
      const name = newName.trim();
      if (!name) return;
      onCreateNewProject(name);
    } else if (selectedId) {
      onAttach(selectedId);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-[70] bg-black/40" onClick={onClose} />
      <div className="fixed left-1/2 top-1/2 z-[71] -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-lg)] shadow-xl flex flex-col max-h-[80vh] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-2">
            <FolderOpen className="size-4 text-[var(--color-violet-500)]" />
            <h2 className="text-sm">Move to project</h2>
          </div>
          <button onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>

        <div className="px-4 py-3 border-b border-[var(--color-border-default)]">
          <p className="text-xs text-muted-foreground truncate">Task: <span className="text-foreground">{taskName}</span></p>
        </div>

        {creating ? (
          <div className="flex-1 p-4 space-y-3">
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">New project name</label>
            <input
              type="text"
              autoFocus
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleConfirm(); }}
              placeholder="e.g. Q2 Launch Readiness"
              className="w-full px-3 py-2 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]"
            />
            <p className="text-[11px] text-muted-foreground">
              Creates a new project and moves this task into it. You can add more tasks and dependencies from the project page.
            </p>
          </div>
        ) : (
          <>
            <div className="px-4 py-2 border-b border-[var(--color-border-default)]">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                <input
                  type="text"
                  autoFocus
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search projects…"
                  className="w-full pl-8 pr-3 py-1.5 text-sm border border-[var(--color-border-default)] rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-400)]"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {filtered.length === 0 ? (
                <div className="px-4 py-8 text-center text-xs text-muted-foreground">
                  No projects match "{query}".
                </div>
              ) : (
                <ul>
                  {filtered.map(p => (
                    <li key={p.id}>
                      <button
                        onClick={() => setSelectedId(p.id)}
                        className={cn(
                          "w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm cursor-pointer border-l-2 transition-colors",
                          selectedId === p.id
                            ? "bg-[var(--color-violet-100)] border-[var(--color-violet-500)] text-[var(--color-violet-600)]"
                            : "border-transparent hover:bg-[var(--color-bg-secondary)]"
                        )}
                      >
                        <FolderOpen className="size-3.5 shrink-0" />
                        <span className="truncate flex-1">{p.name}</span>
                        <span className="text-[10px] text-muted-foreground shrink-0">{p.schedule}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <button
              onClick={() => setCreating(true)}
              className="flex items-center gap-2 px-4 py-2.5 text-xs text-[var(--color-violet-500)] hover:bg-[var(--color-bg-secondary)] cursor-pointer border-t border-[var(--color-border-default)] text-left"
            >
              <Plus className="size-3.5" />
              Create new project…
            </button>
          </>
        )}

        <div className="flex items-center justify-between gap-2 px-4 py-3 border-t border-[var(--color-border-default)]">
          {creating ? (
            <Button variant="outline" size="sm" onClick={() => setCreating(false)}>Back</Button>
          ) : <span />}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
            <Button
              size="sm"
              onClick={handleConfirm}
              disabled={creating ? !newName.trim() : !selectedId}
            >
              {creating ? 'Create & move' : 'Move'}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
