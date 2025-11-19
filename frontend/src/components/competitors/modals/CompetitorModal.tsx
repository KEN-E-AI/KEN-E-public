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

export interface DeleteCompetitorDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  competitorName: string;
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
}: DeleteCompetitorDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Competitor</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{competitorName}"? This action
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
