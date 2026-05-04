import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Clock, RefreshCw, FileOutput } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type AutomationTab = "overview" | "outputs";

export function AutomationDetailsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<AutomationTab>("overview");

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 px-6 py-4 border-b border-[var(--color-border-default)] bg-card">
        <div className="flex items-center gap-3 mb-2">
          <button
            onClick={() => navigate("/workflows/automations")}
            aria-label="Back to automations"
            className="p-1.5 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] transition-colors"
          >
            <ArrowLeft className="size-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-lg truncate">Sample Automation</h1>
              <Badge variant="success">Active</Badge>
            </div>
            <div className="flex items-center gap-4 mt-1">
              <span className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                <Clock className="size-3" />
                Every day at 9:00 AM
              </span>
              <span className="flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                <RefreshCw className="size-3" />
                Last run: Jan 15
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as AutomationTab)}
        >
          <TabsList className="mb-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="outputs">Outputs</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <div
              className={cn(
                "flex flex-col items-center justify-center rounded-[var(--radius-lg)]",
                "border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]",
                "p-12 text-center min-h-[300px]",
              )}
            >
              <p className="text-[var(--color-text-secondary)] mb-2">
                DAG renders here
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)]">
                Visual editor coming soon.
              </p>
            </div>
          </TabsContent>

          <TabsContent value="outputs">
            <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
              <div className="rounded-full bg-[var(--color-bg-secondary)] p-6 mb-4">
                <FileOutput className="size-8 text-[var(--color-text-tertiary)]" />
              </div>
              <h3 className="mb-2">No outputs yet</h3>
              <p className="text-[var(--color-text-tertiary)] max-w-md">
                Run this automation to generate outputs.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
