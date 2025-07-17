import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Plus, Edit2, Trash2, X, ArrowLeft } from "lucide-react";
import { availableKPIs } from "@/lib/kpis";

interface Channel {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

interface EditChannelsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channels: Channel[];
  onChannelsChange: (channels: Channel[]) => void;
  onReturnToView?: () => void;
  showReturnToView?: boolean;
  editChannelId?: string;
  entityType?: "channel" | "tactic";
}

const EditChannelsModal = ({
  open,
  onOpenChange,
  channels,
  onChannelsChange,
  onReturnToView,
  showReturnToView = false,
  editChannelId,
  entityType = "channel",
}: EditChannelsModalProps) => {
  const [editingChannel, setEditingChannel] = useState<Channel | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newKPIName, setNewKPIName] = useState("");
  const [showNewKPIInput, setShowNewKPIInput] = useState<
    "effectiveness" | "efficiency" | "supporting" | null
  >(null);

  // Auto-load channel for editing when editChannelId is provided
  useEffect(() => {
    if (open && editChannelId && channels.length > 0) {
      const channelToEdit = channels.find(
        (channel) => channel.id === editChannelId,
      );
      if (channelToEdit) {
        handleEditChannel(channelToEdit);
      } else {
        console.log(
          "Channel not found:",
          editChannelId,
          "Available channels:",
          channels,
        );
      }
    }
  }, [open, editChannelId, channels]);

  const handleCreateChannel = () => {
    const newChannel: Channel = {
      id: `channel-${Date.now()}`,
      name: "",
      effectivenessKPI: "",
      efficiencyKPI: "",
      supportingMetrics: [],
    };
    setEditingChannel(newChannel);
    setIsCreating(true);
  };

  const handleEditChannel = (channel: Channel) => {
    setEditingChannel({ ...channel });
    setIsCreating(false);
  };

  const handleSaveChannel = () => {
    if (!editingChannel || !editingChannel.name.trim()) return;

    if (isCreating) {
      onChannelsChange([...channels, editingChannel]);
    } else {
      onChannelsChange(
        channels.map((channel) =>
          channel.id === editingChannel.id ? editingChannel : channel,
        ),
      );
    }

    setEditingChannel(null);
    setIsCreating(false);

    // For tactics (when editing from View Modal), return to View Modal
    if (showReturnToView && onReturnToView) {
      onReturnToView();
    } else {
      // For channels (when not editing from View Modal), just close
      onOpenChange(false);
    }
  };

  const handleDeleteChannel = (channelId: string) => {
    onChannelsChange(channels.filter((channel) => channel.id !== channelId));
  };

  const handleKPISelect = (
    value: string,
    type: "effectiveness" | "efficiency",
  ) => {
    if (!editingChannel) return;

    if (value === "create-new") {
      setShowNewKPIInput(type);
      return;
    }

    setEditingChannel({
      ...editingChannel,
      [type === "effectiveness" ? "effectivenessKPI" : "efficiencyKPI"]: value,
    });
  };

  const handleSupportingMetricAdd = (metric: string) => {
    if (!editingChannel || editingChannel.supportingMetrics.length >= 9) return;

    if (metric === "create-new") {
      setShowNewKPIInput("supporting");
      return;
    }

    if (!editingChannel.supportingMetrics.includes(metric)) {
      setEditingChannel({
        ...editingChannel,
        supportingMetrics: [...editingChannel.supportingMetrics, metric],
      });
    }
  };

  const handleSupportingMetricRemove = (metric: string) => {
    if (!editingChannel) return;

    setEditingChannel({
      ...editingChannel,
      supportingMetrics: editingChannel.supportingMetrics.filter(
        (m) => m !== metric,
      ),
    });
  };

  const handleCreateNewKPI = (
    type: "effectiveness" | "efficiency" | "supporting",
  ) => {
    if (!newKPIName.trim() || !editingChannel) return;

    if (type === "effectiveness") {
      setEditingChannel({
        ...editingChannel,
        effectivenessKPI: newKPIName,
      });
    } else if (type === "efficiency") {
      setEditingChannel({
        ...editingChannel,
        efficiencyKPI: newKPIName,
      });
    } else {
      if (
        editingChannel.supportingMetrics.length < 9 &&
        !editingChannel.supportingMetrics.includes(newKPIName)
      ) {
        setEditingChannel({
          ...editingChannel,
          supportingMetrics: [...editingChannel.supportingMetrics, newKPIName],
        });
      }
    }

    setNewKPIName("");
    setShowNewKPIInput(null);
  };

  const KPISelector = ({
    value,
    onChange,
    type,
    placeholder,
  }: {
    value: string;
    onChange: (value: string) => void;
    type: "effectiveness" | "efficiency";
    placeholder: string;
  }) => {
    const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      const selectedValue = e.target.value;
      if (selectedValue === "create-new") {
        setShowNewKPIInput(type);
      } else if (selectedValue) {
        onChange(selectedValue);
      }
    };

    return (
      <div className="space-y-2">
        <select
          value={value}
          onChange={handleSelectChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-medium-blue focus:border-brand-medium-blue bg-white"
        >
          <option value="">{placeholder}</option>
          {availableKPIs.map((kpi) => (
            <option key={kpi} value={kpi}>
              {kpi}
            </option>
          ))}
          <option value="create-new">+ Create new KPI</option>
        </select>
      </div>
    );
  };
  const SupportingMetricsSelector = () => {
    return (
      <div>
        <div className="flex items-center justify-between mb-2">
          <Label>Supporting Metrics</Label>
          <span className="text-xs text-gray-500">
            {editingChannel?.supportingMetrics.length || 0}/9
          </span>
        </div>

        {editingChannel?.supportingMetrics &&
          editingChannel.supportingMetrics.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {editingChannel.supportingMetrics.map((metric) => (
                <Badge
                  key={metric}
                  variant="secondary"
                  className="flex items-center gap-1"
                >
                  {metric}
                  <X
                    className="h-3 w-3 cursor-pointer"
                    onClick={() => handleSupportingMetricRemove(metric)}
                  />
                </Badge>
              ))}
            </div>
          )}

        {showNewKPIInput === "supporting" ? (
          <div className="flex gap-2 mb-2">
            <Input
              value={newKPIName}
              onChange={(e) => setNewKPIName(e.target.value)}
              placeholder="New metric name"
            />
            <Button onClick={() => handleCreateNewKPI("supporting")} size="sm">
              Add
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowNewKPIInput(null)}
              size="sm"
            >
              Cancel
            </Button>
          </div>
        ) : null}

        {(!editingChannel?.supportingMetrics ||
          editingChannel.supportingMetrics.length < 9) && (
          <select
            onChange={(e) => {
              const selectedValue = e.target.value;
              if (selectedValue === "create-new") {
                setShowNewKPIInput("supporting");
              } else if (selectedValue && selectedValue !== "") {
                handleSupportingMetricAdd(selectedValue);
              }
              e.target.value = ""; // Reset select after selection
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-medium-blue focus:border-brand-medium-blue bg-white"
            defaultValue=""
          >
            <option value="">Add supporting metric</option>
            {availableKPIs
              .filter((kpi) => !editingChannel?.supportingMetrics.includes(kpi))
              .map((kpi) => (
                <option key={kpi} value={kpi}>
                  {kpi}
                </option>
              ))}
            <option value="create-new">+ Create new metric</option>
          </select>
        )}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          {showReturnToView && onReturnToView && (
            <div className="mb-4">
              <Button
                variant="ghost"
                onClick={onReturnToView}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 p-0 h-auto"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to View
              </Button>
            </div>
          )}
          <DialogTitle>
            {editChannelId
              ? `Edit ${entityType === "channel" ? "Channel" : "Tactic"}`
              : `Edit Marketing ${entityType === "channel" ? "Channels" : "Tactics"}`}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Edit/Create Channel Form */}
          {editingChannel && (
            <div>
              <div className="grid gap-4">
                <div>
                  <Label htmlFor="channel-name">
                    {entityType === "channel" ? "Channel" : "Tactic"} Name
                  </Label>
                  <Input
                    id="channel-name"
                    value={editingChannel.name}
                    onChange={(e) =>
                      setEditingChannel({
                        ...editingChannel,
                        name: e.target.value.slice(0, 40),
                      })
                    }
                    placeholder={
                      entityType === "channel" ? "Channel name" : "Tactic name"
                    }
                    maxLength={40}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {editingChannel.name.length}/40 characters
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label>Effectiveness KPI</Label>
                    {showNewKPIInput === "effectiveness" ? (
                      <div className="flex gap-2">
                        <Input
                          value={newKPIName}
                          onChange={(e) => setNewKPIName(e.target.value)}
                          placeholder="New KPI name"
                        />
                        <Button
                          onClick={() => handleCreateNewKPI("effectiveness")}
                          size="sm"
                        >
                          Add
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => setShowNewKPIInput(null)}
                          size="sm"
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <KPISelector
                        value={editingChannel.effectivenessKPI}
                        onChange={(value) =>
                          handleKPISelect(value, "effectiveness")
                        }
                        type="effectiveness"
                        placeholder="Select effectiveness KPI"
                      />
                    )}
                  </div>

                  <div>
                    <Label>Efficiency KPI</Label>
                    {showNewKPIInput === "efficiency" ? (
                      <div className="flex gap-2">
                        <Input
                          value={newKPIName}
                          onChange={(e) => setNewKPIName(e.target.value)}
                          placeholder="New KPI name"
                        />
                        <Button
                          onClick={() => handleCreateNewKPI("efficiency")}
                          size="sm"
                        >
                          Add
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => setShowNewKPIInput(null)}
                          size="sm"
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <KPISelector
                        value={editingChannel.efficiencyKPI}
                        onChange={(value) =>
                          handleKPISelect(value, "efficiency")
                        }
                        type="efficiency"
                        placeholder="Select efficiency KPI"
                      />
                    )}
                  </div>
                </div>

                <div>
                  <SupportingMetricsSelector />
                </div>

                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleSaveChannel}
                    disabled={!editingChannel?.name.trim()}
                  >
                    {isCreating
                      ? `Create ${entityType === "channel" ? "Channel" : "Tactic"}`
                      : "Save Changes"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditingChannel(null);
                      setIsCreating(false);
                      setShowNewKPIInput(null);
                      setNewKPIName("");
                      onOpenChange(false);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EditChannelsModal;
