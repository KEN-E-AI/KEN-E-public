import { useState, useEffect } from "react";
import type {
  ValueProposition,
  ValuePropositionCreate,
} from "@/services/valuePropositionService";
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

export interface ValuePropositionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: ValuePropositionCreate) => Promise<void>;
  parentNodeId: string;
  parentNodeType: "SubstituteProduct" | "Competitor";
  parentDisplayName: string;
  initialData?: ValueProposition;
  mode: "create" | "edit";
}

export interface DeleteValuePropositionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  valuePropositionName: string;
}

export const ValuePropositionModal = ({
  isOpen,
  onClose,
  onSubmit,
  parentNodeId,
  parentNodeType,
  parentDisplayName,
  initialData,
  mode,
}: ValuePropositionModalProps) => {
  const [formData, setFormData] = useState<ValuePropositionCreate>({
    display_name: initialData?.display_name || "",
    description: initialData?.description || "",
    parent_node_id: parentNodeId,
    parent_node_type: parentNodeType,
    references: initialData?.references || [],
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        display_name: initialData?.display_name || "",
        description: initialData?.description || "",
        parent_node_id: parentNodeId,
        parent_node_type: parentNodeType,
        references: initialData?.references || [],
      });
    }
  }, [isOpen, initialData, parentNodeId, parentNodeType]);

  const handleSubmit = async () => {
    await onSubmit(formData);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      display_name: "",
      description: "",
      parent_node_id: parentNodeId,
      parent_node_type: parentNodeType,
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
              ? "Create Value Proposition"
              : "Edit Value Proposition"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add a value proposition for ${parentDisplayName}`
              : "Update the value proposition details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="vp-display-name">Display Name *</Label>
            <Input
              id="vp-display-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Advanced HEPA Filtration"
              maxLength={60}
            />
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
              Short, descriptive name (max 60 characters)
            </p>
          </div>
          <div>
            <Label htmlFor="vp-description">Description *</Label>
            <Textarea
              id="vp-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe the value this provides to customers..."
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

export const DeleteValuePropositionDialog = ({
  isOpen,
  onClose,
  onConfirm,
  valuePropositionName,
}: DeleteValuePropositionDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Value Proposition</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{valuePropositionName}"? This
            action cannot be undone.
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
