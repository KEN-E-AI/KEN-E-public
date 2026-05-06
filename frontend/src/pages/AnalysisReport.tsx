import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import ChannelControlsSnapshot from "@/components/dashboard/ChannelControlsSnapshot";
import { ChevronUp, ChevronDown, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

const AnalysisReport = () => {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const [selectedTab, setSelectedTab] = useState("Awareness");
  const [selectedChannel, setSelectedChannel] = useState("Overview");
  const [selectedTactic, setSelectedTactic] = useState("");
  const [dateRange, setDateRange] = useState({
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  });
  const [comparisonDateRange, setComparisonDateRange] = useState<
    | {
        from: Date;
        to: Date;
      }
    | undefined
  >(undefined);

  const [expandedAnalysis, setExpandedAnalysis] = useState<string | null>(null);
  const [expandedRecommendation, setExpandedRecommendation] = useState<
    string | null
  >(null);

  // Sample report data - in a real app, this would be fetched based on reportId
  const reportData = {
    "1": {
      name: "Q1 Campaign Performance Analysis",
      type: "Scheduled",
      dateRange: "Jan 1, 2025 - Jan 8, 2025",
      objective: "Awareness",
      channel: "Social",
      createdDate: "Jan 9, 2025",
      status: "Completed",
    },
    "2": {
      name: "Email Marketing Deep Dive",
      type: "Ad hoc",
      dateRange: "Dec 15, 2024 - Jan 15, 2025",
      objective: "Conversion",
      channel: "Email",
      createdDate: "Jan 8, 2025",
      status: "In Progress",
    },
    "3": {
      name: "Search Campaign Optimization",
      type: "Scheduled",
      dateRange: "Jan 1, 2025 - Jan 31, 2025",
      objective: "Consideration",
      channel: "Search",
      createdDate: "Jan 7, 2025",
      status: "Completed",
    },
    "4": {
      name: "Cross-Channel Attribution Study",
      type: "Ad hoc",
      dateRange: "Dec 1, 2024 - Dec 31, 2024",
      objective: "All",
      channel: "All",
      createdDate: "Jan 5, 2025",
      status: "Completed",
    },
    "5": {
      name: "Customer Loyalty Analysis",
      type: "Scheduled",
      dateRange: "Jan 1, 2025 - Jan 14, 2025",
      objective: "Loyalty",
      channel: "Email",
      createdDate: "Jan 3, 2025",
      status: "Completed",
    },
    "6": {
      name: "Social Media ROI Assessment",
      type: "Ad hoc",
      dateRange: "Jan 8, 2025 - Jan 15, 2025",
      objective: "Awareness",
      channel: "Social",
      createdDate: "Jan 2, 2025",
      status: "Draft",
    },
  };

  const currentReport =
    reportData[reportId as keyof typeof reportData] || reportData["1"];

  // Sample analysis items
  const analysisItems = [
    {
      id: "1",
      title:
        "Brand mentions increased significantly across social media platforms",
      description:
        "Organic reach and engagement metrics show 45% improvement over previous period.",
      content:
        "Our analysis shows a significant increase in brand mentions and user-generated content across social media platforms. This correlates with the recent product launch campaign and influencer partnerships initiated during this period. Engagement rates have improved by 45% with particularly strong performance on Instagram and Twitter.",
    },
    {
      id: "2",
      title:
        "Cost per acquisition decreased while maintaining conversion quality",
      description:
        "Optimization efforts resulted in 23% more efficient ad spend allocation.",
      content:
        "Through strategic bid adjustments and audience refinement, we achieved a 23% reduction in cost per acquisition while maintaining conversion quality. The optimization focused on high-performing demographics and geographic regions, resulting in more efficient budget allocation across campaigns.",
    },
  ];

  // Sample recommendation items
  const recommendationItems = [
    {
      id: "1",
      title: "Increase budget allocation to top-performing social channels",
      description:
        "Redirect 15% of display budget to social media campaigns showing strong ROI.",
      content:
        "Based on the performance data, we recommend reallocating 15% of the current display advertising budget to social media campaigns. Instagram Stories and Twitter promoted posts are showing 3x higher engagement rates and 40% lower cost per acquisition compared to traditional display advertising.",
    },
    {
      id: "2",
      title: "Implement automated bid optimization for search campaigns",
      description:
        "Deploy machine learning algorithms to optimize bids in real-time.",
      content:
        "Implementing automated bid optimization can further improve campaign efficiency. Our analysis suggests that real-time bid adjustments based on conversion probability could increase overall campaign performance by an estimated 18-25% while reducing manual management overhead.",
    },
  ];

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Analysis Report</h1>
      </header>
      <div className="space-y-6">
        {/* Back to Performance Link */}
        <div className="mb-4 flex flex-col">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/performance")}
            className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] p-0 h-auto font-normal mr-auto"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Performance
          </Button>
        </div>

        {/* Report Header */}
        <div className="bg-[var(--color-bg-elevated)] rounded-lg px-6 pt-6 pb-5 border border-[var(--color-border-default)]">
          {/* Report Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <div>
              <span className="text-sm font-medium text-[var(--color-text-tertiary)]">
                Type
              </span>
              <div className="mt-1">
                <Badge
                  variant={
                    currentReport.type === "Scheduled" ? "default" : "secondary"
                  }
                >
                  {currentReport.type}
                </Badge>
              </div>
            </div>
            <div>
              <span className="text-sm font-medium text-[var(--color-text-tertiary)]">
                Date Range
              </span>
              <p className="mt-1 text-sm text-[var(--color-text-primary)]">
                {currentReport.dateRange}
              </p>
            </div>
            <div>
              <span className="text-sm font-medium text-[var(--color-text-tertiary)]">
                Objective
              </span>
              <p className="mt-1 text-sm text-[var(--color-text-primary)]">
                {currentReport.objective}
              </p>
            </div>
            <div>
              <span className="text-sm font-medium text-[var(--color-text-tertiary)]">
                Channel
              </span>
              <p className="mt-1 text-sm text-[var(--color-text-primary)]">
                {currentReport.channel}
              </p>
            </div>
            <div>
              <span className="text-sm font-medium text-[var(--color-text-tertiary)]">
                Creation Date
              </span>
              <p className="mt-1 text-sm text-[var(--color-text-primary)]">
                {currentReport.createdDate}
              </p>
            </div>
          </div>
        </div>

        {/* Marketing Strategies Snapshot */}
        <ChannelControlsSnapshot />

        {/* Analysis Section */}
        <div className="mt-6">
          <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] border-b border-[var(--color-border-strong)] pb-2 mb-6 text-left">
            Analysis
          </h2>

          <div>
            <div>
              {analysisItems.map((item) => (
                <div
                  key={item.id}
                  className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg overflow-hidden mb-4"
                >
                  <button
                    className="w-full px-6 py-4 text-left transition-colors hover:bg-[var(--color-bg-secondary)]"
                    onClick={() =>
                      setExpandedAnalysis(
                        expandedAnalysis === item.id ? null : item.id,
                      )
                    }
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="font-medium text-[var(--color-text-primary)] mb-1">
                          {item.title}
                        </h3>
                        <p className="text-sm text-[var(--color-text-tertiary)]">
                          {item.description}
                        </p>
                      </div>
                      <div className="ml-4">
                        {expandedAnalysis === item.id ? (
                          <ChevronUp className="h-5 w-5 text-[var(--color-text-disabled)]" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-[var(--color-text-disabled)]" />
                        )}
                      </div>
                    </div>
                  </button>
                  {expandedAnalysis === item.id && (
                    <div className="border-t border-[var(--color-border-subtle)] px-6 pb-6">
                      <div className="pt-4">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                          <div>
                            <h4 className="font-medium text-[var(--color-text-primary)] mb-3">
                              <span>Sessions with PDP View</span>
                              <span className="text-[var(--color-text-tertiary)]">
                                {" "}
                                [google analytics]
                              </span>
                            </h4>
                            <p className="text-[var(--color-text-secondary)] mb-4">
                              {item.content}
                            </p>
                          </div>
                          <div className="bg-[var(--color-bg-secondary)] rounded-lg p-4">
                            <div className="h-40">
                              {/* Placeholder chart area */}
                              <div className="w-full h-full bg-[var(--color-bg-elevated)] rounded flex items-center justify-center">
                                <span className="text-[var(--color-text-tertiary)] text-sm">
                                  Chart visualization
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recommendations Section */}
        <div className="mt-6">
          <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] border-b border-[var(--color-border-strong)] pb-2 mb-6 text-left">
            Recommendations
          </h2>

          <div>
            <div>
              {recommendationItems.map((item) => (
                <div
                  key={item.id}
                  className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg overflow-hidden mb-4"
                >
                  <button
                    className="w-full px-6 py-4 text-left transition-colors hover:bg-[var(--color-bg-secondary)]"
                    onClick={() =>
                      setExpandedRecommendation(
                        expandedRecommendation === item.id ? null : item.id,
                      )
                    }
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="font-medium text-[var(--color-text-primary)] mb-1">
                          {item.title}
                        </h3>
                        <p className="text-sm text-[var(--color-text-tertiary)]">
                          {item.description}
                        </p>
                      </div>
                      <div className="ml-4">
                        {expandedRecommendation === item.id ? (
                          <ChevronUp className="h-5 w-5 text-[var(--color-text-disabled)]" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-[var(--color-text-disabled)]" />
                        )}
                      </div>
                    </div>
                  </button>
                  {expandedRecommendation === item.id && (
                    <div className="border-t border-[var(--color-border-subtle)] px-6 pb-6">
                      <div className="pt-4">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                          <div>
                            <h4 className="font-medium text-[var(--color-text-primary)] mb-3">
                              <span>Implementation Strategy</span>
                              <span className="text-[var(--color-text-tertiary)]">
                                {" "}
                                [recommendation details]
                              </span>
                            </h4>
                            <p className="text-[var(--color-text-secondary)] mb-4">
                              {item.content}
                            </p>
                          </div>
                          <div className="bg-[var(--color-bg-secondary)] rounded-lg p-4">
                            <div className="h-40">
                              {/* Placeholder chart area */}
                              <div className="w-full h-full bg-[var(--color-bg-elevated)] rounded flex items-center justify-center">
                                <span className="text-[var(--color-text-tertiary)] text-sm">
                                  Impact projection
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default AnalysisReport;
