import { useState, useEffect } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer } from "recharts";
import RecommendationsSection from "./RecommendationsSection";

interface AnalysisItem {
  id: string;
  title: string;
  summary: string;
  detailed: string;
  chartData?: Array<{ date: string; value: number }>;
  source?: string;
}

interface AnalysisSectionProps {
  effectivenessKPI: string;
  efficiencyKPI: string;
  dateRange: {
    from: Date;
    to: Date;
  };
}

const analysisItems: AnalysisItem[] = [
  {
    id: "1",
    title:
      "Your brand or products are featured or referenced in news and press outlets",
    summary:
      "Some unknown activity made a positive impact on number of sessions with a pdp view.",
    detailed:
      "Our analysis shows a significant increase in sessions that included product detail page views, indicating heightened interest in specific products. This correlates with recent press coverage and mentions across various media outlets.",
    chartData: [
      { date: "23 Nov", value: 50000 },
      { date: "24", value: 52000 },
      { date: "25", value: 55000 },
      { date: "26", value: 58000 },
      { date: "27", value: 62000 },
      { date: "28", value: 65000 },
      { date: "29", value: 67000 },
      { date: "30", value: 68500 },
    ],
    source: "google analytics",
  },
  {
    id: "2",
    title: "Competitor's are driving up ad costs",
    summary:
      "Increased competition in key advertising channels is affecting cost efficiency.",
    detailed:
      "Market analysis indicates that competitor activity has intensified, particularly in search and display advertising, leading to increased CPCs and CPMs across all channels.",
  },
  {
    id: "3",
    title: "Something else happened",
    summary: "Additional insights discovered during data analysis.",
    detailed:
      "Further investigation reveals other factors that may be influencing campaign performance and user behavior patterns.",
  },
  {
    id: "4",
    title: "Oh snap, then something else happened too!",
    summary: "More unexpected findings from the data analysis.",
    detailed:
      "Continued monitoring has uncovered additional trends and patterns that warrant attention and potential action.",
  },
];

const AnalysisSection = ({
  effectivenessKPI,
  efficiencyKPI,
  dateRange,
}: AnalysisSectionProps) => {
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [isAnalysisVisible, setIsAnalysisVisible] = useState(false);
  const [hasDateRangeChanged, setHasDateRangeChanged] = useState(false);
  const [lastAnalyzedDateRange, setLastAnalyzedDateRange] = useState<{
    from: Date;
    to: Date;
  } | null>(null);

  // Check if both KPIs are selected (not empty strings)
  const canShowAnalyzeButton = effectivenessKPI && efficiencyKPI;

  // Track date range changes
  useEffect(() => {
    if (lastAnalyzedDateRange && isAnalysisVisible) {
      const dateRangeChanged =
        dateRange.from.getTime() !== lastAnalyzedDateRange.from.getTime() ||
        dateRange.to.getTime() !== lastAnalyzedDateRange.to.getTime();

      if (dateRangeChanged) {
        setHasDateRangeChanged(true);
        setIsAnalysisVisible(false);
      }
    }
  }, [dateRange, lastAnalyzedDateRange, isAnalysisVisible]);

  const handleAnalyzeClick = () => {
    setIsAnalysisVisible(true);
    setHasDateRangeChanged(false);
    setLastAnalyzedDateRange({ ...dateRange });
  };

  const getButtonText = () => {
    return hasDateRangeChanged
      ? "Re-analyze Funnel Step for new Date Range"
      : "Analyze Funnel Step";
  };

  const shouldShowButton =
    canShowAnalyzeButton && (!isAnalysisVisible || hasDateRangeChanged);

  const toggleItem = (id: string) => {
    setExpandedItem(expandedItem === id ? null : id);
  };

  const chartConfig = {
    value: {
      color: "#3b82f6",
    },
  };

  return (
    <div>
      <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] mb-6 border-b border-[var(--color-border-strong)] pb-2">
        Analysis
      </h2>

      {shouldShowButton && (
        <div className="mb-6 text-center">
          <Button
            onClick={handleAnalyzeClick}
            className="bg-[var(--color-text-primary)] text-white hover:bg-[var(--color-text-secondary)]"
          >
            {getButtonText()}
          </Button>
        </div>
      )}

      {isAnalysisVisible && (
        <div className="space-y-8">
          {/* Analysis Items */}
          <div className="space-y-4">
            {analysisItems.map((item, index) => (
              <div
                key={item.id}
                className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg overflow-hidden"
              >
                {/* Collapsed Header */}
                <button
                  className="w-full px-6 py-4 text-left hover:bg-[var(--color-bg-secondary)] transition-colors"
                  onClick={() => toggleItem(item.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <h3 className="font-medium text-[var(--color-text-primary)] mb-1">
                        {item.title}
                      </h3>
                      <p className="text-sm text-[var(--color-text-tertiary)]">
                        {item.summary}
                      </p>
                    </div>
                    <div className="ml-4">
                      {expandedItem === item.id ? (
                        <ChevronUp className="h-5 w-5 text-[var(--color-text-disabled)]" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-[var(--color-text-disabled)]" />
                      )}
                    </div>
                  </div>
                </button>

                {/* Expanded Content */}
                {expandedItem === item.id && (
                  <div className="px-6 pb-6 border-t border-[var(--color-border-subtle)]">
                    <div className="pt-4">
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Detailed Description */}
                        <div>
                          <h4 className="font-medium text-[var(--color-text-primary)] mb-3">
                            Sessions with PDP View{" "}
                            {item.source && `[${item.source}]`}
                          </h4>
                          <p className="text-[var(--color-text-secondary)] mb-4">
                            {item.detailed}
                          </p>
                        </div>

                        {/* Chart */}
                        {item.chartData && (
                          <div className="bg-[var(--color-bg-secondary)] p-4 rounded-lg">
                            <div className="h-40">
                              <ChartContainer
                                config={chartConfig}
                                className="h-full w-full"
                              >
                                <LineChart
                                  width={400}
                                  height={160}
                                  data={item.chartData}
                                  margin={{
                                    top: 5,
                                    right: 5,
                                    left: 5,
                                    bottom: 5,
                                  }}
                                >
                                  <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: "#64748b" }}
                                  />
                                  <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: "#64748b" }}
                                  />
                                  <ChartTooltip
                                    content={<ChartTooltipContent />}
                                  />
                                  <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="var(--color-value)"
                                    strokeWidth={2}
                                    dot={{
                                      fill: "var(--color-value)",
                                      strokeWidth: 2,
                                      r: 4,
                                    }}
                                  />
                                </LineChart>
                              </ChartContainer>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Action Buttons */}
                      <div className="flex flex-wrap gap-3 mt-6">
                        <Button
                          variant="outline"
                          size="sm"
                          className="bg-[var(--color-text-primary)] text-white hover:bg-[var(--color-text-secondary)] border-[var(--color-border-strong)]"
                        >
                          Log Activity
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="bg-[var(--color-text-primary)] text-white hover:bg-[var(--color-text-secondary)] border-[var(--color-border-strong)]"
                        >
                          Add Intuition
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="bg-[var(--color-text-primary)] text-white hover:bg-[var(--color-text-secondary)] border-[var(--color-border-strong)]"
                        >
                          Create Insight
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Recommendations Section */}
          <RecommendationsSection />
        </div>
      )}
    </div>
  );
};

export default AnalysisSection;
