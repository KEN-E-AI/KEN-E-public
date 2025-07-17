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
import { GripVertical, Plus, Edit2, Trash2 } from "lucide-react";
import { availableKPIs } from "@/lib/kpis";

interface Objective {
  id: string;
  name: string;
  objective: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  order: number;
}

interface EditStepsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  steps: Objective[];
  onStepsChange: (steps: Objective[]) => void;
}

const EditStepsModal = ({
  open,
  onOpenChange,
  steps,
  onStepsChange,
}: EditStepsModalProps) => {
  const [editingStep, setEditingStep] = useState<Objective | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [effectivenessKPIOpen, setEffectivenessKPIOpen] = useState(false);
  const [efficiencyKPIOpen, setEfficiencyKPIOpen] = useState(false);
  const [newKPIName, setNewKPIName] = useState("");
  const [showNewKPIInput, setShowNewKPIInput] = useState<
    "effectiveness" | "efficiency" | null
  >(null);
  const [pendingSteps, setPendingSteps] = useState<Objective[]>([]);
  const [hasOrderChanges, setHasOrderChanges] = useState(false);

  // Initialize pending steps when modal opens or steps change
  useEffect(() => {
    if (open && steps.length > 0) {
      setPendingSteps([...steps]);
    }
  }, [open, steps]);

  const sortedSteps = [...pendingSteps].sort((a, b) => a.order - b.order);

  const handleCreateStep = () => {
    const newStep: Objective = {
      id: `step-${Date.now()}`,
      name: "",
      objective: "",
      effectivenessKPI: "",
      efficiencyKPI: "",
      order: steps.length,
    };
    setEditingStep(newStep);
    setIsCreating(true);
  };

  const handleEditStep = (step: Objective) => {
    setEditingStep({ ...step });
    setIsCreating(false);
  };

  const handleSaveStep = () => {
    if (!editingStep) return;

    let updatedSteps;
    if (isCreating) {
      updatedSteps = [...steps, editingStep];
      onStepsChange(updatedSteps);
    } else {
      updatedSteps = steps.map((step) =>
        step.id === editingStep.id ? editingStep : step,
      );
      onStepsChange(updatedSteps);
    }

    // Update pending steps as well
    setPendingSteps(updatedSteps);
    setEditingStep(null);
    setIsCreating(false);
  };

  const handleDeleteStep = (stepId: string) => {
    onStepsChange(steps.filter((step) => step.id !== stepId));
  };

  const handleSaveOrderChanges = () => {
    onStepsChange(pendingSteps);
    setHasOrderChanges(false);
  };

  const handleDiscardOrderChanges = () => {
    setPendingSteps([...steps]);
    setHasOrderChanges(false);
  };

  const handleReorderStep = (stepId: string, direction: "up" | "down") => {
    const currentIndex = sortedSteps.findIndex((step) => step.id === stepId);
    if (
      (direction === "up" && currentIndex === 0) ||
      (direction === "down" && currentIndex === sortedSteps.length - 1)
    ) {
      return;
    }

    const newSteps = [...sortedSteps];
    const targetIndex =
      direction === "up" ? currentIndex - 1 : currentIndex + 1;

    // Swap the steps
    [newSteps[currentIndex], newSteps[targetIndex]] = [
      newSteps[targetIndex],
      newSteps[currentIndex],
    ];

    // Update order properties
    const updatedSteps = newSteps.map((step, index) => ({
      ...step,
      order: index,
    }));

    setPendingSteps(updatedSteps);
    setHasOrderChanges(true);
  };

  const handleKPISelect = (
    value: string,
    type: "effectiveness" | "efficiency",
  ) => {
    if (!editingStep) return;

    if (value === "create-new") {
      setShowNewKPIInput(type);
      return;
    }

    setEditingStep({
      ...editingStep,
      [type === "effectiveness" ? "effectivenessKPI" : "efficiencyKPI"]: value,
    });
  };

  const handleCreateNewKPI = (type: "effectiveness" | "efficiency") => {
    if (!newKPIName.trim() || !editingStep) return;

    setEditingStep({
      ...editingStep,
      [type === "effectiveness" ? "effectivenessKPI" : "efficiencyKPI"]:
        newKPIName,
    });

    setNewKPIName("");
    setShowNewKPIInput(null);
  };

  const KPISelector = ({
    value,
    onChange,
    placeholder,
    type,
  }: {
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
    type: "effectiveness" | "efficiency";
  }) => {
    const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      const selectedValue = e.target.value;
      if (selectedValue === "create-new") {
        setShowNewKPIInput(type);
      } else {
        onChange(selectedValue);
      }
    };

    return (
      <select
        value={value}
        onChange={handleChange}
        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">{placeholder}</option>
        {availableKPIs.map((kpi) => (
          <option key={kpi} value={kpi}>
            {kpi}
          </option>
        ))}
        <option value="create-new">+ Create new KPI</option>
      </select>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Marketing Objectives</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Current Objectives List */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium">Current Objectives</h3>
              {hasOrderChanges && (
                <div className="flex gap-2">
                  <Button
                    onClick={handleSaveOrderChanges}
                    size="sm"
                    className="bg-brand-light-green hover:bg-brand-light-green/90 text-brand-dark-blue"
                  >
                    Save Order Changes
                  </Button>
                  <Button
                    onClick={handleDiscardOrderChanges}
                    variant="outline"
                    size="sm"
                  >
                    Discard
                  </Button>
                </div>
              )}
              {!hasOrderChanges && (
                <Button onClick={handleCreateStep} size="sm">
                  <Plus className="w-4 h-4 mr-2" />
                  Add Objective
                </Button>
              )}
            </div>

            <div className="space-y-3">
              {sortedSteps.map((step, index) => (
                <div
                  key={step.id}
                  className="border border-dashboard-gray-200 rounded-lg p-4 bg-dashboard-gray-50"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleReorderStep(step.id, "up")}
                        disabled={index === 0}
                        className="p-1 h-auto"
                      >
                        ↑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleReorderStep(step.id, "down")}
                        disabled={index === sortedSteps.length - 1}
                        className="p-1 h-auto"
                      >
                        ↓
                      </Button>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <GripVertical className="h-4 w-4 text-dashboard-gray-400" />
                          <Badge
                            variant="secondary"
                            className="bg-dashboard-gray-200 text-dashboard-gray-800"
                          >
                            #{step.order + 1}
                          </Badge>
                          <div className="font-medium text-dashboard-gray-900">
                            {step.name}
                          </div>
                        </div>
                        <p className="text-sm text-dashboard-gray-600 mb-2">
                          {step.objective}
                        </p>
                        <div className="flex gap-2 text-xs">
                          {step.effectivenessKPI && (
                            <Badge variant="outline">
                              E: {step.effectivenessKPI}
                            </Badge>
                          )}
                          {step.efficiencyKPI && (
                            <Badge variant="outline">
                              Ef: {step.efficiencyKPI}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditStep(step)}
                        className="p-2"
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteStep(step.id)}
                        className="p-2 text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Edit/Create Objective Form */}
          {editingStep && (
            <div className="border-t pt-6">
              <h3 className="text-lg font-medium mb-4">
                {isCreating ? "Create New Objective" : "Edit Objective"}
              </h3>

              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="step-name">Name</Label>
                    <Input
                      id="step-name"
                      value={editingStep.name}
                      onChange={(e) =>
                        setEditingStep({
                          ...editingStep,
                          name: e.target.value,
                        })
                      }
                      placeholder="Objective name"
                      maxLength={40}
                    />
                    <div className="text-xs text-dashboard-gray-500 mt-1">
                      {editingStep.name.length}/40 characters
                    </div>
                  </div>
                </div>

                <div>
                  <Label htmlFor="step-objective">Description</Label>
                  <Textarea
                    id="step-objective"
                    value={editingStep.objective}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        objective: e.target.value,
                      })
                    }
                    placeholder="Describe the objective for this step"
                    rows={3}
                    maxLength={255}
                  />
                  <div className="text-xs text-dashboard-gray-500 mt-1">
                    {editingStep.objective.length}/255 characters
                  </div>
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
                          size="sm"
                          onClick={() => setShowNewKPIInput(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <KPISelector
                        value={editingStep.effectivenessKPI}
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
                          size="sm"
                          onClick={() => setShowNewKPIInput(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <KPISelector
                        value={editingStep.efficiencyKPI}
                        onChange={(value) =>
                          handleKPISelect(value, "efficiency")
                        }
                        type="efficiency"
                        placeholder="Select efficiency KPI"
                      />
                    )}
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button onClick={handleSaveStep}>
                    {isCreating ? "Create Objective" : "Save Changes"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditingStep(null);
                      setNewKPIName("");
                      setShowNewKPIInput(null);
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

export default EditStepsModal;
