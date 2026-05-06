import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  color: "effectiveness" | "efficiency";
  metric: {
    name: string;
    description: string;
    value: string;
    change: string;
    changeLabel: string;
    isPositive: boolean;
  };
  chartData: Array<{ month: string; value: number }>;
}

const MetricCard = ({ title, color, metric, chartData }: MetricCardProps) => {
  const colorClasses = {
    effectiveness: {
      header: "bg-effectiveness text-effectiveness-foreground",
      changeText: "text-effectiveness",
      chart: "#000000",
    },
    efficiency: {
      header: "bg-efficiency text-efficiency-foreground",
      changeText: "text-efficiency",
      chart: "#000000",
    },
  };

  const currentColor = colorClasses[color];

  const chartConfig = {
    value: {
      color: currentColor.chart,
    },
  };

  return (
    <div className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className={cn("px-6 py-3", currentColor.header)}>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-current opacity-80" />
          <h3 className="font-semibold text-sm tracking-wide">{title}</h3>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {/* Metric Info */}
        <div className="mb-6">
          <div className="flex items-start gap-2 mb-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="p-0 h-auto ml-auto"
                  >
                    <HelpCircle className="h-4 w-4 text-[var(--color-text-disabled)]" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="max-w-sm">{metric.description}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <div>
              <h4 className="font-medium text-[var(--color-text-primary)]">
                {metric.name}
              </h4>
              <p className="text-sm text-[var(--color-text-tertiary)] max-w-sm mt-1">
                {metric.description}
              </p>
            </div>
          </div>

          {/* Value and Change */}
          <div className="mt-4">
            <div className="text-3xl font-bold text-[var(--color-text-primary)] mb-2 text-center">
              {metric.value}
            </div>
            <div
              className={cn(
                "text-sm text-center",
                metric.isPositive ? "text-effectiveness" : "text-efficiency",
              )}
            >
              {metric.change}
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="h-32">
          <ChartContainer
            config={chartConfig}
            className="h-full w-full pr-[9px]"
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
              >
                <XAxis
                  dataKey="month"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: "#64748b" }}
                />
                <YAxis hide />
                <ChartTooltip
                  content={<ChartTooltipContent hideLabel />}
                  cursor={false}
                />
                <Bar
                  dataKey="value"
                  fill={`var(--color-value)`}
                  radius={[2, 2, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        </div>
      </div>
    </div>
  );
};

export default MetricCard;
