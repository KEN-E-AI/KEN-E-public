import { useState, useEffect } from "react";
import axios from "axios";
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
import { useAuth } from "@/contexts/AuthContext";

interface ApiMetric {
  id: string;
  account_id: string;
  d3_format?: string;
  verbose_name: string;
  expression: string;
  metric_name: string;
  currency?: string;
  related_dataset_id?: number;
  related_dataset_name?: string;
  related_dataset_products?: string[];
  description: string;
}

interface Dataset {
  id: number;
  account_id: string;
  dataset_id: number;
  dataset_name: string;
  products: string[];
  default_datetime: string;
  description: string;
}

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

// Datasets will be fetched from API

const formats = ["Integer", "Percent", "Double"];

const currencies = ["USD", "CAD", "EUR", "GBP", "JPY", "AUD"];

type SortField = "name" | "dataset" | "product" | null;
type SortDirection = "asc" | "desc";

const MetricsPage = () => {
  const { selectedOrgAccount } = useAuth();
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

  const [metricsData, setMetricsData] = useState<Metric[]>([]);
  const [rawMetricsData, setRawMetricsData] = useState<ApiMetric[]>([]);
  const [datasetsData, setDatasetsData] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortField, setSortField] = useState<SortField>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [expandedMetrics, setExpandedMetrics] = useState<Set<string>>(
    new Set(),
  );
  const [editingMetric, setEditingMetric] = useState<Metric | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  // Convert API metric to component format
  const convertApiMetric = (apiMetric: ApiMetric): Metric => {
    // Find the matching dataset to get the correct product
    const matchingDataset = datasetsData.find(
      (d) => d.dataset_name === apiMetric.related_dataset_name,
    );

    return {
      id: apiMetric.id,
      name: apiMetric.verbose_name,
      description: apiMetric.description,
      dataset: apiMetric.related_dataset_name || "unknown",
      product:
        matchingDataset?.products?.[0] ||
        apiMetric.related_dataset_products?.[0] ||
        "Unknown",
      format: apiMetric.d3_format || "Integer",
      currency: apiMetric.currency || "None",
      sqlExpression: apiMetric.expression,
    };
  };

  // Convert component metric to API format
  const convertToApiMetric = (metric: Metric): Partial<ApiMetric> => {
    const dataset = datasetsData.find((d) => d.dataset_name === metric.dataset);
    return {
      account_id: selectedOrgAccount?.accountId || "",
      verbose_name: metric.name,
      expression: metric.sqlExpression,
      metric_name: metric.name.toLowerCase().replace(/\s+/g, "_"),
      currency: metric.currency === "None" ? undefined : metric.currency,
      d3_format: metric.format,
      description: metric.description,
      related_dataset_name: dataset?.dataset_name || "",
      related_dataset_products: dataset?.products || [],
    };
  };

  // Fetch datasets from API
  const fetchDatasets = async () => {
    if (!selectedOrgAccount?.accountId) {
      setDatasetsLoading(false);
      return;
    }

    try {
      setDatasetsLoading(true);
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/datasets/?account_id=${selectedOrgAccount.accountId}`,
      );

      if (response.data.datasets !== undefined) {
        setDatasetsData(response.data.datasets);
      }
    } catch (err) {
      console.error("Error fetching datasets:", err);
      // Don't set error state for datasets, just log it
    } finally {
      setDatasetsLoading(false);
    }
  };

  // Fetch metrics from API
  const fetchMetrics = async () => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/metrics/?account_id=${selectedOrgAccount.accountId}`,
      );

      if (response.data.metrics !== undefined) {
        // Store raw metrics data, will convert after datasets are loaded
        setRawMetricsData(response.data.metrics);
      } else {
        setError("Failed to fetch metrics");
      }
    } catch (err) {
      console.error("Error fetching metrics:", err);
      setError("Failed to fetch metrics");
    } finally {
      setLoading(false);
    }
  };

  // Create metric via API
  const createMetric = async (metric: Metric) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const apiMetric = convertToApiMetric(metric);
      console.log("Sending to API:", apiMetric);
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/metrics/`,
        apiMetric,
      );

      console.log("Create response:", response.data);
      if (response.data.metric_id || response.status === 200) {
        await fetchMetrics(); // Refresh the list
      } else {
        setError("Failed to create metric");
      }
    } catch (err) {
      console.error("Error creating metric:", err);
      setError("Failed to create metric");
    }
  };

  // Update metric via API
  const updateMetric = async (metric: Metric) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.put(`${API_BASE_URL}/api/v1/metrics/`, {
        ...convertToApiMetric(metric),
        id: metric.id,
      });

      if (response.data.success) {
        await fetchMetrics(); // Refresh the list
      } else {
        setError("Failed to update metric");
      }
    } catch (err) {
      console.error("Error updating metric:", err);
      setError("Failed to update metric");
    }
  };

  // Delete metric via API
  const deleteMetric = async (metricId: string) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.delete(`${API_BASE_URL}/api/v1/metrics/`, {
        data: {
          account_id: selectedOrgAccount.accountId,
          metric_id: metricId,
        },
      });

      if (response.data.success) {
        await fetchMetrics(); // Refresh the list
      } else {
        setError("Failed to delete metric");
      }
    } catch (err) {
      console.error("Error deleting metric:", err);
      setError("Failed to delete metric");
    }
  };

  // Convert raw metrics data when datasets are loaded
  useEffect(() => {
    if (rawMetricsData.length > 0 && datasetsData.length > 0) {
      const convertedMetrics = rawMetricsData.map(convertApiMetric);
      setMetricsData(convertedMetrics);
    }
  }, [rawMetricsData, datasetsData]);

  // Load datasets and metrics on component mount and when account changes
  useEffect(() => {
    fetchDatasets();
    fetchMetrics();
  }, [selectedOrgAccount?.accountId]);

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
    let result = metricsData.filter((metric) => {
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
              datasetsData.find((d) => d.dataset_name === a.dataset)
                ?.dataset_name || a.dataset
            ).toLowerCase();
            valueB = (
              datasetsData.find((d) => d.dataset_name === b.dataset)
                ?.dataset_name || b.dataset
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
  const uniqueProducts = [...new Set(metricsData.map((m) => m.product))];

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

  const handleSaveMetric = async () => {
    if (!editingMetric) return;

    if (isCreating) {
      await createMetric(editingMetric);
    } else {
      await updateMetric(editingMetric);
    }

    setModalOpen(false);
    setEditingMetric(null);
    setIsCreating(false);
  };

  const handleDeleteMetric = async (metricId: string) => {
    await deleteMetric(metricId);
  };

  const handleDatasetChange = (dataset: string) => {
    if (!editingMetric) return;

    const selectedDataset = datasetsData.find(
      (d) => d.dataset_name === dataset,
    );
    setEditingMetric({
      ...editingMetric,
      dataset,
      product: selectedDataset?.products?.[0] || "",
    });
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">Loading metrics...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center py-8">
          <div className="text-red-500">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex items-center justify-end">
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
                <span className="ml-1 px-1.5 py-0.5 bg-brand-light-blue/30 text-brand-dark-blue text-xs rounded-full">
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
                      {datasetsData.map((dataset) => (
                        <SelectItem
                          key={dataset.dataset_id}
                          value={dataset.dataset_name}
                        >
                          {dataset.dataset_name}
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
                    <div className="grid grid-cols-10 gap-4 items-start text-left">
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
                          {datasetsData.find(
                            (d) => d.dataset_name === metric.dataset,
                          )?.dataset_name || metric.dataset}
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
                            {datasetsData.find(
                              (d) => d.dataset_name === metric.dataset,
                            )?.dataset_name || metric.dataset}
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
                      {datasetsData.map((dataset) => (
                        <SelectItem
                          key={dataset.dataset_id}
                          value={dataset.dataset_name}
                        >
                          {dataset.dataset_name}
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
