import { useState } from "react";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  BarChart3,
  LineChart,
  PieChart,
  ScatterChart,
  Plus,
  Save,
  Share2,
  Download,
  FolderPlus,
  Users,
  Copy,
  Eye,
  Settings,
  Trash2,
  Star,
  Filter,
  Calendar,
  Database,
} from "lucide-react";

const Exploration = () => {
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

  const [selectedChartType, setSelectedChartType] = useState("bar");
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [activeView, setActiveView] = useState("builder");

  const chartTypes = [
    { id: "bar", name: "Bar Chart", icon: BarChart3 },
    { id: "line", name: "Line Chart", icon: LineChart },
    { id: "pie", name: "Pie Chart", icon: PieChart },
    { id: "scatter", name: "Scatter Plot", icon: ScatterChart },
  ];

  const dimensions = [
    "Channel",
    "Campaign",
    "Geographic Region",
    "Device Type",
    "Time Period",
    "Customer Segment",
    "Product Category",
    "Traffic Source",
  ];

  const metrics = [
    "Revenue",
    "Conversions",
    "Click-through Rate",
    "Cost per Acquisition",
    "Return on Ad Spend",
    "Sessions",
    "Bounce Rate",
    "Average Order Value",
    "Customer Lifetime Value",
    "Conversion Rate",
  ];

  const savedCharts = [
    {
      id: "1",
      name: "Revenue by Channel",
      type: "bar",
      lastModified: "2 hours ago",
      shared: true,
      favorite: true,
    },
    {
      id: "2",
      name: "Conversion Trends",
      type: "line",
      lastModified: "1 day ago",
      shared: false,
      favorite: false,
    },
    {
      id: "3",
      name: "Traffic Sources",
      type: "pie",
      lastModified: "3 days ago",
      shared: true,
      favorite: true,
    },
    {
      id: "4",
      name: "Campaign Performance",
      type: "scatter",
      lastModified: "1 week ago",
      shared: false,
      favorite: false,
    },
  ];

  const dashboards = [
    {
      id: "1",
      name: "Marketing Performance",
      charts: 5,
      collaborators: 3,
      lastModified: "Yesterday",
    },
    {
      id: "2",
      name: "Sales Analytics",
      charts: 8,
      collaborators: 2,
      lastModified: "2 days ago",
    },
    {
      id: "3",
      name: "Customer Insights",
      charts: 4,
      collaborators: 5,
      lastModified: "1 week ago",
    },
  ];

  return (
    <Layout
      pageTitle="Data Exploration"
      selectedTab={selectedTab}
      selectedChannel={selectedChannel}
      selectedTactic={selectedTactic}
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      <div className="space-y-6">
        {/* View Navigation */}
        <div className="bg-white rounded-lg border border-dashboard-gray-200">
          <div className="flex items-center gap-2 p-4 border-b border-dashboard-gray-200">
            <Button
              variant={activeView === "builder" ? "default" : "ghost"}
              size="sm"
              onClick={() => setActiveView("builder")}
            >
              Chart Builder
            </Button>
            <Button
              variant={activeView === "library" ? "default" : "ghost"}
              size="sm"
              onClick={() => setActiveView("library")}
            >
              Chart Library
            </Button>
            <Button
              variant={activeView === "dashboards" ? "default" : "ghost"}
              size="sm"
              onClick={() => setActiveView("dashboards")}
            >
              Dashboards
            </Button>
          </div>
        </div>

        {/* Chart Builder View */}
        {activeView === "builder" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Chart Configuration */}
            <div className="lg:col-span-1 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="h-5 w-5" />
                    Chart Configuration
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Chart Type Selection */}
                  <div>
                    <label className="text-sm font-medium text-dashboard-gray-700 mb-2 block">
                      Chart Type
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      {chartTypes.map((type) => {
                        const Icon = type.icon;
                        return (
                          <Button
                            key={type.id}
                            variant={
                              selectedChartType === type.id
                                ? "default"
                                : "outline"
                            }
                            size="sm"
                            className="flex flex-col items-center gap-1 h-auto py-3"
                            onClick={() => setSelectedChartType(type.id)}
                          >
                            <Icon className="h-4 w-4" />
                            <span className="text-xs">{type.name}</span>
                          </Button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Dimensions */}
                  <div>
                    <label className="text-sm font-medium text-dashboard-gray-700 mb-2 block">
                      Dimensions
                    </label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Select dimensions..." />
                      </SelectTrigger>
                      <SelectContent>
                        {dimensions.map((dimension) => (
                          <SelectItem key={dimension} value={dimension}>
                            {dimension}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {selectedDimensions.map((dim) => (
                        <Badge key={dim} variant="secondary">
                          {dim}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Metrics */}
                  <div>
                    <label className="text-sm font-medium text-dashboard-gray-700 mb-2 block">
                      Metrics
                    </label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Select metrics..." />
                      </SelectTrigger>
                      <SelectContent>
                        {metrics.map((metric) => (
                          <SelectItem key={metric} value={metric}>
                            {metric}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {selectedMetrics.map((metric) => (
                        <Badge key={metric} variant="secondary">
                          {metric}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Filters */}
                  <div>
                    <label className="text-sm font-medium text-dashboard-gray-700 mb-2 block">
                      Filters
                    </label>
                    <Button variant="outline" size="sm" className="w-full">
                      <Filter className="h-4 w-4 mr-2" />
                      Add Filter
                    </Button>
                  </div>

                  {/* Date Range */}
                  <div>
                    <label className="text-sm font-medium text-dashboard-gray-700 mb-2 block">
                      Date Range
                    </label>
                    <Button variant="outline" size="sm" className="w-full">
                      <Calendar className="h-4 w-4 mr-2" />
                      Custom Range
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Data Source */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5" />
                    Data Source
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Select defaultValue="warehouse">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="warehouse">Data Warehouse</SelectItem>
                      <SelectItem value="analytics">
                        Google Analytics
                      </SelectItem>
                      <SelectItem value="ads">Ad Platforms</SelectItem>
                      <SelectItem value="crm">CRM System</SelectItem>
                    </SelectContent>
                  </Select>
                </CardContent>
              </Card>
            </div>

            {/* Chart Preview */}
            <div className="lg:col-span-2">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Chart Preview</CardTitle>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline">
                        <Save className="h-4 w-4 mr-2" />
                        Save Chart
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="outline">
                            <Share2 className="h-4 w-4 mr-2" />
                            Share
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <Users className="h-4 w-4 mr-2" />
                            Share with team
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Copy className="h-4 w-4 mr-2" />
                            Copy link
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem>
                            <Download className="h-4 w-4 mr-2" />
                            Export PNG
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Download className="h-4 w-4 mr-2" />
                            Export CSV
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="bg-dashboard-gray-50 rounded-lg h-96 flex items-center justify-center">
                    <div className="text-center">
                      <BarChart3 className="h-16 w-16 text-dashboard-gray-400 mx-auto mb-4" />
                      <p className="text-dashboard-gray-600">
                        Select dimensions and metrics to build your chart
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Chart Library View */}
        {activeView === "library" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h2 className="text-lg font-semibold text-dashboard-gray-900">
                  Saved Charts
                </h2>
                <Badge variant="secondary">{savedCharts.length} charts</Badge>
              </div>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                New Chart
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {savedCharts.map((chart) => {
                const Icon =
                  chartTypes.find((t) => t.id === chart.type)?.icon ||
                  BarChart3;
                return (
                  <Card
                    key={chart.id}
                    className="hover:shadow-md transition-shadow"
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 text-dashboard-gray-600" />
                          <CardTitle className="text-sm">
                            {chart.name}
                          </CardTitle>
                        </div>
                        <div className="flex items-center gap-1">
                          {chart.favorite && (
                            <Star className="h-3 w-3 text-yellow-500 fill-current" />
                          )}
                          {chart.shared && (
                            <Users className="h-3 w-3 text-dashboard-gray-400" />
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="bg-dashboard-gray-50 rounded h-24 mb-3 flex items-center justify-center">
                        <Icon className="h-8 w-8 text-dashboard-gray-400" />
                      </div>
                      <div className="flex items-center justify-between text-xs text-dashboard-gray-500">
                        <span>Modified {chart.lastModified}</span>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-auto p-1"
                            >
                              <svg
                                className="h-3 w-3"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                              >
                                <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                              </svg>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem>
                              <Eye className="h-4 w-4 mr-2" />
                              View
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Copy className="h-4 w-4 mr-2" />
                              Duplicate
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Share2 className="h-4 w-4 mr-2" />
                              Share
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-red-600">
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        {/* Dashboards View */}
        {activeView === "dashboards" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h2 className="text-lg font-semibold text-dashboard-gray-900">
                  Dashboards
                </h2>
                <Badge variant="secondary">
                  {dashboards.length} dashboards
                </Badge>
              </div>
              <Button>
                <FolderPlus className="h-4 w-4 mr-2" />
                New Dashboard
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {dashboards.map((dashboard) => (
                <Card
                  key={dashboard.id}
                  className="hover:shadow-md transition-shadow"
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">
                        {dashboard.name}
                      </CardTitle>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto p-1"
                          >
                            <svg
                              className="h-4 w-4"
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                            </svg>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <Eye className="h-4 w-4 mr-2" />
                            View
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Settings className="h-4 w-4 mr-2" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Share2 className="h-4 w-4 mr-2" />
                            Share
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-red-600">
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="bg-dashboard-gray-50 rounded-lg h-32 mb-4 flex items-center justify-center">
                      <div className="grid grid-cols-2 gap-2 w-full h-full p-2">
                        <div className="bg-white rounded flex items-center justify-center">
                          <BarChart3 className="h-4 w-4 text-dashboard-gray-400" />
                        </div>
                        <div className="bg-white rounded flex items-center justify-center">
                          <LineChart className="h-4 w-4 text-dashboard-gray-400" />
                        </div>
                        <div className="bg-white rounded flex items-center justify-center">
                          <PieChart className="h-4 w-4 text-dashboard-gray-400" />
                        </div>
                        <div className="bg-white rounded flex items-center justify-center">
                          <ScatterChart className="h-4 w-4 text-dashboard-gray-400" />
                        </div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-dashboard-gray-600">Charts</span>
                        <span className="font-medium">{dashboard.charts}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-dashboard-gray-600">
                          Collaborators
                        </span>
                        <span className="font-medium">
                          {dashboard.collaborators}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-dashboard-gray-600">
                          Last modified
                        </span>
                        <span className="text-dashboard-gray-500">
                          {dashboard.lastModified}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Exploration;
