import { useState, useEffect } from "react";
import type {
  CompetitorWeakness,
  CompetitorWeaknessCreate,
} from "@/services/competitorWeaknessService";
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

export interface WeaknessModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CompetitorWeaknessCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: CompetitorWeakness;
  mode: "create" | "edit";
}

export interface DeleteWeaknessDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  weaknessName: string;
}

export const WeaknessModal = ({
  isOpen,
  onClose,
  onSubmit,
  competitorId,
  competitorName,
  initialData,
  mode,
}: WeaknessModalProps) => {
  const [formData, setFormData] = useState<CompetitorWeaknessCreate>({
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
            {mode === "create" ? "Create Weakness" : "Edit Weakness"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add a new weakness to ${competitorName}`
              : "Update weakness details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="weakness-name">Name *</Label>
            <Input
              id="weakness-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Limited Distribution Network"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="weakness-description">Description *</Label>
            <Textarea
              id="weakness-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe this weakness..."
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
            {mode === "create" ? "Create Weakness" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteWeaknessDialog = ({
  isOpen,
  onClose,
  onConfirm,
  weaknessName,
}: DeleteWeaknessDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Weakness</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{weaknessName}"? This action cannot
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
