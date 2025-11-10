import { useState, useEffect, useRef } from "react";
import {
  Plus,
  Trash2,
  Boxes,
  Blocks,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Package,
} from "lucide-react";
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
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] =
    useState<ProductCategory | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  );
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<ProductCategoryCreate>({
    product_name: "",
    description: "",
  });
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

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

  const checkScrollPosition = () => {
    const container = scrollContainerRef.current;
    if (!container) return;

    setCanScrollLeft(container.scrollLeft > 0);
    setCanScrollRight(
      container.scrollLeft < container.scrollWidth - container.clientWidth - 1,
    );
  };

  const scrollLeft = () => {
    scrollContainerRef.current?.scrollBy({ left: -300, behavior: "smooth" });
  };

  const scrollRight = () => {
    scrollContainerRef.current?.scrollBy({ left: 300, behavior: "smooth" });
  };

  useEffect(() => {
    checkScrollPosition();
    const handleResize = () => checkScrollPosition();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [categories]);

  const handleCreateClick = () => {
    setFormData({ product_name: "", description: "" });
    setIsCreateModalOpen(true);
  };

  const handleCategoryClick = (category: ProductCategory) => {
    setSelectedCategoryId(category.node_id);
    setSelectedCategory(category);
    setFormData({
      product_name: category.product_name,
      description: category.description,
    });
    setIsEditing(false);
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
      setIsEditing(false);

      await productCategoryService.update(
        selectedOrgAccount.accountId,
        selectedCategory.node_id,
        formData,
      );

      await loadCategories();

      // Update selected category with new data
      setSelectedCategory({
        ...selectedCategory,
        product_name: formData.product_name,
        description: formData.description,
      });

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
              <Blocks className="h-5 w-5" />
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
            <div className="relative">
              {/* Left Scroll Arrow */}
              {canScrollLeft && (
                <button
                  className="absolute left-0 top-0 bottom-0 z-20 bg-gray-500 bg-opacity-75 px-3 flex items-center justify-center hover:bg-opacity-90 transition-opacity"
                  onClick={scrollLeft}
                >
                  <ChevronLeft className="h-6 w-6 text-white" />
                </button>
              )}

              {/* Scrollable Container */}
              <div
                ref={scrollContainerRef}
                className="flex gap-3 overflow-x-auto px-2 py-2"
                onScroll={checkScrollPosition}
              >
                {categories.map((category) => (
                  <div
                    key={category.node_id}
                    className={`flex-shrink-0 p-4 rounded-lg transition-colors cursor-pointer ${
                      selectedCategoryId === category.node_id
                        ? "ring-2 ring-brand-medium-blue"
                        : "hover:ring-2 hover:ring-gray-300"
                    }`}
                    onClick={() => handleCategoryClick(category)}
                  >
                    <div className="flex items-center">
                      {/* Text Box - Left */}
                      <div className="bg-brand-medium-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
                        <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
                          Product Category
                        </p>
                        <p className="font-semibold text-dashboard-gray-900 leading-tight">
                          {category.product_name}
                        </p>
                      </div>

                      {/* Circle with Icon - Right */}
                      <div className="flex-shrink-0 -ml-12 relative z-10">
                        <div
                          className="rounded-full bg-brand-medium-blue flex items-center justify-center"
                          style={{ width: "72px", height: "72px" }}
                        >
                          <Blocks
                            className="text-white"
                            style={{ width: "48px", height: "48px" }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Right Scroll Arrow */}
              {canScrollRight && (
                <button
                  className="absolute right-0 top-0 bottom-0 z-20 bg-gray-500 bg-opacity-75 px-3 flex items-center justify-center hover:bg-opacity-90 transition-opacity"
                  onClick={scrollRight}
                >
                  <ChevronRight className="h-6 w-6 text-white" />
                </button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* About Section or Empty State */}
      <div className="flex gap-6 mt-6">
        {selectedCategoryId ? (
          <Card className="w-[400px]">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="flex items-center gap-2">
                  About
                  {hasEditAccess && !isEditing && (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="text-dashboard-gray-600 hover:text-dashboard-gray-900"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                  )}
                </CardTitle>
                {hasEditAccess && !isEditing && (
                  <button
                    onClick={() =>
                      selectedCategory && handleDeleteClick(selectedCategory)
                    }
                    className="text-brand-red hover:text-brand-red/80"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {isEditing ? (
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="edit-name">Name:</Label>
                    <Input
                      id="edit-name"
                      value={formData.product_name}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          product_name: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit-description">Description:</Label>
                    <Textarea
                      id="edit-description"
                      value={formData.description}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          description: e.target.value,
                        })
                      }
                      rows={4}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => {
                        setIsEditing(false);
                        setFormData({
                          product_name: selectedCategory?.product_name || "",
                          description: selectedCategory?.description || "",
                        });
                      }}
                      variant="outline"
                    >
                      Cancel
                    </Button>
                    <Button onClick={handleSave}>Save Changes</Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <p className="font-semibold">Name:</p>
                    <p>{selectedCategory?.product_name}</p>
                  </div>
                  <div>
                    <p className="font-semibold">Description:</p>
                    <p className="text-sm text-dashboard-gray-600">
                      {selectedCategory?.description ||
                        "No description provided"}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="p-6 bg-dashboard-gray-50 rounded-lg border border-dashboard-gray-200">
            <p className="text-dashboard-gray-500 text-center">
              Select a product category to view details.
            </p>
          </div>
        )}

        {/* Products Card - Only show when category is selected */}
        {selectedCategoryId && (
          <Card className="flex-1 h-[600px]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Products
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-dashboard-gray-500">
                Products content will appear here.
              </p>
            </CardContent>
          </Card>
        )}
      </div>

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
