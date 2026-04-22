import { BookOpen } from 'lucide-react';
import { Outlet } from 'react-router';

export function StrategyLayout() {
  return (
    <div className="flex flex-col h-full">
      {/* Page Header */}
      <div className="px-6 pt-6 pb-3">
        <div className="flex items-center gap-3 mb-1">
          <div
            className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center shrink-0"
            style={{ boxShadow: 'var(--shadow-color-violet)' }}
          >
            <BookOpen className="size-4 text-[var(--color-text-inverse)]" />
          </div>
          <div>
            <h1 className="mb-0">Knowledge Graph</h1>
            <p className="text-xs text-muted-foreground">
              The shared knowledge about your business that is managed by all users in the account.
            </p>
          </div>
        </div>
      </div>

      {/* Content — full remaining height */}
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}