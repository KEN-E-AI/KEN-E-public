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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Target,
  TrendingUp,
  Users,
  Calendar,
  Save,
  Plus,
  X,
  BarChart3,
  Settings,
} from "lucide-react";

interface MarketingObjective {
  id: string;
  name: string;
  description: string;
  priority: "high" | "medium" | "low";
  status: "active" | "paused" | "completed";
}

interface MarketingChannel {
  id: string;
  name: string;
  budget: number;
  status: "active" | "paused";
  tactics: string[];
}

interface AccountMarketingSettingsProps {
  accountId: string;
  marketingData: {
    objectives: MarketingObjective[];
    channels: MarketingChannel[];
    budget: {
      total: number;
      period: "monthly" | "quarterly" | "yearly";
    };
    settings: {
      auto_optimization: boolean;
      performance_alerts: boolean;
      budget_alerts: boolean;
    };
  };
  onUpdate: (
    updates: Partial<AccountMarketingSettingsProps["marketingData"]>,
  ) => void;
}

export const AccountMarketingSettings = ({
  accountId,
  marketingData,
  onUpdate,
}: AccountMarketingSettingsProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [objectives, setObjectives] = useState(marketingData.objectives);
  const [channels, setChannels] = useState(marketingData.channels);
  const [budget, setBudget] = useState(marketingData.budget);
  const [settings, setSettings] = useState(marketingData.settings);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({ objectives, channels, budget, settings });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setObjectives(marketingData.objectives);
    setChannels(marketingData.channels);
    setBudget(marketingData.budget);
    setSettings(marketingData.settings);
    setIsEditing(false);
  };

  const addObjective = () => {
    const newObjective: MarketingObjective = {
      id: Date.now().toString(),
      name: "New Objective",
      description: "",
      priority: "medium",
      status: "active",
    };
    setObjectives([...objectives, newObjective]);
  };

  const updateObjective = (
    id: string,
    updates: Partial<MarketingObjective>,
  ) => {
    setObjectives(
      objectives.map((obj) => (obj.id === id ? { ...obj, ...updates } : obj)),
    );
  };

  const removeObjective = (id: string) => {
    setObjectives(objectives.filter((obj) => obj.id !== id));
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "bg-red-50 text-red-700 border-red-200";
      case "medium":
        return "bg-brand-yellow/20 text-brand-dark-blue border-brand-yellow/40";
      case "low":
        return "bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40";
      default:
        return "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] border-[var(--color-border-default)]";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40";
      case "paused":
        return "bg-brand-yellow/20 text-brand-dark-blue border-brand-yellow/40";
      case "completed":
        return "bg-brand-light-blue/20 text-brand-dark-blue border-brand-light-blue/40";
      default:
        return "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] border-[var(--color-border-default)]";
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit}>
        {/* Marketing Objectives */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Marketing Objectives
              </div>
              {isEditing && (
                <Button type="button" size="sm" onClick={addObjective}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Objective
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {objectives.map((objective) => (
                <div key={objective.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      {isEditing ? (
                        <Input
                          value={objective.name}
                          onChange={(e) =>
                            updateObjective(objective.id, {
                              name: e.target.value,
                            })
                          }
                          className="font-medium mb-2"
                        />
                      ) : (
                        <h3 className="font-medium">{objective.name}</h3>
                      )}
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className={getPriorityColor(objective.priority)}>
                          {objective.priority}
                        </Badge>
                        <Badge className={getStatusColor(objective.status)}>
                          {objective.status}
                        </Badge>
                      </div>
                    </div>
                    {isEditing && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeObjective(objective.id)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="space-y-3">
                      <Textarea
                        value={objective.description}
                        onChange={(e) =>
                          updateObjective(objective.id, {
                            description: e.target.value,
                          })
                        }
                        placeholder="Describe this objective..."
                        rows={2}
                      />
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Priority</Label>
                          <Select
                            value={objective.priority}
                            onValueChange={(value: "high" | "medium" | "low") =>
                              updateObjective(objective.id, { priority: value })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="high">High</SelectItem>
                              <SelectItem value="medium">Medium</SelectItem>
                              <SelectItem value="low">Low</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Status</Label>
                          <Select
                            value={objective.status}
                            onValueChange={(
                              value: "active" | "paused" | "completed",
                            ) =>
                              updateObjective(objective.id, { status: value })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="active">Active</SelectItem>
                              <SelectItem value="paused">Paused</SelectItem>
                              <SelectItem value="completed">
                                Completed
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--color-text-tertiary)]">
                      {objective.description}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Marketing Channels */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Marketing Channels
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {channels.map((channel) => (
                <div key={channel.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium">{channel.name}</h3>
                      <Badge className={getStatusColor(channel.status)}>
                        {channel.status}
                      </Badge>
                    </div>
                    {isEditing && (
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          value={channel.budget}
                          onChange={(e) => {
                            const newChannels = channels.map((c) =>
                              c.id === channel.id
                                ? { ...c, budget: parseInt(e.target.value) }
                                : c,
                            );
                            setChannels(newChannels);
                          }}
                          className="w-24"
                        />
                        <span className="text-sm text-[var(--color-text-tertiary)]">
                          $
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-medium">Budget:</span>
                      <span className="ml-2">
                        ${channel.budget.toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="font-medium">Tactics:</span>
                      <span className="ml-2">{channel.tactics.join(", ")}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Budget Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Budget Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="total_budget">Total Budget</Label>
                <Input
                  id="total_budget"
                  type="number"
                  value={budget.total}
                  onChange={(e) =>
                    setBudget({ ...budget, total: parseInt(e.target.value) })
                  }
                  disabled={!isEditing}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="budget_period">Budget Period</Label>
                <Select
                  value={budget.period}
                  onValueChange={(value: "monthly" | "quarterly" | "yearly") =>
                    setBudget({ ...budget, period: value })
                  }
                  disabled={!isEditing}
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="quarterly">Quarterly</SelectItem>
                    <SelectItem value="yearly">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Marketing Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Marketing Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Auto-optimization
                  </Label>
                  <p className="text-sm text-[var(--color-text-tertiary)]">
                    Automatically optimize campaigns based on performance
                  </p>
                </div>
                <Switch
                  checked={settings.auto_optimization}
                  onCheckedChange={(checked) =>
                    setSettings({ ...settings, auto_optimization: checked })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Performance alerts
                  </Label>
                  <p className="text-sm text-[var(--color-text-tertiary)]">
                    Get notified when campaigns exceed or fall below thresholds
                  </p>
                </div>
                <Switch
                  checked={settings.performance_alerts}
                  onCheckedChange={(checked) =>
                    setSettings({ ...settings, performance_alerts: checked })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">Budget alerts</Label>
                  <p className="text-sm text-[var(--color-text-tertiary)]">
                    Receive notifications when approaching budget limits
                  </p>
                </div>
                <Switch
                  checked={settings.budget_alerts}
                  onCheckedChange={(checked) =>
                    setSettings({ ...settings, budget_alerts: checked })
                  }
                  disabled={!isEditing}
                />
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
              Edit Marketing Settings
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};
