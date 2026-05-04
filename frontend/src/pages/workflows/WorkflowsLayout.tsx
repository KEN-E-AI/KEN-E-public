import type { ReactNode } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Bot, Sparkles, RefreshCw, Network } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type WorkflowTab = "agents" | "automations" | "skills";

export type WorkflowsLayoutProps = {
  activeTab: WorkflowTab;
  children: ReactNode;
};

const tabs = [
  { value: "agents" as const, name: "Agents", icon: Bot },
  { value: "skills" as const, name: "Skills", icon: Sparkles },
  { value: "automations" as const, name: "Automations", icon: RefreshCw },
];

const ALLOWED_TABS: readonly WorkflowTab[] = [
  "agents",
  "skills",
  "automations",
];

export function WorkflowsLayout({ activeTab, children }: WorkflowsLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isCreatePage = location.pathname === "/workflows/agents/new";

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
                  Build agents, teach them skills, and deploy automations
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
                navigate(`/workflows/${value}`);
              }
            }}
          >
            <TabsList className="p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] w-fit h-auto gap-0">
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] text-sm font-medium border-0 bg-transparent shadow-none data-[state=active]:bg-[var(--color-bg-elevated)] data-[state=active]:text-foreground data-[state=active]:shadow-sm data-[state=active]:border-0 data-[state=inactive]:text-muted-foreground data-[state=inactive]:bg-transparent data-[state=inactive]:border-0 data-[state=inactive]:shadow-none"
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

      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
