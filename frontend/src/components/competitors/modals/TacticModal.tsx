import { useState, useEffect } from "react";
import type {
  CompetitorTactic,
  CompetitorTacticCreate,
} from "@/services/competitorTacticService";
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

export interface TacticModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorTacticCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: CompetitorTactic;
  mode: "create" | "edit";
}

export interface DeleteTacticDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  tacticName: string;
}

export const TacticModal = ({
  isOpen,
  onClose,
  onSubmit,
  competitorId,
  competitorName,
  initialData,
  mode,
}: TacticModalProps) => {
  const [formData, setFormData] = useState<CompetitorTacticCreate>({
    display_name: initialData?.display_name || "",
    description: initialData?.description || "",
    competitor_node_id: competitorId,
    references: initialData?.references || [],
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        display_name: initialData?.display_name || "",
        description: initialData?.description || "",
        competitor_node_id: competitorId,
        references: initialData?.references || [],
      });
    }
  }, [isOpen, initialData, competitorId]);

  const handleSubmit = async () => {
    await onSubmit(formData);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      display_name: "",
      description: "",
      competitor_node_id: competitorId,
      references: [],
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create"
              ? "Create Marketing Tactic"
              : "Edit Marketing Tactic"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add a marketing tactic used by ${competitorName}`
              : "Update the tactic details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="tactic-name">Tactic Name *</Label>
            <Input
              id="tactic-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Annual Industry Conference"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="tactic-description">Description *</Label>
            <Textarea
              id="tactic-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe how this tactic is used to bring products to market..."
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
            {mode === "create" ? "Create" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteTacticDialog = ({
  isOpen,
  onClose,
  onConfirm,
  tacticName,
}: DeleteTacticDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Tactic</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{tacticName}"? This action cannot
            be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-brand-red hover:bg-brand-red/90"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
