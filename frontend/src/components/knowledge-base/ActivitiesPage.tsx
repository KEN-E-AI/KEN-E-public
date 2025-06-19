import { useState, useMemo } from "react";
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
import {
  activities,
  type Activity as ImportedActivity,
} from "@/data/activities";

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

// Available datasets for filtering
const datasets = [
  { id: "ga4_sessions", name: "GA4 Sessions", product: "Google Analytics" },
  { id: "ga4_events", name: "GA4 Events", product: "Google Analytics" },
  { id: "google_ads", name: "Google Ads", product: "Google Ads" },
  { id: "facebook_ads", name: "Facebook Ads", product: "Meta" },
  { id: "salesforce", name: "Salesforce", product: "Salesforce" },
  { id: "email_marketing", name: "Email Marketing", product: "Mailchimp" },
  { id: "social_media", name: "Social Media", product: "Social Platforms" },
];

// Available metrics for intuition selection
const availableMetrics: AvailableMetric[] = [
  {
    id: "1",
    name: "Engaged Sessions",
    dataset: "ga4_sessions",
    product: "Google Analytics",
  },
  {
    id: "2",
    name: "Transactions",
    dataset: "ga4_sessions",
    product: "Google Analytics",
  },
  {
    id: "3",
    name: "Page Views",
    dataset: "ga4_events",
    product: "Google Analytics",
  },
  {
    id: "4",
    name: "Session Duration",
    dataset: "ga4_sessions",
    product: "Google Analytics",
  },
  {
    id: "5",
    name: "Bounce Rate",
    dataset: "ga4_sessions",
    product: "Google Analytics",
  },
  {
    id: "6",
    name: "Conversion Rate",
    dataset: "ga4_events",
    product: "Google Analytics",
  },
  {
    id: "7",
    name: "New Users",
    dataset: "ga4_sessions",
    product: "Google Analytics",
  },
  {
    id: "8",
    name: "Returning Users",
    dataset: "ga4_sessions",
    product: "Google Analytics",
  },
  {
    id: "9",
    name: "Cost Per Click",
    dataset: "google_ads",
    product: "Google Ads",
  },
  {
    id: "10",
    name: "Click Through Rate",
    dataset: "google_ads",
    product: "Google Ads",
  },
  {
    id: "11",
    name: "Impressions",
    dataset: "google_ads",
    product: "Google Ads",
  },
  {
    id: "12",
    name: "Cost Per Acquisition",
    dataset: "google_ads",
    product: "Google Ads",
  },
  {
    id: "13",
    name: "Facebook Reach",
    dataset: "facebook_ads",
    product: "Meta",
  },
  {
    id: "14",
    name: "Facebook Engagement",
    dataset: "facebook_ads",
    product: "Meta",
  },
  { id: "15", name: "Ad Spend", dataset: "facebook_ads", product: "Meta" },
  {
    id: "16",
    name: "Lead Generation",
    dataset: "salesforce",
    product: "Salesforce",
  },
  {
    id: "17",
    name: "Deal Value",
    dataset: "salesforce",
    product: "Salesforce",
  },
  {
    id: "18",
    name: "Sales Pipeline",
    dataset: "salesforce",
    product: "Salesforce",
  },
  {
    id: "19",
    name: "Email Open Rate",
    dataset: "email_marketing",
    product: "Mailchimp",
  },
  {
    id: "20",
    name: "Email Click Rate",
    dataset: "email_marketing",
    product: "Mailchimp",
  },
  {
    id: "21",
    name: "Social Media Followers",
    dataset: "social_media",
    product: "Social Platforms",
  },
  {
    id: "22",
    name: "Brand Mentions",
    dataset: "social_media",
    product: "Social Platforms",
  },
];

const initialActivities: Activity[] = [
  {
    id: "1",
    description:
      "Your brand or products are featured or referenced in news and press outlets.",
    internal: false,
    known: true,
    expectedImpact:
      "This activity is expected to build awareness of the brand and drive users to the website.",
    intuitions: [
      { id: "i1", metricName: "Brand Mentions", direction: "increase" },
      { id: "i2", metricName: "Website Traffic", direction: "increase" },
    ],
    logs: [
      {
        id: "l1",
        startDate: "2024-01-01",
        endDate: "2024-01-31",
        description: "Q1 PR campaign launch",
      },
      {
        id: "l2",
        startDate: "2024-02-01",
        endDate: "2024-02-28",
        description: "Product announcement coverage",
      },
    ],
  },
  {
    id: "2",
    description:
      "Offer a temporary promotion or discount to a product/service.",
    internal: true,
    known: true,
    expectedImpact:
      "Expected to drive short-term conversions and clear inventory.",
    intuitions: [
      { id: "i3", metricName: "Conversion Rate", direction: "increase" },
      { id: "i4", metricName: "Average Order Value", direction: "decrease" },
    ],
    logs: [],
  },
  {
    id: "3",
    description: "Do something else...",
    internal: false,
    known: false,
    expectedImpact: "",
    intuitions: [],
    logs: [],
  },
];

const ActivitiesPage = () => {
  // Convert imported activities to component format
  const convertedActivities: Activity[] = activities.map((activity) => ({
    id: activity.activity_id,
    description: activity.description,
    internal: activity.internal,
    known: activity.known_activity,
    expectedImpact: activity.expected_impact,
    intuitions: activity.intuition.map((intuition, index) => {
      const [metricName, direction] = Object.entries(intuition)[0];
      return {
        id: `i${activity.activity_id}_${index}`,
        metricName,
        direction: direction as "increase" | "decrease",
      };
    }),
    logs: activity.logs.map((log) => ({
      id: log.activity_log_id,
      startDate: log.start_date,
      endDate: log.end_date,
      description: log.description,
    })),
  }));

  const [activitiesData, setActivitiesData] =
    useState<Activity[]>(convertedActivities);
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
  }, [activities, searchTerm, filterStatus]);

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
  }, [metricSearchTerm, selectedDataset, selectedProduct]);

  // Get unique products for filtering - optimized with useMemo
  const uniqueProducts = useMemo(() => {
    return [...new Set(availableMetrics.map((m) => m.product))];
  }, []);

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
  const updateActivity = (activityId: string, updates: Partial<Activity>) => {
    setActivities((prev) =>
      prev.map((activity) =>
        activity.id === activityId ? { ...activity, ...updates } : activity,
      ),
    );
  };

  const addActivity = (activity: Omit<Activity, "id">) => {
    const newActivity = { ...activity, id: `a${Date.now()}` };
    setActivities((prev) => [...prev, newActivity]);
  };

  const deleteActivity = (activityId: string) => {
    setActivities((prev) =>
      prev.filter((activity) => activity.id !== activityId),
    );
  };

  const handleEditActivity = (activity: Activity) => {
    setEditingActivity(activity);
    setIsCreating(false);
    setShowActivityModal(true);
  };

  const handleSaveActivity = () => {
    if (!editingActivity || !editingActivity.description.trim()) return;

    if (isCreating) {
      addActivity(editingActivity);
    } else {
      updateActivity(editingActivity.id, editingActivity);
    }

    setEditingActivity(null);
    setIsCreating(false);
    setShowActivityModal(false);
  };

  const addIntuition = (
    activityId: string,
    intuition: Omit<Intuition, "id">,
  ) => {
    const newIntuition = { ...intuition, id: `i${Date.now()}` };
    updateActivity(activityId, {
      intuitions: [
        ...(activitiesData.find((a) => a.id === activityId)?.intuitions || []),
        newIntuition,
      ],
    });
  };

  const updateIntuition = (
    activityId: string,
    intuitionId: string,
    updates: Partial<Intuition>,
  ) => {
    const activity = activitiesData.find((a) => a.id === activityId);
    if (activity) {
      const updatedIntuitions = activity.intuitions.map((i) =>
        i.id === intuitionId ? { ...i, ...updates } : i,
      );
      updateActivity(activityId, { intuitions: updatedIntuitions });
    }
  };

  const deleteIntuition = (activityId: string, intuitionId: string) => {
    const activity = activitiesData.find((a) => a.id === activityId);
    if (activity) {
      const updatedIntuitions = activity.intuitions.filter(
        (i) => i.id !== intuitionId,
      );
      updateActivity(activityId, { intuitions: updatedIntuitions });
    }
  };

  const addLog = (activityId: string, log: Omit<Log, "id">) => {
    const newLog = { ...log, id: `l${Date.now()}` };
    updateActivity(activityId, {
      logs: [
        ...(activitiesData.find((a) => a.id === activityId)?.logs || []),
        newLog,
      ],
    });
  };

  const updateLog = (
    activityId: string,
    logId: string,
    updates: Partial<Log>,
  ) => {
    const activity = activities.find((a) => a.id === activityId);
    if (activity) {
      const updatedLogs = activity.logs.map((l) =>
        l.id === logId ? { ...l, ...updates } : l,
      );
      updateActivity(activityId, { logs: updatedLogs });
    }
  };

  const deleteLog = (activityId: string, logId: string) => {
    const activity = activities.find((a) => a.id === activityId);
    if (activity) {
      const updatedLogs = activity.logs.filter((l) => l.id !== logId);
      updateActivity(activityId, { logs: updatedLogs });
    }
  };

  const handleSaveIntuition = () => {
    if (!editingIntuition.activity || !editingIntuition.intuition?.metricName)
      return;

    // If we're editing within the Activity modal (temp activity)
    if (editingIntuition.activity === "temp" && editingActivity) {
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
        updateIntuition(
          editingIntuition.activity,
          editingIntuition.intuition.id,
          editingIntuition.intuition,
        );
      } else {
        addIntuition(editingIntuition.activity, editingIntuition.intuition);
      }
    }

    setEditingIntuition({ activity: "", intuition: null });
    setShowIntuitionModal(false);
  };

  const handleSaveLog = () => {
    if (!editingLog.activity || !editingLog.log?.description) return;

    // If we're editing within the Activity modal (temp activity)
    if (editingLog.activity === "temp" && editingActivity) {
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
        updateLog(editingLog.activity, editingLog.log.id, editingLog.log);
      } else {
        addLog(editingLog.activity, editingLog.log);
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
                            onClick={() => deleteActivity(activity.id)}
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
                                  {intuition.metricName} [{intuition.direction}]
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

        {/* Intuition Modal */}
        <Dialog open={showIntuitionModal} onOpenChange={setShowIntuitionModal}>
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
                        {datasets.map((dataset) => (
                          <SelectItem key={dataset.id} value={dataset.id}>
                            {dataset.name}
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
                          <SelectItem key={metric.id} value={metric.name}>
                            <div className="flex flex-col">
                              <span className="font-medium">{metric.name}</span>
                              <span className="text-xs text-gray-500">
                                {metric.product} •{" "}
                                {
                                  datasets.find((d) => d.id === metric.dataset)
                                    ?.name
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
        <Dialog open={showLogModal} onOpenChange={setShowLogModal}>
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
        <Dialog open={showActivityModal} onOpenChange={setShowActivityModal}>
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
                        openIntuitionModal(editingActivity?.id || "temp")
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
                          {intuition.metricName} [{intuition.direction}]
                        </span>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0"
                            onClick={() =>
                              openIntuitionModal(
                                editingActivity?.id || "temp",
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
                            onClick={() => {
                              if (editingActivity) {
                                const updatedIntuitions =
                                  editingActivity.intuitions.filter(
                                    (i) => i.id !== intuition.id,
                                  );
                                setEditingActivity({
                                  ...editingActivity,
                                  intuitions: updatedIntuitions,
                                });
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
                          activity: editingActivity?.id || "temp",
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
                                activity: editingActivity?.id || "temp",
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
                            onClick={() => {
                              if (editingActivity) {
                                const updatedLogs = editingActivity.logs.filter(
                                  (l) => l.id !== log.id,
                                );
                                setEditingActivity({
                                  ...editingActivity,
                                  logs: updatedLogs,
                                });
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
