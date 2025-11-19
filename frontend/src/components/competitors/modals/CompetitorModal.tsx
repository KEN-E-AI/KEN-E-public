import { useState, useEffect } from "react";
import type {
  Competitor,
  CompetitorCreate,
} from "@/services/competitorService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export interface CompetitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorCreate) => Promise<void>;
  initialData?: Competitor;
  mode: "create" | "edit";
}

export interface CompetitorDependentCounts {
  strengths: number;
  weaknesses: number;
  tactics: number;
  substituteProducts: number;
  valuePropositions: number;
  risks: number;
  opportunities: number;
}

export interface DeleteCompetitorDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  competitorName: string;
  dependentCounts?: CompetitorDependentCounts;
  isLoadingCounts?: boolean;
}

export const CompetitorModal = ({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  mode,
}: CompetitorModalProps) => {
  const [formData, setFormData] = useState<CompetitorCreate>({
    display_name: initialData?.display_name || "",
    description: initialData?.description || "",
    references: initialData?.references || [],
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        display_name: initialData?.display_name || "",
        description: initialData?.description || "",
        references: initialData?.references || [],
      });
    }
  }, [isOpen, initialData]);

  const handleSubmit = async () => {
    await onSubmit(formData);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      display_name: "",
      description: "",
      references: [],
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create Competitor" : "Edit Competitor"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Add a new competitor to track in your competitive analysis."
              : "Update competitor details."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="competitor-name">Competitor Name *</Label>
            <Input
              id="competitor-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Acme Corp"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="competitor-description">Description *</Label>
            <Textarea
              id="competitor-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe this competitor's business, positioning, and market presence..."
              rows={4}
              maxLength={4000}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={
              !formData.display_name.trim() || !formData.description.trim()
            }
          >
            {mode === "create" ? "Create Competitor" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteCompetitorDialog = ({
  isOpen,
  onClose,
  onConfirm,
  competitorName,
  dependentCounts,
  isLoadingCounts,
}: DeleteCompetitorDialogProps) => {
  const totalDependents = dependentCounts
    ? dependentCounts.strengths +
      dependentCounts.weaknesses +
      dependentCounts.tactics +
      dependentCounts.substituteProducts +
      dependentCounts.valuePropositions +
      dependentCounts.risks +
      dependentCounts.opportunities
    : 0;

  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Competitor</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                Are you sure you want to delete "{competitorName}"? This action
                cannot be undone.
              </p>
              {isLoadingCounts ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Loading dependent entities...
                </div>
              ) : dependentCounts && totalDependents > 0 ? (
                <div className="rounded-md bg-brand-red/10 p-3 space-y-2">
                  <p className="font-semibold text-brand-red text-sm">
                    Warning: This will also delete:
                  </p>
                  <ul className="text-sm space-y-1 text-dashboard-gray-700">
                    {dependentCounts.strengths > 0 && (
                      <li>• {dependentCounts.strengths} strength(s)</li>
                    )}
                    {dependentCounts.weaknesses > 0 && (
                      <li>• {dependentCounts.weaknesses} weakness(es)</li>
                    )}
                    {dependentCounts.tactics > 0 && (
                      <li>• {dependentCounts.tactics} tactic(s)</li>
                    )}
                    {dependentCounts.substituteProducts > 0 && (
                      <li>
                        • {dependentCounts.substituteProducts} substitute
                        product(s)
                      </li>
                    )}
                    {dependentCounts.risks > 0 && (
                      <li>• {dependentCounts.risks} risk(s)</li>
                    )}
                    {dependentCounts.opportunities > 0 && (
                      <li>
                        • {dependentCounts.opportunities} opportunit(y/ies)
                      </li>
                    )}
                    {dependentCounts.valuePropositions > 0 && (
                      <li>
                        • {dependentCounts.valuePropositions} value
                        proposition(s)
                      </li>
                    )}
                  </ul>
                  <p className="text-xs text-dashboard-gray-600 mt-2">
                    Total: {totalDependents} related entities will be
                    permanently removed.
                  </p>
                </div>
              ) : null}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-brand-red hover:bg-brand-red/90"
            disabled={isLoadingCounts}
          >
            Delete {totalDependents > 0 ? "All" : "Competitor"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
