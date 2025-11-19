import { useState, useEffect } from "react";
import type {
  Opportunity,
  OpportunityCreate,
} from "@/services/opportunityService";
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

export interface OpportunityModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: OpportunityCreate) => Promise<void>;
  weaknessId: string;
  weaknessName: string;
  initialData?: Opportunity;
  mode: "create" | "edit";
}

export interface DeleteOpportunityDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  opportunityName: string;
}

export const OpportunityModal = ({
  isOpen,
  onClose,
  onSubmit,
  weaknessId,
  weaknessName,
  initialData,
  mode,
}: OpportunityModalProps) => {
  const [formData, setFormData] = useState<OpportunityCreate>({
    display_name: initialData?.display_name || "",
    description: initialData?.description || "",
    weakness_node_id: weaknessId,
    references: initialData?.references || [],
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        display_name: initialData?.display_name || "",
        description: initialData?.description || "",
        weakness_node_id: weaknessId,
        references: initialData?.references || [],
      });
    }
  }, [isOpen, initialData, weaknessId]);

  const handleSubmit = async () => {
    await onSubmit(formData);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      display_name: "",
      description: "",
      weakness_node_id: weaknessId,
      references: [],
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create Opportunity" : "Edit Opportunity"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add an opportunity created by ${weaknessName}`
              : "Update opportunity details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="opportunity-name">Name *</Label>
            <Input
              id="opportunity-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Expand into underserved segments"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="opportunity-description">Description *</Label>
            <Textarea
              id="opportunity-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe this opportunity..."
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
            {mode === "create" ? "Create Opportunity" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteOpportunityDialog = ({
  isOpen,
  onClose,
  onConfirm,
  opportunityName,
}: DeleteOpportunityDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Opportunity</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{opportunityName}"? This action
            cannot be undone.
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
