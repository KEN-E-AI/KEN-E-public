import { useMemo } from 'react';
import {
  LayoutDashboard,
  Plus,
  CalendarClock,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { mockWorkflows } from '../../data/mockData';
import type { Workflow } from '../../data/mockData';

export function DashboardCreatorExtension() {
  const dashboards = useMemo(() => mockWorkflows.filter((w) => w.type === 'dashboard'), []);

  return (
    <div className="px-6 pb-6 space-y-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="mb-0.5">Dashboards</h2>
          <p className="text-xs text-muted-foreground">
            {dashboards.length} dashboard{dashboards.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <Button
          className="gap-2"
          style={{
            transitionTimingFunction: 'var(--ease-bounce)',
            transitionDuration: 'var(--duration-default)',
          }}
        >
          <Plus className="size-4" />
          New Dashboard
        </Button>
      </div>

      {dashboards.map((dash) => (
        <DashboardCard key={dash.id} dash={dash} />
      ))}

      {dashboards.length === 0 && (
        <div className="text-center py-12">
          <LayoutDashboard className="size-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No dashboards created yet.</p>
          <p className="text-xs text-muted-foreground mt-1">
            Create one to track your key metrics automatically.
          </p>
        </div>
      )}
    </div>
  );
}

function DashboardCard({ dash }: { dash: Workflow }) {
  return (
    <div
      className="flex items-center gap-4 p-5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all cursor-pointer bg-card"
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-fast)',
      }}
    >
      <div
        className="size-10 rounded-[var(--radius-md)] bg-[var(--color-blue-500)] flex items-center justify-center shrink-0 -rotate-2"
        style={{ boxShadow: 'var(--shadow-color-blue)' }}
      >
        <LayoutDashboard className="size-5 text-[var(--color-text-inverse)]" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm truncate">{dash.name}</p>
          <Badge
            variant={
              dash.status === 'success'
                ? 'secondary'
                : dash.status === 'running'
                  ? 'default'
                  : 'destructive'
            }
            className="capitalize"
          >
            {dash.status}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground truncate">{dash.description}</p>
      </div>

      <div className="shrink-0 text-right space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground justify-end">
          <RefreshCw className="size-3" />
          Last refreshed:{' '}
          {dash.lastRun.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} at{' '}
          {dash.lastRun.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
        {dash.nextRun && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground justify-end">
            <CalendarClock className="size-3" />
            Next refresh:{' '}
            {dash.nextRun.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} at{' '}
            {dash.nextRun.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>

      <Button variant="outline" size="sm" className="shrink-0">
        View
      </Button>
    </div>
  );
}
