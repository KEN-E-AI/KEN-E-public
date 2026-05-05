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
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { GripVertical, Plus, Edit2, Trash2, ArrowLeft } from "lucide-react";
import { availableKPIs } from "@/lib/kpis";

interface ObjectiveData {
  step_name: string;
  objective: string;
  effectivenessKPI?: string;
  efficiencyKPI?: string;
  supportingMetrics?: string[];
  channels: Record<string, any>;
}

interface SampleData {
  [key: string]: ObjectiveData;
}

interface EditObjectivesModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sampleData: SampleData;
  onSampleDataChange: (data: SampleData) => void;
  openDirectlyToForm?: boolean;
  editObjectiveId?: string;
  onReturnToView?: () => void;
  showReturnToView?: boolean;
  entityType?: "objective" | "channel" | "tactic";
  parentObjectiveId?: string;
  parentChannelId?: string;
}

const EditObjectivesModal = ({
  open,
  onOpenChange,
  sampleData,
  onSampleDataChange,
  openDirectlyToForm = false,
  editObjectiveId,
  onReturnToView,
  showReturnToView = false,
  entityType = "objective",
  parentObjectiveId,
  parentChannelId,
}: EditObjectivesModalProps) => {
  const [editingObjective, setEditingObjective] = useState<{
    id: string;
    step_name: string;
    objective: string;
    effectivenessKPI: string;
    efficiencyKPI: string;
    supportingMetrics: string[];
  } | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showNewKPIInput, setShowNewKPIInput] = useState<
    "effectiveness" | "efficiency" | "supporting" | null
  >(null);
  const [newKPIName, setNewKPIName] = useState("");

  // When modal opens directly to form (from Add Objective button) or with specific objective to edit
  useEffect(() => {
    if (open && editObjectiveId && sampleData[editObjectiveId]) {
      // Open directly to edit form for specific objective (prioritize editing)
      handleEditObjective(editObjectiveId, sampleData[editObjectiveId]);
    } else if (open && openDirectlyToForm) {
      handleCreateObjective();
    } else if (open && !openDirectlyToForm && !editObjectiveId) {
      setShowForm(false);
      setEditingObjective(null);
      setIsCreating(false);
    }
  }, [open, openDirectlyToForm, editObjectiveId, sampleData]);

  const objectivesList = Object.entries(sampleData).map(([id, data]) => ({
    id,
    ...data,
  }));

  const handleCreateObjective = () => {
    const newId = (
      Math.max(...Object.keys(sampleData).map(Number)) + 1
    ).toString();
    const newObjective = {
      id: newId,
      step_name: "",
      objective: "",
      effectivenessKPI: "",
      efficiencyKPI: "",
      supportingMetrics: [],
    };
    setEditingObjective(newObjective);
    setIsCreating(true);
    setShowForm(true);
  };

  const handleEditObjective = (id: string, data: ObjectiveData) => {
    setEditingObjective({
      id,
      step_name: data.step_name,
      objective: data.objective,
      effectivenessKPI: data.effectivenessKPI || "",
      efficiencyKPI: data.efficiencyKPI || "",
      supportingMetrics: data.supportingMetrics || [],
    });
    setIsCreating(false);
    setShowForm(true);
  };

  const handleSaveObjective = () => {
    if (!editingObjective) return;

    const updatedData = { ...sampleData };

    if (isCreating && entityType === "channel" && parentObjectiveId) {
      // Add new channel to parent objective
      if (updatedData[parentObjectiveId]) {
        const channelId = editingObjective.step_name
          .toLowerCase()
          .replace(/\s+/g, "_");
        updatedData[parentObjectiveId].channels[channelId] = {
          name: editingObjective.step_name,
          effectivenessKPI: editingObjective.effectivenessKPI,
          efficiencyKPI: editingObjective.efficiencyKPI,
          supportingMetrics: editingObjective.supportingMetrics,
          tactics: {},
        };
      }
    } else if (
      isCreating &&
      entityType === "tactic" &&
      parentObjectiveId &&
      parentChannelId
    ) {
      // Add new tactic to parent channel
      if (
        updatedData[parentObjectiveId] &&
        updatedData[parentObjectiveId].channels[parentChannelId]
      ) {
        const tacticId = editingObjective.step_name
          .toLowerCase()
          .replace(/\s+/g, "_");
        if (!updatedData[parentObjectiveId].channels[parentChannelId].tactics) {
          updatedData[parentObjectiveId].channels[parentChannelId].tactics = {};
        }
        updatedData[parentObjectiveId].channels[parentChannelId].tactics[
          tacticId
        ] = {
          name: editingObjective.step_name,
          effectivenessKPI: editingObjective.effectivenessKPI,
          efficiencyKPI: editingObjective.efficiencyKPI,
          supportingMetrics: editingObjective.supportingMetrics,
        };
      }
    } else if (isCreating) {
      // Add new objective
      updatedData[editingObjective.id] = {
        step_name: editingObjective.step_name,
        objective: editingObjective.objective,
        effectivenessKPI: editingObjective.effectivenessKPI,
        efficiencyKPI: editingObjective.efficiencyKPI,
        supportingMetrics: editingObjective.supportingMetrics,
        channels: {}, // Start with empty channels
      };
    } else {
      // Update existing objective
      if (updatedData[editingObjective.id]) {
        updatedData[editingObjective.id] = {
          ...updatedData[editingObjective.id],
          step_name: editingObjective.step_name,
          objective: editingObjective.objective,
          effectivenessKPI: editingObjective.effectivenessKPI,
          efficiencyKPI: editingObjective.efficiencyKPI,
          supportingMetrics: editingObjective.supportingMetrics,
        };
      }
    }

    onSampleDataChange(updatedData);
    setEditingObjective(null);
    setIsCreating(false);
    setShowForm(false);
    setShowNewKPIInput(null);
    setNewKPIName("");

    // Close modal if opened directly to form or editing specific objective
    if (openDirectlyToForm || editObjectiveId) {
      onOpenChange(false);
    }
  };

  const handleDeleteObjective = (id: string) => {
    const updatedData = { ...sampleData };
    delete updatedData[id];
    onSampleDataChange(updatedData);
  };

  const handleBackToList = () => {
    setShowForm(false);
    setEditingObjective(null);
    setIsCreating(false);
    setShowNewKPIInput(null);
    setNewKPIName("");
  };

  const handleKPISelect = (
    value: string,
    type: "effectiveness" | "efficiency",
  ) => {
    if (!editingObjective) return;

    if (value === "create-new") {
      setShowNewKPIInput(type);
      return;
    }

    setEditingObjective({
      ...editingObjective,
      [type === "effectiveness" ? "effectivenessKPI" : "efficiencyKPI"]: value,
    });
  };

  const handleCreateNewKPI = (type: "effectiveness" | "efficiency") => {
    if (!newKPIName.trim() || !editingObjective) return;

    setEditingObjective({
      ...editingObjective,
      [type === "effectiveness" ? "effectivenessKPI" : "efficiencyKPI"]:
        newKPIName,
    });

    setNewKPIName("");
    setShowNewKPIInput(null);
  };

  const handleSupportingMetricAdd = (metric: string) => {
    if (!editingObjective || editingObjective.supportingMetrics.length >= 9)
      return;

    if (metric === "create-new") {
      setShowNewKPIInput("supporting");
      return;
    }

    if (!editingObjective.supportingMetrics.includes(metric)) {
      setEditingObjective({
        ...editingObjective,
        supportingMetrics: [...editingObjective.supportingMetrics, metric],
      });
    }
  };

  const handleSupportingMetricRemove = (metric: string) => {
    if (!editingObjective) return;
    setEditingObjective({
      ...editingObjective,
      supportingMetrics: editingObjective.supportingMetrics.filter(
        (m) => m !== metric,
      ),
    });
  };

  const handleCreateNewSupportingMetric = () => {
    if (!newKPIName.trim() || !editingObjective) return;

    if (
      editingObjective.supportingMetrics.length < 9 &&
      !editingObjective.supportingMetrics.includes(newKPIName)
    ) {
      setEditingObjective({
        ...editingObjective,
        supportingMetrics: [...editingObjective.supportingMetrics, newKPIName],
      });
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
          className="w-full px-3 py-2 border border-[var(--color-border-default)] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-medium-blue focus:border-brand-medium-blue bg-white"
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
      <div className="space-y-2">
        <div className="flex items-center justify-between mb-2">
          <Label>Supporting Metrics</Label>
          <span className="text-xs text-[var(--color-text-tertiary)]">
            {editingObjective?.supportingMetrics.length || 0}/9
          </span>
        </div>

        {editingObjective?.supportingMetrics &&
          editingObjective.supportingMetrics.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {editingObjective.supportingMetrics.map((metric) => (
                <Badge
                  key={metric}
                  variant="secondary"
                  className="flex items-center gap-1"
                >
                  {metric}
                  <button
                    onClick={() => handleSupportingMetricRemove(metric)}
                    className="ml-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}

        {(!editingObjective?.supportingMetrics ||
          editingObjective.supportingMetrics.length < 9) && (
          <select
            value=""
            onChange={(e) => handleSupportingMetricAdd(e.target.value)}
            className="w-full px-3 py-2 border border-[var(--color-border-default)] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-medium-blue focus:border-brand-medium-blue bg-white"
          >
            <option value="">Select a supporting metric...</option>
            {availableKPIs
              .filter(
                (kpi) => !editingObjective?.supportingMetrics.includes(kpi),
              )
              .map((kpi) => (
                <option key={kpi} value={kpi}>
                  {kpi}
                </option>
              ))}
            <option value="create-new">+ Create new metric</option>
          </select>
        )}

        {showNewKPIInput === "supporting" && (
          <div className="flex gap-2">
            <Input
              value={newKPIName}
              onChange={(e) => setNewKPIName(e.target.value)}
              placeholder="Enter new supporting metric name"
              className="flex-1"
            />
            <Button
              onClick={handleCreateNewSupportingMetric}
              disabled={!newKPIName.trim()}
              size="sm"
            >
              Add
            </Button>
            <Button
              onClick={() => {
                setShowNewKPIInput(null);
                setNewKPIName("");
              }}
              variant="outline"
              size="sm"
            >
              Cancel
            </Button>
          </div>
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
                className="flex items-center gap-2 text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] p-0 h-auto"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to View
              </Button>
            </div>
          )}
          <DialogTitle>
            {showForm
              ? isCreating
                ? `Create New ${entityType === "objective" ? "Objective" : entityType === "channel" ? "Channel" : "Tactic"}`
                : `Edit ${entityType === "objective" ? "Objective" : entityType === "channel" ? "Channel" : "Tactic"}`
              : `Edit Marketing ${entityType === "objective" ? "Objectives" : entityType === "channel" ? "Channels" : "Tactics"}`}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Show form if editing/creating or opened directly to form */}
          {showForm && editingObjective ? (
            <div className="space-y-4">
              {!openDirectlyToForm && (
                <Button
                  variant="ghost"
                  onClick={handleBackToList}
                  className="mb-4"
                >
                  ← Back to Objectives
                </Button>
              )}

              <div className="grid gap-4">
                <div>
                  <Label htmlFor="objective-name">
                    {entityType === "objective"
                      ? "Objective Name"
                      : entityType === "channel"
                        ? "Channel Name"
                        : "Tactic Name"}
                  </Label>
                  <Input
                    id="objective-name"
                    value={editingObjective.step_name}
                    onChange={(e) =>
                      setEditingObjective({
                        ...editingObjective,
                        step_name: e.target.value.slice(0, 40),
                      })
                    }
                    placeholder={
                      entityType === "objective"
                        ? "e.g., Awareness, Consideration, Conversion"
                        : entityType === "channel"
                          ? "e.g., Email, Social Media, Search"
                          : "e.g., Banner Ads, Organic Posts, Newsletter"
                    }
                    maxLength={40}
                  />
                  <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                    {editingObjective.step_name.length}/40 characters
                  </p>
                </div>

                {entityType === "objective" && (
                  <div>
                    <Label htmlFor="objective-description">
                      Objective Description
                    </Label>
                    <Textarea
                      id="objective-description"
                      value={editingObjective.objective}
                      onChange={(e) =>
                        setEditingObjective({
                          ...editingObjective,
                          objective: e.target.value.slice(0, 500),
                        })
                      }
                      placeholder="Describe the objective for this step in the marketing funnel"
                      maxLength={500}
                      rows={4}
                    />
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                      {editingObjective.objective.length}/500 characters
                    </p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
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
                        value={editingObjective.effectivenessKPI || ""}
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
                        value={editingObjective.efficiencyKPI || ""}
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
                    onClick={handleSaveObjective}
                    disabled={
                      !editingObjective.step_name.trim() ||
                      (entityType === "objective" &&
                        !editingObjective.objective.trim())
                    }
                  >
                    {isCreating
                      ? `Create ${entityType === "objective" ? "Objective" : entityType === "channel" ? "Channel" : "Tactic"}`
                      : "Save Changes"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setShowNewKPIInput(null);
                      setNewKPIName("");
                      if (openDirectlyToForm) {
                        onOpenChange(false);
                      } else {
                        handleBackToList();
                      }
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            /* Show list of current objectives */
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">Current Objectives</h3>
                <Button onClick={handleCreateObjective} size="sm">
                  <Plus className="w-4 h-4 mr-2" />
                  Add Objective
                </Button>
              </div>

              <div className="space-y-2">
                {objectivesList.length === 0 ? (
                  <div className="text-center py-8 text-[var(--color-text-tertiary)]">
                    No objectives defined yet. Create your first objective to
                    get started.
                  </div>
                ) : (
                  objectivesList.map((objective) => (
                    <div
                      key={objective.id}
                      className="flex items-center gap-3 p-4 border rounded-lg bg-[var(--color-bg-secondary)]"
                    >
                      <GripVertical className="w-4 h-4 text-[var(--color-text-disabled)]" />

                      <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-2 mb-2">
                          <Badge
                            variant="secondary"
                            className="mt-0.5 flex-shrink-0"
                          >
                            {objective.id}
                          </Badge>
                          <span className="font-medium break-words capitalize">
                            {objective.step_name}
                          </span>
                        </div>
                        <p className="text-sm text-[var(--color-text-tertiary)] break-words">
                          {objective.objective}
                        </p>
                        <div className="flex gap-2 mt-2">
                          <Badge variant="outline" className="text-xs">
                            {Object.keys(objective.channels).length} channels
                          </Badge>
                          {objective.effectivenessKPI && (
                            <Badge variant="outline" className="text-xs">
                              E: {objective.effectivenessKPI}
                            </Badge>
                          )}
                          {objective.efficiencyKPI && (
                            <Badge variant="outline" className="text-xs">
                              Ef: {objective.efficiencyKPI}
                            </Badge>
                          )}
                        </div>
                        {objective.supportingMetrics &&
                          objective.supportingMetrics.length > 0 && (
                            <div className="text-xs text-[var(--color-text-tertiary)] mt-1">
                              <span className="font-medium">
                                Supporting Metrics:
                              </span>{" "}
                              {objective.supportingMetrics.join(", ")}
                            </div>
                          )}
                      </div>

                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            handleEditObjective(objective.id, objective)
                          }
                        >
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteObjective(objective.id)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EditObjectivesModal;
