import { useState, useEffect } from "react";
import type { Risk, RiskCreate } from "@/services/riskService";
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

export interface RiskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: RiskCreate) => Promise<void>;
  strengthId: string;
  strengthName: string;
  initialData?: Risk;
  mode: "create" | "edit";
}

export interface DeleteRiskDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  riskName: string;
}

export const RiskModal = ({
  isOpen,
  onClose,
  onSubmit,
  strengthId,
  strengthName,
  initialData,
  mode,
}: RiskModalProps) => {
  const [formData, setFormData] = useState<RiskCreate>({
    display_name: initialData?.display_name || "",
    description: initialData?.description || "",
    strength_node_id: strengthId,
    references: initialData?.references || [],
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        display_name: initialData?.display_name || "",
        description: initialData?.description || "",
        strength_node_id: strengthId,
        references: initialData?.references || [],
      });
    }
  }, [isOpen, initialData, strengthId]);

  const handleSubmit = async () => {
    await onSubmit(formData);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      display_name: "",
      description: "",
      strength_node_id: strengthId,
      references: [],
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create Risk" : "Edit Risk"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add a risk created by ${strengthName}`
              : "Update risk details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="risk-name">Name *</Label>
            <Input
              id="risk-name"
              value={formData.display_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  display_name: e.target.value,
                })
              }
              placeholder="e.g., Market share erosion"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="risk-description">Description *</Label>
            <Textarea
              id="risk-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe this risk..."
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
            {mode === "create" ? "Create Risk" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteRiskDialog = ({
  isOpen,
  onClose,
  onConfirm,
  riskName,
}: DeleteRiskDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Risk</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{riskName}"? This action cannot be
            undone.
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
