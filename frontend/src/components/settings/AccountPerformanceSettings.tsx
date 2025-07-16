import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  TrendingUp,
  Target,
  BarChart3,
  AlertTriangle,
  Bell,
  Calendar,
  Save,
  Plus,
  X,
  LineChart,
  PieChart,
} from "lucide-react";

interface KPI {
  id: string;
  name: string;
  description: string;
  target: number;
  current: number;
  unit: string;
  trend: "up" | "down" | "stable";
  frequency: "daily" | "weekly" | "monthly";
  alerts: {
    threshold: number;
    type: "above" | "below";
    enabled: boolean;
  };
}

interface PerformanceAlert {
  id: string;
  name: string;
  condition: string;
  threshold: number;
  frequency: "immediate" | "daily" | "weekly";
  recipients: string[];
  enabled: boolean;
}

interface ReportSchedule {
  id: string;
  name: string;
  frequency: "daily" | "weekly" | "monthly";
  recipients: string[];
  metrics: string[];
  enabled: boolean;
}

interface AccountPerformanceSettingsProps {
  accountId: string;
  performanceData: {
    kpis: KPI[];
    alerts: PerformanceAlert[];
    reports: ReportSchedule[];
    dashboard: {
      refresh_interval: number;
      show_trends: boolean;
      show_comparisons: boolean;
      default_date_range: "7d" | "30d" | "90d";
    };
    targets: {
      auto_update: boolean;
      notification_threshold: number;
      benchmark_comparison: boolean;
    };
  };
  onUpdate: (
    updates: Partial<AccountPerformanceSettingsProps["performanceData"]>,
  ) => void;
}

export const AccountPerformanceSettings = ({
  accountId,
  performanceData,
  onUpdate,
}: AccountPerformanceSettingsProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [kpis, setKPIs] = useState(performanceData.kpis);
  const [alerts, setAlerts] = useState(performanceData.alerts);
  const [reports, setReports] = useState(performanceData.reports);
  const [dashboard, setDashboard] = useState(performanceData.dashboard);
  const [targets, setTargets] = useState(performanceData.targets);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({ kpis, alerts, reports, dashboard, targets });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setKPIs(performanceData.kpis);
    setAlerts(performanceData.alerts);
    setReports(performanceData.reports);
    setDashboard(performanceData.dashboard);
    setTargets(performanceData.targets);
    setIsEditing(false);
  };

  const addKPI = () => {
    const newKPI: KPI = {
      id: Date.now().toString(),
      name: "New KPI",
      description: "",
      target: 0,
      current: 0,
      unit: "",
      trend: "stable",
      frequency: "monthly",
      alerts: {
        threshold: 0,
        type: "below",
        enabled: false,
      },
    };
    setKPIs([...kpis, newKPI]);
  };

  const updateKPI = (id: string, updates: Partial<KPI>) => {
    setKPIs(kpis.map((kpi) => (kpi.id === id ? { ...kpi, ...updates } : kpi)));
  };

  const removeKPI = (id: string) => {
    setKPIs(kpis.filter((kpi) => kpi.id !== id));
  };

  const addAlert = () => {
    const newAlert: PerformanceAlert = {
      id: Date.now().toString(),
      name: "New Alert",
      condition: "below_threshold",
      threshold: 0,
      frequency: "immediate",
      recipients: [],
      enabled: true,
    };
    setAlerts([...alerts, newAlert]);
  };

  const updateAlert = (id: string, updates: Partial<PerformanceAlert>) => {
    setAlerts(
      alerts.map((alert) =>
        alert.id === id ? { ...alert, ...updates } : alert,
      ),
    );
  };

  const removeAlert = (id: string) => {
    setAlerts(alerts.filter((alert) => alert.id !== id));
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case "up":
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case "down":
        return <TrendingUp className="h-4 w-4 text-red-500 rotate-180" />;
      default:
        return <LineChart className="h-4 w-4 text-gray-500" />;
    }
  };

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case "up":
        return "bg-green-50 text-green-700 border-green-200";
      case "down":
        return "bg-red-50 text-red-700 border-red-200";
      default:
        return "bg-gray-50 text-gray-700 border-gray-200";
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit}>
        {/* KPIs */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Key Performance Indicators
              </div>
              {isEditing && (
                <Button type="button" size="sm" onClick={addKPI}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add KPI
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {kpis.map((kpi) => (
                <div key={kpi.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      {isEditing ? (
                        <div className="space-y-2">
                          <Input
                            value={kpi.name}
                            onChange={(e) =>
                              updateKPI(kpi.id, { name: e.target.value })
                            }
                            className="font-medium"
                            placeholder="KPI Name"
                          />
                          <Textarea
                            value={kpi.description}
                            onChange={(e) =>
                              updateKPI(kpi.id, { description: e.target.value })
                            }
                            placeholder="Description"
                            rows={2}
                          />
                        </div>
                      ) : (
                        <div>
                          <h3 className="font-medium">{kpi.name}</h3>
                          <p className="text-sm text-dashboard-gray-600">
                            {kpi.description}
                          </p>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={getTrendColor(kpi.trend)}>
                        {getTrendIcon(kpi.trend)}
                        {kpi.trend}
                      </Badge>
                      {isEditing && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeKPI(kpi.id)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div>
                      <Label>Current Value</Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          value={kpi.current}
                          onChange={(e) =>
                            updateKPI(kpi.id, {
                              current: parseInt(e.target.value),
                            })
                          }
                          disabled={!isEditing}
                          className="mt-1"
                        />
                        <span className="text-sm text-dashboard-gray-600">
                          {kpi.unit}
                        </span>
                      </div>
                    </div>
                    <div>
                      <Label>Target</Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          value={kpi.target}
                          onChange={(e) =>
                            updateKPI(kpi.id, {
                              target: parseInt(e.target.value),
                            })
                          }
                          disabled={!isEditing}
                          className="mt-1"
                        />
                        <span className="text-sm text-dashboard-gray-600">
                          {kpi.unit}
                        </span>
                      </div>
                    </div>
                    <div>
                      <Label>Unit</Label>
                      <Input
                        value={kpi.unit}
                        onChange={(e) =>
                          updateKPI(kpi.id, { unit: e.target.value })
                        }
                        disabled={!isEditing}
                        className="mt-1"
                        placeholder="e.g., %, $, clicks"
                      />
                    </div>
                    <div>
                      <Label>Frequency</Label>
                      <Select
                        value={kpi.frequency}
                        onValueChange={(
                          value: "daily" | "weekly" | "monthly",
                        ) => updateKPI(kpi.id, { frequency: value })}
                        disabled={!isEditing}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="daily">Daily</SelectItem>
                          <SelectItem value="weekly">Weekly</SelectItem>
                          <SelectItem value="monthly">Monthly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* KPI Alerts */}
                  <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-sm font-medium">
                        Performance Alerts
                      </Label>
                      <Switch
                        checked={kpi.alerts.enabled}
                        onCheckedChange={(checked) =>
                          updateKPI(kpi.id, {
                            alerts: { ...kpi.alerts, enabled: checked },
                          })
                        }
                        disabled={!isEditing}
                      />
                    </div>
                    {kpi.alerts.enabled && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <Label>Alert Type</Label>
                          <Select
                            value={kpi.alerts.type}
                            onValueChange={(value: "above" | "below") =>
                              updateKPI(kpi.id, {
                                alerts: { ...kpi.alerts, type: value },
                              })
                            }
                            disabled={!isEditing}
                          >
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="above">
                                Above threshold
                              </SelectItem>
                              <SelectItem value="below">
                                Below threshold
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Threshold</Label>
                          <Input
                            type="number"
                            value={kpi.alerts.threshold}
                            onChange={(e) =>
                              updateKPI(kpi.id, {
                                alerts: {
                                  ...kpi.alerts,
                                  threshold: parseInt(e.target.value),
                                },
                              })
                            }
                            disabled={!isEditing}
                            className="mt-1"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Performance Alerts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Performance Alerts
              </div>
              {isEditing && (
                <Button type="button" size="sm" onClick={addAlert}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Alert
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {alerts.map((alert) => (
                <div key={alert.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      {isEditing ? (
                        <Input
                          value={alert.name}
                          onChange={(e) =>
                            updateAlert(alert.id, { name: e.target.value })
                          }
                          className="font-medium"
                          placeholder="Alert Name"
                        />
                      ) : (
                        <h3 className="font-medium">{alert.name}</h3>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={alert.enabled ? "default" : "secondary"}>
                        {alert.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                      {isEditing && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeAlert(alert.id)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label>Condition</Label>
                      <Select
                        value={alert.condition}
                        onValueChange={(value) =>
                          updateAlert(alert.id, { condition: value })
                        }
                        disabled={!isEditing}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="below_threshold">
                            Below threshold
                          </SelectItem>
                          <SelectItem value="above_threshold">
                            Above threshold
                          </SelectItem>
                          <SelectItem value="percentage_change">
                            Percentage change
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Threshold</Label>
                      <Input
                        type="number"
                        value={alert.threshold}
                        onChange={(e) =>
                          updateAlert(alert.id, {
                            threshold: parseInt(e.target.value),
                          })
                        }
                        disabled={!isEditing}
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Frequency</Label>
                      <Select
                        value={alert.frequency}
                        onValueChange={(
                          value: "immediate" | "daily" | "weekly",
                        ) => updateAlert(alert.id, { frequency: value })}
                        disabled={!isEditing}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="immediate">Immediate</SelectItem>
                          <SelectItem value="daily">Daily</SelectItem>
                          <SelectItem value="weekly">Weekly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Dashboard Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Dashboard Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Refresh Interval (seconds)</Label>
                  <Input
                    type="number"
                    value={dashboard.refresh_interval}
                    onChange={(e) =>
                      setDashboard({
                        ...dashboard,
                        refresh_interval: parseInt(e.target.value),
                      })
                    }
                    disabled={!isEditing}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Default Date Range</Label>
                  <Select
                    value={dashboard.default_date_range}
                    onValueChange={(value: "7d" | "30d" | "90d") =>
                      setDashboard({ ...dashboard, default_date_range: value })
                    }
                    disabled={!isEditing}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="7d">Last 7 days</SelectItem>
                      <SelectItem value="30d">Last 30 days</SelectItem>
                      <SelectItem value="90d">Last 90 days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Show trends</Label>
                  <Switch
                    checked={dashboard.show_trends}
                    onCheckedChange={(checked) =>
                      setDashboard({ ...dashboard, show_trends: checked })
                    }
                    disabled={!isEditing}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Show comparisons</Label>
                  <Switch
                    checked={dashboard.show_comparisons}
                    onCheckedChange={(checked) =>
                      setDashboard({ ...dashboard, show_comparisons: checked })
                    }
                    disabled={!isEditing}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Target Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              Target Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Auto-update targets
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Automatically adjust targets based on performance trends
                  </p>
                </div>
                <Switch
                  checked={targets.auto_update}
                  onCheckedChange={(checked) =>
                    setTargets({ ...targets, auto_update: checked })
                  }
                  disabled={!isEditing}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Benchmark comparison
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Compare performance against industry benchmarks
                  </p>
                </div>
                <Switch
                  checked={targets.benchmark_comparison}
                  onCheckedChange={(checked) =>
                    setTargets({ ...targets, benchmark_comparison: checked })
                  }
                  disabled={!isEditing}
                />
              </div>

              <div>
                <Label>Notification threshold (%)</Label>
                <Input
                  type="number"
                  value={targets.notification_threshold}
                  onChange={(e) =>
                    setTargets({
                      ...targets,
                      notification_threshold: parseInt(e.target.value),
                    })
                  }
                  disabled={!isEditing}
                  className="mt-1"
                  placeholder="e.g., 80"
                />
                <p className="text-sm text-dashboard-gray-600 mt-1">
                  Get notified when performance is below this percentage of
                  target
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          {isEditing ? (
            <>
              <Button type="button" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
              <Button type="submit">
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </>
          ) : (
            <Button type="button" onClick={() => setIsEditing(true)}>
              Edit Performance Settings
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};
