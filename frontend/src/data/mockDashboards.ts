import type { Brand } from "@/lib/branded-types";

export type DashboardId = Brand<string, "DashboardId">;

/**
 * Card-facing summary of a scheduled dashboard. Mirrors the subset of the
 * figma-export `Workflow` shape that the Dashboards list renders. DB-PRD-02
 * replaces this mock with the real `/api/v1/dashboards` data in Release 2.
 */
export type DashboardSummary = {
  id: DashboardId;
  name: string;
  schedule: string;
  lastRun: Date;
  description?: string;
  isActive?: boolean;
};

const id = (value: string): DashboardId => value as DashboardId;

// A single placeholder dashboard until DB-PRD-02 wires real data in Release 2.
export const mockDashboards: DashboardSummary[] = [
  {
    id: id("1"),
    name: "Weekly Performance Digest",
    schedule: "Every Monday 9:00 AM",
    lastRun: new Date(2026, 1, 10, 9, 0),
    description:
      "Automated weekly report with key marketing metrics and channel breakdowns",
    isActive: true,
  },
];
