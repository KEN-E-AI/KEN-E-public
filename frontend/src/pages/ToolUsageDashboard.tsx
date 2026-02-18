import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart3, CheckCircle, XCircle, Wrench } from "lucide-react";
import {
  getToolUsage,
  type ToolUsageAggregation,
  type ToolBreakdown,
} from "@/services/toolUsageService";

type ToolRow = { name: string } & ToolBreakdown;

const DATE_RANGE_OPTIONS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
] as const;

const ToolUsageDashboard = () => {
  const navigate = useNavigate();
  const { isSuperAdmin } = useAuth();
  const [days, setDays] = useState(30);

  if (!isSuperAdmin) {
    navigate("/settings");
    return null;
  }

  const { data, isLoading, error } = useQuery<ToolUsageAggregation>({
    queryKey: ["tool-usage", days],
    queryFn: () => getToolUsage(days),
    staleTime: 5 * 60 * 1000,
  });

  const toolRows: ToolRow[] = data
    ? Object.entries(data.by_tool)
        .map(([name, breakdown]) => ({ name, ...breakdown }))
        .sort((a, b) => b.calls - a.calls)
    : [];

  return (
    <SettingsLayout
      pageTitle="Tool Usage"
      currentPage="admin"
      showBackButton={true}
      showEntitySelector={false}
      showContextSidebar={false}
    >
      {/* Date range selector */}
      <div className="flex items-center gap-2 mb-6">
        {DATE_RANGE_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant={days === opt.value ? "default" : "outline"}
            size="sm"
            onClick={() => setDays(opt.value)}
          >
            {opt.label}
          </Button>
        ))}
      </div>

      {error && (
        <p className="text-destructive">
          Failed to load tool usage data. Please try again.
        </p>
      )}

      {isLoading && (
        <div className="grid gap-4 md:grid-cols-3 mb-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 md:grid-cols-3 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Invocations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-brand-medium-blue" />
                  <span className="text-2xl font-bold">
                    {data.total_calls.toLocaleString()}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Success Rate
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <span className="text-2xl font-bold">
                    {(data.success_rate * 100).toFixed(1)}%
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Active Tools
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Wrench className="h-5 w-5 text-brand-medium-blue" />
                  <span className="text-2xl font-bold">
                    {Object.keys(data.by_tool).length}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Tool breakdown table */}
          <Card>
            <CardHeader>
              <CardTitle>Tool Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              {toolRows.length === 0 ? (
                <p className="text-muted-foreground py-4 text-center">
                  No tool usage data for this period.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tool Name</TableHead>
                      <TableHead className="text-right">Calls</TableHead>
                      <TableHead className="text-right">Success</TableHead>
                      <TableHead className="text-right">Failures</TableHead>
                      <TableHead className="text-right">Success Rate</TableHead>
                      <TableHead className="text-right">Avg Duration</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {toolRows.map((row) => (
                      <TableRow key={row.name}>
                        <TableCell className="font-medium">
                          {row.name}
                        </TableCell>
                        <TableCell className="text-right">
                          {row.calls.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right text-green-600">
                          {row.success.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right text-destructive">
                          {row.failure > 0 ? row.failure.toLocaleString() : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {(row.success_rate * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {row.avg_duration_ms != null
                            ? `${Math.round(row.avg_duration_ms)}ms`
                            : "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Failure summary */}
          {data.failure_count > 0 && (
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-destructive">
                  <XCircle className="h-5 w-5" />
                  Failures ({data.failure_count})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1 text-sm">
                  {Object.entries(data.by_status)
                    .filter(([s]) => s !== "success")
                    .map(([statusName, count]) => (
                      <div key={statusName} className="flex justify-between">
                        <span className="capitalize">{statusName}</span>
                        <span className="font-medium">{count}</span>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </SettingsLayout>
  );
};

export default ToolUsageDashboard;
