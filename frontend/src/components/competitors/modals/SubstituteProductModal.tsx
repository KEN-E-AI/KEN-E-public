import { useState, useEffect } from "react";
import type {
  SubstituteProduct,
  SubstituteProductCreate,
} from "@/services/substituteProductService";
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

export interface SubstituteProductModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: SubstituteProductCreate) => Promise<void>;
  competitorId: string;
  competitorName: string;
  initialData?: SubstituteProduct;
  mode: "create" | "edit";
}

export interface DeleteSubstituteProductDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  productName: string;
}

export const SubstituteProductModal = ({
  isOpen,
  onClose,
  onSubmit,
  competitorId,
  competitorName,
  initialData,
  mode,
}: SubstituteProductModalProps) => {
  const [formData, setFormData] = useState<SubstituteProductCreate>({
    product_name: initialData?.product_name || "",
    description: initialData?.description || "",
    competitor_node_id: competitorId,
    references: initialData?.references || [],
    product_detail_page: initialData?.product_detail_page || "",
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({
        product_name: initialData?.product_name || "",
        description: initialData?.description || "",
        competitor_node_id: competitorId,
        references: initialData?.references || [],
        product_detail_page: initialData?.product_detail_page || "",
      });
    }
  }, [isOpen, initialData, competitorId]);

  const handleSubmit = async () => {
    await onSubmit(formData);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      product_name: "",
      description: "",
      competitor_node_id: competitorId,
      references: [],
      product_detail_page: "",
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create"
              ? "Create Substitute Product"
              : "Edit Substitute Product"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? `Add a new substitute product to ${competitorName}`
              : "Update substitute product details"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <Label htmlFor="substitute-product-name">Product Name *</Label>
            <Input
              id="substitute-product-name"
              value={formData.product_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  product_name: e.target.value,
                })
              }
              placeholder="e.g., Premium Air Purifier Pro"
              maxLength={200}
            />
          </div>
          <div>
            <Label htmlFor="substitute-product-description">
              Description *
            </Label>
            <Textarea
              id="substitute-product-description"
              value={formData.description}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  description: e.target.value,
                })
              }
              placeholder="Describe this substitute product..."
              rows={4}
              maxLength={4000}
            />
          </div>
          <div>
            <Label htmlFor="substitute-product-page">
              Product Detail Page (Optional)
            </Label>
            <Input
              id="substitute-product-page"
              type="url"
              value={formData.product_detail_page || ""}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  product_detail_page: e.target.value,
                })
              }
              placeholder="https://..."
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
              !formData.product_name.trim() || !formData.description.trim()
            }
          >
            {mode === "create" ? "Create Substitute Product" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const DeleteSubstituteProductDialog = ({
  isOpen,
  onClose,
  onConfirm,
  productName,
}: DeleteSubstituteProductDialogProps) => {
  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Substitute Product</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete "{productName}"? This action cannot
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
