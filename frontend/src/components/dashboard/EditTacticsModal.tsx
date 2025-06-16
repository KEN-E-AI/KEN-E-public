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

interface Tactic {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

interface EditTacticsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tactics: Tactic[];
  onTacticsChange: (tactics: Tactic[]) => void;
  onReturnToView?: () => void;
  showReturnToView?: boolean;
  editTacticId?: string;
}

const EditTacticsModal = ({
  open,
  onOpenChange,
  tactics,
  onTacticsChange,
  onReturnToView,
  showReturnToView = false,
  editTacticId,
}: EditTacticsModalProps) => {
  const [editingTactic, setEditingTactic] = useState<Tactic | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newKPIName, setNewKPIName] = useState("");
  const [showNewKPIInput, setShowNewKPIInput] = useState<
    "effectiveness" | "efficiency" | "supporting" | null
  >(null);

  // Auto-load tactic for editing when editTacticId is provided
  useEffect(() => {
    if (open && editTacticId) {
      const tacticToEdit = tactics.find((tactic) => tactic.id === editTacticId);
      if (tacticToEdit) {
        setEditingTactic(tacticToEdit);
        setIsCreating(false);
      }
    }
  }, [open, editTacticId, tactics]);

  const handleCreateTactic = () => {
    const newTactic: Tactic = {
      id: `tactic-${Date.now()}`,
      name: "",
      effectivenessKPI: "",
      efficiencyKPI: "",
      supportingMetrics: [],
    };
    setEditingTactic(newTactic);
    setIsCreating(true);
  };

  const handleEditTactic = (tactic: Tactic) => {
    setEditingTactic({ ...tactic });
    setIsCreating(false);
  };

  const handleSaveTactic = () => {
    if (!editingTactic || !editingTactic.name.trim()) return;

    if (isCreating) {
      onTacticsChange([...tactics, editingTactic]);
    } else {
      onTacticsChange(
        tactics.map((tactic) =>
          tactic.id === editingTactic.id ? editingTactic : tactic,
        ),
      );
    }

    setEditingTactic(null);
    setIsCreating(false);
  };

  const handleDeleteTactic = (tacticId: string) => {
    onTacticsChange(tactics.filter((tactic) => tactic.id !== tacticId));
  };

  const handleKPISelect = (
    value: string,
    type: "effectiveness" | "efficiency",
  ) => {
    if (!editingTactic) return;

    if (value === "create-new") {
      setShowNewKPIInput(type);
      return;
    }

    setEditingTactic({
      ...editingTactic,
      [type === "effectiveness" ? "effectivenessKPI" : "efficiencyKPI"]: value,
    });
  };

  const handleSupportingMetricAdd = (metric: string) => {
    if (!editingTactic || editingTactic.supportingMetrics.length >= 9) return;

    if (metric === "create-new") {
      setShowNewKPIInput("supporting");
      return;
    }

    if (!editingTactic.supportingMetrics.includes(metric)) {
      setEditingTactic({
        ...editingTactic,
        supportingMetrics: [...editingTactic.supportingMetrics, metric],
      });
    }
  };

  const handleSupportingMetricRemove = (metric: string) => {
    if (!editingTactic) return;

    setEditingTactic({
      ...editingTactic,
      supportingMetrics: editingTactic.supportingMetrics.filter(
        (m) => m !== metric,
      ),
    });
  };

  const handleCreateNewKPI = (
    type: "effectiveness" | "efficiency" | "supporting",
  ) => {
    if (!newKPIName.trim() || !editingTactic) return;

    if (type === "effectiveness") {
      setEditingTactic({
        ...editingTactic,
        effectivenessKPI: newKPIName,
      });
    } else if (type === "efficiency") {
      setEditingTactic({
        ...editingTactic,
        efficiencyKPI: newKPIName,
      });
    } else {
      if (
        editingTactic.supportingMetrics.length < 9 &&
        !editingTactic.supportingMetrics.includes(newKPIName)
      ) {
        setEditingTactic({
          ...editingTactic,
          supportingMetrics: [...editingTactic.supportingMetrics, newKPIName],
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
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
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
            {editingTactic?.supportingMetrics.length || 0}/9
          </span>
        </div>

        {editingTactic?.supportingMetrics &&
          editingTactic.supportingMetrics.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {editingTactic.supportingMetrics.map((metric) => (
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

        {(!editingTactic?.supportingMetrics ||
          editingTactic.supportingMetrics.length < 9) && (
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
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
            defaultValue=""
          >
            <option value="">Add supporting metric</option>
            {availableKPIs
              .filter((kpi) => !editingTactic?.supportingMetrics.includes(kpi))
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
            {editTacticId ? "Edit Tactic" : "Edit Marketing Tactics"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Current Tactics List */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium">Current Tactics</h3>
              <Button onClick={handleCreateTactic} size="sm">
                <Plus className="w-4 h-4 mr-2" />
                Add Tactic
              </Button>
            </div>

            <div className="space-y-2">
              {tactics.map((tactic) => (
                <div
                  key={tactic.id}
                  className="flex items-start gap-3 p-3 border rounded-lg bg-gray-50"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium break-words">
                        {tactic.name}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2">
                      {tactic.effectivenessKPI && (
                        <div className="text-xs">
                          <span className="font-medium">Effectiveness:</span>{" "}
                          {tactic.effectivenessKPI}
                        </div>
                      )}
                      {tactic.efficiencyKPI && (
                        <div className="text-xs">
                          <span className="font-medium">Efficiency:</span>{" "}
                          {tactic.efficiencyKPI}
                        </div>
                      )}
                    </div>

                    {tactic.supportingMetrics.length > 0 && (
                      <div className="text-xs text-gray-600">
                        <span className="font-medium">Supporting Metrics:</span>{" "}
                        {tactic.supportingMetrics.join(", ")}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEditTactic(tactic)}
                    >
                      <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteTactic(tactic.id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Edit/Create Tactic Form */}
          {editingTactic && (
            <div className="border-t pt-6">
              <h3 className="text-lg font-medium mb-4">
                {isCreating ? "Create New Tactic" : "Edit Tactic"}
              </h3>

              <div className="grid gap-4">
                <div>
                  <Label htmlFor="tactic-name">Name</Label>
                  <Input
                    id="tactic-name"
                    value={editingTactic.name}
                    onChange={(e) =>
                      setEditingTactic({
                        ...editingTactic,
                        name: e.target.value.slice(0, 40),
                      })
                    }
                    placeholder="Tactic name"
                    maxLength={40}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {editingTactic.name.length}/40 characters
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
                        value={editingTactic.effectivenessKPI}
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
                        value={editingTactic.efficiencyKPI}
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
                  <Button onClick={handleSaveTactic}>
                    {isCreating ? "Create Tactic" : "Save Changes"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditingTactic(null);
                      setIsCreating(false);
                      setShowNewKPIInput(null);
                      setNewKPIName("");
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

export default EditTacticsModal;
