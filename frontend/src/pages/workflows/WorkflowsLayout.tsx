import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Bot, Sparkles, RefreshCw, Network } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type WorkflowTab = "agents" | "automations" | "skills";

export type WorkflowsLayoutProps = {
  activeTab: WorkflowTab;
  children: ReactNode;
};

const tabs = [
  { value: "automations" as const, name: "Automations", icon: RefreshCw },
  { value: "agents" as const, name: "Agents", icon: Bot },
  { value: "skills" as const, name: "Skills", icon: Sparkles },
];

const ALLOWED_TABS: readonly WorkflowTab[] = [
  "automations",
  "agents",
  "skills",
];

// Persists focus-restoration intent across the unmount/remount cycle caused by
// React Router navigation. Set before navigate(), cleared after focus is restored.
let pendingFocusTab: WorkflowTab | null = null;

export function WorkflowsLayout({ activeTab, children }: WorkflowsLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isCreatePage = location.pathname === "/workflows/agents/new";

  // Refs for each tab trigger — indexed to match the `tabs` array order.
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // After React Router navigation remounts this component with a new activeTab,
  // restore keyboard focus to the newly-active tab trigger so arrow-key users
  // retain their position in the tab strip (WCAG 2.4.3 Focus Order).
  //
  // No unmount-cleanup effect clears pendingFocusTab: React runs unmounted
  // components' cleanup effects *before* newly mounted components' setup effects,
  // so a cleanup here would erase the value before the new instance can read it.
  // A stale value across unrelated navigations is benign — it only fires when
  // pendingFocusTab === activeTab, meaning focus lands on the current active tab.
  useEffect(() => {
    if (pendingFocusTab === activeTab) {
      pendingFocusTab = null;
      const idx = tabs.findIndex((t) => t.value === activeTab);
      if (idx >= 0) tabRefs.current[idx]?.focus();
    }
  }, [activeTab]);

  return (
    <div className="flex flex-col h-full">
      {!isCreatePage && (
        <div className="px-6 pt-6 pb-4">
          <div className="mb-4">
            <div className="flex items-center gap-3 mb-1">
              <div
                className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center shrink-0"
                style={{ boxShadow: "var(--shadow-color-violet)" }}
              >
                <Network className="size-4 text-[var(--color-text-inverse)]" />
              </div>
              <div>
                <h1 className="mb-0">Workflows</h1>
                <p className="text-sm text-muted-foreground">
                  Build specialized agents and have them complete tasks on a
                  schedule.
                </p>
              </div>
            </div>
          </div>

          <Tabs
            value={activeTab}
            onValueChange={(value) => {
              if (
                value !== activeTab &&
                (ALLOWED_TABS as string[]).includes(value)
              ) {
                pendingFocusTab = value as WorkflowTab;
                navigate(`/workflows/${value}`);
              }
            }}
          >
            <TabsList className="p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] w-fit h-auto gap-0">
              {tabs.map((tab, i) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  // Override Radix's React useId()-generated IDs (which contain colons
                  // that break axe-core's CSS-selector-based aria-controls validation).
                  id={`workflows-tab-${tab.value}`}
                  aria-controls={`workflows-panel-${tab.value}`}
                  ref={(el) => {
                    tabRefs.current[i] = el;
                  }}
                  className="flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] text-sm font-medium border-0 bg-transparent shadow-none data-[state=active]:bg-[var(--color-surface-muted)] data-[state=active]:text-foreground data-[state=active]:shadow-sm data-[state=active]:border-0 data-[state=inactive]:text-[var(--color-text-secondary)] data-[state=inactive]:bg-transparent data-[state=inactive]:border-0 data-[state=inactive]:shadow-none"
                  style={{
                    transitionTimingFunction: "var(--ease-default)",
                    transitionDuration: "var(--duration-fast)",
                  }}
                >
                  <tab.icon className="size-4" />
                  <span>{tab.name}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
      )}

      {isCreatePage ? (
        // Create-page layout has no tab chrome — plain container, no tabpanel semantics.
        <div className="flex-1 overflow-auto">{children}</div>
      ) : (
        // Three tabpanel divs: one active (visible, contains children), two hidden.
        // All three must exist so each trigger's aria-controls resolves to a real element.
        tabs.map((tab) => (
          <div
            key={tab.value}
            id={`workflows-panel-${tab.value}`}
            role="tabpanel"
            aria-labelledby={`workflows-tab-${tab.value}`}
            hidden={tab.value !== activeTab}
            className={
              tab.value === activeTab ? "flex-1 overflow-auto" : undefined
            }
          >
            {tab.value === activeTab ? children : null}
          </div>
        ))
      )}
    </div>
  );
}
