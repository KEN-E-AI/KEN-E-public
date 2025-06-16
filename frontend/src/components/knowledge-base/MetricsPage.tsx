import { useState } from "react";
import {
  Search,
  Filter,
  Plus,
  ChevronDown,
  ChevronUp,
  MoreHorizontal,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Metric {
  id: string;
  name: string;
  description: string;
  dataset: string;
  product: string;
  format: string;
  currency: string;
  sqlExpression: string;
}

const datasets = [
  { id: "ga4_sessions", name: "GA4 Sessions", product: "Google Analytics" },
  { id: "ga4_events", name: "GA4 Events", product: "Google Analytics" },
  { id: "google_ads", name: "Google Ads", product: "Google Ads" },
  { id: "facebook_ads", name: "Facebook Ads", product: "Meta" },
  { id: "salesforce", name: "Salesforce", product: "Salesforce" },
];

const formats = ["Integer", "Percent", "Double"];

const currencies = ["USD", "CAD", "EUR", "GBP", "JPY", "AUD"];

const initialMetrics: Metric[] = [
  {
    id: "1",
    name: "Engaged Sessions",
    description:
      "Engaged sessions are a subset of total sessions. An engaged session indicates a user's meaningful interaction with a website or app. An engaged session is a session that lasts longer than 10 seconds, having at least one conversion event, or having ten or more page views or screen views. These sessions are used to calculate engagement rate, which represents the percentage of engaged sessions on your website or app.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when engaged_session_ind = 1 then 1 end)",
  },
  {
    id: "2",
    name: "Transactions",
    description:
      "The total count of orders that were successfully completed in Google Analytics 4.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'purchase' then 1 end)",
  },
  {
    id: "3",
    name: "Total Users",
    description:
      "The total number of unique users who initiated sessions on your website or app during the specified date range.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "count(distinct user_pseudo_id)",
  },
  {
    id: "4",
    name: "New Users",
    description:
      "The number of users who interacted with your site or app for the first time (users who had no previous sessions).",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression:
      "count(distinct case when new_user_ind = 1 then user_pseudo_id end)",
  },
  {
    id: "5",
    name: "Sessions",
    description:
      "The total number of sessions initiated by users on your website or app during the specified date range.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "count(distinct session_id)",
  },
  {
    id: "6",
    name: "Page Views",
    description:
      "The total number of page views across all sessions. Multiple views of the same page are counted separately.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'page_view' then 1 end)",
  },
  {
    id: "7",
    name: "Bounce Rate",
    description:
      "The percentage of single-page sessions (sessions in which the user left your site from the entrance page without interacting with the page).",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Percent",
    currency: "None",
    sqlExpression:
      "safe_divide(sum(case when bounced_session_ind = 1 then 1 end), count(distinct session_id)) * 100",
  },
  {
    id: "8",
    name: "Average Session Duration",
    description:
      "The average length of a session. This metric is calculated as the total duration of all sessions (in seconds) divided by the number of sessions.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Double",
    currency: "None",
    sqlExpression:
      "safe_divide(sum(session_duration_seconds), count(distinct session_id))",
  },
  {
    id: "9",
    name: "Conversion Rate",
    description:
      "The percentage of sessions that resulted in a conversion (purchase, sign-up, or other goal completion).",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Percent",
    currency: "None",
    sqlExpression:
      "safe_divide(sum(case when conversion_ind = 1 then 1 end), count(distinct session_id)) * 100",
  },
  {
    id: "10",
    name: "Revenue",
    description:
      "The total revenue generated from e-commerce transactions on your website or app.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Double",
    currency: "USD",
    sqlExpression:
      "sum(case when event_name = 'purchase' then revenue_usd end)",
  },
  {
    id: "11",
    name: "Average Order Value",
    description:
      "The average monetary value of e-commerce transactions. Calculated as total revenue divided by the number of transactions.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Double",
    currency: "USD",
    sqlExpression:
      "safe_divide(sum(case when event_name = 'purchase' then revenue_usd end), sum(case when event_name = 'purchase' then 1 end))",
  },
  {
    id: "12",
    name: "Add to Cart Events",
    description:
      "The total number of times users added items to their shopping cart.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'add_to_cart' then 1 end)",
  },
  {
    id: "13",
    name: "Checkout Events",
    description:
      "The total number of times users initiated the checkout process.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'begin_checkout' then 1 end)",
  },
  {
    id: "14",
    name: "Event Count",
    description:
      "The total count of events triggered across all sessions, including both automatically collected and custom events.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "count(*)",
  },
  {
    id: "15",
    name: "Unique Events",
    description:
      "The number of unique events per session. Multiple instances of the same event in a session are counted as one.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "count(distinct concat(session_id, event_name))",
  },
  {
    id: "16",
    name: "Sessions per User",
    description:
      "The average number of sessions per user. Calculated as total sessions divided by total users.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Double",
    currency: "None",
    sqlExpression:
      "safe_divide(count(distinct session_id), count(distinct user_pseudo_id))",
  },
  {
    id: "17",
    name: "Engagement Rate",
    description:
      "The percentage of engaged sessions out of total sessions. An engaged session is one that lasts longer than 10 seconds, has a conversion event, or has 2 or more page views.",
    dataset: "ga4_sessions",
    product: "Google Analytics",
    format: "Percent",
    currency: "None",
    sqlExpression:
      "safe_divide(sum(case when engaged_session_ind = 1 then 1 end), count(distinct session_id)) * 100",
  },
  {
    id: "18",
    name: "Pages per Session",
    description:
      "The average number of pages viewed during a session. Calculated as total page views divided by total sessions.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Double",
    currency: "None",
    sqlExpression:
      "safe_divide(sum(case when event_name = 'page_view' then 1 end), count(distinct session_id))",
  },
  {
    id: "19",
    name: "Scroll Events",
    description:
      "The total number of scroll events, indicating user engagement with page content.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'scroll' then 1 end)",
  },
  {
    id: "20",
    name: "File Downloads",
    description:
      "The total number of file download events tracked on your website.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'file_download' then 1 end)",
  },
  {
    id: "21",
    name: "Video Start Events",
    description:
      "The total number of video start events, indicating how many times users began watching videos on your site.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'video_start' then 1 end)",
  },
  {
    id: "22",
    name: "Search Events",
    description:
      "The total number of search events performed by users on your website's internal search functionality.",
    dataset: "ga4_events",
    product: "Google Analytics",
    format: "Integer",
    currency: "None",
    sqlExpression: "sum(case when event_name = 'search' then 1 end)",
  },
];

type SortField = "name" | "dataset" | "product" | null;
type SortDirection = "asc" | "desc";

const MetricsPage = () => {
  const [metrics, setMetrics] = useState<Metric[]>(initialMetrics);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortField, setSortField] = useState<SortField>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [expandedMetrics, setExpandedMetrics] = useState<Set<string>>(
    new Set(),
  );
  const [editingMetric, setEditingMetric] = useState<Metric | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  // Filter state
  const [selectedDataset, setSelectedDataset] = useState<string>("all");
  const [selectedProduct, setSelectedProduct] = useState<string>("all");
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-3 w-3 text-gray-400" />;
    }
    return sortDirection === "asc" ? (
      <ArrowUp className="h-3 w-3 text-gray-700" />
    ) : (
      <ArrowDown className="h-3 w-3 text-gray-700" />
    );
  };

  const filteredAndSortedMetrics = (() => {
    // First filter
    let result = metrics.filter((metric) => {
      // Search filter
      const matchesSearch =
        metric.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        metric.description.toLowerCase().includes(searchTerm.toLowerCase());

      // Dataset filter
      const matchesDataset =
        selectedDataset === "all" || metric.dataset === selectedDataset;

      // Product filter
      const matchesProduct =
        selectedProduct === "all" || metric.product === selectedProduct;

      return matchesSearch && matchesDataset && matchesProduct;
    });

    // Then sort
    if (sortField) {
      result.sort((a, b) => {
        let valueA = "";
        let valueB = "";

        switch (sortField) {
          case "name":
            valueA = a.name.toLowerCase();
            valueB = b.name.toLowerCase();
            break;
          case "dataset":
            valueA = (
              datasets.find((d) => d.id === a.dataset)?.name || a.dataset
            ).toLowerCase();
            valueB = (
              datasets.find((d) => d.id === b.dataset)?.name || b.dataset
            ).toLowerCase();
            break;
          case "product":
            valueA = a.product.toLowerCase();
            valueB = b.product.toLowerCase();
            break;
        }

        if (valueA < valueB) return sortDirection === "asc" ? -1 : 1;
        if (valueA > valueB) return sortDirection === "asc" ? 1 : -1;
        return 0;
      });
    }

    return result;
  })();

  // Get unique products for filtering
  const uniqueProducts = [...new Set(metrics.map((m) => m.product))];

  const toggleExpanded = (metricId: string) => {
    const newExpanded = new Set(expandedMetrics);
    if (newExpanded.has(metricId)) {
      newExpanded.delete(metricId);
    } else {
      newExpanded.add(metricId);
    }
    setExpandedMetrics(newExpanded);
  };

  const handleCreateMetric = () => {
    const newMetric: Metric = {
      id: `metric-${Date.now()}`,
      name: "",
      description: "",
      dataset: "",
      product: "",
      format: "Integer",
      currency: "USD",
      sqlExpression: "",
    };
    setEditingMetric(newMetric);
    setIsCreating(true);
    setModalOpen(true);
  };

  const handleEditMetric = (metric: Metric) => {
    setEditingMetric({ ...metric });
    setIsCreating(false);
    setModalOpen(true);
  };

  const handleSaveMetric = () => {
    if (!editingMetric || !editingMetric.name.trim()) return;

    if (isCreating) {
      setMetrics([...metrics, editingMetric]);
    } else {
      setMetrics(
        metrics.map((metric) =>
          metric.id === editingMetric.id ? editingMetric : metric,
        ),
      );
    }

    setEditingMetric(null);
    setIsCreating(false);
    setModalOpen(false);
  };

  const handleDeleteMetric = (metricId: string) => {
    setMetrics(metrics.filter((metric) => metric.id !== metricId));
  };

  const handleDatasetChange = (dataset: string) => {
    if (!editingMetric) return;

    const selectedDataset = datasets.find((d) => d.id === dataset);
    setEditingMetric({
      ...editingMetric,
      dataset,
      product: selectedDataset?.product || "",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl sm:text-2xl font-semibold text-dashboard-gray-900">
          Metrics
        </h2>
        <Button onClick={handleCreateMetric} size="sm">
          <Plus className="w-4 h-4 mr-2" />
          <span className="hidden sm:inline">Add Metric</span>
          <span className="sm:hidden">Add</span>
        </Button>
      </div>

      {/* Search and Filter */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search metrics..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <DropdownMenu
          open={showFilterDropdown}
          onOpenChange={setShowFilterDropdown}
        >
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4 mr-2" />
              <span className="hidden sm:inline">Filter</span>
              {(selectedDataset !== "all" || selectedProduct !== "all") && (
                <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                  {[
                    selectedDataset !== "all" ? "Dataset" : "",
                    selectedProduct !== "all" ? "Product" : "",
                  ]
                    .filter(Boolean)
                    .join(", ")}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64">
            <div className="p-2">
              <div className="space-y-3">
                {/* Dataset Filter */}
                <div>
                  <Label className="text-xs font-medium text-gray-700 mb-1 block">
                    Filter by Dataset
                  </Label>
                  <Select
                    value={selectedDataset}
                    onValueChange={setSelectedDataset}
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue placeholder="All Datasets" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Datasets</SelectItem>
                      {datasets.map((dataset) => (
                        <SelectItem key={dataset.id} value={dataset.id}>
                          {dataset.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Product Filter */}
                <div>
                  <Label className="text-xs font-medium text-gray-700 mb-1 block">
                    Filter by Product
                  </Label>
                  <Select
                    value={selectedProduct}
                    onValueChange={setSelectedProduct}
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue placeholder="All Products" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Products</SelectItem>
                      {uniqueProducts.map((product) => (
                        <SelectItem key={product} value={product}>
                          {product}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Clear Filters */}
                {(selectedDataset !== "all" || selectedProduct !== "all") && (
                  <div className="pt-2 border-t">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setSelectedDataset("all");
                        setSelectedProduct("all");
                      }}
                    >
                      Clear Filters
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Metrics Table */}
      <div className="bg-white border border-dashboard-gray-200 rounded-lg overflow-hidden">
        {/* Desktop Table */}
        <div className="hidden md:block overflow-x-auto">
          <div className="min-w-[700px]">
            {/* Table Header */}
            <div className="grid grid-cols-10 gap-4 p-4 border-b border-dashboard-gray-200 bg-gray-50 text-sm font-medium text-gray-700">
              <div className="col-span-1 text-center">Expand</div>
              <div className="col-span-4">
                <button
                  onClick={() => handleSort("name")}
                  className="flex items-center gap-2 hover:text-gray-900 transition-colors"
                >
                  Name
                  {getSortIcon("name")}
                </button>
              </div>
              <div className="col-span-3">
                <button
                  onClick={() => handleSort("dataset")}
                  className="flex items-center gap-2 hover:text-gray-900 transition-colors"
                >
                  Dataset
                  {getSortIcon("dataset")}
                </button>
              </div>
              <div className="col-span-1">
                <button
                  onClick={() => handleSort("product")}
                  className="flex items-center gap-2 hover:text-gray-900 transition-colors"
                >
                  Product
                  {getSortIcon("product")}
                </button>
              </div>
              <div className="col-span-1 text-center">Actions</div>
            </div>

            {/* Desktop Metrics List */}
            <div className="divide-y divide-dashboard-gray-200">
              {filteredAndSortedMetrics.map((metric) => {
                const isExpanded = expandedMetrics.has(metric.id);
                return (
                  <div key={metric.id} className="p-4">
                    {/* Main Row */}
                    <div className="grid grid-cols-10 gap-4 items-start">
                      <div className="col-span-1 flex justify-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 hover:bg-gray-100"
                          onClick={() => toggleExpanded(metric.id)}
                        >
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                      <div className="col-span-4 min-w-0">
                        <span className="font-medium text-dashboard-gray-900 break-words">
                          {metric.name}
                        </span>
                      </div>
                      <div className="col-span-3 min-w-0">
                        <span className="text-sm text-gray-700 break-words">
                          {datasets.find((d) => d.id === metric.dataset)
                            ?.name || metric.dataset}
                        </span>
                      </div>
                      <div className="col-span-1 min-w-0">
                        <span className="text-sm text-gray-700 break-words">
                          {metric.product}
                        </span>
                      </div>
                      <div className="col-span-1 flex justify-center">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 hover:bg-gray-100 border border-gray-200"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => handleEditMetric(metric)}
                            >
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleDeleteMetric(metric.id)}
                              className="text-red-600"
                            >
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="mt-4 ml-12 grid grid-cols-1 gap-4 p-4 bg-gray-50 rounded-lg">
                        {/* Description */}
                        <div className="min-w-0">
                          <Label className="text-xs font-medium text-gray-700">
                            Description
                          </Label>
                          <p className="text-sm text-gray-600 mt-1 break-words hyphens-auto">
                            {metric.description}
                          </p>
                        </div>

                        {/* Format, Currency, SQL in a grid */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                          <div className="min-w-0">
                            <Label className="text-xs font-medium text-gray-700">
                              Format
                            </Label>
                            <p className="text-sm text-gray-900 mt-1 break-words">
                              {metric.format}
                            </p>
                          </div>
                          <div className="min-w-0">
                            <Label className="text-xs font-medium text-gray-700">
                              Currency
                            </Label>
                            <p className="text-sm text-gray-900 mt-1 break-words">
                              {metric.currency}
                            </p>
                          </div>
                          <div className="lg:col-span-3 min-w-0">
                            <Label className="text-xs font-medium text-gray-700">
                              SQL Expression
                            </Label>
                            <div className="text-sm text-gray-900 mt-1 font-mono bg-white p-3 rounded border break-all whitespace-pre-wrap overflow-hidden">
                              {metric.sqlExpression}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Mobile Card Layout */}
        <div className="md:hidden">
          {/* Mobile Sort Options */}
          <div className="p-3 border-b border-dashboard-gray-200 bg-gray-50">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700 overflow-x-auto">
              <span className="whitespace-nowrap">Sort:</span>
              <button
                onClick={() => handleSort("name")}
                className={`flex items-center gap-1 px-2 py-1 rounded whitespace-nowrap ${
                  sortField === "name" ? "bg-gray-200" : "hover:bg-gray-100"
                }`}
              >
                Name {getSortIcon("name")}
              </button>
              <button
                onClick={() => handleSort("dataset")}
                className={`flex items-center gap-1 px-2 py-1 rounded whitespace-nowrap ${
                  sortField === "dataset" ? "bg-gray-200" : "hover:bg-gray-100"
                }`}
              >
                Dataset {getSortIcon("dataset")}
              </button>
              <button
                onClick={() => handleSort("product")}
                className={`flex items-center gap-1 px-2 py-1 rounded whitespace-nowrap ${
                  sortField === "product" ? "bg-gray-200" : "hover:bg-gray-100"
                }`}
              >
                Product {getSortIcon("product")}
              </button>
            </div>
          </div>

          {/* Mobile Metrics List */}
          <div className="divide-y divide-dashboard-gray-200">
            {filteredAndSortedMetrics.map((metric) => {
              const isExpanded = expandedMetrics.has(metric.id);
              return (
                <div key={metric.id} className="p-4">
                  {/* Mobile Card */}
                  <div className="space-y-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-dashboard-gray-900 break-words text-sm">
                          {metric.name}
                        </h3>
                        <div className="mt-1 space-y-1">
                          <p className="text-xs text-gray-600">
                            <span className="font-medium">Dataset:</span>{" "}
                            {datasets.find((d) => d.id === metric.dataset)
                              ?.name || metric.dataset}
                          </p>
                          <p className="text-xs text-gray-600">
                            <span className="font-medium">Product:</span>{" "}
                            {metric.product}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 hover:bg-gray-100"
                          onClick={() => toggleExpanded(metric.id)}
                        >
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 hover:bg-gray-100 border border-gray-200"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => handleEditMetric(metric)}
                            >
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleDeleteMetric(metric.id)}
                              className="text-red-600"
                            >
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>

                    {/* Mobile Expanded Details */}
                    {isExpanded && (
                      <div className="mt-4 space-y-4 p-3 bg-gray-50 rounded-lg">
                        <div>
                          <Label className="text-xs font-medium text-gray-700">
                            Description
                          </Label>
                          <p className="text-sm text-gray-600 mt-1 break-words">
                            {metric.description}
                          </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs font-medium text-gray-700">
                              Format
                            </Label>
                            <p className="text-sm text-gray-900 mt-1">
                              {metric.format}
                            </p>
                          </div>
                          <div>
                            <Label className="text-xs font-medium text-gray-700">
                              Currency
                            </Label>
                            <p className="text-sm text-gray-900 mt-1">
                              {metric.currency}
                            </p>
                          </div>
                        </div>

                        <div>
                          <Label className="text-xs font-medium text-gray-700">
                            SQL Expression
                          </Label>
                          <div className="text-xs text-gray-900 mt-1 font-mono bg-white p-2 rounded border break-all whitespace-pre-wrap overflow-hidden">
                            {metric.sqlExpression}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Edit/Create Metric Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl mx-4">
          <DialogHeader>
            <DialogTitle>
              {isCreating ? "Create New Metric" : "Edit Metric"}
            </DialogTitle>
          </DialogHeader>

          {editingMetric && (
            <div className="grid gap-4">
              <div>
                <Label htmlFor="metric-name">Name</Label>
                <Input
                  id="metric-name"
                  value={editingMetric.name}
                  onChange={(e) =>
                    setEditingMetric({
                      ...editingMetric,
                      name: e.target.value.slice(0, 40),
                    })
                  }
                  placeholder="Metric name"
                  maxLength={40}
                />
                <p className="text-xs text-gray-500 mt-1">
                  {editingMetric.name.length}/40 characters
                </p>
              </div>

              <div>
                <Label htmlFor="metric-description">Description</Label>
                <Textarea
                  id="metric-description"
                  value={editingMetric.description}
                  onChange={(e) =>
                    setEditingMetric({
                      ...editingMetric,
                      description: e.target.value.slice(0, 255),
                    })
                  }
                  placeholder="Metric description"
                  maxLength={255}
                  rows={3}
                />
                <p className="text-xs text-gray-500 mt-1">
                  {editingMetric.description.length}/255 characters
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label>Dataset</Label>
                  <Select
                    value={editingMetric.dataset}
                    onValueChange={handleDatasetChange}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select dataset" />
                    </SelectTrigger>
                    <SelectContent>
                      {datasets.map((dataset) => (
                        <SelectItem key={dataset.id} value={dataset.id}>
                          {dataset.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Product</Label>
                  <Input
                    value={editingMetric.product}
                    disabled
                    className="bg-gray-50"
                    placeholder="Auto-set based on dataset"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label>Format</Label>
                  <Select
                    value={editingMetric.format}
                    onValueChange={(value) =>
                      setEditingMetric({ ...editingMetric, format: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {formats.map((format) => (
                        <SelectItem key={format} value={format}>
                          {format}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Currency</Label>
                  <Select
                    value={editingMetric.currency}
                    onValueChange={(value) =>
                      setEditingMetric({ ...editingMetric, currency: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="None">None</SelectItem>
                      {currencies.map((currency) => (
                        <SelectItem key={currency} value={currency}>
                          {currency}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label htmlFor="sql-expression">SQL Expression</Label>
                <Textarea
                  id="sql-expression"
                  value={editingMetric.sqlExpression}
                  onChange={(e) =>
                    setEditingMetric({
                      ...editingMetric,
                      sqlExpression: e.target.value.slice(0, 255),
                    })
                  }
                  placeholder="SQL expression for the metric"
                  maxLength={255}
                  rows={3}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  {editingMetric.sqlExpression.length}/255 characters
                </p>
              </div>

              <div className="flex gap-2 pt-4">
                <Button onClick={handleSaveMetric}>
                  {isCreating ? "Create Metric" : "Save Changes"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setEditingMetric(null);
                    setIsCreating(false);
                    setModalOpen(false);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MetricsPage;
