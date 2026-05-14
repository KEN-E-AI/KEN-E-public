import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Info,
  Calendar,
  Edit3,
  Search,
  Filter,
  Database,
  BarChart3,
  FileText,
  Clock,
  Target,
  Mail,
  MousePointer,
  Users,
  Heart,
  Pencil,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";

const Performance = () => {
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

  const [selectedMetric, setSelectedMetric] = useState("Income");
  const [editMetricsOpen, setEditMetricsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("all");
  const [selectedProduct, setSelectedProduct] = useState("all");

  // Selected KPIs state
  const [selectedKPIs, setSelectedKPIs] = useState({
    income: "Total Revenue",
    netIncome: "Net Profit",
    marketingCost: "Marketing Spend Total",
  });

  // Analysis Reports filtering state
  const [reportTypeFilter, setReportTypeFilter] = useState("all");
  const [reportObjectiveFilter, setReportObjectiveFilter] = useState("all");
  const [reportChannelFilter, setReportChannelFilter] = useState("all");

  // Objective selection state
  const [selectedObjective, setSelectedObjective] = useState("1");

  // Objective data (from ChannelControls.tsx line 508)
  const objectiveData = {
    "1": {
      step_name: "awareness",
      objective:
        "Increase the number of prospective customers who are aware of the brand and its unique positioning in the market.",
      effectivenessKPI: "Brand Awareness Lift",
      efficiencyKPI: "Cost Per Impression",
      supportingMetrics: ["Reach", "Frequency", "Video Completion Rate"],
    },
    "2": {
      step_name: "consideration",
      objective:
        "Ensure that customers currently in the market for air purifiers are evaluating products on intellipure.com.",
      effectivenessKPI: "Sessions",
      efficiencyKPI: "Cost Per Click",
      supportingMetrics: [
        "Page Views",
        "Bounce Rate",
        "Average Session Duration",
      ],
    },
    "3": {
      step_name: "conversion",
      objective:
        "Persuade customers visiting intellipure.com to purchase a new unit.",
      effectivenessKPI: "Conversion Rate",
      efficiencyKPI: "Cost Per Acquisition",
      supportingMetrics: [
        "Add to Cart Events",
        "Checkout Events",
        "Average Order Value",
      ],
    },
    "4": {
      step_name: "loyalty",
      objective:
        "Ensure that existing customers continue to purchase filter refills.",
      effectivenessKPI: "Customer Lifetime Value",
      efficiencyKPI: "Cost Per Retained Client",
      supportingMetrics: [
        "Retention Rate",
        "Repeat Purchase Rate",
        "Email Open Rate",
      ],
    },
  };

  // Metric definitions for tooltips
  const metricDefinitions = {
    Income:
      "Total revenue generated from all sources during the selected period",
    "Net Income": "Total income minus all expenses, taxes, and costs",
    "Marketing Cost":
      "Total amount spent on marketing activities and campaigns",
    "Operating Efficiency Ratio (OER)":
      "Ratio measuring how efficiently the company converts inputs into outputs",
    "Marketing Efficiency Ratio (MER)":
      "Ratio of marketing spend to revenue generated from marketing efforts",
    "Marketing Investment Ratio (MIR)":
      "Percentage of total revenue invested back into marketing activities",
  };

  // Available metrics for KPI selection
  const availableMetrics = [
    {
      name: "Total Revenue",
      dataset: "ga4_sessions",
      product: "Google Analytics",
      description: "Sum of all revenue from sessions",
    },
    {
      name: "Net Profit",
      dataset: "financial_data",
      product: "Internal Systems",
      description: "Revenue minus all costs and expenses",
    },
    {
      name: "Marketing Spend Total",
      dataset: "google_ads",
      product: "Google Ads",
      description: "Total advertising spend across all campaigns",
    },
    {
      name: "Session Revenue",
      dataset: "ga4_sessions",
      product: "Google Analytics",
      description: "Revenue attributed to user sessions",
    },
    {
      name: "E-commerce Revenue",
      dataset: "ga4_events",
      product: "Google Analytics",
      description: "Revenue from e-commerce transactions",
    },
    {
      name: "Cost Per Acquisition",
      dataset: "google_ads",
      product: "Google Ads",
      description: "Average cost to acquire a customer",
    },
    {
      name: "Return on Ad Spend",
      dataset: "google_ads",
      product: "Google Ads",
      description: "Revenue generated per dollar spent on ads",
    },
    {
      name: "Lifetime Value",
      dataset: "crm_data",
      product: "CRM System",
      description: "Average customer lifetime value",
    },
    {
      name: "Conversion Value",
      dataset: "ga4_events",
      product: "Google Analytics",
      description: "Value from conversion events",
    },
    {
      name: "Operating Income",
      dataset: "financial_data",
      product: "Internal Systems",
      description: "Income from core business operations",
    },
    {
      name: "Gross Profit",
      dataset: "financial_data",
      product: "Internal Systems",
      description: "Revenue minus cost of goods sold",
    },
    {
      name: "Marketing ROI",
      dataset: "mixed_data",
      product: "Mixed Sources",
      description: "Return on marketing investment",
    },
  ];

  const datasets = [
    "ga4_sessions",
    "ga4_events",
    "google_ads",
    "financial_data",
    "crm_data",
    "mixed_data",
  ];
  const products = [
    "Google Analytics",
    "Google Ads",
    "Internal Systems",
    "CRM System",
    "Mixed Sources",
  ];

  // Filter metrics based on search and filters
  const filteredMetrics = availableMetrics.filter((metric) => {
    const matchesSearch =
      metric.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      metric.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDataset =
      selectedDataset === "all" || metric.dataset === selectedDataset;
    const matchesProduct =
      selectedProduct === "all" || metric.product === selectedProduct;

    return matchesSearch && matchesDataset && matchesProduct;
  });

  // Sample metrics data
  const metrics = [
    {
      name: "Income",
      value: "$31,329",
      change: "+4.4%",
      changeType: "positive" as const,
      subtitle: selectedKPIs.income,
    },
    {
      name: "Net Income",
      value: "$5,198",
      change: "-1.4%",
      changeType: "negative" as const,
      subtitle: selectedKPIs.netIncome,
    },
    {
      name: "Marketing Cost",
      value: "$2,506",
      change: "+8.4%",
      changeType: "negative" as const,
      subtitle: selectedKPIs.marketingCost,
    },
    {
      name: "Operating Efficiency Ratio",
      value: "16.6%",
      change: "+2.4%",
      changeType: "positive" as const,
      subtitle: "OER",
    },
    {
      name: "Marketing Efficiency Ratio",
      value: "32.5%",
      change: "-4.4%",
      changeType: "negative" as const,
      subtitle: "MER",
    },
    {
      name: "Marketing Investment Ratio",
      value: "12.5",
      change: "+4.4%",
      changeType: "positive" as const,
      subtitle: "MIR",
    },
  ];

  const chartButtons = [
    { id: "Income", label: "Income" },
    { id: "Net Income", label: "Net Income" },
    { id: "Cost", label: "Cost" },
    { id: "OER", label: "OER" },
    { id: "MER", label: "MER" },
    { id: "MIR", label: "MIR" },
  ];

  // Sample recommendations data
  const recommendations = [
    {
      id: "1",
      title: "Reallocate display spend",
      summary:
        "Make the following budget adjustments to offset for increased competition:",
      details:
        "Based on recent performance data, your display campaigns are experiencing increased competition which has driven up costs by 23%. To maintain efficiency while preserving reach, we recommend reallocating 15% of your display budget to search campaigns where you have stronger positioning. Additionally, consider adjusting your targeting to focus on higher-intent audiences during peak conversion hours.",
      priority: "high",
    },
    {
      id: "2",
      title: "Optimize email send times",
      summary: "Adjust email campaign timing for better engagement",
      details:
        "Analysis of your email engagement patterns shows that sends on Tuesday and Thursday between 10-11 AM generate 34% higher open rates and 28% higher click-through rates. Your current Wednesday afternoon sends are experiencing declining performance. We recommend shifting your primary sends to these optimal time slots and implementing automated A/B testing for timing optimization.",
      priority: "medium",
    },
    {
      id: "3",
      title: "Increase search budget allocation",
      summary: "Scale successful search campaigns",
      details:
        "Your search campaigns are consistently outperforming targets with a 156% ROAS and impression share opportunity of 23%. There's clear evidence that increased investment would capture additional qualified traffic. We recommend increasing search budget by 25% and expanding to related keyword themes that are currently underfunded.",
      priority: "high",
    },
    {
      id: "4",
      title: "Pause underperforming social campaigns",
      summary: "Discontinue low-performing social initiatives",
      details:
        "Three of your social campaigns have been underperforming for the past 6 weeks with costs 67% above target and conversion rates 43% below benchmark. These campaigns are consuming 18% of your social budget with minimal return. We recommend pausing these campaigns and redistributing budget to your top-performing creative sets.",
      priority: "low",
    },
  ];

  // Sample Analysis Reports data
  const analysisReports = [
    {
      id: "1",
      name: "Q1 Campaign Performance Analysis",
      type: "Scheduled",
      dateRange: "Jan 1, 2025 - Jan 8, 2025",
      objective: "Awareness",
      channel: "Social",
      createdDate: "Jan 9, 2025",
      status: "Completed",
    },
    {
      id: "2",
      name: "Email Marketing Deep Dive",
      type: "Ad hoc",
      dateRange: "Dec 15, 2024 - Jan 15, 2025",
      objective: "Conversion",
      channel: "Email",
      createdDate: "Jan 8, 2025",
      status: "In Progress",
    },
    {
      id: "3",
      name: "Search Campaign Optimization",
      type: "Scheduled",
      dateRange: "Jan 1, 2025 - Jan 31, 2025",
      objective: "Consideration",
      channel: "Search",
      createdDate: "Jan 7, 2025",
      status: "Completed",
    },
    {
      id: "4",
      name: "Cross-Channel Attribution Study",
      type: "Ad hoc",
      dateRange: "Dec 1, 2024 - Dec 31, 2024",
      objective: "All",
      channel: "All",
      createdDate: "Jan 5, 2025",
      status: "Completed",
    },
    {
      id: "5",
      name: "Customer Loyalty Analysis",
      type: "Scheduled",
      dateRange: "Jan 1, 2025 - Jan 14, 2025",
      objective: "Loyalty",
      channel: "Email",
      createdDate: "Jan 3, 2025",
      status: "Completed",
    },
    {
      id: "6",
      name: "Social Media ROI Assessment",
      type: "Ad hoc",
      dateRange: "Jan 8, 2025 - Jan 15, 2025",
      objective: "Awareness",
      channel: "Social",
      createdDate: "Jan 2, 2025",
      status: "Draft",
    },
  ];

  // Filter and sort reports based on selected filters
  const filteredReports = analysisReports
    .filter((report) => {
      const matchesType =
        reportTypeFilter === "all" || report.type === reportTypeFilter;
      const matchesObjective =
        reportObjectiveFilter === "all" ||
        report.objective === reportObjectiveFilter;
      const matchesChannel =
        reportChannelFilter === "all" || report.channel === reportChannelFilter;

      return matchesType && matchesObjective && matchesChannel;
    })
    .sort((a, b) => {
      // Parse start dates from date range strings (format: "Jan 1, 2025 - Jan 8, 2025")
      const getStartDate = (dateRange: string) => {
        const startDateStr = dateRange.split(" - ")[0];
        return new Date(startDateStr);
      };

      const dateA = getStartDate(a.dateRange);
      const dateB = getStartDate(b.dateRange);

      return dateA.getTime() - dateB.getTime(); // Ascending order
    });

  // Navigation handler for reports
  const handleReportClick = (reportId: string) => {
    // Navigate to report details page
    navigate(`/analysis-report/${reportId}`);
  };

  // Delete handler for reports
  const handleDeleteReport = (e: React.MouseEvent, reportId: string) => {
    e.stopPropagation(); // Prevent triggering the report click
    if (
      window.confirm("Are you sure you want to delete this analysis report?")
    ) {
      console.log(`Deleting report: ${reportId}`);
      // In a real app, this would call an API to delete the report
      // For now, we'll just log it
    }
  };

  // Helper function to get objective icon
  const getObjectiveIcon = (objective: string) => {
    switch (objective) {
      case "Awareness":
        return Target;
      case "Consideration":
        return MousePointer;
      case "Conversion":
        return Users;
      case "Loyalty":
        return Heart;
      default:
        return FileText;
    }
  };

  // Helper function to get channel icon
  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case "Email":
        return Mail;
      case "Search":
        return Search;
      case "Social":
        return Users;
      default:
        return BarChart3;
    }
  };

  // Report options for each recommendation
  const getReportOptions = (recommendationId: string) => {
    switch (recommendationId) {
      case "1":
        return [
          "Display Campaign Performance Report",
          "Competitive Analysis Report",
          "Budget Allocation Optimization Report",
          "Cost Per Acquisition Trends Report",
        ];
      case "2":
        return [
          "Email Engagement Analytics Report",
          "Send Time Optimization Report",
          "Subject Line Performance Report",
          "Audience Segmentation Report",
        ];
      case "3":
        return [
          "Search Campaign ROI Report",
          "Keyword Performance Analysis",
          "Impression Share Report",
          "Search Query Analysis Report",
        ];
      case "4":
        return [
          "Social Media Performance Report",
          "Campaign ROI Analysis",
          "Creative Performance Report",
          "Audience Insights Report",
        ];
      default:
        return ["Performance Report", "Analytics Report", "Summary Report"];
    }
  };

  // Handle "Do It For Me" actions
  const handleDoItForMe = (recommendationId: string) => {
    console.log(`Executing recommendation: ${recommendationId}`);
    // In a real app, this would trigger automated actions
  };

  // Handle report selection
  const handleReportSelect = (recommendationId: string, reportName: string) => {
    console.log(
      `Opening report: ${reportName} for recommendation: ${recommendationId}`,
    );
    // In a real app, this would navigate to the specific report
  };

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Performance</h1>
      </header>
      <TooltipProvider>
        <div className="space-y-6">
          <div className="bg-[var(--color-bg-elevated)] rounded-lg p-6 border border-[var(--color-border-default)]">
            {/* Date Range Selector */}
            <div className="mb-6">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                    <Select defaultValue="jan-2025">
                      <SelectTrigger className="w-48 min-w-[12.5rem]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="jan-2025">
                          Jan 1, 2025 - Jan 31, 2025
                        </SelectItem>
                        <SelectItem value="dec-2024">
                          Dec 1, 2024 - Dec 31, 2024
                        </SelectItem>
                        <SelectItem value="nov-2024">
                          Nov 1, 2024 - Nov 30, 2024
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-[var(--color-text-tertiary)]">
                    <span>vs</span>
                    <Select defaultValue="previous-period">
                      <SelectTrigger className="w-40 min-w-[10rem]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="previous-period">
                          Previous Period
                        </SelectItem>
                        <SelectItem value="previous-year">
                          Previous Year
                        </SelectItem>
                        <SelectItem value="custom">Custom Range</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Edit Metrics Button */}
                <Dialog
                  open={editMetricsOpen}
                  onOpenChange={setEditMetricsOpen}
                >
                  <DialogTrigger asChild>
                    <Button variant="outline" size="sm" className="ml-auto">
                      <Edit3 className="h-4 w-4 mr-2" />
                      Edit Metrics
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl">
                    <DialogHeader>
                      <DialogTitle>Edit Metrics Configuration</DialogTitle>
                    </DialogHeader>

                    {/* Search and Filters — search on its own row, filters below */}
                    <div className="space-y-3 mb-6">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-[var(--color-text-disabled)]" />
                        <Input
                          placeholder="Search metrics..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          className="pl-10"
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <Select
                          value={selectedDataset}
                          onValueChange={setSelectedDataset}
                        >
                          <SelectTrigger className="flex-1">
                            <Filter className="h-4 w-4 mr-2 shrink-0" />
                            <SelectValue placeholder="Dataset" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All Datasets</SelectItem>
                            {datasets.map((dataset) => (
                              <SelectItem key={dataset} value={dataset}>
                                {dataset}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Select
                          value={selectedProduct}
                          onValueChange={setSelectedProduct}
                        >
                          <SelectTrigger className="flex-1">
                            <BarChart3 className="h-4 w-4 mr-2 shrink-0" />
                            <SelectValue placeholder="Product" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All Products</SelectItem>
                            {products.map((product) => (
                              <SelectItem key={product} value={product}>
                                {product}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-6">
                      {/* Income KPI */}
                      <div className="space-y-2">
                        <Label
                          htmlFor="income-kpi"
                          className="text-sm font-medium"
                        >
                          Income KPI
                        </Label>
                        <Select
                          value={selectedKPIs.income}
                          onValueChange={(value) =>
                            setSelectedKPIs((prev) => ({
                              ...prev,
                              income: value,
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a metric…" />
                          </SelectTrigger>
                          <SelectContent className="max-h-72">
                            {filteredMetrics.map((metric) => (
                              <SelectItem key={metric.name} value={metric.name}>
                                <span className="inline-flex items-center gap-2 truncate">
                                  <span className="font-medium truncate">
                                    {metric.name}
                                  </span>
                                  <Badge
                                    variant="secondary"
                                    className="text-xs shrink-0"
                                  >
                                    {metric.dataset}
                                  </Badge>
                                </span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Net Income KPI */}
                      <div className="space-y-2">
                        <Label
                          htmlFor="net-income-kpi"
                          className="text-sm font-medium"
                        >
                          Net Income KPI
                        </Label>
                        <Select
                          value={selectedKPIs.netIncome}
                          onValueChange={(value) =>
                            setSelectedKPIs((prev) => ({
                              ...prev,
                              netIncome: value,
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a metric…" />
                          </SelectTrigger>
                          <SelectContent className="max-h-72">
                            {filteredMetrics.map((metric) => (
                              <SelectItem key={metric.name} value={metric.name}>
                                <span className="inline-flex items-center gap-2 truncate">
                                  <span className="font-medium truncate">
                                    {metric.name}
                                  </span>
                                  <Badge
                                    variant="secondary"
                                    className="text-xs shrink-0"
                                  >
                                    {metric.dataset}
                                  </Badge>
                                </span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Marketing Cost KPI */}
                      <div className="space-y-2">
                        <Label
                          htmlFor="marketing-cost-kpi"
                          className="text-sm font-medium"
                        >
                          Marketing Cost KPI
                        </Label>
                        <Select
                          value={selectedKPIs.marketingCost}
                          onValueChange={(value) =>
                            setSelectedKPIs((prev) => ({
                              ...prev,
                              marketingCost: value,
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a metric…" />
                          </SelectTrigger>
                          <SelectContent className="max-h-72">
                            {filteredMetrics.map((metric) => (
                              <SelectItem key={metric.name} value={metric.name}>
                                <span className="inline-flex items-center gap-2 truncate">
                                  <span className="font-medium truncate">
                                    {metric.name}
                                  </span>
                                  <Badge
                                    variant="secondary"
                                    className="text-xs shrink-0"
                                  >
                                    {metric.dataset}
                                  </Badge>
                                </span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => setEditMetricsOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button onClick={() => setEditMetricsOpen(false)}>
                        Save Changes
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </div>

            {/* Metrics Scorecards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
              {metrics.map((metric) => (
                <Card
                  key={metric.name}
                  className="border border-[var(--color-border-default)]"
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Tooltip>
                          <TooltipTrigger>
                            <Info className="h-4 w-4 text-[var(--color-text-disabled)] hover:text-[var(--color-text-tertiary)]" />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="max-w-xs">
                              {
                                metricDefinitions[
                                  metric.name as keyof typeof metricDefinitions
                                ]
                              }
                            </p>
                          </TooltipContent>
                        </Tooltip>
                        <span className="text-sm font-medium text-[var(--color-text-primary)]">
                          {metric.name}
                        </span>
                      </div>
                    </div>
                    <div className="text-xs text-[var(--color-text-tertiary)] mb-1">
                      {metric.subtitle}
                    </div>
                    <div className="text-2xl font-bold text-[var(--color-text-primary)] mb-1">
                      {metric.value}
                    </div>
                    <div
                      className={cn(
                        "text-sm font-medium",
                        metric.changeType === "positive"
                          ? "text-brand-dark-green"
                          : "text-red-600",
                      )}
                    >
                      {metric.change}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Chart Section */}
            <div className="border border-[var(--color-border-default)] rounded-lg p-4">
              {/* Chart Toggle Buttons */}
              <div className="flex flex-wrap gap-2 mb-4">
                {chartButtons.map((button) => (
                  <Button
                    key={button.id}
                    variant={
                      selectedMetric === button.id ? "default" : "outline"
                    }
                    size="sm"
                    onClick={() => setSelectedMetric(button.id)}
                    className={cn(
                      "text-xs",
                      selectedMetric === button.id
                        ? "bg-[var(--color-text-primary)] text-white"
                        : "bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)] border-[var(--color-border-default)]",
                    )}
                  >
                    {button.label}
                  </Button>
                ))}
              </div>

              {/* Chart Area */}
              <div className="h-80 bg-[var(--color-bg-secondary)] rounded-lg flex flex-col justify-between p-4">
                {/* Chart Title */}
                <div className="text-sm text-[var(--color-text-tertiary)] mb-4">
                  <span className="font-medium">&lt;Metric Name&gt;</span>
                  <span className="text-[var(--color-text-tertiary)] ml-2">
                    [Dataset name]
                  </span>
                </div>

                {/* Mock Chart Area */}
                <div className="flex-1 relative">
                  <div className="ml-12 mr-4 h-full relative" />
                </div>
              </div>
            </div>
          </div>

          {/* Current Recommendations Card */}
          <div className="bg-[var(--color-bg-elevated)] rounded-lg p-6 border border-[var(--color-border-default)]">
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-6 text-left">
              Objectives
            </h2>

            {/* Objective Buttons */}
            <div className="mb-6">
              <div className="flex flex-wrap gap-2 mb-6">
                {Object.entries(objectiveData).map(([key, objective]) => (
                  <Button
                    key={key}
                    variant={selectedObjective === key ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedObjective(key)}
                    className="capitalize"
                  >
                    {objective.step_name}
                  </Button>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate("/measurement-plan")}
                  className="ml-auto"
                >
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit Measurement Plan
                </Button>
              </div>

              {/* Metrics Chart */}
              {selectedObjective && (
                <div className="border border-[var(--color-border-default)] rounded-lg p-4">
                  <div className="mb-4">
                    <h4 className="text-md font-medium text-[var(--color-text-primary)] mb-2">
                      {objectiveData[selectedObjective].step_name
                        .charAt(0)
                        .toUpperCase() +
                        objectiveData[selectedObjective].step_name.slice(
                          1,
                        )}{" "}
                      KPIs
                    </h4>
                    <p className="text-sm text-[var(--color-text-tertiary)] mb-4">
                      {objectiveData[selectedObjective].objective}
                    </p>
                  </div>

                  <div className="h-80 bg-[var(--color-bg-secondary)] rounded-lg p-4">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <div className="flex items-center gap-4 text-sm">
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 bg-brand-medium-blue rounded-full"></div>
                            <span className="font-medium">
                              {
                                objectiveData[selectedObjective]
                                  .effectivenessKPI
                              }
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 bg-brand-light-green rounded-full"></div>
                            <span className="font-medium">
                              {objectiveData[selectedObjective].efficiencyKPI}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Chart Area */}
                    <div className="h-full relative">
                      <svg className="w-full h-full" viewBox="0 0 400 200">
                        {/* Grid lines */}
                        <defs>
                          <pattern
                            id="metrics-grid"
                            width="50"
                            height="40"
                            patternUnits="userSpaceOnUse"
                          >
                            <path
                              d="M 50 0 L 0 0 0 40"
                              fill="none"
                              stroke="#E5E7EB"
                              strokeWidth="0.5"
                            />
                          </pattern>
                        </defs>
                        <rect
                          width="100%"
                          height="100%"
                          fill="url(#metrics-grid)"
                        />

                        {/* Effectiveness KPI line (blue) */}
                        <polyline
                          fill="none"
                          stroke="#3B82F6"
                          strokeWidth="2"
                          points="20,140 70,130 120,120 170,110 220,105 270,95 320,85 370,75"
                        />

                        {/* Efficiency KPI line (green) */}
                        <polyline
                          fill="none"
                          stroke="#10B981"
                          strokeWidth="2"
                          points="20,160 70,155 120,145 170,140 220,135 270,125 320,115 370,105"
                        />

                        {/* Data points for effectiveness */}
                        {[20, 70, 120, 170, 220, 270, 320, 370].map((x, i) => (
                          <circle
                            key={`eff-${i}`}
                            cx={x}
                            cy={140 - i * 8}
                            r="3"
                            fill="#3B82F6"
                          />
                        ))}

                        {/* Data points for efficiency */}
                        {[20, 70, 120, 170, 220, 270, 320, 370].map((x, i) => (
                          <circle
                            key={`ef-${i}`}
                            cx={x}
                            cy={160 - i * 7}
                            r="3"
                            fill="#10B981"
                          />
                        ))}
                      </svg>

                      {/* X-axis labels */}
                      <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-[var(--color-text-tertiary)] px-4">
                        <span>Jan 1</span>
                        <span>Jan 8</span>
                        <span>Jan 15</span>
                        <span>Jan 22</span>
                        <span>Jan 29</span>
                        <span>Feb 5</span>
                        <span>Feb 12</span>
                        <span>Feb 19</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Analysis Reports Card */}
          <div className="bg-[var(--color-bg-elevated)] rounded-lg p-6 border border-[var(--color-border-default)]">
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-6 text-left">
              Analysis Reports
            </h2>

            {/* Filter Controls */}
            <div className="flex flex-wrap items-center gap-4 mb-6">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                <Select
                  value={reportTypeFilter}
                  onValueChange={setReportTypeFilter}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="Scheduled">Scheduled</SelectItem>
                    <SelectItem value="Ad hoc">Ad hoc</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                <Select
                  value={reportObjectiveFilter}
                  onValueChange={setReportObjectiveFilter}
                >
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="Objective" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Objectives</SelectItem>
                    <SelectItem value="All">All</SelectItem>
                    <SelectItem value="Awareness">Awareness</SelectItem>
                    <SelectItem value="Consideration">Consideration</SelectItem>
                    <SelectItem value="Conversion">Conversion</SelectItem>
                    <SelectItem value="Loyalty">Loyalty</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-[var(--color-text-tertiary)]" />
                <Select
                  value={reportChannelFilter}
                  onValueChange={setReportChannelFilter}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Channel" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Channels</SelectItem>
                    <SelectItem value="All">All</SelectItem>
                    <SelectItem value="Email">Email</SelectItem>
                    <SelectItem value="Search">Search</SelectItem>
                    <SelectItem value="Social">Social</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="ml-auto">
                <Badge variant="secondary" className="text-xs">
                  {filteredReports.length} reports
                </Badge>
              </div>
            </div>

            {/* Reports List */}
            <div className="space-y-3">
              {filteredReports.map((report) => {
                const ObjectiveIcon = getObjectiveIcon(report.objective);
                const ChannelIcon = getChannelIcon(report.channel);

                return (
                  <div
                    key={report.id}
                    onClick={() => handleReportClick(report.id)}
                    className="border border-[var(--color-border-default)] rounded-lg p-4 hover:bg-[var(--color-bg-secondary)] transition-colors cursor-pointer"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <Badge
                            variant={
                              report.type === "Scheduled"
                                ? "default"
                                : "secondary"
                            }
                            className="text-xs"
                          >
                            {report.type}
                          </Badge>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-[var(--color-text-tertiary)]">
                          <div className="flex items-center gap-2">
                            <Calendar className="h-3 w-3" />
                            <span>{report.dateRange}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <ObjectiveIcon className="h-3 w-3" />
                            <span>Objective: {report.objective}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <ChannelIcon className="h-3 w-3" />
                            <span>Channel: {report.channel}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="text-xs text-[var(--color-text-tertiary)]">
                          {report.createdDate}
                        </div>
                        <button
                          onClick={(e) => handleDeleteReport(e, report.id)}
                          className="p-1 text-[var(--color-text-disabled)] hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                          title="Delete Report"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}

              {filteredReports.length === 0 && (
                <div className="text-center py-8 text-[var(--color-text-tertiary)]">
                  <FileText className="h-8 w-8 mx-auto mb-2 text-[var(--color-text-disabled)]" />
                  <p>No reports match the selected filters</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </TooltipProvider>
    </>
  );
};

export default Performance;
