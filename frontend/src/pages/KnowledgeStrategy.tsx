import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { Node, Edge } from "reactflow";
import { ArrowLeft, Blocks, Filter, Users } from "lucide-react";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import { useToast } from "@/hooks/use-toast";
import {
  useRollupStrategies,
  useIndividualStrategies,
  useUpdateStrategy,
  useDeleteStrategy,
} from "@/queries/marketing";
import { useProductCategories } from "@/queries/products";
import {
  useCustomerProfiles,
  useLinkedProductCategories,
} from "@/queries/customerProfiles";
import { MarketingFunnelVisualization } from "@/components/marketing/MarketingFunnelVisualization";
import {
  CustomerProfileNode,
  IndividualStrategyNode,
} from "@/components/marketing/StrategyFlowNodes";
import { CategoryNode } from "@/components/products/ProductFlowNodes";
import {
  KnowledgeGraphCard,
  HorizontalScrollList,
  HorizontalScrollItem,
  GraphVisualizationCard,
  KnowledgeGraphSideSheet,
  DIAGRAM_LAYOUT,
  DEFAULT_EDGE_STYLE,
} from "@/components/knowledge-graph";
import type { ProductCategory } from "@/services/productCategoryService";
import type { CustomerProfile } from "@/services/customerProfileService";
import type {
  MarketingStrategy,
  StrategyType,
} from "@/services/marketingStrategyService";
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

type SelectedNode =
  | { type: "category"; data: ProductCategory }
  | { type: "profile"; data: CustomerProfile }
  | { type: "strategy"; data: MarketingStrategy };

const NODE_TYPE_PREFIX_MAP: Record<string, string> = {
  problemaware_: "ProblemAwarenessStrategy",
  brandaware_: "BrandAwarenessStrategy",
  consideration_: "ConsiderationStrategy",
  conversion_: "ConversionStrategy",
  loyalty_: "LoyaltyStrategy",
};

const STRATEGY_PREFIX_TO_API_TYPE: Record<string, StrategyType> = {
  problemaware_: "problem-awareness",
  brandaware_: "brand-awareness",
  consideration_: "consideration",
  conversion_: "conversion",
  loyalty_: "loyalty",
};

export default function KnowledgeStrategy() {
  const navigate = useNavigate();
  const { selectedOrgAccount, user, isSuperAdmin } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();

  // Permissions
  const hasEditAccess = useMemo(() => {
    if (!selectedOrgAccount) return false;
    if (isSuperAdmin) return true;

    const accountId = selectedOrgAccount.accountId;
    const orgId = selectedOrgAccount.orgId;

    const orgRole = user?.permissions?.organizations?.[orgId];
    if (orgRole === "admin" || orgRole === "owner") return true;

    const accountPerm =
      user?.permissions?.account_permissions?.[accountId] ||
      user?.permissions?.accounts?.[accountId];
    return accountPerm === "edit" || accountPerm === "admin";
  }, [selectedOrgAccount, user, isSuperAdmin]);

  // State
  const [selectedStrategyMode, setSelectedStrategyMode] =
    useState<StrategyType>("problem-awareness");
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  );
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(
    null,
  );
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [isSideSheetOpen, setIsSideSheetOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedDescription, setEditedDescription] = useState("");
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  // Data fetching
  const { data: rollupStrategiesData, isLoading: isLoadingRollup } =
    useRollupStrategies(selectedOrgAccount?.accountId || null);

  const { data: categoriesData, isLoading: isLoadingCategories } =
    useProductCategories(selectedOrgAccount?.accountId || null);
  const categories = categoriesData?.categories || [];

  const { data: profilesData } = useCustomerProfiles(
    selectedOrgAccount?.accountId || null,
  );
  const allProfiles = profilesData?.customer_profiles || [];

  const { data: linkedCategoriesData } = useLinkedProductCategories(
    selectedOrgAccount?.accountId || null,
    selectedProfileId,
  );
  const linkedCategories = linkedCategoriesData?.categories || [];

  const { data: individualStrategies = [], isLoading: isLoadingStrategies } =
    useIndividualStrategies(
      selectedOrgAccount?.accountId || null,
      selectedCategoryId,
      selectedProfileId,
    );

  // Mutations
  const updateRollupMutation = useUpdateStrategy(selectedStrategyMode);

  const getStrategyTypeForNode = (
    strategy: MarketingStrategy,
  ): StrategyType | null => {
    const entry = Object.entries(STRATEGY_PREFIX_TO_API_TYPE).find(([prefix]) =>
      strategy.node_id.startsWith(prefix),
    );
    return entry?.[1] || null;
  };

  const updateIndividualMutation = useUpdateStrategy(
    selectedNode?.type === "strategy"
      ? getStrategyTypeForNode(selectedNode.data) || "problem-awareness"
      : "problem-awareness",
  );

  const deleteStrategyMutation = useDeleteStrategy(
    selectedNode?.type === "strategy"
      ? getStrategyTypeForNode(selectedNode.data) || "problem-awareness"
      : "problem-awareness",
  );

  // Filter profiles that are linked to the selected category
  const profilesForCategory = useMemo(() => {
    if (!selectedCategoryId) return [];
    return allProfiles.filter((profile) =>
      linkedCategories.some((cat) => cat.node_id === selectedCategoryId),
    );
  }, [allProfiles, selectedCategoryId, linkedCategories]);

  // React Flow setup
  const nodeTypes = {
    categoryNode: CategoryNode,
    customerProfileNode: CustomerProfileNode,
    individualStrategyNode: IndividualStrategyNode,
  };

  const generateNodes = (): Node[] => {
    const nodes: Node[] = [];

    if (!selectedCategoryId) return nodes;

    const selectedCategory = categories.find(
      (c) => c.node_id === selectedCategoryId,
    );
    if (!selectedCategory) return nodes;

    // Level 1: Product Category
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
          selectedCategoryId === selectedCategory.node_id && !selectedProfileId,
      },
    });

    // Level 2: Customer Profiles
    const profiles = profilesForCategory;
    const totalWidth =
      profiles.length * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH -
      DIAGRAM_LAYOUT.HORIZONTAL_GAP;
    const startX = DIAGRAM_LAYOUT.PARENT_NODE_X - totalWidth / 2;

    profiles.forEach((profile, index) => {
      nodes.push({
        id: profile.node_id,
        type: "customerProfileNode",
        position: {
          x: startX + index * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: profile.display_name,
          isSelected: selectedProfileId === profile.node_id,
        },
      });
    });

    // Level 3: Individual Strategies
    if (selectedProfileId && individualStrategies.length > 0) {
      const strategyWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
      const strategyTotalWidth =
        individualStrategies.length * strategyWidth -
        DIAGRAM_LAYOUT.HORIZONTAL_GAP;
      const strategyStartX =
        DIAGRAM_LAYOUT.PARENT_NODE_X - strategyTotalWidth / 2;
      const strategyY =
        DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING * 2;

      individualStrategies.forEach((strategy, index) => {
        nodes.push({
          id: strategy.node_id,
          type: "individualStrategyNode",
          position: {
            x: strategyStartX + index * strategyWidth,
            y: strategyY,
          },
          data: {
            strategyType: getNodeTypeFromId(strategy.node_id),
            isSelected:
              selectedNode?.type === "strategy" &&
              selectedNode.data.node_id === strategy.node_id,
          },
        });
      });
    }

    return nodes;
  };

  const getNodeTypeFromId = (nodeId: string): string => {
    const entry = Object.entries(NODE_TYPE_PREFIX_MAP).find(([prefix]) =>
      nodeId.startsWith(prefix),
    );
    return entry?.[1] || "ProblemAwarenessStrategy";
  };

  const generateEdges = (): Edge[] => {
    const edges: Edge[] = [];

    if (!selectedCategoryId) return edges;

    const selectedCategory = categories.find(
      (c) => c.node_id === selectedCategoryId,
    );
    if (!selectedCategory) return edges;

    // Category → Profiles
    profilesForCategory.forEach((profile) => {
      edges.push({
        id: `${selectedCategory.node_id}-${profile.node_id}`,
        source: selectedCategory.node_id,
        target: profile.node_id,
        type: "smoothstep",
        style: DEFAULT_EDGE_STYLE,
        sourceHandle: "bottom",
        targetHandle: "top",
      });
    });

    // Profile → Strategies
    if (selectedProfileId) {
      individualStrategies.forEach((strategy) => {
        edges.push({
          id: `${selectedProfileId}-${strategy.node_id}`,
          source: selectedProfileId,
          target: strategy.node_id,
          type: "smoothstep",
          style: DEFAULT_EDGE_STYLE,
          sourceHandle: "bottom",
          targetHandle: "top",
        });
      });
    }

    return edges;
  };

  const nodes = useMemo(
    () => generateNodes(),
    [
      categories,
      selectedCategoryId,
      profilesForCategory,
      selectedProfileId,
      individualStrategies,
      selectedNode,
    ],
  );

  const edges = useMemo(
    () => generateEdges(),
    [
      categories,
      selectedCategoryId,
      profilesForCategory,
      selectedProfileId,
      individualStrategies,
    ],
  );

  // Handlers
  const handleSaveRollupDescription = async (
    strategyMode: StrategyType,
    description: string,
  ) => {
    if (!selectedOrgAccount?.accountId || !rollupStrategiesData) return;

    const strategyMap: Record<StrategyType, MarketingStrategy | null> = {
      "problem-awareness": rollupStrategiesData.problemAwareness,
      "brand-awareness": rollupStrategiesData.brandAwareness,
      consideration: rollupStrategiesData.consideration,
      conversion: rollupStrategiesData.conversion,
      loyalty: rollupStrategiesData.loyalty,
    };

    const strategy = strategyMap[strategyMode];
    if (!strategy) return;

    await updateRollupMutation.mutateAsync({
      accountId: selectedOrgAccount.accountId,
      nodeId: strategy.node_id,
      updates: { description },
    });
  };

  const handleCategoryClick = (category: ProductCategory) => {
    setSelectedCategoryId(category.node_id);
    setSelectedProfileId(null);
    setSelectedNode(null);
    setIsSideSheetOpen(false);
  };

  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    if (node.type === "categoryNode") {
      const category = categories.find((c) => c.node_id === node.id);
      if (!category) return;

      setSelectedNode({ type: "category", data: category });
      setIsSideSheetOpen(true);
    } else if (node.type === "customerProfileNode") {
      const profile = allProfiles.find((p) => p.node_id === node.id);
      if (!profile) return;

      setSelectedProfileId(node.id);
      setSelectedNode({ type: "profile", data: profile });
      setIsSideSheetOpen(true);
    } else if (node.type === "individualStrategyNode") {
      const strategy = individualStrategies.find((s) => s.node_id === node.id);
      if (!strategy) return;

      setSelectedNode({ type: "strategy", data: strategy });
      setEditedDescription(strategy.description);
      setIsSideSheetOpen(true);
    }
  };

  const handleSaveIndividualStrategy = async () => {
    if (!selectedOrgAccount?.accountId || selectedNode?.type !== "strategy")
      return;

    try {
      startOperation("Updating strategy...");

      await updateIndividualMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedNode.data.node_id,
        updates: { description: editedDescription },
      });

      setIsEditing(false);
      toast({
        title: "Success",
        description: "Strategy updated successfully",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update strategy",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  const handleDeleteStrategy = async () => {
    if (!selectedOrgAccount?.accountId || selectedNode?.type !== "strategy")
      return;

    try {
      startOperation("Deleting strategy...");
      setIsDeleteDialogOpen(false);

      await deleteStrategyMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedNode.data.node_id,
      });

      setIsSideSheetOpen(false);
      setSelectedNode(null);

      toast({
        title: "Success",
        description: "Strategy deleted successfully",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete strategy",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  const getCategoryName = (categoryId: string | undefined): string => {
    if (!categoryId) return "Unknown Category";
    const category = categories.find((c) => c.node_id === categoryId);
    return category?.product_name || "Unknown Category";
  };

  const getProfileName = (profileId: string | undefined): string => {
    if (!profileId) return "Unknown Profile";
    const profile = allProfiles.find((p) => p.node_id === profileId);
    return profile?.display_name || "Unknown Profile";
  };

  return (
    <Layout pageTitle="Marketing Strategy" maxWidth={false}>
      <div className="space-y-6">
        {/* Back Button */}
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/knowledge")}
            className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal mr-auto"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Knowledge Base
          </Button>
        </div>

        {/* Rollup Strategy Funnel */}
        <MarketingFunnelVisualization
          strategies={rollupStrategiesData || null}
          isLoading={isLoadingRollup}
          selectedStrategyMode={selectedStrategyMode}
          onStrategyModeChange={setSelectedStrategyMode}
          onSaveDescription={handleSaveRollupDescription}
          hasEditAccess={hasEditAccess}
          isSaving={updateRollupMutation.isPending}
        />

        {/* Product Categories Slider */}
        <KnowledgeGraphCard
          title="Product Categories"
          icon={Blocks}
          tooltip="Select a product category to view marketing strategies for customer profiles within that category."
        >
          <HorizontalScrollList
            items={categories}
            selectedId={selectedCategoryId}
            onItemClick={handleCategoryClick}
            isLoading={isLoadingCategories}
            emptyMessage="No product categories found."
            hasEditAccess={false}
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

        {/* React Flow Diagram */}
        <GraphVisualizationCard
          title="Targeted Marketing Strategies"
          icon={Filter}
          tooltip="View and edit individual marketing strategies for each customer profile within the selected product category."
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          isLoading={isLoadingStrategies}
          showEmpty={!selectedCategoryId}
          emptyMessage="Select a product category to view strategies."
        />

        {/* Side Sheet */}
        <KnowledgeGraphSideSheet
          open={isSideSheetOpen}
          onOpenChange={setIsSideSheetOpen}
          title={
            selectedNode?.type === "category"
              ? selectedNode.data.product_name
              : selectedNode?.type === "profile"
                ? selectedNode.data.display_name
                : "Strategy Details"
          }
          icon={
            selectedNode?.type === "category"
              ? Blocks
              : selectedNode?.type === "profile"
                ? Users
                : Package
          }
          isEditing={isEditing && selectedNode?.type === "strategy"}
          onEdit={
            selectedNode?.type === "category"
              ? () =>
                  navigate("/knowledge/products", {
                    state: {
                      selectedCategoryId: selectedNode.data.node_id,
                      autoEdit: true,
                    },
                  })
              : selectedNode?.type === "profile"
                ? () =>
                    navigate("/knowledge/customers", {
                      state: {
                        selectedProfileId: selectedNode.data.node_id,
                        autoEdit: true,
                      },
                    })
                : () => setIsEditing(true)
          }
          onSave={
            selectedNode?.type === "strategy"
              ? handleSaveIndividualStrategy
              : undefined
          }
          onCancel={
            selectedNode?.type === "strategy"
              ? () => {
                  setIsEditing(false);
                  setEditedDescription(selectedNode.data.description);
                }
              : undefined
          }
          onDelete={
            selectedNode?.type === "strategy"
              ? () => setIsDeleteDialogOpen(true)
              : undefined
          }
          hasEditAccess={hasEditAccess}
          editButtonLabel={
            selectedNode?.type === "category" ||
            selectedNode?.type === "profile"
              ? "Edit on Details Page"
              : undefined
          }
          modal={false}
        >
          {selectedNode?.type === "category" ? (
            <div className="space-y-3">
              <div>
                <p className="font-semibold">Category Name:</p>
                <p>{selectedNode.data.product_name}</p>
              </div>
              <div>
                <p className="font-semibold">Description:</p>
                <p className="text-sm text-dashboard-gray-600">
                  {selectedNode.data.description}
                </p>
              </div>
              <div className="rounded-md bg-muted p-3 mt-4">
                <p className="text-xs text-muted-foreground">
                  Click "Edit on Details Page" to manage this category on the
                  Products page.
                </p>
              </div>
            </div>
          ) : selectedNode?.type === "profile" ? (
            <div className="space-y-3">
              <div>
                <p className="font-semibold">Profile Name:</p>
                <p>{selectedNode.data.display_name}</p>
              </div>
              <div>
                <p className="font-semibold">Narrative:</p>
                <p className="text-sm text-dashboard-gray-600">
                  {selectedNode.data.narrative || "No narrative provided."}
                </p>
              </div>
              {linkedCategories.length > 0 && (
                <div>
                  <p className="font-semibold">Linked Product Categories:</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {linkedCategories.map((cat) => (
                      <Badge key={cat.node_id} variant="secondary">
                        {cat.product_name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              <div className="rounded-md bg-muted p-3 mt-4">
                <p className="text-xs text-muted-foreground">
                  Click "Edit on Details Page" to manage this customer profile
                  on the Customers page.
                </p>
              </div>
            </div>
          ) : selectedNode?.type === "strategy" ? (
            isEditing ? (
              <div className="space-y-4">
                <div>
                  <Label>Description:</Label>
                  <Textarea
                    value={editedDescription}
                    onChange={(e) => setEditedDescription(e.target.value)}
                    rows={8}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="font-semibold">Description:</p>
                  <p className="text-sm text-dashboard-gray-600">
                    {selectedNode.data.description}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">Product Category:</p>
                  <p>
                    {getCategoryName(
                      selectedNode.data.product_category_node_id,
                    )}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">Customer Profile:</p>
                  <p>
                    {getProfileName(selectedNode.data.customer_profile_node_id)}
                  </p>
                </div>
              </div>
            )
          ) : null}
        </KnowledgeGraphSideSheet>

        {/* Delete Confirmation Dialog */}
        <AlertDialog
          open={isDeleteDialogOpen}
          onOpenChange={setIsDeleteDialogOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Strategy</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete this strategy? This action
                cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteStrategy}
                className="bg-brand-red hover:bg-brand-red/90"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </Layout>
  );
}
