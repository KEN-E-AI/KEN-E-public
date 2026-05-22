import { useState, useMemo, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { Node, Edge } from "reactflow";
import { Plus, Trash2, Users, Pencil, Loader2, Blocks } from "lucide-react";
import {
  calculateChildNodeX,
  calculateChildNodeY,
} from "@/components/knowledge-graph/utils/layoutCalculations";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import type { CustomerProfile } from "@/services/customerProfileService";
import type { ProductCategory } from "@/services/productCategoryService";
import {
  useCustomerProfiles,
  useCreateCustomerProfile,
  useUpdateCustomerProfile,
  useDeleteCustomerProfile,
  useLinkedProductCategories,
  useLinkProductCategoryToProfile,
  useUnlinkProductCategoryFromProfile,
} from "@/queries/customerProfiles";
import { useProductCategories, useValuePropositions } from "@/queries/products";
import { CustomerProfileNode, ProductCategoryNode } from "./CustomerFlowNodes";
import { CustomerKeywordsSection } from "./CustomerKeywordsSection";
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

// Import knowledge graph components
import {
  KnowledgeGraphCard,
  HorizontalScrollList,
  HorizontalScrollItem,
  GraphVisualizationCard,
  KnowledgeGraphSideSheet,
  useUnsavedChanges,
  DIAGRAM_LAYOUT,
  DEFAULT_EDGE_STYLE,
} from "@/components/knowledge-graph";

interface CustomerProfilesManagementProps {
  hasEditAccess: boolean;
}

interface FormDataState {
  display_name: string;
  description: string;
}

export const CustomerProfilesManagement = ({
  hasEditAccess,
}: CustomerProfilesManagementProps) => {
  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const hasProcessedNavigation = useRef(false);

  // Fetch customer profiles
  const { data: profilesData, isLoading } = useCustomerProfiles(
    selectedOrgAccount?.accountId || null,
  );
  const customerProfiles = profilesData?.customer_profiles || [];

  // Fetch all product categories (for link dialog)
  const { data: categoriesData } = useProductCategories(
    selectedOrgAccount?.accountId || null,
  );
  const allProductCategories = categoriesData?.categories || [];

  // UI state - MUST be declared before hooks that depend on them
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedProfile, setSelectedProfile] =
    useState<CustomerProfile | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(
    null,
  );

  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormDataState>({
    display_name: "",
    description: "",
  });

  // Side sheet state
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [contextMenuType, setContextMenuType] = useState<
    "customerProfile" | "productCategory" | null
  >(null);

  // Product category state (for side sheet)
  const [selectedProductCategory, setSelectedProductCategory] =
    useState<ProductCategory | null>(null);

  // Link dialog state
  const [isLinkCategoryDialogOpen, setIsLinkCategoryDialogOpen] =
    useState(false);
  const [selectedCategoryToLink, setSelectedCategoryToLink] =
    useState<ProductCategory | null>(null);
  const [isUnlinkDialogOpen, setIsUnlinkDialogOpen] = useState(false);

  // Fetch linked product categories for selected profile
  const { data: linkedCategoriesData, isLoading: isLoadingLinkedCategories } =
    useLinkedProductCategories(
      selectedOrgAccount?.accountId || null,
      selectedProfileId,
    );
  const linkedProductCategories = linkedCategoriesData?.categories || [];

  // React Query mutations
  const createProfileMutation = useCreateCustomerProfile();
  const updateProfileMutation = useUpdateCustomerProfile();
  const deleteProfileMutation = useDeleteCustomerProfile();
  const linkCategoryMutation = useLinkProductCategoryToProfile();
  const unlinkCategoryMutation = useUnlinkProductCategoryFromProfile();

  // Value propositions for selected product category
  const { data: valuePropositionsData, isLoading: isLoadingVPs } =
    useValuePropositions(
      selectedOrgAccount?.accountId || null,
      selectedProductCategory?.node_id || null,
    );
  const valuePropositions = valuePropositionsData?.value_propositions || [];

  // Unsaved changes detection
  const hasUnsavedChanges = useUnsavedChanges(
    selectedProfile,
    formData,
    isEditing,
  );

  // Handle navigation from other pages (e.g., Strategy page)
  useEffect(() => {
    const navState = location.state as {
      selectedProfileId?: string;
      autoEdit?: boolean;
    } | null;

    if (
      navState?.selectedProfileId &&
      navState?.autoEdit &&
      !hasProcessedNavigation.current
    ) {
      const profile = customerProfiles.find(
        (p) => p.node_id === navState.selectedProfileId,
      );
      if (profile) {
        hasProcessedNavigation.current = true;

        setSelectedProfileId(profile.node_id);
        setSelectedProfile(profile);
        setFormData({
          display_name: profile.display_name,
          description: profile.description,
        });
        setContextMenuType("customerProfile");
        setIsContextMenuOpen(true);
        setIsEditing(true);

        // Clear navigation state
        navigate(location.pathname, { replace: true, state: {} });
      }
    }
  }, [customerProfiles, location, navigate]);

  // Reset navigation processing flag when location changes
  useEffect(() => {
    return () => {
      hasProcessedNavigation.current = false;
    };
  }, [location.pathname]);

  const handleCreateClick = () => {
    setFormData({ display_name: "", description: "" });
    setIsCreateModalOpen(true);
  };

  const handleProfileClick = (profile: CustomerProfile) => {
    setSelectedProfileId(profile.node_id);
    setSelectedProfile(profile);
    setFormData({
      display_name: profile.display_name,
      description: profile.description,
    });
    setIsEditing(false);
    // Don't open side sheet here - only open when clicking nodes in React Flow

    // Prefetch linked categories for faster UX
    if (selectedOrgAccount?.accountId) {
      queryClient.prefetchQuery({
        queryKey: [
          "linkedProductCategories",
          selectedOrgAccount.accountId,
          profile.node_id,
        ],
        queryFn: async () => {
          const { customerProfileService } = await import(
            "@/services/customerProfileService"
          );
          // TODO: getLinkedProductCategories isn't on CustomerProfileService
          // today. Either the method was removed or this query needs to be
          // pointed elsewhere. Cast preserves the pre-typecheck behavior
          // until the right home is identified.
          return (
            customerProfileService as unknown as {
              getLinkedProductCategories: (
                accountId: string,
                profileId: string,
              ) => Promise<unknown>;
            }
          ).getLinkedProductCategories(
            selectedOrgAccount.accountId,
            profile.node_id,
          );
        },
      });
    }
  };

  const handleDeleteClick = (profile: CustomerProfile) => {
    setSelectedProfile(profile);
    setIsDeleteDialogOpen(true);
  };

  const handleCreate = async () => {
    if (!selectedOrgAccount?.accountId) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating customer profile...");
      setIsCreateModalOpen(false);

      await createProfileMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        profile: formData,
      });

      toast({
        title: "Success",
        description: "Customer profile created successfully",
      });
    } catch (error) {
      console.error("Failed to create customer profile:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create customer profile";

        if (status === 409) {
          toast({
            title: "Duplicate Profile",
            description: "A customer profile with this name already exists",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description:
              "You don't have permission to create customer profiles",
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
    if (!selectedOrgAccount?.accountId || !selectedProfile) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Updating customer profile...");
      setIsEditing(false);

      await updateProfileMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedProfile.node_id,
        updates: formData,
      });

      setSelectedProfile({
        ...selectedProfile,
        display_name: formData.display_name,
        description: formData.description,
      });

      toast({
        title: "Success",
        description: "Customer profile updated successfully",
      });
    } catch (error) {
      console.error("Failed to update customer profile:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update customer profile";
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
    if (!selectedOrgAccount?.accountId || !selectedProfile) return;

    try {
      startOperation("Deleting customer profile...");
      setIsDeleteDialogOpen(false);

      await deleteProfileMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedProfile.node_id,
      });

      setSelectedProfileId(null);
      setSelectedProfile(null);
      setIsContextMenuOpen(false);

      toast({
        title: "Success",
        description: "Customer profile deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete customer profile:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to delete customer profile";

        if (status === 400 && message.includes("dependencies")) {
          toast({
            title: "Cannot Delete",
            description:
              "This customer profile has dependencies. Remove them first.",
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

  // Handle opening link category dialog
  const handleOpenLinkCategoryDialog = () => {
    if (!selectedProfile) return;

    // Filter out already linked categories
    const linkedCategoryIds = new Set(
      linkedProductCategories.map((c) => c.node_id),
    );
    const availableCategories = allProductCategories.filter(
      (c) => !linkedCategoryIds.has(c.node_id),
    );

    if (availableCategories.length === 0) {
      toast({
        title: "No Categories Available",
        description:
          "All product categories are already linked to this profile.",
      });
      return;
    }

    setIsLinkCategoryDialogOpen(true);
  };

  // Handle linking product category
  const handleLinkProductCategory = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedProfile ||
      !selectedCategoryToLink
    )
      return;

    try {
      startOperation("Linking product category...");

      await linkCategoryMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        productCategoryId: selectedCategoryToLink.node_id,
        customerProfileId: selectedProfile.node_id,
      });

      toast({
        title: "Success",
        description: "Product category linked successfully",
      });

      setIsLinkCategoryDialogOpen(false);
      setSelectedCategoryToLink(null);
    } catch (error) {
      console.error("Failed to link product category:", error);
      toast({
        title: "Error",
        description: "Failed to link product category",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // Handle unlinking product category
  const handleUnlinkProductCategory = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedProfile ||
      !selectedProductCategory
    )
      return;

    try {
      startOperation("Unlinking product category...");
      setIsUnlinkDialogOpen(false);

      await unlinkCategoryMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        productCategoryId: selectedProductCategory.node_id,
        customerProfileId: selectedProfile.node_id,
      });

      toast({
        title: "Success",
        description: "Product category unlinked successfully",
      });

      setIsContextMenuOpen(false);
      setSelectedProductCategory(null);
    } catch (error) {
      console.error("Failed to unlink product category:", error);
      toast({
        title: "Error",
        description: "Failed to unlink product category",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // Handle navigating to Products page to edit product category
  const handleNavigateToProductCategoryEdit = () => {
    if (!selectedProductCategory) return;
    navigate("/knowledge/products", {
      state: {
        selectedCategoryId: selectedProductCategory.node_id,
        autoEdit: true,
      },
    });
  };

  // React Flow node types
  const nodeTypes = {
    customerProfileNode: CustomerProfileNode,
    productCategoryNode: ProductCategoryNode,
  };

  // Generate nodes for React Flow
  const generateNodes = (): Node[] => {
    if (!selectedProfile) return [];

    const nodes: Node[] = [];

    // Row 1: Selected Customer Profile
    nodes.push({
      id: selectedProfile.node_id,
      type: "customerProfileNode",
      position: {
        x: DIAGRAM_LAYOUT.PARENT_NODE_X,
        y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
      },
      data: {
        label: selectedProfile.display_name,
        isSelected: isContextMenuOpen && contextMenuType === "customerProfile",
        onAddCategory: handleOpenLinkCategoryDialog,
      },
    });

    // Row 2: Linked Product Categories
    linkedProductCategories.forEach((category, index) => {
      nodes.push({
        id: category.node_id,
        type: "productCategoryNode",
        position: {
          x: calculateChildNodeX(index, linkedProductCategories.length),
          y: calculateChildNodeY(),
        },
        data: {
          label: category.product_name,
          isSelected:
            isContextMenuOpen &&
            contextMenuType === "productCategory" &&
            selectedProductCategory?.node_id === category.node_id,
          strategyCount: category.strategy_count,
        },
      });
    });

    return nodes;
  };

  // Generate edges for React Flow
  const generateEdges = (): Edge[] => {
    if (!selectedProfile) return [];

    const edges: Edge[] = [];

    linkedProductCategories.forEach((category) => {
      edges.push({
        id: `${selectedProfile.node_id}-${category.node_id}`,
        source: selectedProfile.node_id,
        target: category.node_id,
        type: "smoothstep",
        style: DEFAULT_EDGE_STYLE,
        sourceHandle: "bottom",
        targetHandle: "top",
      });
    });

    return edges;
  };

  // Handle node clicks in React Flow
  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    if (node.type === "customerProfileNode") {
      const profile = customerProfiles.find((p) => p.node_id === node.id);
      if (profile) {
        setSelectedProfile(profile);
        setFormData({
          display_name: profile.display_name,
          description: profile.description,
        });
        setIsEditing(false);
        setContextMenuType("customerProfile");
        setIsContextMenuOpen(true);
      }
    } else if (node.type === "productCategoryNode") {
      const category = linkedProductCategories.find(
        (c) => c.node_id === node.id,
      );
      if (category) {
        setSelectedProductCategory(category);
        setContextMenuType("productCategory");
        setIsContextMenuOpen(true);
      }
    }
  };

  const nodes = useMemo(
    () => generateNodes(),
    [
      selectedProfile,
      linkedProductCategories,
      isContextMenuOpen,
      contextMenuType,
      selectedProductCategory,
    ],
  );
  const edges = useMemo(
    () => generateEdges(),
    [selectedProfile, linkedProductCategories],
  );

  return (
    <>
      {/* Customer Profiles Card with Horizontal Scroll */}
      <KnowledgeGraphCard
        title="Ideal Customer Profiles"
        icon={Users}
        tooltip="Create ideal customer profiles to help KEN-E understand the types of customers your business targets."
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
          items={customerProfiles}
          selectedId={selectedProfileId}
          onItemClick={handleProfileClick}
          isLoading={isLoading}
          emptyMessage="No customer profiles found."
          emptyMessageWithAction="Click '+' to add one."
          hasEditAccess={hasEditAccess}
          renderItem={(profile, isSelected) => (
            <HorizontalScrollItem
              label={profile.display_name}
              sublabel="Ideal Customer Profile"
              icon={Users}
              bgColor="bg-brand-light-blue bg-opacity-30"
              iconBgColor="bg-brand-light-blue"
              isSelected={isSelected}
              onClick={() => {}}
            />
          )}
        />
      </KnowledgeGraphCard>

      {/* Targeted Product Categories Visualization Card */}
      <div className="mt-6">
        <GraphVisualizationCard
          title="Targeted Product Categories"
          icon={Users}
          tooltip="View which product categories this ideal customer profile is interested in."
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeClick}
          isLoading={isLoadingLinkedCategories}
          showEmpty={!selectedProfileId}
          emptyMessage="Select a customer profile to view targeted product categories."
        />
      </div>

      {/* Create Profile Modal */}
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Customer Profile</DialogTitle>
            <DialogDescription>
              Add a new ideal customer profile.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-display-name">Name</Label>
              <Input
                id="create-display-name"
                value={formData.display_name}
                onChange={(e) =>
                  setFormData({ ...formData, display_name: e.target.value })
                }
                placeholder="e.g., Small Business Sam"
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
                placeholder="Describe this customer profile..."
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
              disabled={!formData.display_name.trim()}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Profile Confirmation */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Customer Profile?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedProfile?.display_name}
              "? This action cannot be undone.
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

      {/* Link Product Category Dialog */}
      <Dialog
        open={isLinkCategoryDialogOpen}
        onOpenChange={setIsLinkCategoryDialogOpen}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Link Product Category</DialogTitle>
            <DialogDescription>
              Select which product category this customer profile is interested
              in.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {allProductCategories.filter(
              (c) =>
                !linkedProductCategories.some((lc) => lc.node_id === c.node_id),
            ).length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No available product categories to link. All categories are
                already linked.
              </p>
            ) : (
              <>
                <Label>Select Product Category</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={selectedCategoryToLink?.node_id || ""}
                  onChange={(e) => {
                    const category = allProductCategories.find(
                      (c) => c.node_id === e.target.value,
                    );
                    setSelectedCategoryToLink(category || null);
                  }}
                >
                  <option value="">-- Select Product Category --</option>
                  {allProductCategories
                    .filter(
                      (c) =>
                        !linkedProductCategories.some(
                          (lc) => lc.node_id === c.node_id,
                        ),
                    )
                    .map((category) => (
                      <option key={category.node_id} value={category.node_id}>
                        {category.product_name}
                      </option>
                    ))}
                </select>
              </>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsLinkCategoryDialogOpen(false);
                setSelectedCategoryToLink(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleLinkProductCategory}
              disabled={
                !selectedCategoryToLink || linkCategoryMutation.isPending
              }
            >
              {linkCategoryMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Linking...
                </>
              ) : (
                "Link Product Category"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unlink Product Category Confirmation */}
      <AlertDialog
        open={isUnlinkDialogOpen}
        onOpenChange={setIsUnlinkDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unlink Product Category?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to unlink "
              {selectedProductCategory?.product_name}"? This will also delete
              all associated marketing strategies for this customer
              profile/category pair. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleUnlinkProductCategory}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Unlink and Delete Strategies
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Context Menu Side Sheet */}
      <KnowledgeGraphSideSheet
        open={isContextMenuOpen}
        onOpenChange={(open) => {
          if (!open && isEditing && hasUnsavedChanges) {
            return;
          }
          setIsContextMenuOpen(open);
          if (!open) {
            setIsEditing(false);
            setSelectedProductCategory(null);
          }
        }}
        title={
          contextMenuType === "customerProfile"
            ? "Ideal Customer Profile"
            : "Product Category"
        }
        icon={contextMenuType === "customerProfile" ? Users : Blocks}
        isEditing={isEditing && contextMenuType === "customerProfile"}
        onEdit={
          contextMenuType === "customerProfile"
            ? () => setIsEditing(true)
            : handleNavigateToProductCategoryEdit
        }
        onSave={contextMenuType === "customerProfile" ? handleSave : undefined}
        onCancel={() => {
          setIsEditing(false);
          if (selectedProfile) {
            setFormData({
              display_name: selectedProfile.display_name,
              description: selectedProfile.description,
            });
          }
        }}
        onDelete={
          contextMenuType === "customerProfile"
            ? () => {
                setIsContextMenuOpen(false);
                if (selectedProfile) {
                  handleDeleteClick(selectedProfile);
                }
              }
            : () => setIsUnlinkDialogOpen(true)
        }
        deleteButtonLabel={
          contextMenuType === "productCategory" ? "Unlink" : undefined
        }
        hasEditAccess={hasEditAccess}
        preventClose={isEditing && hasUnsavedChanges}
        modal={false}
      >
        {contextMenuType === "customerProfile" ? (
          <>
            {isEditing ? (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="context-edit-name">Name:</Label>
                  <Input
                    id="context-edit-name"
                    value={formData.display_name}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        display_name: e.target.value,
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
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="font-semibold">Name:</p>
                  <p>{selectedProfile?.display_name}</p>
                </div>
                <div>
                  <p className="font-semibold">Description:</p>
                  <p className="text-sm text-[var(--color-text-tertiary)]">
                    {selectedProfile?.description}
                  </p>
                </div>
              </div>
            )}

            {/* News Monitoring Keywords Section */}
            {selectedProfile && (
              <CustomerKeywordsSection
                customerProfileNodeId={selectedProfile.node_id}
                hasEditAccess={hasEditAccess}
              />
            )}
          </>
        ) : contextMenuType === "productCategory" ? (
          <>
            <div className="space-y-3">
              <div>
                <p className="font-semibold">Name:</p>
                <p>{selectedProductCategory?.product_name}</p>
              </div>
              <div>
                <p className="font-semibold">Description:</p>
                <p className="text-sm text-[var(--color-text-tertiary)]">
                  {selectedProductCategory?.description}
                </p>
              </div>
              {selectedProductCategory?.strategy_count !== undefined && (
                <div>
                  <p className="font-semibold">Strategies:</p>
                  <p className="text-sm text-[var(--color-text-tertiary)]">
                    {selectedProductCategory.strategy_count} of 5 strategies
                    defined
                  </p>
                </div>
              )}
            </div>

            {/* Value Propositions Section */}
            {selectedProductCategory && (
              <div className="border-t border-[var(--color-border-default)] pt-4 mt-4">
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">
                  Value Propositions
                </h3>
                {isLoadingVPs ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-disabled)]" />
                  </div>
                ) : valuePropositions.length > 0 ? (
                  <div className="space-y-2">
                    {valuePropositions.map((vp) => (
                      <div
                        key={vp.node_id}
                        className="p-2 bg-[var(--color-bg-secondary)] rounded"
                      >
                        <p className="font-medium text-sm">{vp.display_name}</p>
                        <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                          {vp.description}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No value propositions defined for this category
                  </p>
                )}
              </div>
            )}
          </>
        ) : null}
      </KnowledgeGraphSideSheet>
    </>
  );
};
