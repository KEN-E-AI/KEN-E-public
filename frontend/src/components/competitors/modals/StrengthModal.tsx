import { useState, useEffect } from "react";
import type {
  CompetitorStrength,
  CompetitorStrengthCreate,
} from "@/services/competitorStrengthService";
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

export interface StrengthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorStrengthCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: CompetitorStrength;
  mode: "create" | "edit";
}

export interface DeleteStrengthDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  strengthName: string;
}

export const StrengthModal = ({
  isOpen,
  onClose,
  onSubmit,
  competitorId,
  competitorName,
  initialData,
  mode,
}: StrengthModalProps) => {
  const [formData, setFormData] = useState<CompetitorStrengthCreate>({
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
            {mode === "create" ? "Create Strength" : "Edit Strength"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add a new strength to ${competitorName}`
              : "Update strength details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="strength-name">Name *</Label>
            <Input
              id="strength-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Strong Brand Recognition"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="strength-description">Description *</Label>
            <Textarea
              id="strength-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe this strength..."
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
            {mode === "create" ? "Create Strength" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteStrengthDialog = ({
  isOpen,
  onClose,
  onConfirm,
  strengthName,
}: DeleteStrengthDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Strength</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{strengthName}"? This action cannot
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
