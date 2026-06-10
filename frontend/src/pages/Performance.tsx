import { TrendingUp } from "lucide-react";
import { DashboardsSection } from "@/components/dashboard/DashboardsSection";

// The Performance page is a multi-tab surface in the design (Analysis,
// Dashboards, Simulations, Goals, Diagnostics, Config). Only the Dashboards
// tab is built today; the remaining tabs (and the tab selector) arrive with
// their backing projects in Release 2, so the page renders the Dashboards
// surface directly for now.
export default function Performance() {
  return (
    <div className="flex flex-col h-full">
      {/* Page Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center gap-3">
          <div
            className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center"
            style={{ boxShadow: "var(--shadow-color-violet)" }}
          >
            <TrendingUp className="size-4 text-[var(--color-text-inverse)]" />
          </div>
          <div>
            <h1>Performance</h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              AI-powered analysis of your marketing KPIs with actionable
              recommendations.
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <DashboardsSection />
      </div>
    </div>
  );
}
