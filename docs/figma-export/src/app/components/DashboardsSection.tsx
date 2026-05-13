import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import { Clock, RefreshCw, Settings2, Plus, LayoutDashboard } from 'lucide-react';
import { Button } from './ui/button';
import { OriginBadge } from './OriginBadge';
import { mockWorkflows } from '../data/mockData';
import type { Workflow } from '../data/mockData';

export function DashboardsSection() {
  const dashboards = useMemo(() => mockWorkflows.filter(w => w.type === 'dashboard'), []);
  const navigate = useNavigate();

  return (
    <div>
      {/* Description */}
      <div className="mb-4 p-4 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)]">
        <p className="text-sm text-muted-foreground">
          Scheduled dashboards that automatically compile and refresh your marketing data.
          Each dashboard runs on a defined schedule, aggregating metrics across channels into visual reports.
        </p>
      </div>

      {/* Header with New button */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs text-muted-foreground">
          {dashboards.length} dashboard{dashboards.length !== 1 ? 's' : ''}
        </p>
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

      {/* Dashboard Cards */}
      <div className="space-y-3">
        {dashboards.map(d => (
          <DashboardCard key={d.id} dashboard={d} />
        ))}

        {dashboards.length === 0 && (
          <div className="text-center py-12">
            <LayoutDashboard className="size-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No dashboards created yet.</p>
            <p className="text-xs text-muted-foreground mt-1">
              Create a dashboard to schedule automated performance reports.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function DashboardCard({ dashboard }: { dashboard: Workflow }) {
  const navigate = useNavigate();

  return (
    <div
      className={`flex items-center gap-4 p-5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all cursor-pointer bg-card ${
        dashboard.isActive === false ? 'opacity-60' : ''
      }`}
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-fast)',
      }}
      onClick={() => navigate(`/performance/dashboards/${dashboard.id}`)}
    >
      {/* Icon */}
      <div
        className="size-10 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center shrink-0"
        style={{ boxShadow: 'var(--shadow-color-violet)' }}
      >
        <LayoutDashboard className="size-5 text-[var(--color-text-inverse)]" />
      </div>

      {/* Name + status */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <p className="text-sm truncate">{dashboard.name}</p>
          <OriginBadge extensionId={dashboard.extensionId} />
          {dashboard.isActive === false ? (
            <span className="text-[0.625rem] px-1.5 py-0.5 rounded bg-[var(--color-error-bg)] text-[var(--color-error-text)]">
              Inactive
            </span>
          ) : (
            <span className="text-[0.625rem] px-1.5 py-0.5 rounded bg-[var(--color-success-bg)] text-[var(--color-success-text)]">
              Active
            </span>
          )}
        </div>
        {dashboard.description && (
          <p className="text-xs text-muted-foreground truncate">{dashboard.description}</p>
        )}
      </div>

      {/* Schedule & Last Run */}
      <div className="shrink-0 text-right space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground justify-end">
          <Clock className="size-3" />
          {dashboard.schedule}
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground justify-end">
          <RefreshCw className="size-3" />
          Last run: {dashboard.lastRun.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} at{' '}
          {dashboard.lastRun.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>

      {/* Configure button */}
      <div className="flex items-center gap-2 shrink-0">
        <Button
          variant="outline"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/performance/dashboards/${dashboard.id}`);
          }}
        >
          <Settings2 className="size-3.5 mr-1" />
          Configure
        </Button>
      </div>
    </div>
  );
}
