import { createContext, useContext, useState } from 'react';
import { Outlet, useLocation, Link } from 'react-router';
import { Bot, Sparkles, RefreshCw, Puzzle, ListFilter, Network } from 'lucide-react';
import { cn } from '../../components/ui/utils';

export type WorkflowSourceFilter = 'all' | 'custom' | 'extension';

const WorkflowFilterContext = createContext<WorkflowSourceFilter>('all');

export function useWorkflowFilter() {
  return useContext(WorkflowFilterContext);
}

const tabs = [
  { name: 'Agents', href: '/workflows', icon: Bot },
  { name: 'Skills', href: '/workflows/skills', icon: Sparkles },
  { name: 'Automations', href: '/workflows/automations', icon: RefreshCw },
];

const filterOptions: { value: WorkflowSourceFilter; label: string; icon?: typeof Puzzle }[] = [
  { value: 'all', label: 'All' },
  { value: 'custom', label: 'Custom' },
  { value: 'extension', label: 'From Extensions', icon: Puzzle },
];

export function WorkflowsLayout() {
  const location = useLocation();
  const [sourceFilter, setSourceFilter] = useState<WorkflowSourceFilter>('all');

  // Determine which tab is active — /workflows and /workflows/agents/* both map to Agents
  const isAgentsActive = location.pathname === '/workflows' || location.pathname.startsWith('/workflows/agents');
  const isSkillsActive = location.pathname.startsWith('/workflows/skills');
  const isAutomationsActive = location.pathname.startsWith('/workflows/automations');

  const getIsActive = (href: string) => {
    if (href === '/workflows') return isAgentsActive;
    if (href === '/workflows/skills') return isSkillsActive;
    if (href === '/workflows/automations') return isAutomationsActive;
    return false;
  };

  // Hide the tab bar on the create agent page
  const isCreatePage = location.pathname === '/workflows/agents/new';

  return (
    <WorkflowFilterContext.Provider value={sourceFilter}>
      <div className="flex flex-col h-full">
        {/* Page Header */}
        <div className="px-6 pt-6 pb-4">
          {!isCreatePage && (
            <>
              <div className="mb-4">
                <div className="flex items-center gap-3 mb-1">
                  <div
                    className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center shrink-0"
                    style={{ boxShadow: 'var(--shadow-color-violet)' }}
                  >
                    <Network className="size-4 text-[var(--color-text-inverse)]" />
                  </div>
                  <div>
                    <h1 className="mb-0">Workflows</h1>
                    <p className="text-sm text-muted-foreground">
                      Build agents, teach them skills, and deploy automations
                    </p>
                  </div>
                </div>
              </div>

              {/* Tab Navigation + Source Filter */}
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-1 p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] w-fit">
                  {tabs.map((tab) => {
                    const active = getIsActive(tab.href);
                    return (
                      <Link
                        key={tab.name}
                        to={tab.href}
                        className={cn(
                          "flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] transition-all text-sm",
                          active
                            ? "bg-[var(--color-bg-elevated)] text-foreground shadow-sm"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                        style={{
                          transitionTimingFunction: 'var(--ease-default)',
                          transitionDuration: 'var(--duration-fast)',
                        }}
                      >
                        <tab.icon className="size-4" />
                        <span>{tab.name}</span>
                      </Link>
                    );
                  })}
                </div>

                {/* Source Filter */}
                <div className="flex items-center gap-1.5">
                  <ListFilter className="size-3.5 text-muted-foreground" />
                  <div className="flex items-center gap-0.5 p-0.5 rounded-[var(--radius-sm)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)]">
                    {filterOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setSourceFilter(opt.value)}
                        className={cn(
                          "px-2.5 py-1 rounded-[var(--radius-sm)] text-xs transition-all flex items-center gap-1",
                          sourceFilter === opt.value
                            ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)]"
                            : "text-muted-foreground hover:text-foreground hover:bg-[var(--color-bg-secondary)]"
                        )}
                      >
                        {opt.icon && <opt.icon className="size-3" />}
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Content */}
        <div className={`flex-1 overflow-auto ${isAutomationsActive ? 'max-w-none' : ''}`}>
          <Outlet />
        </div>
      </div>
    </WorkflowFilterContext.Provider>
  );
}