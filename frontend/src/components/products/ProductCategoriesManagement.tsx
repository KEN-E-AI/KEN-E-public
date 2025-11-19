import { useState, useMemo, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { Node, Edge } from "reactflow";
import { Plus, Trash2, Blocks, Pencil, Package, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import type { ProductCategory } from "@/services/productCategoryService";
import type {
  Product,
  ProductCreate,
  ProductUpdate,
} from "@/services/productService";
import type {
  ValueProposition,
  ValuePropositionCreate,
} from "@/services/valuePropositionService";
import {
  useProductCategories,
  useProducts,
  useCreateProductCategory,
  useUpdateProductCategory,
  useDeleteProductCategory,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
  useValuePropositions,
  useCreateValueProposition,
  useUpdateValueProposition,
  useDeleteValueProposition,
} from "@/queries/products";
import {
  useSubstituteProducts,
  useLinkProductToSubstitute,
  useUnlinkProductFromSubstitute,
} from "@/queries/competitors";
import type { SubstituteProduct } from "@/services/substituteProductService";
import { substituteProductService } from "@/services/substituteProductService";
import { competitorService } from "@/services/competitorService";
import { CategoryNode, ProductNode } from "./ProductFlowNodes";
import { SubstituteProductNode } from "../competitors/CompetitorFlowNodes";
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
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

// Import new knowledge graph components
import {
  KnowledgeGraphCard,
  HorizontalScrollList,
  HorizontalScrollItem,
  GraphVisualizationCard,
  KnowledgeGraphSideSheet,
  SideSheetNestedList,
  useUnsavedChanges,
  DIAGRAM_LAYOUT,
  DEFAULT_EDGE_STYLE,
} from "@/components/knowledge-graph";

interface ProductCategoriesManagementProps {
  hasEditAccess: boolean;
}

interface FormDataState {
  product_name: string;
  description: string;
  product_detail_page?: string;
}

export const ProductCategoriesManagement = ({
  hasEditAccess,
}: ProductCategoriesManagementProps) => {
  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const hasProcessedNavigation = useRef(false);

  // Fetch categories
  const { data: categoriesData, isLoading } = useProductCategories(
    selectedOrgAccount?.accountId || null,
  );
  const categories = categoriesData?.categories || [];

  // UI state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] =
    useState<ProductCategory | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  );
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormDataState>({
    product_name: "",
    description: "",
    product_detail_page: "",
  });

  // Product state and queries
  const { data: productsData, isLoading: isLoadingProducts } = useProducts(
    selectedOrgAccount?.accountId || null,
    selectedCategoryId,
  );
  const products = productsData?.products || [];

  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(
    null,
  );
  const [isCreateProductModalOpen, setIsCreateProductModalOpen] =
    useState(false);
  const [productFormData, setProductFormData] = useState<ProductCreate>({
    product_name: "",
    description: "",
    category_node_id: "",
    references: [],
    product_detail_page: "",
  });

  // Context menu state
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [contextMenuType, setContextMenuType] = useState<
    "category" | "product" | "substitute" | null
  >(null);
  const [isUnsavedChangesDialogOpen, setIsUnsavedChangesDialogOpen] =
    useState(false);
  const [pendingNode, setPendingNode] = useState<{
    type: "category" | "product";
    data: ProductCategory | Product;
  } | null>(null);

  // Product delete state
  const [isDeleteProductDialogOpen, setIsDeleteProductDialogOpen] =
    useState(false);

  // React Query mutations
  const createCategoryMutation = useCreateProductCategory();
  const updateCategoryMutation = useUpdateProductCategory();
  const deleteCategoryMutation = useDeleteProductCategory();
  const createProductMutation = useCreateProduct();
  const updateProductMutation = useUpdateProduct();
  const deleteProductMutation = useDeleteProduct();

  // Value Proposition state and mutations
  const [valuePropositionFormData, setValuePropositionFormData] =
    useState<ValuePropositionCreate>({
      display_name: "",
      description: "",
      parent_node_id: "",
      parent_node_type: "ProductCategory",
      references: [],
    });
  const [isCreateVPModalOpen, setIsCreateVPModalOpen] = useState(false);
  const [selectedValueProposition, setSelectedValueProposition] =
    useState<ValueProposition | null>(null);
  const [isDeleteVPDialogOpen, setIsDeleteVPDialogOpen] = useState(false);

  // Query for value propositions based on selected node
  const parentNodeId =
    contextMenuType === "category"
      ? selectedCategory?.node_id
      : selectedProduct?.node_id;

  const { data: valuePropositionsData, isLoading: isLoadingVPs } =
    useValuePropositions(
      selectedOrgAccount?.accountId || null,
      parentNodeId || null,
    );
  const valuePropositions = valuePropositionsData?.value_propositions || [];

  // Substitute Products linked to selected Product (for React Flow third row)
  const {
    data: substituteProductsData,
    isLoading: isLoadingSubstituteProducts,
  } = useSubstituteProducts(
    selectedProductId ? selectedOrgAccount?.accountId || null : null,
    null, // No competitor filter on Products page
    selectedProductId, // Filter by Product
  );
  const substituteProducts = substituteProductsData?.products || [];

  // Track selected substitute product (third level)
  const [selectedSubstituteProduct, setSelectedSubstituteProduct] =
    useState<SubstituteProduct | null>(null);
  const [selectedSubstituteProductId, setSelectedSubstituteProductId] =
    useState<string | null>(null);

  const createVPMutation = useCreateValueProposition();
  const updateVPMutation = useUpdateValueProposition();
  const deleteVPMutation = useDeleteValueProposition();

  // Link/Unlink mutations for substitute products
  const linkProductMutation = useLinkProductToSubstitute();
  const unlinkProductMutation = useUnlinkProductFromSubstitute();

  // Link substitute dialog state
  const [isLinkSubstituteDialogOpen, setIsLinkSubstituteDialogOpen] =
    useState(false);
  const [selectedSubstituteToLink, setSelectedSubstituteToLink] =
    useState<SubstituteProduct | null>(null);
  const [linkDialogSubstitutes, setLinkDialogSubstitutes] = useState<
    SubstituteProduct[]
  >([]);
  const [linkDialogCompetitorMap, setLinkDialogCompetitorMap] = useState<
    Map<string, string>
  >(new Map());
  const [isLoadingLinkDialogSubstitutes, setIsLoadingLinkDialogSubstitutes] =
    useState(false);

  // Unsaved changes detection
  const originalData =
    contextMenuType === "category" ? selectedCategory : selectedProduct;
  const hasUnsavedChanges = useUnsavedChanges(
    originalData,
    formData,
    isEditing,
  );

  // Handle navigation from other pages (e.g., Competitors page)
  useEffect(() => {
    const navState = location.state as {
      selectedProductId?: string;
      categoryNodeId?: string;
      autoEdit?: boolean;
    } | null;

    if (
      navState?.selectedProductId &&
      navState?.autoEdit &&
      !hasProcessedNavigation.current
    ) {
      // Step 1: Select the category if provided and not already selected
      if (
        navState.categoryNodeId &&
        navState.categoryNodeId !== selectedCategoryId
      ) {
        const category = categories.find(
          (c) => c.node_id === navState.categoryNodeId,
        );
        if (category) {
          setSelectedCategoryId(category.node_id);
          setSelectedCategory(category);
          // Don't mark as processed yet - wait for products to load
          return;
        }
      }

      // Step 2: Once category is selected and products loaded, find and select the product
      if (selectedCategoryId && products.length > 0) {
        const product = products.find(
          (p) => p.node_id === navState.selectedProductId,
        );

        if (product) {
          // Product found - select it and enter edit mode
          hasProcessedNavigation.current = true;

          setSelectedProduct(product);
          setSelectedProductId(product.node_id);
          setFormData({
            product_name: product.product_name,
            description: product.description,
            product_detail_page: product.product_detail_page || "",
          });
          setContextMenuType("product");
          setIsContextMenuOpen(true);
          setIsEditing(true);

          // Clear navigation state
          navigate(location.pathname, { replace: true, state: {} });
        }
      }
    }
  }, [
    location.state,
    products,
    categories,
    selectedCategoryId,
    navigate,
    location.pathname,
  ]);

  const handleCreateClick = () => {
    setFormData({ product_name: "", description: "", product_detail_page: "" });
    setIsCreateModalOpen(true);
  };

  const handleCategoryClick = (category: ProductCategory) => {
    setSelectedCategoryId(category.node_id);
    setSelectedCategory(category);
    setFormData({
      product_name: category.product_name,
      description: category.description,
      product_detail_page: "",
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

      await createCategoryMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        category: formData,
      });

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

      await updateCategoryMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedCategory.node_id,
        updates: formData,
      });

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

      await deleteCategoryMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedCategory.node_id,
      });

      setSelectedCategoryId(null);
      setSelectedCategory(null);
      setSelectedProductId(null);
      setSelectedProduct(null);
      setIsContextMenuOpen(false);

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

  // React Flow node types
  const nodeTypes = {
    categoryNode: CategoryNode,
    productNode: ProductNode,
    substituteProductNode: SubstituteProductNode,
  };

  // Generate nodes for React Flow
  const generateNodes = (): Node[] => {
    if (!selectedCategory) return [];

    const nodes: Node[] = [];
    const gap = DIAGRAM_LAYOUT.HORIZONTAL_GAP;

    nodes.push({
      id: selectedCategory.node_id,
      type: "categoryNode",
      position: {
        x: DIAGRAM_LAYOUT.PARENT_NODE_X,
        y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
      },
      data: {
        label: selectedCategory.product_name,
        isSelected:
          selectedCategoryId === selectedCategory.node_id && !selectedProductId,
        onAddProduct: () => setIsCreateProductModalOpen(true),
      },
    });

    const totalWidth =
      products.length * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH -
      DIAGRAM_LAYOUT.HORIZONTAL_GAP;
    const startX = DIAGRAM_LAYOUT.PARENT_NODE_X - totalWidth / 2;

    products.forEach((product, index) => {
      nodes.push({
        id: product.node_id,
        type: "productNode",
        position: {
          x: startX + index * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: product.product_name,
          showHandle: selectedProductId === product.node_id,
          isSelected: selectedProductId === product.node_id,
          onAddSubstitute: () => handleOpenLinkSubstituteDialog(),
        },
      });
    });

    // Add third row for SubstituteProducts when a Product is selected
    if (selectedProductId && substituteProducts.length > 0) {
      const substituteWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
      const substituteTotalWidth =
        substituteProducts.length * substituteWidth - gap;
      const substituteStartX =
        DIAGRAM_LAYOUT.PARENT_NODE_X - substituteTotalWidth / 2;
      const substituteY =
        DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING * 2;

      substituteProducts.forEach((sub, index) => {
        nodes.push({
          id: sub.node_id,
          type: "substituteProductNode",
          position: {
            x: substituteStartX + index * substituteWidth,
            y: substituteY,
          },
          data: {
            label: sub.product_name,
            showHandle: false,
            isSelected: selectedSubstituteProductId === sub.node_id,
            onAddProduct: () => {}, // No add functionality from Products page
          },
        });
      });
    }

    return nodes;
  };

  // Generate edges for React Flow
  const generateEdges = (): Edge[] => {
    if (!selectedCategory) return [];

    const edges: Edge[] = [];

    products.forEach((product) => {
      edges.push({
        id: `${selectedCategory.node_id}-${product.node_id}`,
        source: selectedCategory.node_id,
        target: product.node_id,
        type: "smoothstep",
        style: DEFAULT_EDGE_STYLE,
        sourceHandle: "bottom",
        targetHandle: "top",
      });
    });

    // Add Product → SubstituteProduct edges
    if (selectedProductId && selectedProduct) {
      substituteProducts.forEach((sub) => {
        edges.push({
          id: `${selectedProductId}-${sub.node_id}`,
          source: selectedProductId,
          target: sub.node_id,
          type: "smoothstep",
          style: DEFAULT_EDGE_STYLE,
          sourceHandle: "bottom",
          targetHandle: "top",
        });
      });
    }

    return edges;
  };

  // Handle node clicks in React Flow
  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    if (isEditing && hasUnsavedChanges) {
      if (node.type === "productNode") {
        const product = products.find((p) => p.node_id === node.id);
        if (product) {
          setPendingNode({ type: "product", data: product });
          setIsUnsavedChangesDialogOpen(true);
        }
      } else if (node.type === "categoryNode") {
        const category = categories.find((c) => c.node_id === node.id);
        if (category) {
          setPendingNode({ type: "category", data: category });
          setIsUnsavedChangesDialogOpen(true);
        }
      }
      return;
    }

    setIsEditing(false);

    if (node.type === "productNode") {
      const product = products.find((p) => p.node_id === node.id);
      if (!product) return;

      setSelectedProductId(node.id);
      setSelectedProduct(product);

      setFormData({
        product_name: product.product_name,
        description: product.description,
        product_detail_page: product.product_detail_page || "",
      });

      setContextMenuType("product");
      setIsContextMenuOpen(true);
    } else if (node.type === "substituteProductNode") {
      const sub = substituteProducts.find((s) => s.node_id === node.id);
      if (sub) {
        setSelectedSubstituteProduct(sub);
        setSelectedSubstituteProductId(sub.node_id);
        setContextMenuType("substitute");
        setIsContextMenuOpen(true);
      }
      return;
    } else if (node.type === "categoryNode") {
      const category = categories.find((c) => c.node_id === node.id);
      if (!category) return;

      setSelectedProductId(null);
      setSelectedProduct(null);

      setSelectedCategoryId(category.node_id);
      setSelectedCategory(category);

      setFormData({
        product_name: category.product_name,
        description: category.description,
        product_detail_page: "",
      });

      setContextMenuType("category");
      setIsContextMenuOpen(true);
    }
  };

  const handleDiscardChanges = () => {
    if (!pendingNode) return;

    setIsEditing(false);
    setIsUnsavedChangesDialogOpen(false);

    if (pendingNode.type === "product") {
      const product = pendingNode.data as Product;
      setSelectedProductId(product.node_id);
      setSelectedProduct(product);

      setFormData({
        product_name: product.product_name,
        description: product.description,
        product_detail_page: product.product_detail_page || "",
      });

      setContextMenuType("product");
      setIsContextMenuOpen(true);
    } else {
      const category = pendingNode.data as ProductCategory;

      setSelectedProductId(null);
      setSelectedProduct(null);

      setSelectedCategoryId(category.node_id);
      setSelectedCategory(category);

      setFormData({
        product_name: category.product_name,
        description: category.description,
        product_detail_page: "",
      });

      setContextMenuType("category");
      setIsContextMenuOpen(true);
    }

    setPendingNode(null);
  };

  const handleCreateProduct = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCategory) return;
    if (
      !productFormData.product_name.trim() ||
      !productFormData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Product name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating product...");
      setIsCreateProductModalOpen(false);

      const productData: ProductCreate = {
        product_name: productFormData.product_name,
        description: productFormData.description,
        category_node_id: selectedCategory.node_id,
        references: productFormData.references?.filter((r) => r.trim()) || [],
        product_detail_page:
          productFormData.product_detail_page?.trim() || undefined,
      };

      const newProduct = await createProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        product: productData,
      });

      setSelectedProductId(newProduct.node_id);
      setSelectedProduct(newProduct);

      setFormData({
        product_name: newProduct.product_name,
        description: newProduct.description,
        product_detail_page: newProduct.product_detail_page || "",
      });

      setContextMenuType("product");
      setIsContextMenuOpen(true);

      setProductFormData({
        product_name: "",
        description: "",
        category_node_id: "",
        references: [],
        product_detail_page: "",
      });

      toast({
        title: "Success",
        description: "Product created successfully",
      });
    } catch (error) {
      console.error("Failed to create product:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create product";

        if (status === 409) {
          toast({
            title: "Duplicate Product",
            description:
              "A product with this name already exists in this category",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to create products",
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

  const handleProductSave = async () => {
    if (!selectedOrgAccount?.accountId || !selectedProduct) return;

    if (!formData.product_name.trim() || !formData.description.trim()) {
      toast({
        title: "Validation Error",
        description: "Product name and description are required",
        variant: "destructive",
      });
      return;
    }

    const hasChanges =
      formData.product_name.trim() !== selectedProduct.product_name.trim() ||
      formData.description.trim() !== selectedProduct.description.trim() ||
      (formData.product_detail_page || "").trim() !==
        (selectedProduct.product_detail_page || "").trim();

    if (!hasChanges) {
      setIsEditing(false);
      toast({
        title: "No Changes",
        description: "No changes were made",
      });
      return;
    }

    try {
      startOperation("Updating product...");
      setIsEditing(false);

      const updateData: ProductUpdate = {
        product_name: formData.product_name.trim(),
        description: formData.description.trim(),
        product_detail_page: formData.product_detail_page?.trim() || undefined,
      };

      const updatedProduct = await updateProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedProduct.node_id,
        updates: updateData,
        categoryId:
          selectedCategory?.node_id || selectedProduct.category_node_id,
      });

      setSelectedProduct(updatedProduct);

      setFormData({
        product_name: updatedProduct.product_name,
        description: updatedProduct.description,
        product_detail_page: updatedProduct.product_detail_page || "",
      });

      toast({
        title: "Success",
        description: "Product updated successfully",
      });
    } catch (error) {
      console.error("Failed to update product:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to update product";

        if (status === 409) {
          toast({
            title: "Duplicate Product",
            description:
              "A product with this name already exists in this category",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to edit products",
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

  const handleDeleteProduct = async () => {
    if (!selectedOrgAccount?.accountId || !selectedProduct) return;

    try {
      startOperation("Deleting product...");
      setIsDeleteProductDialogOpen(false);

      await deleteProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedProduct.node_id,
        categoryId:
          selectedCategory?.node_id || selectedProduct.category_node_id,
      });

      setIsContextMenuOpen(false);
      setSelectedProductId(null);
      setSelectedProduct(null);

      toast({
        title: "Success",
        description: "Product deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete product:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to delete product";
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

  // Handle navigating to Competitors page to edit a substitute product
  const handleNavigateToSubstituteEdit = () => {
    if (!selectedSubstituteProduct) return;
    // Navigate to Competitors page with selected substitute product and auto-edit mode
    navigate("/knowledge/competitors", {
      state: {
        selectedSubstituteProductId: selectedSubstituteProduct.node_id,
        competitorNodeId: selectedSubstituteProduct.competitor_node_id,
        autoEdit: true,
      },
    });
  };

  // Handle unlinking substitute product from product
  const handleUnlinkSubstituteProduct = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedProduct ||
      !selectedSubstituteProduct
    )
      return;

    try {
      startOperation("Unlinking substitute product...");

      await unlinkProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        substituteProductId: selectedSubstituteProduct.node_id,
        productNodeId: selectedProduct.node_id,
      });

      toast({
        title: "Success",
        description: "Substitute product unlinked successfully",
      });

      setIsContextMenuOpen(false);
      setSelectedSubstituteProduct(null);
      setSelectedSubstituteProductId(null);
    } catch (error) {
      console.error("Failed to unlink substitute product:", error);
      toast({
        title: "Error",
        description: "Failed to unlink substitute product",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // Handle opening link substitute dialog
  const handleOpenLinkSubstituteDialog = async () => {
    if (!selectedOrgAccount?.accountId) return;

    setIsLinkSubstituteDialogOpen(true);
    setIsLoadingLinkDialogSubstitutes(true);

    try {
      // Load ALL substitute products and competitors in parallel
      const [substitutesResponse, competitorsResponse] = await Promise.all([
        substituteProductService.list(
          selectedOrgAccount.accountId,
          undefined, // No competitor filter
          undefined, // No product filter
          0,
          1000,
        ),
        competitorService.list(selectedOrgAccount.accountId, 0, 1000),
      ]);

      // Create competitor name lookup map
      const competitorMap = new Map(
        competitorsResponse.competitors.map((c) => [c.node_id, c.display_name]),
      );

      // Filter out already linked substitutes
      const linkedSubstituteIds = new Set(
        substituteProducts.map((s) => s.node_id),
      );
      const availableSubstitutes = substitutesResponse.products.filter(
        (s) => !linkedSubstituteIds.has(s.node_id),
      );

      // Sort by competitor name, then by product name
      const sorted = availableSubstitutes.sort((a, b) => {
        const compA = competitorMap.get(a.competitor_node_id) || "";
        const compB = competitorMap.get(b.competitor_node_id) || "";
        const compCompare = compA.localeCompare(compB);
        if (compCompare !== 0) return compCompare;
        return a.product_name.localeCompare(b.product_name);
      });

      setLinkDialogSubstitutes(sorted);
      setLinkDialogCompetitorMap(competitorMap);
    } catch (error) {
      console.error("Failed to load substitute products:", error);
      toast({
        title: "Error",
        description: "Failed to load substitute products",
        variant: "destructive",
      });
    } finally {
      setIsLoadingLinkDialogSubstitutes(false);
    }
  };

  // Handle linking substitute product
  const handleLinkSubstituteProduct = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedProduct ||
      !selectedSubstituteToLink
    )
      return;

    try {
      startOperation("Linking substitute product...");

      await linkProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        substituteProductId: selectedSubstituteToLink.node_id,
        productNodeId: selectedProduct.node_id,
      });

      toast({
        title: "Success",
        description: "Substitute product linked successfully",
      });

      setIsLinkSubstituteDialogOpen(false);
      setSelectedSubstituteToLink(null);
    } catch (error) {
      console.error("Failed to link substitute product:", error);
      toast({
        title: "Error",
        description: "Failed to link substitute product",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // Value Proposition handlers
  const handleCreateValueProposition = async () => {
    if (!selectedOrgAccount) return;

    try {
      startOperation("Creating value proposition...");

      await createVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        valueProposition: valuePropositionFormData,
      });

      toast({
        title: "Success",
        description: "Value proposition created successfully",
      });

      setIsCreateVPModalOpen(false);
      setValuePropositionFormData({
        display_name: "",
        description: "",
        parent_node_id: "",
        parent_node_type: "ProductCategory",
        references: [],
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        if (status === 409) {
          toast({
            title: "Duplicate Value Proposition",
            description: "A value proposition with this name already exists",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description:
              "You don't have permission to create value propositions",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description:
              error.response?.data?.detail ||
              "Failed to create value proposition",
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  const handleUpdateValueProposition = async () => {
    if (!selectedOrgAccount || !selectedValueProposition) return;

    try {
      startOperation("Updating value proposition...");

      await updateVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedValueProposition.node_id,
        updates: {
          display_name: valuePropositionFormData.display_name,
          description: valuePropositionFormData.description,
          references: valuePropositionFormData.references,
        },
        parentNodeId: valuePropositionFormData.parent_node_id,
      });

      toast({
        title: "Success",
        description: "Value proposition updated successfully",
      });

      setIsCreateVPModalOpen(false);
      setSelectedValueProposition(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        toast({
          title: "Error",
          description:
            error.response?.data?.detail ||
            "Failed to update value proposition",
          variant: "destructive",
        });
      }
    } finally {
      endOperation();
    }
  };

  const handleDeleteValueProposition = async () => {
    if (!selectedOrgAccount || !selectedValueProposition) return;

    try {
      startOperation("Deleting value proposition...");

      await deleteVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedValueProposition.node_id,
        parentNodeId: valuePropositionFormData.parent_node_id,
      });

      toast({
        title: "Success",
        description: "Value proposition deleted successfully",
      });

      setIsDeleteVPDialogOpen(false);
      setSelectedValueProposition(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        toast({
          title: "Error",
          description:
            error.response?.data?.detail ||
            "Failed to delete value proposition",
          variant: "destructive",
        });
      }
    } finally {
      endOperation();
    }
  };

  const nodes = useMemo(
    () => generateNodes(),
    [
      selectedCategory,
      products,
      selectedProductId,
      substituteProducts,
      selectedSubstituteProductId,
    ],
  );
  const edges = useMemo(
    () => generateEdges(),
    [
      selectedCategory,
      selectedCategoryId,
      products,
      selectedProductId,
      selectedProduct,
      substituteProducts,
    ],
  );

  return (
    <>
      {/* Product Categories Card with Horizontal Scroll */}
      <KnowledgeGraphCard
        title="Product Categories"
        icon={Blocks}
        tooltip="Create product categories to help KEN-E understand the types of products or services that your business sells."
        actions={
          hasEditAccess ? (
            <Button
              onClick={handleCreateClick}
              size="sm"
              variant="ghost"
              className="h-8 w-8 p-0"
            >
              <Plus className="h-5 w-5" />
            </Button>
          ) : undefined
        }
      >
        <HorizontalScrollList
          items={categories}
          selectedId={selectedCategoryId}
          onItemClick={handleCategoryClick}
          isLoading={isLoading}
          emptyMessage="No product categories found."
          emptyMessageWithAction="Click '+' to add one."
          hasEditAccess={hasEditAccess}
          renderItem={(category, isSelected) => (
            <HorizontalScrollItem
              label={category.product_name}
              sublabel="Product Category"
              icon={Blocks}
              bgColor="bg-brand-light-blue bg-opacity-30"
              iconBgColor="bg-brand-light-blue"
              isSelected={isSelected}
              onClick={() => {}}
            />
          )}
        />
      </KnowledgeGraphCard>

      {/* Products Visualization Card */}
      <div className="mt-6">
        <GraphVisualizationCard
          title="Products and Services"
          icon={Package}
          tooltip="Identify a few of your flagship products within the selected product category. An exhaustive list is not required."
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeClick}
          isLoading={isLoadingProducts}
          showEmpty={!selectedCategoryId}
          emptyMessage="Select a product category to view details."
        />
      </div>

      {/* Create Category Modal */}
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

      {/* Delete Category Confirmation */}
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

      {/* Delete Product Confirmation */}
      <AlertDialog
        open={isDeleteProductDialogOpen}
        onOpenChange={setIsDeleteProductDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Product</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedProduct?.product_name}"?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteProduct}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Link Substitute Product Dialog */}
      <Dialog
        open={isLinkSubstituteDialogOpen}
        onOpenChange={setIsLinkSubstituteDialogOpen}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Link Substitute Product</DialogTitle>
            <DialogDescription>
              Select which competitor offering may substitute this product.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {isLoadingLinkDialogSubstitutes ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : linkDialogSubstitutes.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No available substitute products to link. All substitutes are
                already linked or you have no substitute products yet.
              </p>
            ) : (
              <>
                <Label>Select Substitute Product</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={selectedSubstituteToLink?.node_id || ""}
                  onChange={(e) => {
                    const substitute = linkDialogSubstitutes.find(
                      (s) => s.node_id === e.target.value,
                    );
                    setSelectedSubstituteToLink(substitute || null);
                  }}
                >
                  <option value="">-- Select Substitute Product --</option>
                  {linkDialogSubstitutes.map((substitute) => {
                    const competitorName =
                      linkDialogCompetitorMap.get(
                        substitute.competitor_node_id,
                      ) || "Unknown Competitor";
                    return (
                      <option
                        key={substitute.node_id}
                        value={substitute.node_id}
                      >
                        {competitorName}: {substitute.product_name}
                      </option>
                    );
                  })}
                </select>
              </>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsLinkSubstituteDialogOpen(false);
                setSelectedSubstituteToLink(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleLinkSubstituteProduct}
              disabled={
                !selectedSubstituteToLink || linkProductMutation.isPending
              }
            >
              {linkProductMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Linking...
                </>
              ) : (
                "Link Substitute"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Value Proposition Confirmation */}
      <AlertDialog
        open={isDeleteVPDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteVPDialogOpen(open);
          if (!open) {
            setSelectedValueProposition(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Value Proposition?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "
              {selectedValueProposition?.display_name}"? This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => setSelectedValueProposition(null)}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteValueProposition}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Unsaved Changes Warning */}
      <AlertDialog
        open={isUnsavedChangesDialogOpen}
        onOpenChange={setIsUnsavedChangesDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Are you sure you want to discard them?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingNode(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDiscardChanges}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Discard Changes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create Product Modal */}
      <Dialog
        open={isCreateProductModalOpen}
        onOpenChange={setIsCreateProductModalOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Product</DialogTitle>
            <DialogDescription>
              Add a new product to {selectedCategory?.product_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-product-name">Product Name *</Label>
              <Input
                id="create-product-name"
                value={productFormData.product_name}
                onChange={(e) =>
                  setProductFormData({
                    ...productFormData,
                    product_name: e.target.value,
                  })
                }
                placeholder="e.g., Business Loans"
                maxLength={200}
              />
            </div>
            <div>
              <Label htmlFor="create-product-description">Description *</Label>
              <Textarea
                id="create-product-description"
                value={productFormData.description}
                onChange={(e) =>
                  setProductFormData({
                    ...productFormData,
                    description: e.target.value,
                  })
                }
                placeholder="Describe this product..."
                rows={4}
                maxLength={4000}
              />
            </div>
            <div>
              <Label htmlFor="create-product-detail-page">
                Product Detail Page (Optional)
              </Label>
              <Input
                id="create-product-detail-page"
                type="url"
                value={productFormData.product_detail_page}
                onChange={(e) =>
                  setProductFormData({
                    ...productFormData,
                    product_detail_page: e.target.value,
                  })
                }
                placeholder="https://..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateProductModalOpen(false);
                setProductFormData({
                  product_name: "",
                  description: "",
                  category_node_id: "",
                  references: [],
                  product_detail_page: "",
                });
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateProduct}
              disabled={
                !productFormData.product_name.trim() ||
                !productFormData.description.trim()
              }
            >
              Create Product
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create/Edit Value Proposition Modal */}
      <Dialog
        open={isCreateVPModalOpen}
        onOpenChange={(open) => {
          setIsCreateVPModalOpen(open);
          if (!open) {
            setSelectedValueProposition(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedValueProposition ? "Edit" : "Create"} Value Proposition
            </DialogTitle>
            <DialogDescription>
              {selectedValueProposition
                ? "Update the value proposition details"
                : `Add a value proposition to ${
                    contextMenuType === "category"
                      ? selectedCategory?.product_name
                      : selectedProduct?.product_name
                  }`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="vp-display-name">Display Name *</Label>
              <Input
                id="vp-display-name"
                value={valuePropositionFormData.display_name}
                onChange={(e) =>
                  setValuePropositionFormData({
                    ...valuePropositionFormData,
                    display_name: e.target.value,
                  })
                }
                placeholder="e.g., Fast Processing Times"
                maxLength={60}
              />
              <p className="text-xs text-dashboard-gray-500 mt-1">
                Short, descriptive name (max 60 characters)
              </p>
            </div>
            <div>
              <Label htmlFor="vp-description">Description *</Label>
              <Textarea
                id="vp-description"
                value={valuePropositionFormData.description}
                onChange={(e) =>
                  setValuePropositionFormData({
                    ...valuePropositionFormData,
                    description: e.target.value,
                  })
                }
                placeholder="Describe the value this provides to customers..."
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateVPModalOpen(false);
                setSelectedValueProposition(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={
                selectedValueProposition
                  ? handleUpdateValueProposition
                  : handleCreateValueProposition
              }
              disabled={
                !valuePropositionFormData.display_name.trim() ||
                !valuePropositionFormData.description.trim()
              }
            >
              {selectedValueProposition ? "Save Changes" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Node Context Menu Side Sheet */}
      <KnowledgeGraphSideSheet
        open={isContextMenuOpen}
        onOpenChange={(open) => {
          if (!open && (isCreateVPModalOpen || isDeleteVPDialogOpen)) {
            return;
          }
          if (!open && isEditing && hasUnsavedChanges) {
            return;
          }
          setIsContextMenuOpen(open);
          if (!open) {
            setIsEditing(false);
          }
        }}
        title={
          contextMenuType === "category"
            ? "Product Category"
            : contextMenuType === "product"
              ? selectedProduct?.product_name || "Product"
              : contextMenuType === "substitute"
                ? selectedSubstituteProduct?.product_name ||
                  "Substitute Product"
                : ""
        }
        icon={
          contextMenuType === "category"
            ? Blocks
            : contextMenuType === "product"
              ? Package
              : contextMenuType === "substitute"
                ? Package
                : Package
        }
        isEditing={isEditing}
        onEdit={
          contextMenuType === "substitute"
            ? handleNavigateToSubstituteEdit
            : () => setIsEditing(true)
        }
        onSave={contextMenuType === "category" ? handleSave : handleProductSave}
        onCancel={() => {
          setIsEditing(false);
          if (selectedCategory && contextMenuType === "category") {
            setFormData({
              product_name: selectedCategory.product_name,
              description: selectedCategory.description,
              product_detail_page: "",
            });
          } else if (selectedProduct && contextMenuType === "product") {
            setFormData({
              product_name: selectedProduct.product_name,
              description: selectedProduct.description,
              product_detail_page: selectedProduct.product_detail_page || "",
            });
          }
        }}
        onDelete={
          contextMenuType === "substitute"
            ? handleUnlinkSubstituteProduct
            : () => {
                setIsContextMenuOpen(false);
                if (contextMenuType === "category" && selectedCategory) {
                  handleDeleteClick(selectedCategory);
                } else if (contextMenuType === "product" && selectedProduct) {
                  setIsDeleteProductDialogOpen(true);
                }
              }
        }
        deleteButtonLabel={
          contextMenuType === "substitute" ? "Unlink" : undefined
        }
        hasEditAccess={hasEditAccess}
        preventClose={isEditing && hasUnsavedChanges}
        modal={false}
      >
        {isEditing ? (
          <div className="space-y-4">
            <div>
              <Label htmlFor="context-edit-name">Name:</Label>
              <Input
                id="context-edit-name"
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
              <Label htmlFor="context-edit-description">Description:</Label>
              <Textarea
                id="context-edit-description"
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
            {contextMenuType === "product" && (
              <div>
                <Label htmlFor="context-edit-product-detail-page">
                  Product Detail Page (Optional):
                </Label>
                <Input
                  id="context-edit-product-detail-page"
                  type="url"
                  value={formData.product_detail_page || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      product_detail_page: e.target.value,
                    })
                  }
                  placeholder="https://example.com/product-details"
                />
              </div>
            )}
          </div>
        ) : contextMenuType === "substitute" ? (
          // SubstituteProduct view (read-only with navigation to edit)
          <div className="space-y-4">
            <div>
              <Label>Product Name</Label>
              <p className="text-sm text-muted-foreground mt-1">
                {selectedSubstituteProduct?.product_name}
              </p>
            </div>
            <div>
              <Label>Description</Label>
              <p className="text-sm text-muted-foreground mt-1">
                {selectedSubstituteProduct?.description}
              </p>
            </div>
            {selectedSubstituteProduct?.product_detail_page && (
              <div>
                <Label>Product Page</Label>
                <a
                  href={selectedSubstituteProduct.product_detail_page}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline mt-1 block"
                >
                  {selectedSubstituteProduct.product_detail_page}
                </a>
              </div>
            )}
            <div className="rounded-md bg-muted p-3 mt-4">
              <p className="text-xs text-muted-foreground">
                This competitor offering may substitute your product. Click
                "Unlink" to remove this relationship. Click "Edit" to manage
                details on the Competitors page.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <p className="font-semibold">Name:</p>
              <p>
                {contextMenuType === "category"
                  ? selectedCategory?.product_name
                  : selectedProduct?.product_name}
              </p>
            </div>
            <div>
              <p className="font-semibold">Description:</p>
              <p className="text-sm text-dashboard-gray-600">
                {contextMenuType === "category"
                  ? selectedCategory?.description
                  : selectedProduct?.description}
              </p>
            </div>
            {contextMenuType === "product" &&
              selectedProduct?.product_detail_page && (
                <div>
                  <p className="font-semibold">Product Detail Page:</p>
                  <a
                    href={selectedProduct.product_detail_page}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-800 underline break-all"
                  >
                    {selectedProduct.product_detail_page}
                  </a>
                </div>
              )}
          </div>
        )}

        {/* Value Propositions Nested List */}
        <SideSheetNestedList
          title="Value Propositions"
          tooltip={
            contextMenuType === "category"
              ? "Create a list of reasons why customers might choose to purchase the products or services within this category. What problems do they solve for them? How is your offering unique from those of your competitors?"
              : "Create a list of reasons why customers might choose to purchase this product or service. What problems does it solve for them? How is this product or service unique from those of your competitors?"
          }
          items={valuePropositions}
          isLoading={isLoadingVPs}
          onAdd={() => {
            setValuePropositionFormData({
              display_name: "",
              description: "",
              parent_node_id: parentNodeId || "",
              parent_node_type:
                contextMenuType === "category" ? "ProductCategory" : "Product",
              references: [],
            });
            setIsCreateVPModalOpen(true);
          }}
          onEdit={(vp) => {
            setSelectedValueProposition(vp);
            setValuePropositionFormData({
              display_name: vp.display_name,
              description: vp.description,
              parent_node_id: parentNodeId || "",
              parent_node_type:
                contextMenuType === "category" ? "ProductCategory" : "Product",
              references: vp.references || [],
            });
            setIsCreateVPModalOpen(true);
          }}
          onDelete={(vp) => {
            setSelectedValueProposition(vp);
            setValuePropositionFormData({
              ...valuePropositionFormData,
              parent_node_id: parentNodeId || "",
            });
            setIsDeleteVPDialogOpen(true);
          }}
          hasEditAccess={hasEditAccess}
          isEditingParent={isEditing}
        />
      </KnowledgeGraphSideSheet>
    </>
  );
};
