import { useState, useMemo, useEffect, useCallback } from "react";
import {
  Plus,
  Info,
  Edit2,
  Trash2,
  Calendar,
  MoreHorizontal,
  Search,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/contexts/AuthContext";
import axios from "axios";

interface Intuition {
  id: string;
  metricName: string;
  direction: "increase" | "decrease";
}

interface Log {
  id: string;
  startDate: string;
  endDate: string;
  description: string;
}

interface ApiActivity {
  id: string;
  account_id: string;
  activity_description: string;
  expected_impact: string;
  internal: boolean;
  known_activity: boolean;
  logs: ApiLog[];
}

interface ApiLog {
  id: string;
  account_id: string;
  start_date: string;
  end_date: string;
  description: string;
  evidence: any;
}

interface Activity {
  id: string;
  description: string;
  internal: boolean;
  known: boolean;
  expectedImpact: string;
  intuitions: Intuition[];
  logs: Log[];
}

// Metric interface for intuition selection
interface AvailableMetric {
  id: string;
  name: string;
  dataset: string;
  product: string;
}

// Dataset interface for API integration
interface Dataset {
  id: number;
  account_id: string;
  dataset_id: number;
  dataset_name: string;
  products: string[];
  default_datetime: string;
  description: string;
}

// Metrics will be fetched from API

const ActivitiesPage = () => {
  const { selectedOrgAccount } = useAuth();
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

  // State for dynamic metrics and datasets from API
  const [availableMetrics, setAvailableMetrics] = useState<AvailableMetric[]>([]);
  const [datasetsData, setDatasetsData] = useState<Dataset[]>([]);

  // Convert API activity to component format
  const convertApiActivity = (apiActivity: ApiActivity): Activity => ({
    id: apiActivity.id,
    description: apiActivity.activity_description,
    internal: apiActivity.internal,
    known: apiActivity.known_activity,
    expectedImpact: apiActivity.expected_impact,
    intuitions: [], // Will be populated separately from intuitions API
    logs: apiActivity.logs.map((log) => ({
      id: log.id,
      startDate: log.start_date,
      endDate: log.end_date,
      description: log.description,
    })),
  });

  // Convert component log to API format
  const convertToApiLog = (log: Log): Partial<ApiLog> => ({
    account_id: selectedOrgAccount?.accountId || "",
    start_date: log.startDate,
    end_date: log.endDate,
    description: log.description,
    evidence: null,
  });

  // Convert component activity to API format
  const convertToApiActivity = (activity: Activity): Partial<ApiActivity> => ({
    account_id: selectedOrgAccount?.accountId || "",
    activity_description: activity.description,
    expected_impact: activity.expectedImpact,
    internal: activity.internal,
    known_activity: activity.known,
  });

  const [activitiesData, setActivitiesData] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingActivity, setEditingActivity] = useState<Activity | null>(null);
  const [editingIntuition, setEditingIntuition] = useState<{
    activity: string;
    intuition: Intuition | null;
  }>({ activity: "", intuition: null });
  const [editingLog, setEditingLog] = useState<{
    activity: string;
    log: Log | null;
  }>({ activity: "", log: null });
  const [showActivityModal, setShowActivityModal] = useState(false);
  const [showIntuitionModal, setShowIntuitionModal] = useState(false);
  const [showLogModal, setShowLogModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<
    "all" | "internal" | "known" | "both"
  >("all");
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);

  // Metric selection state
  const [metricSearchTerm, setMetricSearchTerm] = useState("");
  const [selectedDataset, setSelectedDataset] = useState<string>("all");
  const [selectedProduct, setSelectedProduct] = useState<string>("all");
  // Fetch intuitions and populate them into activities
  const fetchAndPopulateIntuitions = async (activities: Activity[]) => {
    if (!selectedOrgAccount?.accountId) {
      return activities;
    }

    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/intuitions/?account_id=${selectedOrgAccount.accountId}`
      );
      
      if (response.data.intuitions) {
        // Create a map of activity ID to intuitions
        const intuitionsByActivity = new Map<string, Intuition[]>();
        
        response.data.intuitions.forEach((intuition: any) => {
          const activityId = intuition.activity_id;
          if (!intuitionsByActivity.has(activityId)) {
            intuitionsByActivity.set(activityId, []);
          }
          
          const convertedIntuition: Intuition = {
            id: `i_${intuition.activity_id}_${intuition.metric_id}`,
            metricName: intuition.metric_id,
            direction: intuition.direction === "positive" ? "increase" : "decrease",
          };
          
          intuitionsByActivity.get(activityId)!.push(convertedIntuition);
        });
        
        // Populate intuitions into activities
        return activities.map(activity => ({
          ...activity,
          intuitions: intuitionsByActivity.get(activity.id) || [],
        }));
      }
    } catch (err) {
      console.error("Error fetching intuitions:", err);
    }
    
    return activities;
  };

  // Fetch activities from API
  const fetchActivities = useCallback(async () => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/activities/?account_id=${selectedOrgAccount.accountId}`
      );
      
      if (response.data.activities !== undefined) {
        let convertedActivities = response.data.activities.map(convertApiActivity);
        
        // Fetch and populate intuitions
        convertedActivities = await fetchAndPopulateIntuitions(convertedActivities);
        
        console.log("Activities: ", convertedActivities);

        setActivitiesData(convertedActivities);
      } else {
        setError("Failed to fetch activities");
      }
    } catch (err) {
      console.error("Error fetching activities:", err);
      setError("Failed to fetch activities");
    } finally {
      setLoading(false);
    }
  }, [selectedOrgAccount?.accountId, API_BASE_URL]);

  // Fetch available metrics for intuition selection
  const fetchAvailableMetrics = useCallback(async () => {
    if (!selectedOrgAccount?.accountId) {
      return;
    }

    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/metrics/?account_id=${selectedOrgAccount.accountId}`
      );
      
      if (response.data.metrics !== undefined) {
        const metrics: AvailableMetric[] = response.data.metrics.map((metric: any) => ({
          id: metric.id,
          name: metric.verbose_name || metric.metric_name,
          dataset: metric.related_dataset_name || "unknown",
          product: metric.related_dataset_products?.[0] || "Unknown",
        }));
        setAvailableMetrics(metrics);
      }
    } catch (err) {
      console.error("Error fetching available metrics:", err);
      // Keep empty array on error
    }
  }, [selectedOrgAccount?.accountId, API_BASE_URL]);

  // Fetch available datasets for filtering
  const fetchAvailableDatasets = useCallback(async () => {
    if (!selectedOrgAccount?.accountId) {
      return;
    }

    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/datasets/?account_id=${selectedOrgAccount.accountId}`
      );
      
      if (response.data.datasets !== undefined) {
        setDatasetsData(response.data.datasets);
      }
    } catch (err) {
      console.error("Error fetching datasets:", err);
      // Don't set error state for datasets, just log it
    }
  }, [selectedOrgAccount?.accountId, API_BASE_URL]);

  // Load metrics and datasets when component mounts
  useEffect(() => {
    fetchAvailableMetrics();
    fetchAvailableDatasets();
  }, [fetchAvailableMetrics, fetchAvailableDatasets]);

  // Create activity log via API
  const createActivityLog = async (activityId: string, log: Log) => {
    if (!selectedOrgAccount?.accountId) {
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/activities/logs`,
        {
          ...convertToApiLog(log),
          activity_id: activityId,
        }
      );
      return response.data.success;
    } catch (err) {
      console.error("Error creating activity log:", err);
      return false;
    }
  };

  // Create activity via API
  const createActivity = async (activity: Activity) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/activities/`,
        convertToApiActivity(activity)
      );
      
      if (response.data.success) {
        const newActivityId = response.data.data.id;
        
        // Create any logs for this activity
        if (activity.logs && activity.logs.length > 0) {
          for (const log of activity.logs) {
            await createActivityLog(newActivityId, log);
          }
        }
        
        // Create any intuitions for this activity
        if (activity.intuitions && activity.intuitions.length > 0) {
          for (const intuition of activity.intuitions) {
            await createIntuition(newActivityId, intuition);
          }
        }
        
        // Add a small delay to ensure database consistency
        setTimeout(async () => {
          await fetchActivities(); // Refresh the list
        }, 100);
      } else {
        setError("Failed to create activity");
      }
    } catch (err) {
      console.error("Error creating activity:", err);
      setError("Failed to create activity");
    }
  };

  // Update activity via API
  const updateActivity = async (activity: Activity) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/activities/`,
        { ...convertToApiActivity(activity), activity_id: activity.id }
      );
      
      if (response.data.success) {
        await fetchActivities(); // Refresh the list
      } else {
        setError("Failed to update activity");
      }
    } catch (err) {
      console.error("Error updating activity:", err);
      setError("Failed to update activity");
    }
  };

  // Delete activity via API
  const deleteActivity = async (activityId: string) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.delete(
        `${API_BASE_URL}/api/v1/activities/`,
        { 
          data: { 
            activity_id: activityId,
            account_id: selectedOrgAccount.accountId 
          } 
        }
      );
      
      if (response.data.success) {
        await fetchActivities(); // Refresh the list
      } else {
        setError("Failed to delete activity");
      }
    } catch (err) {
      console.error("Error deleting activity:", err);
      setError("Failed to delete activity");
    }
  };

  // Load activities on component mount
  useEffect(() => {
    fetchActivities();
  }, [selectedOrgAccount?.accountId]);

  // Filter and search activities - optimized with useMemo
  const filteredActivities = useMemo(() => {
    return activitiesData.filter((activity) => {
      // Search filter
      const matchesSearch =
        activity.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        activity.expectedImpact
          .toLowerCase()
          .includes(searchTerm.toLowerCase());

      // Status filter
      const matchesFilter =
        filterStatus === "all" ||
        (filterStatus === "internal" && activity.internal) ||
        (filterStatus === "known" && activity.known) ||
        (filterStatus === "both" && activity.internal && activity.known);

      return matchesSearch && matchesFilter;
    });
  }, [activitiesData, searchTerm, filterStatus]);

  // Filter and search metrics for intuition selection - optimized with useMemo
  const filteredMetrics = useMemo(() => {
    return availableMetrics.filter((metric) => {
      // Search filter
      const matchesSearch = metric.name
        .toLowerCase()
        .includes(metricSearchTerm.toLowerCase());

      // Dataset filter
      const matchesDataset =
        selectedDataset === "all" || metric.dataset === selectedDataset;

      // Product filter
      const matchesProduct =
        selectedProduct === "all" || metric.product === selectedProduct;

      return matchesSearch && matchesDataset && matchesProduct;
    });
  }, [availableMetrics, metricSearchTerm, selectedDataset, selectedProduct]);

  // Get unique products for filtering - optimized with useMemo
  const uniqueProducts = useMemo(() => {
    return [...new Set(availableMetrics.map((m) => m.product))];
  }, [availableMetrics]);

  // Helper function to get metric name from ID
  const getMetricNameById = (metricId: string): string => {
    const metric = availableMetrics.find(m => m.id === metricId);
    return metric ? metric.name : metricId;
  };

  // Reset metric filters when opening intuition modal
  const openIntuitionModal = (activityId: string, intuition?: Intuition) => {
    setMetricSearchTerm("");
    setSelectedDataset("all");
    setSelectedProduct("all");
    setEditingIntuition({
      activity: activityId,
      intuition: intuition || {
        id: "",
        metricName: "",
        direction: "increase",
      },
    });
    setShowIntuitionModal(true);
  };
  const handleEditActivity = (activity: Activity) => {
    setEditingActivity(activity);
    setIsCreating(false);
    setShowActivityModal(true);
  };

  const handleSaveActivity = async () => {
    if (!editingActivity || !editingActivity.description.trim()) return;

    if (isCreating || !editingActivity.id || editingActivity.id === "") {
      await createActivity(editingActivity);
    } else {
      // Update the activity first
      await updateActivity(editingActivity);
      
      // For existing activities, intuitions are created immediately when the intuition modal is saved
      // So we don't need to create them again here
    }

    setEditingActivity(null);
    setIsCreating(false);
    setShowActivityModal(false);
  };

  const handleDeleteActivity = async (activityId: string) => {
    await deleteActivity(activityId);
  };

  const addIntuition = async (
    activityId: string,
    intuition: Omit<Intuition, "id">,
  ) => {
    const newIntuition = { ...intuition, id: `i${Date.now()}` };
    await createIntuition(activityId, newIntuition);
  };

  const addLog = async (activityId: string, log: Omit<Log, "id">) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/activities/logs`,
        {
          ...convertToApiLog({ ...log, id: "" }),
          activity_id: activityId,
        }
      );
      
      if (response.data.success) {
        // Update the editingActivity state immediately to show the new log in the modal
        if (editingActivity && editingActivity.id === activityId) {
          const newLog = { ...log, id: response.data.data?.id || `l${Date.now()}` };
          setEditingActivity({
            ...editingActivity,
            logs: [...editingActivity.logs, newLog],
          });
        }
        await fetchActivities(); // Refresh the list to get updated logs
      } else {
        setError("Failed to add log");
      }
    } catch (err) {
      console.error("Error adding log:", err);
      setError("Failed to add log");
    }
  };

  const updateLog = async (
    activityId: string,
    logId: string,
    updates: Partial<Log>,
  ) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/activities/logs`,
        {
          id: logId,
          account_id: selectedOrgAccount.accountId,
          start_date: updates.startDate,
          end_date: updates.endDate,
          description: updates.description,
        }
      );
      
      if (response.data.success) {
        // Update the editingActivity state immediately to show the updated log in the modal
        if (editingActivity && editingActivity.id === activityId) {
          const updatedLogs = editingActivity.logs.map((l) =>
            l.id === logId ? { ...l, ...updates } : l
          );
          setEditingActivity({
            ...editingActivity,
            logs: updatedLogs,
          });
        }
        await fetchActivities(); // Refresh the list to get updated logs
      } else {
        setError("Failed to update log");
      }
    } catch (err) {
      console.error("Error updating log:", err);
      setError("Failed to update log");
    }
  };

  // Create intuition via API
  const createIntuition = async (activityId: string, intuition: Intuition) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const payload = {
        account_id: selectedOrgAccount.accountId,
        activity_id: activityId,
        metric_id: intuition.metricName, // This should be the actual metric ID
        direction: intuition.direction === "increase" ? "positive" : "negative",
      };
      
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/intuitions/`,
        payload
      );
      
      if (response.data.success) {
        // Update the editingActivity state immediately to show the new intuition in the modal
        if (editingActivity && editingActivity.id === activityId) {
          setEditingActivity({
            ...editingActivity,
            intuitions: [...editingActivity.intuitions, intuition],
          });
        }
        await fetchActivities(); // Refresh the list
      } else {
        setError("Failed to add intuition");
      }
    } catch (err) {
      console.error("Error creating intuition:", err);
      setError("Failed to add intuition");
    }
  };

  // Update intuition via API
  const updateIntuition = async (activityId: string, intuitionId: string, updates: Partial<Intuition>) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/intuitions/`,
        {
          account_id: selectedOrgAccount.accountId,
          activity_id: activityId,
          metric_id: updates.metricName,
          direction: updates.direction === "increase" ? "positive" : "negative",
        }
      );
      
      if (response.data.success) {
        // Update the editingActivity state immediately
        if (editingActivity && editingActivity.id === activityId) {
          const updatedIntuitions = editingActivity.intuitions.map((i) =>
            i.id === intuitionId ? { ...i, ...updates } : i
          );
          setEditingActivity({
            ...editingActivity,
            intuitions: updatedIntuitions,
          });
        }
        await fetchActivities(); // Refresh the list
      } else {
        setError("Failed to update intuition");
      }
    } catch (err) {
      console.error("Error updating intuition:", err);
      setError("Failed to update intuition");
    }
  };

  // Delete intuition via API
  const deleteIntuition = async (activityId: string, metricId: string) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.delete(
        `${API_BASE_URL}/api/v1/intuitions/`,
        {
          data: {
            account_id: selectedOrgAccount.accountId,
            activity_id: activityId,
            metric_id: metricId,
          },
        }
      );
      
      if (response.data.success) {
        await fetchActivities(); // Refresh the list
      } else {
        setError("Failed to delete intuition");
      }
    } catch (err) {
      console.error("Error deleting intuition:", err);
      setError("Failed to delete intuition");
    }
  };

  // Delete log via API
  const deleteLog = async (logId: string, activityId: string) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      return;
    }

    try {
      const response = await axios.delete(
        `${API_BASE_URL}/api/v1/activities/logs`,
        {
          data: {
            account_id: selectedOrgAccount.accountId,
            activity_id: activityId,
            activity_log_id: logId,
          },
        }
      );
      
      if (response.data.success) {
        await fetchActivities(); // Refresh the list
      } else {
        setError("Failed to delete log");
      }
    } catch (err) {
      console.error("Error deleting log:", err);
      setError("Failed to delete log");
    }
  };

  const handleSaveIntuition = async () => {
    if (!editingIntuition.activity || !editingIntuition.intuition?.metricName)
      return;

    // If we're editing within the Activity modal for a new activity being created
    if ((editingIntuition.activity === "temp" || isCreating) && editingActivity) {
      const newIntuition = {
        ...editingIntuition.intuition,
        id: editingIntuition.intuition.id || `i${Date.now()}`,
      };

      if (editingIntuition.intuition.id) {
        // Update existing intuition
        const updatedIntuitions = editingActivity.intuitions.map((i) =>
          i.id === editingIntuition.intuition!.id ? newIntuition : i,
        );
        setEditingActivity({
          ...editingActivity,
          intuitions: updatedIntuitions,
        });
      } else {
        // Add new intuition
        setEditingActivity({
          ...editingActivity,
          intuitions: [...editingActivity.intuitions, newIntuition],
        });
      }
    } else {
      // Regular activity editing (in accordion)
      if (editingIntuition.intuition.id) {
        await updateIntuition(
          editingIntuition.activity,
          editingIntuition.intuition.id,
          editingIntuition.intuition,
        );
      } else {
        await addIntuition(editingIntuition.activity, editingIntuition.intuition);
      }
    }

    setEditingIntuition({ activity: "", intuition: null });
    setShowIntuitionModal(false);
  };

  const handleSaveLog = async () => {
    if (!editingLog.activity || !editingLog.log?.description) return;


    // If we're editing within the Activity modal for a new activity being created
    if ((editingLog.activity === "temp" || isCreating) && editingActivity) {
      const newLog = {
        ...editingLog.log,
        id: editingLog.log.id || `l${Date.now()}`,
      };

      if (editingLog.log.id) {
        // Update existing log
        const updatedLogs = editingActivity.logs.map((l) =>
          l.id === editingLog.log!.id ? newLog : l,
        );
        setEditingActivity({
          ...editingActivity,
          logs: updatedLogs,
        });
      } else {
        // Add new log
        setEditingActivity({
          ...editingActivity,
          logs: [...editingActivity.logs, newLog],
        });
      }
    } else {
      // Regular activity editing (in accordion)
      if (editingLog.log.id) {
        await updateLog(editingLog.activity, editingLog.log.id, editingLog.log);
      } else {
        await addLog(editingLog.activity, editingLog.log);
      }
    }

    setEditingLog({ activity: "", log: null });
    setShowLogModal(false);
  };

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-xl sm:text-2xl font-semibold text-dashboard-gray-900">
            Activities
          </h2>
          <Button
            size="sm"
            onClick={() => {
              setEditingActivity({
                id: "",
                description: "",
                internal: false,
                known: false,
                expectedImpact: "",
                intuitions: [],
                logs: [],
              });
              setIsCreating(true);
              setShowActivityModal(true);
            }}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Activity
          </Button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <Info className="h-5 w-5 text-red-400" />
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-8">
            <div className="text-sm text-gray-500">Loading activities...</div>
          </div>
        )}

        {/* Search and Filter */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search activities..."
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
                {filterStatus !== "all" && (
                  <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                    {filterStatus === "internal"
                      ? "Internal"
                      : filterStatus === "known"
                        ? "Known"
                        : filterStatus === "both"
                          ? "Both"
                          : ""}
                  </span>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem
                onClick={() => {
                  setFilterStatus("all");
                  setShowFilterDropdown(false);
                }}
                className={filterStatus === "all" ? "bg-blue-50" : ""}
              >
                <span className="flex items-center justify-between w-full">
                  All Activities
                  {filterStatus === "all" && (
                    <span className="text-blue-600">✓</span>
                  )}
                </span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  setFilterStatus("internal");
                  setShowFilterDropdown(false);
                }}
                className={filterStatus === "internal" ? "bg-blue-50" : ""}
              >
                <span className="flex items-center justify-between w-full">
                  Internal Only
                  {filterStatus === "internal" && (
                    <span className="text-blue-600">✓</span>
                  )}
                </span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  setFilterStatus("known");
                  setShowFilterDropdown(false);
                }}
                className={filterStatus === "known" ? "bg-blue-50" : ""}
              >
                <span className="flex items-center justify-between w-full">
                  Known Only
                  {filterStatus === "known" && (
                    <span className="text-blue-600">✓</span>
                  )}
                </span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  setFilterStatus("both");
                  setShowFilterDropdown(false);
                }}
                className={filterStatus === "both" ? "bg-blue-50" : ""}
              >
                <span className="flex items-center justify-between w-full">
                  Internal & Known
                  {filterStatus === "both" && (
                    <span className="text-blue-600">✓</span>
                  )}
                </span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Activities Accordion */}
        {!loading && (
          <div className="bg-white border border-dashboard-gray-200 rounded-lg">
            {filteredActivities.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-gray-500 text-sm">
                  {searchTerm || filterStatus !== "all"
                    ? "No activities match your current filter criteria."
                    : "No activities have been added yet."}
                </p>
                {(searchTerm || filterStatus !== "all") && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2"
                    onClick={() => {
                      setSearchTerm("");
                      setFilterStatus("all");
                    }}
                  >
                    Clear filters
                  </Button>
                )}
              </div>
            ) : (
              <Accordion type="multiple" className="w-full">
                {filteredActivities.map((activity) => (
                  <AccordionItem
                    key={activity.id}
                    value={activity.id}
                    className="border-b border-dashboard-gray-200 last:border-b-0"
                  >
                    <div className="flex items-start justify-between px-4 sm:px-6 py-4 gap-3">
                      <AccordionTrigger className="flex items-start gap-3 hover:no-underline [&>svg]:hidden cursor-pointer flex-1 min-w-0">
                        <div className="flex items-center justify-center w-6 h-6 rounded hover:bg-gray-100 transition-colors flex-shrink-0 mt-0.5">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="h-4 w-4 shrink-0 transition-transform duration-200 accordion-chevron text-dashboard-gray-600"
                          >
                            <path d="m6 9 6 6 6-6" />
                          </svg>
                        </div>
                        <div className="text-left flex-1 min-w-0">
                          <p className="text-sm text-dashboard-gray-900 break-words leading-relaxed">
                            {activity.description}
                          </p>
                        </div>
                      </AccordionTrigger>
                      <div className="flex-shrink-0">
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
                              onClick={() => handleEditActivity(activity)}
                            >
                              <Edit2 className="w-4 h-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={() => handleDeleteActivity(activity.id)}
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                    <AccordionContent className="px-6 pb-6">
                      <div className="space-y-6">
                        {/* Full Description */}
                        <div>
                          <Label className="text-sm font-medium text-dashboard-gray-900 mb-2 block">
                            Description
                          </Label>
                          <p className="text-sm text-dashboard-gray-600 break-words">
                            {activity.description}
                          </p>
                        </div>

                        {/* Checkboxes Row */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="flex items-center space-x-2">
                            <Checkbox
                              id={`internal-${activity.id}`}
                              checked={activity.internal}
                              disabled={true}
                              className="opacity-60"
                            />
                            <Label
                              htmlFor={`internal-${activity.id}`}
                              className="text-sm font-medium text-gray-600"
                            >
                              Internal
                            </Label>
                            <Tooltip>
                              <TooltipTrigger>
                                <Info className="h-4 w-4 text-gray-400" />
                              </TooltipTrigger>
                              <TooltipContent className="max-w-xs">
                                <p>
                                  Check if your internal team can choose to
                                  activate this Activity. Leave unchecked for
                                  holidays and other Activities outside of your
                                  control.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>

                          <div className="flex items-center space-x-2">
                            <Checkbox
                              id={`known-${activity.id}`}
                              checked={activity.known}
                              disabled={true}
                              className="opacity-60"
                            />
                            <Label
                              htmlFor={`known-${activity.id}`}
                              className="text-sm font-medium text-gray-600"
                            >
                              Known
                            </Label>
                            <Tooltip>
                              <TooltipTrigger>
                                <Info className="h-4 w-4 text-gray-400" />
                              </TooltipTrigger>
                              <TooltipContent className="max-w-xs">
                                <p>
                                  Check if you always know when this Activity is
                                  active, and it will be recorded in the Logs.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                        </div>

                        {/* Expected Impact */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Label className="text-sm font-medium text-gray-600">
                              Expected Impact
                            </Label>
                            <Tooltip>
                              <TooltipTrigger>
                                <Info className="h-4 w-4 text-gray-400" />
                              </TooltipTrigger>
                              <TooltipContent className="max-w-xs">
                                <p>
                                  Describe the expected impact this activity will
                                  have on your metrics
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          <div className="min-h-[80px] p-3 bg-gray-50 border border-gray-200 rounded-md">
                            <p className="text-sm text-gray-700 whitespace-pre-wrap">
                              {activity.expectedImpact ||
                                "No expected impact description provided."}
                            </p>
                          </div>
                        </div>

                        {/* Intuition and Logs Row */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                          {/* Intuition */}
                          <div>
                            <div className="flex items-center gap-2 mb-3">
                              <Label className="text-sm font-medium text-gray-600">
                                Intuition
                              </Label>
                              <Tooltip>
                                <TooltipTrigger>
                                  <Info className="h-4 w-4 text-gray-400" />
                                </TooltipTrigger>
                                <TooltipContent className="max-w-sm">
                                  <p>
                                    Identify any metrics that will reliably be
                                    influenced by this Activity when it is active
                                    (at least 80% of the time), and indicate if
                                    the metrics is expected to be influenced in a
                                    'positive' or 'negative' direction.
                                  </p>
                                </TooltipContent>
                              </Tooltip>
                            </div>
                            <div className="space-y-2">
                              {activity.intuitions.map((intuition) => (
                                <div
                                  key={intuition.id}
                                  className="p-2 bg-gray-50 rounded border"
                                >
                                  <span className="text-sm text-gray-700">
                                    {getMetricNameById(intuition.metricName)} [{intuition.direction}]
                                  </span>
                                </div>
                              ))}
                              {activity.intuitions.length === 0 && (
                                <p className="text-sm text-gray-500 italic">
                                  No intuitions added yet
                                </p>
                              )}
                            </div>
                          </div>

                          {/* Logs */}
                          <div>
                            <div className="flex items-center gap-2 mb-3">
                              <Label className="text-sm font-medium text-gray-600">
                                Logs
                              </Label>
                              <Tooltip>
                                <TooltipTrigger>
                                  <Info className="h-4 w-4 text-gray-400" />
                                </TooltipTrigger>
                                <TooltipContent className="max-w-xs">
                                  <p>Timeline and history of this activity</p>
                                </TooltipContent>
                              </Tooltip>
                            </div>
                            <div className="space-y-2">
                              {activity.logs.map((log) => (
                                <div
                                  key={log.id}
                                  className="p-2 bg-gray-50 rounded border"
                                >
                                  <div className="flex items-center gap-2 mb-1">
                                    <Calendar className="w-3 h-3 text-gray-500" />
                                    <span className="text-xs text-gray-600">
                                      {log.startDate} to {log.endDate}
                                    </span>
                                  </div>
                                  <p className="text-sm text-gray-700">
                                    {log.description}
                                  </p>
                                </div>
                              ))}
                              {activity.logs.length === 0 && (
                                <p className="text-sm text-gray-500 italic">
                                  No logs added yet
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </div>
        )}

        {/* Intuition Modal */}
        <Dialog 
          open={showIntuitionModal} 
          onOpenChange={(open) => {
            if (!open) {
              setShowIntuitionModal(false);
              setEditingIntuition({ activity: "", intuition: null });
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingIntuition.intuition?.id ? "Edit" : "Add"} Intuition
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* Metric Selection with Search and Filters */}
              <div>
                <Label htmlFor="metric-name">Select Metric</Label>

                {/* Search and Filter Controls */}
                <div className="space-y-3 mt-2">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        placeholder="Search metrics..."
                        value={metricSearchTerm}
                        onChange={(e) => setMetricSearchTerm(e.target.value)}
                        className="pl-10"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <Select
                      value={selectedDataset}
                      onValueChange={setSelectedDataset}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="All Datasets" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Datasets</SelectItem>
                        {datasetsData.map((dataset) => (
                          <SelectItem key={dataset.dataset_id} value={dataset.dataset_name}>
                            {dataset.dataset_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select
                      value={selectedProduct}
                      onValueChange={setSelectedProduct}
                    >
                      <SelectTrigger>
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
                </div>

                {/* Metric Selection */}
                <div className="mt-3">
                  <Select
                    value={editingIntuition.intuition?.metricName || ""}
                    onValueChange={(value) =>
                      setEditingIntuition((prev) => ({
                        ...prev,
                        intuition: prev.intuition
                          ? { ...prev.intuition, metricName: value }
                          : null,
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a metric" />
                    </SelectTrigger>
                    <SelectContent className="max-h-60">
                      {filteredMetrics.length === 0 ? (
                        <div className="p-2 text-center text-gray-500 text-sm">
                          No metrics match your search criteria
                        </div>
                      ) : (
                        filteredMetrics.map((metric) => (
                          <SelectItem key={metric.id} value={metric.id}>
                            <div className="flex flex-col">
                              <span className="font-medium">{metric.name}</span>
                              <span className="text-xs text-gray-500">
                                {metric.product} •{" "}
                                {
                                  datasetsData.find((d) => d.dataset_name === metric.dataset)
                                    ?.dataset_name || metric.dataset
                                }
                              </span>
                            </div>
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>

                  {filteredMetrics.length > 0 && (
                    <p className="text-xs text-gray-500 mt-1">
                      Showing {filteredMetrics.length} of{" "}
                      {availableMetrics.length} metrics
                    </p>
                  )}
                </div>
              </div>
              <div>
                <Label>Direction</Label>
                <div className="flex gap-4 mt-2">
                  <label className="flex items-center space-x-2">
                    <input
                      type="radio"
                      value="increase"
                      checked={
                        editingIntuition.intuition?.direction === "increase"
                      }
                      onChange={(e) =>
                        setEditingIntuition((prev) => ({
                          ...prev,
                          intuition: prev.intuition
                            ? {
                                ...prev.intuition,
                                direction: e.target.value as
                                  | "increase"
                                  | "decrease",
                              }
                            : null,
                        }))
                      }
                    />
                    <span className="text-sm">Increase</span>
                  </label>
                  <label className="flex items-center space-x-2">
                    <input
                      type="radio"
                      value="decrease"
                      checked={
                        editingIntuition.intuition?.direction === "decrease"
                      }
                      onChange={(e) =>
                        setEditingIntuition((prev) => ({
                          ...prev,
                          intuition: prev.intuition
                            ? {
                                ...prev.intuition,
                                direction: e.target.value as
                                  | "increase"
                                  | "decrease",
                              }
                            : null,
                        }))
                      }
                    />
                    <span className="text-sm">Decrease</span>
                  </label>
                </div>
              </div>
              <div className="flex gap-2 pt-4">
                <Button onClick={handleSaveIntuition}>
                  {editingIntuition.intuition?.id ? "Update" : "Add"} Intuition
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setShowIntuitionModal(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Log Modal */}
        <Dialog 
          open={showLogModal} 
          onOpenChange={(open) => {
            if (!open) {
              setShowLogModal(false);
              setEditingLog({ activity: "", log: null });
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingLog.log?.id ? "Edit" : "Add"} Log
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="start-date">Start Date</Label>
                  <Input
                    id="start-date"
                    type="date"
                    value={editingLog.log?.startDate || ""}
                    onChange={(e) =>
                      setEditingLog((prev) => ({
                        ...prev,
                        log: prev.log
                          ? { ...prev.log, startDate: e.target.value }
                          : null,
                      }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="end-date">End Date</Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={editingLog.log?.endDate || ""}
                    onChange={(e) =>
                      setEditingLog((prev) => ({
                        ...prev,
                        log: prev.log
                          ? { ...prev.log, endDate: e.target.value }
                          : null,
                      }))
                    }
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="log-description">Description</Label>
                <Textarea
                  id="log-description"
                  value={editingLog.log?.description || ""}
                  onChange={(e) =>
                    setEditingLog((prev) => ({
                      ...prev,
                      log: prev.log
                        ? { ...prev.log, description: e.target.value }
                        : null,
                    }))
                  }
                  placeholder="Describe what happened during this time period"
                  rows={3}
                />
              </div>
              <div className="flex gap-2 pt-4">
                <Button onClick={handleSaveLog}>
                  {editingLog.log?.id ? "Update" : "Add"} Log
                </Button>
                <Button variant="ghost" onClick={() => setShowLogModal(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Activity Modal */}
        <Dialog 
          open={showActivityModal} 
          onOpenChange={(open) => {
            if (!open) {
              setShowActivityModal(false);
              setEditingActivity(null);
              setIsCreating(false);
            }
          }}
        >
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{isCreating ? "Add" : "Edit"} Activity</DialogTitle>
            </DialogHeader>
            <div className="space-y-6">
              {/* Description */}
              <div>
                <Label htmlFor="activity-description">Description *</Label>
                <Textarea
                  id="activity-description"
                  value={editingActivity?.description || ""}
                  onChange={(e) =>
                    setEditingActivity((prev) =>
                      prev ? { ...prev, description: e.target.value } : null,
                    )
                  }
                  placeholder="Describe the activity..."
                  rows={3}
                  className="resize-none"
                />
              </div>

              {/* Checkboxes */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="activity-internal"
                    checked={editingActivity?.internal || false}
                    onCheckedChange={(checked) =>
                      setEditingActivity((prev) =>
                        prev ? { ...prev, internal: checked as boolean } : null,
                      )
                    }
                  />
                  <Label
                    htmlFor="activity-internal"
                    className="text-sm font-medium"
                  >
                    Internal
                  </Label>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>
                        Check if your internal team can choose to activate this
                        Activity. Leave unchecked for holidays and other
                        Activities outside of your control.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="activity-known"
                    checked={editingActivity?.known || false}
                    onCheckedChange={(checked) =>
                      setEditingActivity((prev) =>
                        prev ? { ...prev, known: checked as boolean } : null,
                      )
                    }
                  />
                  <Label
                    htmlFor="activity-known"
                    className="text-sm font-medium"
                  >
                    Known
                  </Label>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>
                        Check if you always know when this Activity is active,
                        and it will be recorded in the Logs.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>

              {/* Expected Impact */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Label
                    htmlFor="activity-impact"
                    className="text-sm font-medium"
                  >
                    Expected Impact
                  </Label>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>
                        Describe the expected impact this activity will have on
                        your metrics
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Textarea
                  id="activity-impact"
                  value={editingActivity?.expectedImpact || ""}
                  onChange={(e) =>
                    setEditingActivity((prev) =>
                      prev
                        ? {
                            ...prev,
                            expectedImpact: e.target.value.slice(0, 255),
                          }
                        : null,
                    )
                  }
                  placeholder="Describe the expected impact of this activity..."
                  maxLength={255}
                  rows={3}
                  className="resize-none"
                />
                <p className="text-xs text-gray-500 mt-1">
                  {(editingActivity?.expectedImpact || "").length}/255
                  characters
                </p>
              </div>

              {/* Intuition and Logs Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Intuition */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm font-medium text-dashboard-gray-900">
                        Intuition
                      </Label>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-gray-400" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-sm">
                          <p>
                            Identify any metrics that will reliably be
                            influenced by this Activity when it is active (at
                            least 80% of the time), and indicate if the metrics
                            is expected to be influenced in a 'positive' or
                            'negative' direction.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        openIntuitionModal(isCreating ? "temp" : (editingActivity?.id || "temp"))
                      }
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {(editingActivity?.intuitions || []).map((intuition) => (
                      <div
                        key={intuition.id}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded"
                      >
                        <span className="text-sm text-gray-700">
                          {getMetricNameById(intuition.metricName)} [{intuition.direction}]
                        </span>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0"
                            onClick={() =>
                              openIntuitionModal(
                                isCreating ? "temp" : (editingActivity?.id || "temp"),
                                intuition,
                              )
                            }
                          >
                            <Edit2 className="w-3 h-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0"
                            onClick={async () => {
                              if (editingActivity) {
                                // If this is a new activity being created, just remove from local state
                                if (isCreating) {
                                  const updatedIntuitions =
                                    editingActivity.intuitions.filter(
                                      (i) => i.id !== intuition.id,
                                    );
                                  setEditingActivity({
                                    ...editingActivity,
                                    intuitions: updatedIntuitions,
                                  });
                                } else {
                                  // For existing activities, delete via API and update local state
                                  await deleteIntuition(editingActivity.id, intuition.metricName);
                                  const updatedIntuitions =
                                    editingActivity.intuitions.filter(
                                      (i) => i.id !== intuition.id,
                                    );
                                  setEditingActivity({
                                    ...editingActivity,
                                    intuitions: updatedIntuitions,
                                  });
                                }
                              }
                            }}
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                    {(editingActivity?.intuitions || []).length === 0 && (
                      <p className="text-sm text-gray-500 italic">
                        No intuitions added yet
                      </p>
                    )}
                  </div>
                </div>

                {/* Logs */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm font-medium text-dashboard-gray-900">
                        Logs
                      </Label>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-gray-400" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p>Timeline and history of this activity</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingLog({
                          activity: isCreating ? "temp" : (editingActivity?.id || "temp"),
                          log: {
                            id: "",
                            startDate: "",
                            endDate: "",
                            description: "",
                          },
                        });
                        setShowLogModal(true);
                      }}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {(editingActivity?.logs || []).map((log) => (
                      <div
                        key={log.id}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Calendar className="w-3 h-3 text-gray-500" />
                            <span className="text-xs text-gray-600">
                              {log.startDate} to {log.endDate}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700 truncate">
                            {log.description}
                          </p>
                        </div>
                        <div className="flex gap-1 ml-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0"
                            onClick={() => {
                              setEditingLog({
                                activity: isCreating ? "temp" : (editingActivity?.id || "temp"),
                                log,
                              });
                              setShowLogModal(true);
                            }}
                          >
                            <Edit2 className="w-3 h-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0"
                            onClick={async () => {
                              if (editingActivity) {
                                // If this is a new activity being created, just remove from local state
                                if (isCreating) {
                                  const updatedLogs = editingActivity.logs.filter(
                                    (l) => l.id !== log.id,
                                  );
                                  setEditingActivity({
                                    ...editingActivity,
                                    logs: updatedLogs,
                                  });
                                } else {
                                  // For existing activities, delete via API and update local state
                                  await deleteLog(log.id, editingActivity.id);
                                  const updatedLogs = editingActivity.logs.filter(
                                    (l) => l.id !== log.id,
                                  );
                                  setEditingActivity({
                                    ...editingActivity,
                                    logs: updatedLogs,
                                  });
                                }
                              }
                            }}
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                    {(editingActivity?.logs || []).length === 0 && (
                      <p className="text-sm text-gray-500 italic">
                        No logs added yet
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-4">
                <Button onClick={handleSaveActivity}>
                  {isCreating ? "Add" : "Update"} Activity
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowActivityModal(false);
                    setEditingActivity(null);
                    setIsCreating(false);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
};

export default ActivitiesPage;
