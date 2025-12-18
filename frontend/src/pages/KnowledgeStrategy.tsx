import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { Node, Edge } from "reactflow";
import { ArrowLeft, Blocks, Filter, Users, Loader2 } from "lucide-react";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import { useToast } from "@/hooks/use-toast";
import {
  useRollupStrategies,
  useIndividualStrategies,
  useUpdateStrategy,
  useDeleteStrategy,
} from "@/queries/marketing";
import {
  useProductCategories,
  useLinkedCustomerProfilesForCategory,
} from "@/queries/products";
import {
  useCustomerProfiles,
  useLinkedProductCategories,
  useLinkProductCategoryToProfile,
  useUnlinkProductCategoryFromProfile,
} from "@/queries/customerProfiles";
import { MarketingFunnelVisualization } from "@/components/marketing/MarketingFunnelVisualization";
import { MiniMarketingFunnel } from "@/components/marketing/MiniMarketingFunnel";
import {
  CustomerProfileNode,
  IndividualStrategyNode,
  StrategyBundleNode,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type SelectedNode =
  | { type: "category"; data: ProductCategory }
  | { type: "profile"; data: CustomerProfile }
  | { type: "strategy"; data: MarketingStrategy }
  | {
      type: "strategyBundle";
      data: {
        categoryId: string;
        profileId: string;
        strategies: MarketingStrategy[];
      };
    };

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
  const [isLinkProfileDialogOpen, setIsLinkProfileDialogOpen] = useState(false);
  const [selectedProfileToLink, setSelectedProfileToLink] =
    useState<CustomerProfile | null>(null);
  const [isUnlinkProfileDialogOpen, setIsUnlinkProfileDialogOpen] =
    useState(false);
  const [editedStrategies, setEditedStrategies] = useState<
    Record<StrategyType, string>
  >({
    "problem-awareness": "",
    "brand-awareness": "",
    consideration: "",
    conversion: "",
    loyalty: "",
  });

  // Data fetching
  const { data: rollupStrategiesData, isLoading: isLoadingRollup } =
    useRollupStrategies(selectedOrgAccount?.accountId || null);

  const { data: categoriesData, isLoading: isLoadingCategories } =
    useProductCategories(selectedOrgAccount?.accountId || null);
  const categories = categoriesData?.categories || [];

  const { data: linkedCategoriesData } = useLinkedProductCategories(
    selectedOrgAccount?.accountId || null,
    selectedProfileId,
  );
  const linkedCategories = linkedCategoriesData?.categories || [];

  // Fetch customer profiles linked to the selected category via IS_MARKETED_TO
  const { data: linkedProfilesData } = useLinkedCustomerProfilesForCategory(
    selectedOrgAccount?.accountId || null,
    selectedCategoryId,
  );
  const profilesForCategory = linkedProfilesData?.customer_profiles || [];

  // Fetch all customer profiles (for link dialog)
  const { data: allProfilesData } = useCustomerProfiles(
    selectedOrgAccount?.accountId || null,
  );
  const allProfiles = allProfilesData?.customer_profiles || [];

  // Fetch strategies for selected category (all profiles, for bundle nodes)
  const { data: individualStrategies = [], isLoading: isLoadingStrategies } =
    useIndividualStrategies(
      selectedOrgAccount?.accountId || null,
      selectedCategoryId,
      null, // Fetch for all profiles, not just selected one
    );

  // Mutations
  const updateRollupMutation = useUpdateStrategy(selectedStrategyMode);
  const linkProfileMutation = useLinkProductCategoryToProfile();
  const unlinkProfileMutation = useUnlinkProductCategoryFromProfile();

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

  // Handlers
  const handleOpenLinkProfileDialog = () => {
    if (!selectedCategoryId) return;

    // Filter out already linked profiles
    const linkedProfileIds = new Set(profilesForCategory.map((p) => p.node_id));
    const availableProfiles = allProfiles.filter(
      (p) => !linkedProfileIds.has(p.node_id),
    );

    if (availableProfiles.length === 0) {
      toast({
        title: "No Profiles Available",
        description:
          "All customer profiles are already linked to this category.",
      });
      return;
    }

    setIsLinkProfileDialogOpen(true);
  };

  const handleLinkCustomerProfile = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedCategoryId ||
      !selectedProfileToLink
    )
      return;

    try {
      startOperation("Linking customer profile...");

      await linkProfileMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        productCategoryId: selectedCategoryId,
        customerProfileId: selectedProfileToLink.node_id,
      });

      toast({
        title: "Success",
        description: "Customer profile linked successfully",
      });

      setIsLinkProfileDialogOpen(false);
      setSelectedProfileToLink(null);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to link customer profile",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  const handleUnlinkCustomerProfile = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedCategoryId ||
      selectedNode?.type !== "profile"
    )
      return;

    try {
      startOperation("Unlinking customer profile...");
      setIsUnlinkProfileDialogOpen(false);

      await unlinkProfileMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        productCategoryId: selectedCategoryId,
        customerProfileId: selectedNode.data.node_id,
      });

      toast({
        title: "Success",
        description: "Customer profile unlinked successfully",
      });

      setIsSideSheetOpen(false);
      setSelectedNode(null);
      setSelectedProfileId(null);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to unlink customer profile",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // React Flow setup
  const nodeTypes = {
    categoryNode: CategoryNode,
    customerProfileNode: CustomerProfileNode,
    individualStrategyNode: IndividualStrategyNode,
    strategyBundleNode: StrategyBundleNode,
  };

  const generateNodes = (): Node[] => {
    const nodes: Node[] = [];

    if (!selectedCategoryId) return nodes;

    console.log("=== generateNodes Debug ===");
    console.log("selectedCategoryId:", selectedCategoryId);
    console.log("individualStrategies:", individualStrategies);
    console.log("Total strategies fetched:", individualStrategies.length);

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
          selectedNode?.type === "category" &&
          selectedNode.data.node_id === selectedCategory.node_id,
        onAddProduct: handleOpenLinkProfileDialog,
      },
    });

    // Level 2: Customer Profiles
    const profiles = profilesForCategory;
    const totalWidth =
      profiles.length * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH -
      DIAGRAM_LAYOUT.HORIZONTAL_GAP;
    const startX = DIAGRAM_LAYOUT.PARENT_NODE_X - totalWidth / 2;

    profiles.forEach((profile, index) => {
      // Level 3: Strategy Bundle for this profile (if strategies exist)
      // Support both property-based and node_id-based matching for backward compatibility
      const profileStrategies = individualStrategies.filter((s) => {
        // Try property first (new nodes)
        if (s.customer_profile_node_id === profile.node_id) return true;
        // Fallback to parsing node_id (old nodes without properties)
        // Format: {prefix}_{categoryId}_{profileId}
        return s.node_id.endsWith(`_${profile.node_id}`);
      });

      console.log(
        `Profile: ${profile.display_name} (${profile.node_id}), Strategies:`,
        profileStrategies,
      );

      const hasStrategies = profileStrategies.length > 0;

      nodes.push({
        id: profile.node_id,
        type: "customerProfileNode",
        position: {
          x: startX + index * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: profile.display_name,
          isSelected:
            selectedNode?.type === "profile" &&
            selectedNode.data.node_id === profile.node_id,
          hasStrategies, // NEW: pass this to show bottom handle
        },
      });

      if (hasStrategies) {
        console.log(`Creating bundle for ${profile.display_name}`);
        nodes.push({
          id: `bundle_${selectedCategoryId}_${profile.node_id}`,
          type: "strategyBundleNode",
          position: {
            x: startX + index * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH,
            y:
              DIAGRAM_LAYOUT.PARENT_NODE_Y +
              DIAGRAM_LAYOUT.VERTICAL_SPACING * 2,
          },
          data: {
            label: "5 Funnel Stages",
            isSelected:
              selectedNode?.type === "strategyBundle" &&
              selectedNode.data.profileId === profile.node_id,
          },
        });
      }
    });

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

      // Profile → Strategy Bundle (if this profile has strategies)
      const profileStrategies = individualStrategies.filter((s) => {
        if (s.customer_profile_node_id === profile.node_id) return true;
        return s.node_id.endsWith(`_${profile.node_id}`);
      });

      if (profileStrategies.length > 0) {
        edges.push({
          id: `${profile.node_id}-bundle`,
          source: profile.node_id,
          target: `bundle_${selectedCategoryId}_${profile.node_id}`,
          type: "smoothstep",
          style: DEFAULT_EDGE_STYLE,
          sourceHandle: "bottom",
          targetHandle: "top",
        });
      }
    });

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
      const profile = profilesForCategory.find((p) => p.node_id === node.id);
      if (!profile) return;

      setSelectedProfileId(node.id);
      setSelectedNode({ type: "profile", data: profile });
      setIsSideSheetOpen(true);
    } else if (node.type === "strategyBundleNode") {
      if (!selectedCategoryId) return;

      // Extract profileId from bundle node ID: bundle_{categoryId}_{profileId}
      const profileId = node.id.split("_").slice(2).join("_");

      // Get strategies for this specific profile (support old nodes without properties)
      const bundleStrategies = individualStrategies.filter((s) => {
        if (s.customer_profile_node_id === profileId) return true;
        return s.node_id.endsWith(`_${profileId}`);
      });

      // Initialize edited strategies from current data
      const initialStrategies: Record<StrategyType, string> = {
        "problem-awareness": "",
        "brand-awareness": "",
        consideration: "",
        conversion: "",
        loyalty: "",
      };

      bundleStrategies.forEach((strategy) => {
        if (strategy.node_id.startsWith("problemaware_")) {
          initialStrategies["problem-awareness"] = strategy.description;
        } else if (strategy.node_id.startsWith("brandaware_")) {
          initialStrategies["brand-awareness"] = strategy.description;
        } else if (strategy.node_id.startsWith("consideration_")) {
          initialStrategies.consideration = strategy.description;
        } else if (strategy.node_id.startsWith("conversion_")) {
          initialStrategies.conversion = strategy.description;
        } else if (strategy.node_id.startsWith("loyalty_")) {
          initialStrategies.loyalty = strategy.description;
        }
      });

      setEditedStrategies(initialStrategies);
      setSelectedProfileId(profileId);
      setSelectedNode({
        type: "strategyBundle",
        data: {
          categoryId: selectedCategoryId,
          profileId: profileId,
          strategies: bundleStrategies,
        },
      });
      setIsSideSheetOpen(true);
    } else if (node.type === "individualStrategyNode") {
      const strategy = individualStrategies.find((s) => s.node_id === node.id);
      if (!strategy) return;

      setSelectedNode({ type: "strategy", data: strategy });
      setEditedDescription(strategy.description);
      setIsSideSheetOpen(true);
    }
  };

  const handleSaveStrategyBundle = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      selectedNode?.type !== "strategyBundle"
    )
      return;

    try {
      startOperation("Updating strategies...");

      // Save all strategies that have been modified
      const savePromises = selectedNode.data.strategies.map(
        async (strategy) => {
          const strategyType = getStrategyTypeForNode(strategy);
          if (!strategyType) return;

          const newDescription = editedStrategies[strategyType];
          // Only update if description has changed
          if (newDescription !== strategy.description) {
            return updateIndividualMutation.mutateAsync({
              accountId: selectedOrgAccount.accountId,
              nodeId: strategy.node_id,
              updates: { description: newDescription },
            });
          }
        },
      );

      await Promise.all(savePromises);

      setIsEditing(false);
      toast({
        title: "Success",
        description: "Strategies updated successfully",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update strategies",
        variant: "destructive",
      });
    } finally {
      endOperation();
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
    const profile = profilesForCategory.find((p) => p.node_id === profileId);
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

        {/* Product Categories and Targeted Strategies - Grouped */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-5 w-5" />
              Targeted Marketing Strategies
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="max-w-xs">
                      Select a product category to view targeted customer
                      profiles and their individual marketing strategies across
                      the funnel stages.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
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
              title="Targeted Customer Profiles"
              icon={Users}
              tooltip="Customer profiles who are targeted with messaging about the selected product category. Click a profile to view and edit their individual marketing strategies."
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={handleNodeClick}
              isLoading={isLoadingStrategies}
              showEmpty={!selectedCategoryId}
              emptyMessage="Select a product category to view strategies."
            />
          </CardContent>
        </Card>

        {/* Side Sheet */}
        <KnowledgeGraphSideSheet
          open={isSideSheetOpen}
          onOpenChange={setIsSideSheetOpen}
          title={
            selectedNode?.type === "category"
              ? selectedNode.data.product_name
              : selectedNode?.type === "profile"
                ? selectedNode.data.display_name
                : selectedNode?.type === "strategyBundle"
                  ? "Marketing Strategies"
                  : "Strategy Details"
          }
          icon={
            selectedNode?.type === "category"
              ? Blocks
              : selectedNode?.type === "profile"
                ? Users
                : Filter
          }
          isEditing={
            isEditing &&
            (selectedNode?.type === "strategy" ||
              selectedNode?.type === "strategyBundle")
          }
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
              : selectedNode?.type === "strategyBundle"
                ? handleSaveStrategyBundle
                : undefined
          }
          onCancel={
            selectedNode?.type === "strategy"
              ? () => {
                  setIsEditing(false);
                  setEditedDescription(selectedNode.data.description);
                }
              : selectedNode?.type === "strategyBundle"
                ? () => {
                    setIsEditing(false);
                    // Reset to original descriptions
                    const resetStrategies: Record<StrategyType, string> = {
                      "problem-awareness": "",
                      "brand-awareness": "",
                      consideration: "",
                      conversion: "",
                      loyalty: "",
                    };
                    selectedNode.data.strategies.forEach((s) => {
                      if (s.node_id.startsWith("problemaware_"))
                        resetStrategies["problem-awareness"] = s.description;
                      else if (s.node_id.startsWith("brandaware_"))
                        resetStrategies["brand-awareness"] = s.description;
                      else if (s.node_id.startsWith("consideration_"))
                        resetStrategies.consideration = s.description;
                      else if (s.node_id.startsWith("conversion_"))
                        resetStrategies.conversion = s.description;
                      else if (s.node_id.startsWith("loyalty_"))
                        resetStrategies.loyalty = s.description;
                    });
                    setEditedStrategies(resetStrategies);
                  }
                : undefined
          }
          onDelete={
            selectedNode?.type === "strategy"
              ? () => setIsDeleteDialogOpen(true)
              : selectedNode?.type === "profile"
                ? () => setIsUnlinkProfileDialogOpen(true)
                : undefined
          }
          deleteButtonLabel={
            selectedNode?.type === "profile" ? "Unlink" : undefined
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
                <p className="font-semibold">Description:</p>
                <p className="text-sm text-dashboard-gray-600">
                  {selectedNode.data.description || "No description provided."}
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
          ) : selectedNode?.type === "strategyBundle" ? (
            <MiniMarketingFunnel
              strategies={selectedNode.data.strategies}
              selectedMode={selectedStrategyMode}
              onModeChange={setSelectedStrategyMode}
              onDescriptionChange={(mode, value) => {
                setEditedStrategies((prev) => ({
                  ...prev,
                  [mode]: value,
                }));
              }}
              descriptions={editedStrategies}
              isEditing={isEditing}
            />
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

        {/* Link Customer Profile Dialog */}
        <Dialog
          open={isLinkProfileDialogOpen}
          onOpenChange={setIsLinkProfileDialogOpen}
        >
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Link Customer Profile</DialogTitle>
              <DialogDescription>
                Select which customer profile should be targeted with messaging
                about this product category.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {allProfiles.filter(
                (p) =>
                  !profilesForCategory.some((lp) => lp.node_id === p.node_id),
              ).length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No available customer profiles to link. All profiles are
                  already linked.
                </p>
              ) : (
                <>
                  <Label>Select Customer Profile</Label>
                  <select
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={selectedProfileToLink?.node_id || ""}
                    onChange={(e) => {
                      const profile = allProfiles.find(
                        (p) => p.node_id === e.target.value,
                      );
                      setSelectedProfileToLink(profile || null);
                    }}
                  >
                    <option value="">-- Select Customer Profile --</option>
                    {allProfiles
                      .filter(
                        (p) =>
                          !profilesForCategory.some(
                            (lp) => lp.node_id === p.node_id,
                          ),
                      )
                      .map((profile) => (
                        <option key={profile.node_id} value={profile.node_id}>
                          {profile.display_name}
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
                  setIsLinkProfileDialogOpen(false);
                  setSelectedProfileToLink(null);
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleLinkCustomerProfile}
                disabled={
                  !selectedProfileToLink || linkProfileMutation.isPending
                }
              >
                {linkProfileMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Linking...
                  </>
                ) : (
                  "Link Customer Profile"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Unlink Customer Profile Confirmation */}
        <AlertDialog
          open={isUnlinkProfileDialogOpen}
          onOpenChange={setIsUnlinkProfileDialogOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Unlink Customer Profile?</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to unlink "
                {selectedNode?.type === "profile"
                  ? selectedNode.data.display_name
                  : ""}
                "? This will also delete all associated marketing strategies for
                this customer profile/category pair. This action cannot be
                undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleUnlinkCustomerProfile}
                className="bg-brand-red hover:bg-brand-red/90"
              >
                Unlink and Delete Strategies
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

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
