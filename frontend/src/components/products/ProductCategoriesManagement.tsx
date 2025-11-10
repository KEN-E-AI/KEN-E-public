import { useState, useEffect } from "react";
import { Plus, Trash2, Boxes } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import {
  productCategoryService,
  type ProductCategory,
  type ProductCategoryCreate,
  type ProductCategoryUpdate,
} from "@/services/productCategoryService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

interface ProductCategoriesManagementProps {
  hasEditAccess: boolean;
}

export const ProductCategoriesManagement = ({
  hasEditAccess,
}: ProductCategoriesManagementProps) => {
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] =
    useState<ProductCategory | null>(null);
  const [formData, setFormData] = useState<ProductCategoryCreate>({
    product_name: "",
    description: "",
  });

  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();

  useEffect(() => {
    if (selectedOrgAccount?.accountId) {
      loadCategories();
    }
  }, [selectedOrgAccount]);

  const loadCategories = async () => {
    if (!selectedOrgAccount?.accountId) return;

    try {
      setIsLoading(true);
      const response = await productCategoryService.list(
        selectedOrgAccount.accountId,
      );
      setCategories(response.categories);
    } catch (error) {
      console.error("Failed to load product categories:", error);
      toast({
        title: "Error",
        description: "Failed to load product categories",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateClick = () => {
    setFormData({ product_name: "", description: "" });
    setIsCreateModalOpen(true);
  };

  const handleEditClick = (category: ProductCategory) => {
    setSelectedCategory(category);
    setFormData({
      product_name: category.product_name,
      description: category.description,
    });
    setIsEditModalOpen(true);
  };

  const handleDeleteClick = (category: ProductCategory) => {
    setSelectedCategory(category);
    setIsDeleteDialogOpen(true);
  };

  const handleCreate = async () => {
    if (!selectedOrgAccount?.accountId) return;
    if (!formData.product_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Product name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating product category...");
      setIsCreateModalOpen(false);

      await productCategoryService.create(
        selectedOrgAccount.accountId,
        formData,
      );

      await loadCategories();

      toast({
        title: "Success",
        description: "Product category created successfully",
      });
    } catch (error) {
      console.error("Failed to create product category:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create product category";

        if (status === 409) {
          toast({
            title: "Duplicate Category",
            description: "A category with this name already exists",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to create categories",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  const handleSave = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCategory) return;
    if (!formData.product_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Product name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Updating product category...");
      setIsEditModalOpen(false);

      await productCategoryService.update(
        selectedOrgAccount.accountId,
        selectedCategory.node_id,
        formData,
      );

      await loadCategories();

      toast({
        title: "Success",
        description: "Product category updated successfully",
      });
    } catch (error) {
      console.error("Failed to update product category:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update product category";
        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
      }
    } finally {
      endOperation();
    }
  };

  const handleDelete = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCategory) return;

    try {
      startOperation("Deleting product category...");
      setIsDeleteDialogOpen(false);

      await productCategoryService.delete(
        selectedOrgAccount.accountId,
        selectedCategory.node_id,
      );

      await loadCategories();

      toast({
        title: "Success",
        description: "Product category deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete product category:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to delete product category";

        if (status === 400 && message.includes("dependencies")) {
          toast({
            title: "Cannot Delete",
            description:
              "This category has products linked to it. Remove them first.",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="flex items-center gap-2">
              <Boxes className="h-5 w-5" />
              Product Categories
            </CardTitle>
            {hasEditAccess && (
              <Button
                onClick={handleCreateClick}
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0"
              >
                <Plus className="h-5 w-5" />
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-dashboard-gray-500">
              Loading categories...
            </div>
          ) : categories.length === 0 ? (
            <div className="text-center py-8 text-dashboard-gray-500">
              No product categories found.
              {hasEditAccess && " Click 'Create Category' to add one."}
            </div>
          ) : (
            <div className="space-y-3">
              {categories.map((category) => (
                <div
                  key={category.node_id}
                  className={`p-4 border border-dashboard-gray-200 rounded-lg hover:bg-dashboard-gray-50 transition-colors ${
                    hasEditAccess ? "cursor-pointer" : ""
                  }`}
                  onClick={() => hasEditAccess && handleEditClick(category)}
                >
                  <h3 className="font-semibold text-dashboard-gray-900 mb-1">
                    {category.product_name}
                  </h3>
                  <p className="text-sm text-dashboard-gray-600">
                    {category.description}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Modal */}
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Product Category</DialogTitle>
            <DialogDescription>
              Add a new product category to organize your products.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-product-name">Category Name</Label>
              <Input
                id="create-product-name"
                value={formData.product_name}
                onChange={(e) =>
                  setFormData({ ...formData, product_name: e.target.value })
                }
                placeholder="e.g., Software Products"
              />
            </div>
            <div>
              <Label htmlFor="create-description">Description</Label>
              <Textarea
                id="create-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Describe this product category..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!formData.product_name.trim()}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Product Category</DialogTitle>
            <DialogDescription>
              Update the category name or description.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="edit-product-name">Category Name</Label>
              <Input
                id="edit-product-name"
                value={formData.product_name}
                onChange={(e) =>
                  setFormData({ ...formData, product_name: e.target.value })
                }
                placeholder="e.g., Software Products"
              />
            </div>
            <div>
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Describe this product category..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => {
                setIsEditModalOpen(false);
                if (selectedCategory) {
                  handleDeleteClick(selectedCategory);
                }
              }}
              className="text-brand-red hover:text-brand-red hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </Button>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setIsEditModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={!formData.product_name.trim()}
              >
                Save Changes
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Product Category?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedCategory?.product_name}
              "? This action cannot be undone.
              {selectedCategory && (
                <span className="block mt-2 text-dashboard-gray-600">
                  Note: Categories with linked products cannot be deleted.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
