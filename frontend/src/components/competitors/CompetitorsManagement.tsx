import { useState, useMemo, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import type { Node, Edge } from "reactflow";
import "reactflow/dist/style.css";
import {
  Plus,
  Trash2,
  Users,
  Pencil,
  ThumbsUp,
  ThumbsDown,
  Package,
  Loader2,
  Info,
  ShieldAlert,
  Star,
  Dumbbell,
  Unlink,
  Swords,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import type {
  Competitor,
  CompetitorCreate,
  CompetitorDependentCounts,
} from "@/services/competitorService";
import { competitorService } from "@/services/competitorService";
import type {
  CompetitorStrength,
  CompetitorStrengthCreate,
} from "@/services/competitorStrengthService";
import type {
  CompetitorWeakness,
  CompetitorWeaknessCreate,
} from "@/services/competitorWeaknessService";
import type {
  SubstituteProduct,
  SubstituteProductCreate,
} from "@/services/substituteProductService";
import type {
  CompetitorTactic,
  CompetitorTacticCreate,
} from "@/services/competitorTacticService";
import type { Risk, RiskCreate } from "@/services/riskService";
import type {
  Opportunity,
  OpportunityCreate,
} from "@/services/opportunityService";
import type {
  ValueProposition,
  ValuePropositionCreate,
} from "@/services/valuePropositionService";
import {
  useCompetitors,
  useCreateCompetitor,
  useUpdateCompetitor,
  useDeleteCompetitor,
  useCompetitorStrengths,
  useCreateCompetitorStrength,
  useUpdateCompetitorStrength,
  useDeleteCompetitorStrength,
  useCompetitorWeaknesses,
  useCreateCompetitorWeakness,
  useUpdateCompetitorWeakness,
  useDeleteCompetitorWeakness,
  useSubstituteProducts,
  useCreateSubstituteProduct,
  useUpdateSubstituteProduct,
  useDeleteSubstituteProduct,
  useCompetitorTactics,
  useCreateCompetitorTactic,
  useUpdateCompetitorTactic,
  useDeleteCompetitorTactic,
  useLinkProductToSubstitute,
  useUnlinkProductFromSubstitute,
} from "@/queries/competitors";
import {
  useRisks,
  useCreateRisk,
  useUpdateRisk,
  useDeleteRisk,
  useOpportunities,
  useCreateOpportunity,
  useUpdateOpportunity,
  useDeleteOpportunity,
} from "@/queries/swot";
import {
  useProducts,
  useValuePropositions,
  useCreateValueProposition,
  useUpdateValueProposition,
  useDeleteValueProposition,
} from "@/queries/products";
import { productService } from "@/services/productService";
import type { Product } from "@/services/productService";
import {
  CompetitorNode,
  CompetitorStrengthNode,
  CompetitorWeaknessNode,
  SubstituteProductNode,
  RiskNode,
  OpportunityNode,
  OurProductNode,
} from "./CompetitorFlowNodes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
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
  ModeSelector,
  KnowledgeGraphCard,
  HorizontalScrollList,
  HorizontalScrollItem,
  GraphVisualization,
  GraphVisualizationCard,
  KnowledgeGraphSideSheet,
  SideSheetNestedList,
  BorderedSection,
  SectionHeader,
  DIAGRAM_LAYOUT,
  DEFAULT_EDGE_STYLE,
  CARD_HEIGHTS,
} from "@/components/knowledge-graph";
import type {
  ModeConfig,
  KnowledgeGraphItem,
} from "@/components/knowledge-graph";
import {
  CompetitorModal,
  DeleteCompetitorDialog,
  StrengthModal,
  DeleteStrengthDialog,
  WeaknessModal,
  DeleteWeaknessDialog,
  TacticModal,
  DeleteTacticDialog,
  SubstituteProductModal,
  DeleteSubstituteProductDialog,
  RiskModal,
  DeleteRiskDialog,
  OpportunityModal,
  DeleteOpportunityDialog,
  ValuePropositionModal,
  DeleteValuePropositionDialog,
} from "./modals";
import { CompetitorKeywordsSection } from "./CompetitorKeywordsSection";

type CompetitorMode = "strengths" | "weaknesses" | "substitute-products";

interface CompetitorsManagementProps {
  hasEditAccess: boolean;
}

interface FormDataState {
  display_name: string;
  description: string;
  product_name?: string;
  product_detail_page?: string;
}

const COMPETITOR_MODES: readonly ModeConfig<CompetitorMode>[] = [
  { value: "strengths", label: "Strengths" },
  { value: "weaknesses", label: "Weaknesses" },
  { value: "substitute-products", label: "Substitute Products" },
] as const;

// CompetitorStrength and CompetitorWeakness expose `display_name`;
// SubstituteProduct uses `product_name` for the same role. This helper picks
// the right field via the `in` operator (which narrows the union without a
// runtime check), so a single render site can label any child entity without
// the caller needing to know the mode.
//
// Named `getChildName` (not `childLabel`) because the component scope already
// defines a local `childLabel: string` for human-readable labels.
const getChildName = (
  child:
    | CompetitorStrength
    | CompetitorWeakness
    | SubstituteProduct
    | null
    | undefined,
): string => {
  if (!child) return "";
  return "display_name" in child ? child.display_name : child.product_name;
};

// Same pattern for grandchildren: Risk and Opportunity expose `display_name`;
// Product (the linked product in substitute-products mode) uses `product_name`.
const getGrandchildName = (
  g: Risk | Opportunity | Product | null | undefined,
): string => {
  if (!g) return "";
  return "display_name" in g ? g.display_name : g.product_name;
};

export const CompetitorsManagement = ({
  hasEditAccess,
}: CompetitorsManagementProps) => {
  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const hasProcessedNavigation = useRef(false);

  // Mode state
  const [mode, setMode] = useState<CompetitorMode>("strengths");

  // Fetch competitors
  const { data: competitorsData, isLoading: isLoadingCompetitors } =
    useCompetitors(selectedOrgAccount?.accountId || null);
  const competitors = competitorsData?.competitors || [];

  // Selected competitor state
  const [selectedCompetitorId, setSelectedCompetitorId] = useState<
    string | null
  >(null);
  const [selectedCompetitor, setSelectedCompetitor] =
    useState<Competitor | null>(null);

  // Competitor UI state
  const [isCreateCompetitorModalOpen, setIsCreateCompetitorModalOpen] =
    useState(false);
  const [isDeleteCompetitorDialogOpen, setIsDeleteCompetitorDialogOpen] =
    useState(false);
  const [competitorFormData, setCompetitorFormData] =
    useState<CompetitorCreate>({
      display_name: "",
      description: "",
      references: [],
    });
  const [competitorDependentCounts, setCompetitorDependentCounts] =
    useState<CompetitorDependentCounts | null>(null);
  const [isLoadingDependentCounts, setIsLoadingDependentCounts] =
    useState(false);

  // Scroll state - now handled by HorizontalScrollList component

  // Child node state (strength, weakness, or substitute product) - MUST be before queries
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);
  const [selectedChild, setSelectedChild] = useState<
    CompetitorStrength | CompetitorWeakness | SubstituteProduct | null
  >(null);

  // Grandchild state. In strengths/weaknesses mode this holds a Risk or
  // Opportunity; in substitute-products mode it holds a Product (the linked
  // product that this substitute competes with). The state type reflects all
  // three runtime shapes — handlers narrow via `mode` or the explicit casts
  // below.
  const [selectedGrandchildId, setSelectedGrandchildId] = useState<
    string | null
  >(null);
  const [selectedGrandchild, setSelectedGrandchild] = useState<
    Risk | Opportunity | Product | null
  >(null);

  // Fetch children based on mode and selected competitor
  const { data: strengthsData, isLoading: isLoadingStrengths } =
    useCompetitorStrengths(
      mode === "strengths" ? selectedOrgAccount?.accountId || null : null,
      mode === "strengths" ? selectedCompetitorId : null,
    );
  const strengths = strengthsData?.strengths || [];

  const { data: weaknessesData, isLoading: isLoadingWeaknesses } =
    useCompetitorWeaknesses(
      mode === "weaknesses" ? selectedOrgAccount?.accountId || null : null,
      mode === "weaknesses" ? selectedCompetitorId : null,
    );
  const weaknesses = weaknessesData?.weaknesses || [];

  const {
    data: substituteProductsData,
    isLoading: isLoadingSubstituteProducts,
  } = useSubstituteProducts(
    mode === "substitute-products"
      ? selectedOrgAccount?.accountId || null
      : null,
    mode === "substitute-products" ? selectedCompetitorId : null,
    null, // No product filter on Competitors page
  );
  const substituteProducts = substituteProductsData?.products || [];

  // Grandchildren (risks from strengths, opportunities from weaknesses)
  const selectedStrength =
    mode === "strengths"
      ? strengths.find((s) => s.node_id === selectedChildId)
      : null;
  const selectedWeakness =
    mode === "weaknesses"
      ? weaknesses.find((w) => w.node_id === selectedChildId)
      : null;

  const { data: risksData, isLoading: isLoadingRisks } = useRisks(
    mode === "strengths" && selectedStrength?.node_id
      ? selectedOrgAccount?.accountId || null
      : null,
    mode === "strengths" && selectedStrength?.node_id
      ? selectedStrength.node_id
      : null,
    "strength", // Indicate this is a CompetitorStrength parent
  );
  const risks = risksData?.risks || [];

  const { data: opportunitiesData, isLoading: isLoadingOpportunities } =
    useOpportunities(
      mode === "weaknesses" && selectedWeakness?.node_id
        ? selectedOrgAccount?.accountId || null
        : null,
      mode === "weaknesses" && selectedWeakness?.node_id
        ? selectedWeakness.node_id
        : null,
      "weakness", // Indicate this is a CompetitorWeakness parent
    );
  const opportunities = opportunitiesData?.opportunities || [];

  // Context menu state
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [contextMenuType, setContextMenuType] = useState<
    "competitor" | "child" | "grandchild" | null
  >(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormDataState>({
    display_name: "",
    description: "",
  });

  // Create/delete dialogs for children
  const [isCreateChildModalOpen, setIsCreateChildModalOpen] = useState(false);
  const [isDeleteChildDialogOpen, setIsDeleteChildDialogOpen] = useState(false);
  const [isCreateGrandchildModalOpen, setIsCreateGrandchildModalOpen] =
    useState(false);
  const [isDeleteGrandchildDialogOpen, setIsDeleteGrandchildDialogOpen] =
    useState(false);

  // Child form data
  const [childFormData, setChildFormData] = useState<
    | CompetitorStrengthCreate
    | CompetitorWeaknessCreate
    | SubstituteProductCreate
  >({
    display_name: "",
    description: "",
    competitor_node_id: "",
    references: [],
  });

  // Grandchild form data
  const [grandchildFormData, setGrandchildFormData] = useState<
    RiskCreate | OpportunityCreate
  >({
    display_name: "",
    description: "",
    weakness_node_id: "",
    references: [],
  });

  // Tactics state (shown in competitor side sheet)
  const { data: tacticsData, isLoading: isLoadingTactics } =
    useCompetitorTactics(
      selectedCompetitorId ? selectedOrgAccount?.accountId || null : null,
      selectedCompetitorId,
    );
  const tactics = tacticsData?.tactics || [];

  const [selectedTactic, setSelectedTactic] = useState<CompetitorTactic | null>(
    null,
  );
  const [isCreateTacticModalOpen, setIsCreateTacticModalOpen] = useState(false);
  const [isDeleteTacticDialogOpen, setIsDeleteTacticDialogOpen] =
    useState(false);
  const [tacticFormData, setTacticFormData] = useState<CompetitorTacticCreate>({
    display_name: "",
    description: "",
    competitor_node_id: "",
    references: [],
  });

  // Value Propositions state (for substitute products and competitors)
  // Query VPs for either: Competitor (when viewing competitor) or SubstituteProduct (when viewing substitute)
  const vpParentNodeId =
    contextMenuType === "competitor"
      ? selectedCompetitor?.node_id
      : mode === "substitute-products" && selectedChildId
        ? selectedChildId
        : null;

  const { data: valuePropositionsData, isLoading: isLoadingVPs } =
    useValuePropositions(
      vpParentNodeId ? selectedOrgAccount?.accountId || null : null,
      vpParentNodeId,
    );
  const valuePropositions = valuePropositionsData?.value_propositions || [];

  // Products linked to selected SubstituteProduct (for React Flow)
  const { data: linkedProductsData, isLoading: isLoadingLinkedProducts } =
    useProducts(
      mode === "substitute-products" && selectedChildId
        ? selectedOrgAccount?.accountId || null
        : null,
      null, // No category filter
      mode === "substitute-products" && selectedChildId
        ? selectedChildId // SubstituteProduct node_id
        : null,
    );
  const linkedProducts = linkedProductsData?.products || [];

  const [selectedValueProposition, setSelectedValueProposition] =
    useState<ValueProposition | null>(null);
  const [isCreateVPModalOpen, setIsCreateVPModalOpen] = useState(false);
  const [isDeleteVPDialogOpen, setIsDeleteVPDialogOpen] = useState(false);
  const [valuePropositionFormData, setValuePropositionFormData] =
    useState<ValuePropositionCreate>({
      display_name: "",
      description: "",
      parent_node_id: "",
      parent_node_type: "SubstituteProduct",
      references: [],
    });

  // Link product dialog state
  const [isLinkProductDialogOpen, setIsLinkProductDialogOpen] = useState(false);
  const [selectedProductToLink, setSelectedProductToLink] =
    useState<Product | null>(null);
  const [linkDialogProducts, setLinkDialogProducts] = useState<Product[]>([]);
  const [isLoadingLinkDialogProducts, setIsLoadingLinkDialogProducts] =
    useState(false);

  // Mutations
  const createCompetitorMutation = useCreateCompetitor();
  const updateCompetitorMutation = useUpdateCompetitor();
  const deleteCompetitorMutation = useDeleteCompetitor();

  const createStrengthMutation = useCreateCompetitorStrength();
  const updateStrengthMutation = useUpdateCompetitorStrength();
  const deleteStrengthMutation = useDeleteCompetitorStrength();

  const createWeaknessMutation = useCreateCompetitorWeakness();
  const updateWeaknessMutation = useUpdateCompetitorWeakness();
  const deleteWeaknessMutation = useDeleteCompetitorWeakness();

  const createSubstituteProductMutation = useCreateSubstituteProduct();
  const updateSubstituteProductMutation = useUpdateSubstituteProduct();
  const deleteSubstituteProductMutation = useDeleteSubstituteProduct();

  const createRiskMutation = useCreateRisk();
  const updateRiskMutation = useUpdateRisk();
  const deleteRiskMutation = useDeleteRisk();

  const createOpportunityMutation = useCreateOpportunity();
  const updateOpportunityMutation = useUpdateOpportunity();
  const deleteOpportunityMutation = useDeleteOpportunity();

  const createTacticMutation = useCreateCompetitorTactic();
  const updateTacticMutation = useUpdateCompetitorTactic();
  const deleteTacticMutation = useDeleteCompetitorTactic();

  const createVPMutation = useCreateValueProposition();
  const updateVPMutation = useUpdateValueProposition();
  const deleteVPMutation = useDeleteValueProposition();

  // Link/Unlink mutations
  const linkProductMutation = useLinkProductToSubstitute();
  const unlinkProductMutation = useUnlinkProductFromSubstitute();

  // Mode switch handler
  const handleModeSwitch = (newMode: CompetitorMode) => {
    if (isEditing) {
      toast({
        title: "Unsaved Changes",
        description:
          "Please save or cancel your changes before switching modes",
        variant: "destructive",
      });
      return;
    }

    setMode(newMode);
    setSelectedChildId(null);
    setSelectedChild(null);
    setSelectedGrandchildId(null);
    setSelectedGrandchild(null);
    setIsContextMenuOpen(false);
  };

  // Handle navigation from other pages (e.g., Products page)
  useEffect(() => {
    const navState = location.state as {
      selectedSubstituteProductId?: string;
      competitorNodeId?: string;
      autoEdit?: boolean;
    } | null;

    if (
      navState?.selectedSubstituteProductId &&
      navState?.competitorNodeId &&
      navState?.autoEdit &&
      !hasProcessedNavigation.current
    ) {
      // Step 1: Select the competitor if not already selected
      if (navState.competitorNodeId !== selectedCompetitorId) {
        const competitor = competitors.find(
          (c) => c.node_id === navState.competitorNodeId,
        );
        if (competitor) {
          setSelectedCompetitorId(competitor.node_id);
          setSelectedCompetitor(competitor);
          setMode("substitute-products");
          // Don't mark as processed yet - wait for substitute products to load
          return;
        }
      }

      // Step 2: Once competitor is selected and substitute products loaded, select the substitute
      if (
        selectedCompetitorId &&
        mode === "substitute-products" &&
        substituteProducts.length > 0
      ) {
        const substitute = substituteProducts.find(
          (s) => s.node_id === navState.selectedSubstituteProductId,
        );

        if (substitute) {
          // Substitute found - select it and enter edit mode
          hasProcessedNavigation.current = true;

          setSelectedChildId(substitute.node_id);
          setSelectedChild(substitute);
          setFormData({
            display_name: substitute.product_name,
            description: substitute.description,
            product_name: substitute.product_name,
            product_detail_page: substitute.product_detail_page || "",
          });
          setContextMenuType("child");
          setIsContextMenuOpen(true);
          setIsEditing(true);

          // Clear navigation state
          navigate(location.pathname, { replace: true, state: {} });
        }
      }
    }
  }, [
    location.state,
    competitors,
    selectedCompetitorId,
    mode,
    substituteProducts,
    navigate,
    location.pathname,
  ]);

  // Competitor handlers
  const handleCompetitorClick = (competitor: Competitor) => {
    setSelectedCompetitorId(competitor.node_id);
    setSelectedCompetitor(competitor);
    setSelectedChildId(null);
    setSelectedChild(null);
    setSelectedGrandchildId(null);
    setSelectedGrandchild(null);
  };

  const handleCreateCompetitor = async (data?: CompetitorCreate) => {
    if (!selectedOrgAccount?.accountId) return;

    const competitorData = data || competitorFormData;

    if (!competitorData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Competitor name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating competitor...");
      setIsCreateCompetitorModalOpen(false);

      await createCompetitorMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        competitor: competitorData,
      });

      toast({
        title: "Success",
        description: "Competitor created successfully",
      });

      setCompetitorFormData({
        display_name: "",
        description: "",
        references: [],
      });
    } catch (error) {
      console.error("Failed to create competitor:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create competitor";

        if (status === 409) {
          toast({
            title: "Duplicate Competitor",
            description: "A competitor with this name already exists",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to create competitors",
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

  const handleUpdateCompetitor = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Competitor name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Updating competitor...");
      setIsEditing(false);

      const updatedCompetitor = await updateCompetitorMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedCompetitor.node_id,
        updates: {
          display_name: formData.display_name,
          description: formData.description,
        },
      });

      setSelectedCompetitor(updatedCompetitor);

      toast({
        title: "Success",
        description: "Competitor updated successfully",
      });
    } catch (error) {
      console.error("Failed to update competitor:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update competitor";
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

  const handleInitiateDeleteCompetitor = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    // Fetch dependent counts
    setIsDeleteCompetitorDialogOpen(true);
    setIsLoadingDependentCounts(true);

    try {
      const counts = await competitorService.getDependentCounts(
        selectedOrgAccount.accountId,
        selectedCompetitor.node_id,
      );
      setCompetitorDependentCounts(counts);
    } catch (error) {
      console.error("Failed to fetch dependent counts:", error);
      toast({
        title: "Error",
        description: "Failed to load deletion preview",
        variant: "destructive",
      });
    } finally {
      setIsLoadingDependentCounts(false);
    }
  };

  const handleDeleteCompetitor = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    try {
      startOperation("Deleting competitor...");
      setIsDeleteCompetitorDialogOpen(false);

      await deleteCompetitorMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedCompetitor.node_id,
        cascade: true,
      });

      setSelectedCompetitorId(null);
      setSelectedCompetitor(null);
      setSelectedChildId(null);
      setSelectedChild(null);
      setIsContextMenuOpen(false);
      setCompetitorDependentCounts(null);

      toast({
        title: "Success",
        description: "Competitor and all related data deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete competitor:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to delete competitor";
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

  // React Flow node types
  const nodeTypes = useMemo(() => {
    if (mode === "strengths") {
      return {
        competitorNode: CompetitorNode,
        competitorStrengthNode: CompetitorStrengthNode,
        riskNode: RiskNode,
      };
    } else if (mode === "weaknesses") {
      return {
        competitorNode: CompetitorNode,
        competitorWeaknessNode: CompetitorWeaknessNode,
        opportunityNode: OpportunityNode,
      };
    } else if (mode === "substitute-products") {
      return {
        competitorNode: CompetitorNode,
        substituteProductNode: SubstituteProductNode,
        ourProductNode: OurProductNode,
      };
    }
    return {};
  }, [mode]);

  // Generate nodes for React Flow (only 2 levels: child → grandchildren)
  const generateNodes = (): Node[] => {
    if (!selectedChild) return [];

    const nodes: Node[] = [];
    const gap = DIAGRAM_LAYOUT.HORIZONTAL_GAP;

    if (mode === "strengths") {
      const strength = selectedChild as CompetitorStrength;

      // Row 1: Competitor node
      if (selectedCompetitor) {
        nodes.push({
          id: selectedCompetitor.node_id,
          type: "competitorNode",
          position: {
            x: DIAGRAM_LAYOUT.PARENT_NODE_X,
            y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
          },
          data: {
            label: selectedCompetitor.display_name,
            isSelected: false,
            showHandle: false, // Hide "+" button in detail view
            onAddChild: () => {},
          },
        });
      }

      // Row 2: Strength node
      nodes.push({
        id: strength.node_id,
        type: "competitorStrengthNode",
        position: {
          x: DIAGRAM_LAYOUT.PARENT_NODE_X,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: strength.display_name,
          isSelected: !selectedGrandchildId,
          onAddRisk: () => setIsCreateGrandchildModalOpen(true),
        },
      });

      // Row 3: Risks
      const grandchildWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
      const grandchildTotalWidth = risks.length * grandchildWidth - gap;
      const grandchildStartX =
        DIAGRAM_LAYOUT.PARENT_NODE_X - grandchildTotalWidth / 2;

      risks.forEach((risk, index) => {
        nodes.push({
          id: risk.node_id,
          type: "riskNode",
          position: {
            x: grandchildStartX + index * grandchildWidth,
            y:
              DIAGRAM_LAYOUT.PARENT_NODE_Y +
              DIAGRAM_LAYOUT.VERTICAL_SPACING * 2,
          },
          data: {
            label: risk.display_name,
            showHandle: false,
            isSelected: selectedGrandchildId === risk.node_id,
            onAddSubstitute: () => {},
          },
        });
      });
    } else if (mode === "weaknesses") {
      const weakness = selectedChild as CompetitorWeakness;

      // Row 1: Competitor node
      if (selectedCompetitor) {
        nodes.push({
          id: selectedCompetitor.node_id,
          type: "competitorNode",
          position: {
            x: DIAGRAM_LAYOUT.PARENT_NODE_X,
            y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
          },
          data: {
            label: selectedCompetitor.display_name,
            isSelected: false,
            showHandle: false, // Hide "+" button in detail view
            onAddChild: () => {},
          },
        });
      }

      // Row 2: Weakness node
      nodes.push({
        id: weakness.node_id,
        type: "competitorWeaknessNode",
        position: {
          x: DIAGRAM_LAYOUT.PARENT_NODE_X,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: weakness.display_name,
          isSelected: !selectedGrandchildId,
          onAddOpportunity: () => setIsCreateGrandchildModalOpen(true),
        },
      });

      // Row 3: Opportunities
      const grandchildWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
      const grandchildTotalWidth = opportunities.length * grandchildWidth - gap;
      const grandchildStartX =
        DIAGRAM_LAYOUT.PARENT_NODE_X - grandchildTotalWidth / 2;

      opportunities.forEach((opportunity, index) => {
        nodes.push({
          id: opportunity.node_id,
          type: "opportunityNode",
          position: {
            x: grandchildStartX + index * grandchildWidth,
            y:
              DIAGRAM_LAYOUT.PARENT_NODE_Y +
              DIAGRAM_LAYOUT.VERTICAL_SPACING * 2,
          },
          data: {
            label: opportunity.display_name,
            showHandle: false,
            isSelected: selectedGrandchildId === opportunity.node_id,
            onAddSubstitute: () => {},
          },
        });
      });
    } else if (mode === "substitute-products") {
      const substituteProduct = selectedChild as SubstituteProduct;

      // Row 1: Competitor node
      if (selectedCompetitor) {
        nodes.push({
          id: selectedCompetitor.node_id,
          type: "competitorNode",
          position: {
            x: DIAGRAM_LAYOUT.PARENT_NODE_X,
            y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
          },
          data: {
            label: selectedCompetitor.display_name,
            isSelected: false,
            showHandle: false, // Hide "+" button in detail view
            onAddChild: () => {},
          },
        });
      }

      // Row 2: SubstituteProduct node
      nodes.push({
        id: substituteProduct.node_id,
        type: "substituteProductNode",
        position: {
          x: DIAGRAM_LAYOUT.PARENT_NODE_X,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: substituteProduct.product_name,
          isSelected: !selectedGrandchildId,
          showHandle: true, // Show "+" button to link products
          onAddProduct: () => handleOpenLinkDialog(),
        },
      });

      // Row 3: Linked Products
      const grandchildWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
      const grandchildTotalWidth =
        linkedProducts.length * grandchildWidth - gap;
      const grandchildStartX =
        DIAGRAM_LAYOUT.PARENT_NODE_X - grandchildTotalWidth / 2;

      linkedProducts.forEach((product, index) => {
        nodes.push({
          id: product.node_id,
          type: "ourProductNode",
          position: {
            x: grandchildStartX + index * grandchildWidth,
            y:
              DIAGRAM_LAYOUT.PARENT_NODE_Y +
              DIAGRAM_LAYOUT.VERTICAL_SPACING * 2,
          },
          data: {
            label: product.product_name,
            showHandle: false,
            isSelected: selectedGrandchildId === product.node_id,
          },
        });
      });
    }

    return nodes;
  };

  // Generate edges for React Flow
  const generateEdges = (): Edge[] => {
    if (!selectedChild) return [];

    const edges: Edge[] = [];

    if (mode === "strengths" && selectedChildId && selectedCompetitor) {
      // Competitor → Strength edge
      edges.push({
        id: `${selectedCompetitor.node_id}-${selectedChildId}`,
        source: selectedCompetitor.node_id,
        target: selectedChildId,
        type: "smoothstep",
        style: DEFAULT_EDGE_STYLE,
        sourceHandle: "bottom",
        targetHandle: "top",
      });

      // Strength → Risks edges
      risks.forEach((risk) => {
        edges.push({
          id: `${selectedChildId}-${risk.node_id}`,
          source: selectedChildId,
          target: risk.node_id,
          type: "smoothstep",
          style: DEFAULT_EDGE_STYLE,
          sourceHandle: "bottom",
          targetHandle: "top",
        });
      });
    } else if (mode === "weaknesses" && selectedChildId && selectedCompetitor) {
      // Competitor → Weakness edge
      edges.push({
        id: `${selectedCompetitor.node_id}-${selectedChildId}`,
        source: selectedCompetitor.node_id,
        target: selectedChildId,
        type: "smoothstep",
        style: DEFAULT_EDGE_STYLE,
        sourceHandle: "bottom",
        targetHandle: "top",
      });

      // Weakness → Opportunities edges
      opportunities.forEach((opportunity) => {
        edges.push({
          id: `${selectedChildId}-${opportunity.node_id}`,
          source: selectedChildId,
          target: opportunity.node_id,
          type: "smoothstep",
          style: DEFAULT_EDGE_STYLE,
          sourceHandle: "bottom",
          targetHandle: "top",
        });
      });
    } else if (
      mode === "substitute-products" &&
      selectedChildId &&
      selectedCompetitor
    ) {
      // Competitor → SubstituteProduct edge
      edges.push({
        id: `${selectedCompetitor.node_id}-${selectedChildId}`,
        source: selectedCompetitor.node_id,
        target: selectedChildId,
        type: "smoothstep",
        style: DEFAULT_EDGE_STYLE,
        sourceHandle: "bottom",
        targetHandle: "top",
      });

      // SubstituteProduct → Products edges
      linkedProducts.forEach((product) => {
        edges.push({
          id: `${selectedChildId}-${product.node_id}`,
          source: selectedChildId,
          target: product.node_id,
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
  const handleNodeClick = (event: React.MouseEvent, node: Node) => {
    // Prevent event from bubbling to pane click which would close the sheet
    event.stopPropagation();

    if (isEditing) {
      toast({
        title: "Unsaved Changes",
        description: "Please save or cancel your changes first",
        variant: "destructive",
      });
      return;
    }

    // Competitor node click
    if (node.type === "competitorNode") {
      if (selectedCompetitor) {
        setFormData({
          display_name: selectedCompetitor.display_name,
          description: selectedCompetitor.description,
        });
        setContextMenuType("competitor");
        setIsContextMenuOpen(true);
      }
      return;
    }

    // Child nodes (strength/weakness) - now at second row of diagram
    if (
      node.type === "competitorStrengthNode" ||
      node.type === "competitorWeaknessNode"
    ) {
      // Just open the side sheet for the already-selected child.
      // `node.type` check above guarantees selectedChild is a strength or
      // weakness here (not a SubstituteProduct), so display_name is present.
      if (selectedChild) {
        const child = selectedChild as CompetitorStrength | CompetitorWeakness;
        setFormData({
          display_name: child.display_name,
          description: child.description,
        });

        setContextMenuType("child");
        setIsContextMenuOpen(true);
      }
      return;
    }

    // Grandchild nodes (risk or opportunity)
    if (node.type === "riskNode" || node.type === "opportunityNode") {
      const grandchildren = mode === "strengths" ? risks : opportunities;
      const grandchild = grandchildren.find((g) => g.node_id === node.id);
      if (!grandchild) return;

      setSelectedGrandchildId(node.id);
      setSelectedGrandchild(grandchild);

      setFormData({
        display_name: grandchild.display_name,
        description: grandchild.description,
      });

      setContextMenuType("grandchild");
      setIsContextMenuOpen(true);
    }

    // Product nodes (in substitute-products mode)
    if (node.type === "ourProductNode" && mode === "substitute-products") {
      const product = linkedProducts.find((p) => p.node_id === node.id);
      if (product) {
        setSelectedGrandchild(product as any); // Cast needed for type compatibility
        setSelectedGrandchildId(product.node_id);
        // Open side sheet to allow unlinking
        setContextMenuType("grandchild");
        setIsContextMenuOpen(true);
      }
      return;
    }

    // SubstituteProduct node (parent in diagram)
    if (
      node.type === "substituteProductNode" &&
      mode === "substitute-products"
    ) {
      // Open side sheet for substitute product (shows VPs)
      if (selectedChild) {
        const subProduct = selectedChild as SubstituteProduct;
        setFormData({
          display_name: subProduct.product_name,
          description: subProduct.description,
          product_name: subProduct.product_name,
          product_detail_page: subProduct.product_detail_page || "",
        } as any);
        setContextMenuType("child");
        setIsContextMenuOpen(true);
      }
      return;
    }
  };

  // Handle opening link product dialog
  const handleOpenLinkDialog = async () => {
    if (!selectedOrgAccount?.accountId) return;

    setIsLinkProductDialogOpen(true);
    setIsLoadingLinkDialogProducts(true);

    try {
      // Load ALL products in the account
      // We need to call the service directly since useProducts requires a filter
      const response = await productService.list(
        selectedOrgAccount.accountId,
        undefined, // No category filter
        undefined, // No substitute filter
        0,
        1000,
      );

      // Filter out already linked products
      const linkedProductIds = new Set(linkedProducts.map((p) => p.node_id));
      const availableProducts = response.products.filter(
        (p) => !linkedProductIds.has(p.node_id),
      );

      setLinkDialogProducts(availableProducts);
    } catch (error) {
      console.error("Failed to load products:", error);
      toast({
        title: "Error",
        description: "Failed to load products",
        variant: "destructive",
      });
    } finally {
      setIsLoadingLinkDialogProducts(false);
    }
  };

  // Handle linking product
  const handleLinkProduct = async () => {
    if (
      !selectedOrgAccount?.accountId ||
      !selectedChild ||
      !selectedProductToLink
    )
      return;

    try {
      startOperation("Linking product...");

      await linkProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        substituteProductId: selectedChild.node_id,
        productNodeId: selectedProductToLink.node_id,
      });

      toast({
        title: "Success",
        description: "Product linked successfully",
      });

      setIsLinkProductDialogOpen(false);
      setSelectedProductToLink(null);
    } catch (error) {
      console.error("Failed to link product:", error);
      toast({
        title: "Error",
        description: "Failed to link product",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // Handle unlinking product
  const handleUnlinkProduct = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild || !selectedGrandchild)
      return;

    try {
      startOperation("Unlinking product...");

      await unlinkProductMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        substituteProductId: selectedChild.node_id,
        productNodeId: selectedGrandchild.node_id,
      });

      toast({
        title: "Success",
        description: "Product unlinked successfully",
      });

      setIsContextMenuOpen(false);
      setSelectedGrandchild(null);
      setSelectedGrandchildId(null);
    } catch (error) {
      console.error("Failed to unlink product:", error);
      toast({
        title: "Error",
        description: "Failed to unlink product",
        variant: "destructive",
      });
    } finally {
      endOperation();
    }
  };

  // Handle navigating to Products page to edit a product
  const handleNavigateToProductEdit = () => {
    if (!selectedGrandchild) return;
    const product = selectedGrandchild as Product;
    // Navigate to Products page with selected product, category, and auto-edit mode
    navigate("/knowledge/products", {
      state: {
        selectedProductId: product.node_id,
        categoryNodeId: product.category_node_id,
        autoEdit: true,
      },
    });
  };

  // Create child (strength, weakness, or substitute product)
  const handleCreateChild = async (
    data?:
      | CompetitorStrengthCreate
      | CompetitorWeaknessCreate
      | SubstituteProductCreate,
  ) => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    const childData = data || childFormData;

    // TODO: discriminate on `mode` and validate product_name for
    // substitute-products instead of casting through display_name.
    if (
      !(childData as { display_name: string }).display_name.trim() ||
      !childData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const childType =
        mode === "strengths"
          ? "strength"
          : mode === "weaknesses"
            ? "weakness"
            : "substitute product";
      startOperation(`Creating ${childType}...`);
      setIsCreateChildModalOpen(false);

      if (mode === "strengths") {
        await createStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          strength: {
            ...childData,
            competitor_node_id: selectedCompetitor.node_id,
          } as CompetitorStrengthCreate,
        });
      } else if (mode === "weaknesses") {
        await createWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          weakness: {
            ...childData,
            competitor_node_id: selectedCompetitor.node_id,
          } as CompetitorWeaknessCreate,
        });
      } else {
        const subProductData = childData as SubstituteProductCreate;
        await createSubstituteProductMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          product: {
            // TODO: drop the display_name fallback once childFormData is
            // cleared on mode switch (currently it can carry a stale value).
            product_name:
              (subProductData as { display_name?: string }).display_name ||
              subProductData.product_name,
            description: subProductData.description,
            competitor_node_id: selectedCompetitor.node_id,
            references: subProductData.references || [],
            product_detail_page: (subProductData as any).product_detail_page,
          },
        });
      }

      toast({
        title: "Success",
        description: `${childType.charAt(0).toUpperCase() + childType.slice(1)} created successfully`,
      });

      setChildFormData({
        display_name: "",
        description: "",
        competitor_node_id: "",
        references: [],
      });
    } catch (error) {
      console.error("Failed to create child:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const childType =
          mode === "strengths"
            ? "strength"
            : mode === "weaknesses"
              ? "weakness"
              : "substitute product";
        const message =
          error.response?.data?.detail || `Failed to create ${childType}`;

        if (status === 409) {
          toast({
            title: "Duplicate",
            description: `A ${childType} with this name already exists`,
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: `You don't have permission to create ${childType}s`,
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

  // Update child
  const handleUpdateChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild) return;

    if (!formData.display_name.trim() && !formData.product_name?.trim()) {
      toast({
        title: "Validation Error",
        description: "Name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      const childType =
        mode === "strengths"
          ? "strength"
          : mode === "weaknesses"
            ? "weakness"
            : "substitute product";
      startOperation(`Updating ${childType}...`);
      setIsEditing(false);

      if (mode === "strengths") {
        await updateStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: {
            display_name: formData.display_name,
            description: formData.description,
          },
        });
      } else if (mode === "weaknesses") {
        await updateWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: {
            display_name: formData.display_name,
            description: formData.description,
          },
        });
      } else {
        await updateSubstituteProductMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: {
            product_name: formData.product_name,
            description: formData.description,
            product_detail_page: formData.product_detail_page,
          },
        });
      }

      toast({
        title: "Success",
        description: `${childType.charAt(0).toUpperCase() + childType.slice(1)} updated successfully`,
      });
    } catch (error) {
      console.error("Failed to update child:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to update";
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

  // Delete child
  const handleDeleteChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild) return;

    try {
      const childType =
        mode === "strengths"
          ? "strength"
          : mode === "weaknesses"
            ? "weakness"
            : "substitute product";
      startOperation(`Deleting ${childType}...`);
      setIsDeleteChildDialogOpen(false);

      if (mode === "strengths") {
        await deleteStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
        });
      } else if (mode === "weaknesses") {
        await deleteWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
        });
      } else {
        await deleteSubstituteProductMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
        });
      }

      setIsContextMenuOpen(false);
      setSelectedChildId(null);
      setSelectedChild(null);
      setSelectedGrandchildId(null);
      setSelectedGrandchild(null);

      toast({
        title: "Success",
        description: `${childType.charAt(0).toUpperCase() + childType.slice(1)} deleted successfully`,
      });
    } catch (error) {
      console.error("Failed to delete child:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to delete";
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

  // Create grandchild (risk or opportunity)
  const handleCreateGrandchild = async (
    data?: RiskCreate | OpportunityCreate,
  ) => {
    if (!selectedOrgAccount?.accountId || !selectedChild) return;

    const grandchildData = data || grandchildFormData;

    if (
      !grandchildData.display_name.trim() ||
      !grandchildData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "risk" : "opportunity";
      startOperation(`Creating ${label}...`);
      setIsCreateGrandchildModalOpen(false);

      if (mode === "strengths") {
        // Competitor strength creates risk (linked to the competitor strength)
        await createRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          risk: {
            display_name: grandchildData.display_name,
            description: grandchildData.description,
            references: grandchildData.references || [],
            strength_node_id: selectedChild.node_id, // CompetitorStrength node_id
          } as RiskCreate,
        });
      } else {
        // Competitor weakness creates opportunity (linked to the competitor weakness)
        await createOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          opportunity: {
            display_name: grandchildData.display_name,
            description: grandchildData.description,
            references: grandchildData.references || [],
            weakness_node_id: selectedChild.node_id, // CompetitorWeakness node_id
          } as OpportunityCreate,
        });
      }

      toast({
        title: "Success",
        description: `${label.charAt(0).toUpperCase() + label.slice(1)} created successfully`,
      });

      setGrandchildFormData({
        display_name: "",
        description: "",
        weakness_node_id: "",
        strength_node_id: "",
        references: [],
      } as RiskCreate | OpportunityCreate);
    } catch (error) {
      console.error("Failed to create grandchild:", error);

      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        let message = "Failed to create";

        // Handle Pydantic validation errors (422)
        if (Array.isArray(detail)) {
          message = detail.map((err: any) => err.msg).join(", ");
        } else if (typeof detail === "string") {
          message = detail;
        }

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

  // Update grandchild
  const handleUpdateGrandchild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedGrandchild || !selectedChild)
      return;

    if (!formData.display_name.trim() || !formData.description.trim()) {
      toast({
        title: "Validation Error",
        description: "Name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "risk" : "opportunity";
      startOperation(`Updating ${label}...`);
      setIsEditing(false);

      const updateData = {
        display_name: formData.display_name.trim(),
        description: formData.description.trim(),
      };

      if (mode === "strengths") {
        await updateRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          updates: updateData,
          strengthId: selectedChild.node_id, // CompetitorStrength node_id
        });
      } else {
        await updateOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          updates: updateData,
          weaknessId: selectedChild.node_id, // CompetitorWeakness node_id
        });
      }

      toast({
        title: "Success",
        description: `${label.charAt(0).toUpperCase() + label.slice(1)} updated successfully`,
      });
    } catch (error) {
      console.error("Failed to update grandchild:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to update";
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

  // Delete grandchild
  const handleDeleteGrandchild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedGrandchild || !selectedChild)
      return;

    try {
      const label = mode === "strengths" ? "risk" : "opportunity";
      startOperation(`Deleting ${label}...`);
      setIsDeleteGrandchildDialogOpen(false);

      if (mode === "strengths") {
        await deleteRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          strengthId: selectedChild.node_id, // CompetitorStrength node_id
        });
      } else {
        await deleteOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          weaknessId: selectedChild.node_id, // CompetitorWeakness node_id
        });
      }

      setIsContextMenuOpen(false);
      setSelectedGrandchildId(null);
      setSelectedGrandchild(null);

      toast({
        title: "Success",
        description: `${label.charAt(0).toUpperCase() + label.slice(1)} deleted successfully`,
      });
    } catch (error) {
      console.error("Failed to delete grandchild:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to delete";
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

  // Tactic handlers
  const handleCreateTactic = async (data?: CompetitorTacticCreate) => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    const tacticData = data || tacticFormData;

    if (!tacticData.display_name.trim() || !tacticData.description.trim()) {
      toast({
        title: "Validation Error",
        description: "Tactic name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating tactic...");

      await createTacticMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        tactic: {
          ...tacticData,
          competitor_node_id: selectedCompetitor.node_id,
        },
      });

      toast({
        title: "Success",
        description: "Tactic created successfully",
      });

      setIsCreateTacticModalOpen(false);
      setTacticFormData({
        display_name: "",
        description: "",
        competitor_node_id: "",
        references: [],
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to create tactic";
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

  const handleUpdateTactic = async (data?: CompetitorTacticCreate) => {
    if (!selectedOrgAccount || !selectedTactic) return;

    const tacticData = data || tacticFormData;

    try {
      startOperation("Updating tactic...");

      await updateTacticMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedTactic.node_id,
        updates: {
          display_name: tacticData.display_name,
          description: tacticData.description,
          references: tacticData.references,
        },
      });

      toast({
        title: "Success",
        description: "Tactic updated successfully",
      });

      setIsCreateTacticModalOpen(false);
      setSelectedTactic(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update tactic";
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

  const handleDeleteTactic = async () => {
    if (!selectedOrgAccount || !selectedTactic) return;

    try {
      startOperation("Deleting tactic...");

      await deleteTacticMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedTactic.node_id,
      });

      toast({
        title: "Success",
        description: "Tactic deleted successfully",
      });

      setIsDeleteTacticDialogOpen(false);
      setSelectedTactic(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to delete tactic";
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

  // Value Proposition handlers (for substitute products)
  const handleCreateValueProposition = async (
    data?: ValuePropositionCreate,
  ) => {
    if (!selectedOrgAccount) return;

    const vpData = data || valuePropositionFormData;

    try {
      startOperation("Creating value proposition...");

      await createVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        valueProposition: vpData,
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
        parent_node_type: "SubstituteProduct",
        references: [],
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to create value proposition";
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

  const handleUpdateValueProposition = async (
    data?: ValuePropositionCreate,
  ) => {
    if (!selectedOrgAccount || !selectedValueProposition) return;

    const vpData = data || valuePropositionFormData;

    try {
      startOperation("Updating value proposition...");

      await updateVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedValueProposition.node_id,
        updates: {
          display_name: vpData.display_name,
          description: vpData.description,
          references: vpData.references,
        },
        parentNodeId: vpData.parent_node_id,
      });

      toast({
        title: "Success",
        description: "Value proposition updated successfully",
      });

      setIsCreateVPModalOpen(false);
      setSelectedValueProposition(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update value proposition";
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
        const message =
          error.response?.data?.detail || "Failed to delete value proposition";
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

  // Derived values
  const isLoadingChildren =
    mode === "strengths"
      ? isLoadingStrengths
      : mode === "weaknesses"
        ? isLoadingWeaknesses
        : isLoadingSubstituteProducts;

  const childLabel =
    mode === "strengths"
      ? "Strength"
      : mode === "weaknesses"
        ? "Weakness"
        : "Substitute Product";

  const childrenLabel =
    mode === "strengths"
      ? "Competitor Strengths"
      : mode === "weaknesses"
        ? "Competitor Weaknesses"
        : "Substitute Products";

  const grandchildLabel =
    mode === "strengths"
      ? "Risk"
      : mode === "weaknesses"
        ? "Opportunity"
        : "Product";
  const grandchildrenLabel =
    mode === "strengths"
      ? "Risks"
      : mode === "weaknesses"
        ? "Opportunities"
        : "Linked Products";

  // Derived values for children display
  const children =
    mode === "strengths"
      ? strengths
      : mode === "weaknesses"
        ? weaknesses
        : substituteProducts;

  // Get display properties based on mode
  const getChildIcon = () => {
    if (mode === "strengths") return Dumbbell;
    if (mode === "weaknesses") return Unlink;
    return Package;
  };

  const getChildBgColor = () => {
    if (mode === "strengths") return "bg-brand-light-red bg-opacity-30";
    if (mode === "weaknesses") return "bg-brand-light-green bg-opacity-30";
    return "bg-brand-yellow bg-opacity-30";
  };

  const getChildIconBgColor = () => {
    if (mode === "strengths") return "bg-brand-light-red";
    if (mode === "weaknesses") return "bg-brand-light-green";
    return "bg-brand-yellow";
  };

  const ChildIcon = getChildIcon();

  const nodes = useMemo(
    () => generateNodes(),
    [
      selectedChild,
      mode,
      risks,
      opportunities,
      linkedProducts, // CHANGED: from valuePropositions
      selectedGrandchildId,
    ],
  );
  const edges = useMemo(
    () => generateEdges(),
    [
      selectedChild,
      selectedChildId,
      mode,
      risks,
      opportunities,
      linkedProducts, // CHANGED: from valuePropositions
    ],
  );

  return (
    <>
      {/* Card 1: Competitors horizontal scroll */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Swords className="h-5 w-5" />
              <h3 className="text-lg font-semibold">Competitors</h3>
            </div>
            {hasEditAccess && (
              <Button
                onClick={() => setIsCreateCompetitorModalOpen(true)}
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0"
              >
                <Plus className="h-5 w-5" />
              </Button>
            )}
          </div>
          <HorizontalScrollList
            items={competitors}
            selectedId={selectedCompetitorId}
            onItemClick={handleCompetitorClick}
            isLoading={isLoadingCompetitors}
            emptyMessage="No competitors found."
            emptyMessageWithAction="Click '+' to add one."
            hasEditAccess={hasEditAccess}
            renderItem={(competitor, isSelected) => (
              <HorizontalScrollItem
                label={competitor.display_name}
                sublabel="Competitor"
                icon={Swords}
                bgColor="bg-brand-light-blue bg-opacity-30"
                iconBgColor="bg-brand-light-blue"
                isSelected={isSelected}
                onClick={() => {}}
              />
            )}
          />
        </CardContent>
      </Card>

      {/* Card 2: Mode Selector + Children + React Flow */}
      {!selectedCompetitorId ? (
        <div className="p-6 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border-default)] h-[37.5rem] flex items-center justify-center">
          <p className="text-[var(--color-text-tertiary)] text-center">
            Select a competitor to view{" "}
            {mode === "strengths"
              ? "strengths"
              : mode === "weaknesses"
                ? "weaknesses"
                : "substitute products"}
            .
          </p>
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6 space-y-6">
            {/* Selected Competitor Heading */}
            {selectedCompetitor && (
              <div className="flex items-start justify-between gap-4">
                <h2 className="text-2xl font-semibold text-[var(--color-text-primary)]">
                  {selectedCompetitor.display_name}
                </h2>
                {hasEditAccess && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleInitiateDeleteCompetitor}
                  >
                    Delete Competitor
                  </Button>
                )}
              </div>
            )}

            {/* Mode Selector - Inside card */}
            <ModeSelector
              modes={COMPETITOR_MODES}
              value={mode}
              onChange={handleModeSwitch}
            />
            {/* Children Section (Strengths/Weaknesses/Substitutes) */}
            <KnowledgeGraphCard
              title={childrenLabel}
              icon={ChildIcon}
              tooltip={
                mode === "strengths"
                  ? "Competitor strengths create risks for your business. Identify their advantages and the threats they pose."
                  : mode === "weaknesses"
                    ? "Competitor weaknesses create opportunities for your business. Identify their disadvantages and how you can capitalize."
                    : "Substitute products offered by this competitor that compete with your products or services."
              }
              actions={
                hasEditAccess ? (
                  <Button
                    onClick={() => setIsCreateChildModalOpen(true)}
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
                // TODO: loosen KnowledgeGraphItem (display_name optional +
                // product_name optional) so SubstituteProduct satisfies the
                // constraint structurally and this double-cast goes away.
                items={children as unknown as KnowledgeGraphItem[]}
                selectedId={selectedChildId}
                onItemClick={(child) => {
                  setSelectedChildId(child.node_id);
                  setSelectedChild(
                    child as unknown as
                      | CompetitorStrength
                      | CompetitorWeakness
                      | SubstituteProduct,
                  );
                  setSelectedGrandchildId(null);
                  setSelectedGrandchild(null);
                  // Don't auto-open side sheet for substitute products
                  // User must click on a node in React Flow to view/edit
                }}
                isLoading={isLoadingChildren}
                emptyMessage={`No ${childrenLabel.toLowerCase()} found.`}
                emptyMessageWithAction="Click '+' to add one."
                hasEditAccess={hasEditAccess}
                renderItem={(child, isSelected) => {
                  const displayName =
                    mode === "substitute-products"
                      ? (child as unknown as SubstituteProduct).product_name
                      : (child as CompetitorStrength | CompetitorWeakness)
                          .display_name;

                  return (
                    <HorizontalScrollItem
                      label={displayName}
                      sublabel={childLabel}
                      icon={ChildIcon}
                      bgColor={getChildBgColor()}
                      iconBgColor={getChildIconBgColor()}
                      isSelected={isSelected}
                      onClick={() => {}}
                    />
                  );
                }}
              />
            </KnowledgeGraphCard>

            {/* React Flow Visualization */}
            <GraphVisualizationCard
              title={grandchildrenLabel}
              icon={
                mode === "strengths"
                  ? ShieldAlert
                  : mode === "weaknesses"
                    ? Star
                    : Package
              }
              tooltip={
                mode === "strengths"
                  ? "Risks created by this competitor strength."
                  : mode === "weaknesses"
                    ? "Opportunities created by this competitor weakness."
                    : "Value propositions offered by this substitute product."
              }
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeClick}
              isLoading={
                isLoadingChildren ||
                (mode === "strengths" && isLoadingRisks) ||
                (mode === "weaknesses" && isLoadingOpportunities) ||
                (mode === "substitute-products" && isLoadingVPs)
              }
              showEmpty={!selectedChildId}
              emptyMessage={`Select a ${mode === "strengths" ? "strength" : mode === "weaknesses" ? "weakness" : "substitute product"} to view ${grandchildrenLabel.toLowerCase()}.`}
            />
          </CardContent>
        </Card>
      )}

      {/* Create Competitor Modal */}
      <CompetitorModal
        isOpen={isCreateCompetitorModalOpen}
        onClose={() => {
          setIsCreateCompetitorModalOpen(false);
          setCompetitorFormData({
            display_name: "",
            description: "",
            references: [],
          });
        }}
        onSubmit={async (data) => {
          await handleCreateCompetitor(data);
        }}
        mode="create"
      />

      {/* Delete Competitor Dialog */}
      <DeleteCompetitorDialog
        isOpen={isDeleteCompetitorDialogOpen}
        onClose={() => {
          setIsDeleteCompetitorDialogOpen(false);
          setCompetitorDependentCounts(null);
        }}
        onConfirm={handleDeleteCompetitor}
        competitorName={selectedCompetitor?.display_name || ""}
        dependentCounts={competitorDependentCounts || undefined}
        isLoadingCounts={isLoadingDependentCounts}
      />

      {/* Create Child Modals (Strength, Weakness, or Substitute Product) */}
      {mode === "strengths" && (
        <>
          <StrengthModal
            isOpen={isCreateChildModalOpen}
            onClose={() => {
              setIsCreateChildModalOpen(false);
              setChildFormData({
                display_name: "",
                description: "",
                competitor_node_id: "",
                references: [],
              });
            }}
            onSubmit={async (data) => {
              await handleCreateChild(data);
            }}
            competitorId={selectedCompetitor?.node_id || ""}
            competitorName={selectedCompetitor?.display_name || ""}
            mode="create"
          />
          <DeleteStrengthDialog
            isOpen={isDeleteChildDialogOpen}
            onClose={() => setIsDeleteChildDialogOpen(false)}
            onConfirm={handleDeleteChild}
            strengthName={getChildName(selectedChild)}
          />
        </>
      )}
      {mode === "weaknesses" && (
        <>
          <WeaknessModal
            isOpen={isCreateChildModalOpen}
            onClose={() => {
              setIsCreateChildModalOpen(false);
              setChildFormData({
                display_name: "",
                description: "",
                competitor_node_id: "",
                references: [],
              });
            }}
            onSubmit={async (data) => {
              await handleCreateChild(data);
            }}
            competitorId={selectedCompetitor?.node_id || ""}
            competitorName={selectedCompetitor?.display_name || ""}
            mode="create"
          />
          <DeleteWeaknessDialog
            isOpen={isDeleteChildDialogOpen}
            onClose={() => setIsDeleteChildDialogOpen(false)}
            onConfirm={handleDeleteChild}
            weaknessName={getChildName(selectedChild)}
          />
        </>
      )}
      {mode === "substitute-products" && (
        <>
          <SubstituteProductModal
            isOpen={isCreateChildModalOpen}
            onClose={() => {
              setIsCreateChildModalOpen(false);
              setChildFormData({
                display_name: "",
                description: "",
                competitor_node_id: "",
                references: [],
              });
            }}
            onSubmit={async (data) => {
              await handleCreateChild(data);
            }}
            competitorId={selectedCompetitor?.node_id || ""}
            competitorName={selectedCompetitor?.display_name || ""}
            mode="create"
          />
          <DeleteSubstituteProductDialog
            isOpen={isDeleteChildDialogOpen}
            onClose={() => setIsDeleteChildDialogOpen(false)}
            onConfirm={handleDeleteChild}
            productName={
              (selectedChild as SubstituteProduct)?.product_name || ""
            }
          />
        </>
      )}

      {/* Create Grandchild Modals (Risk or Opportunity) */}
      {mode === "strengths" && (
        <>
          <RiskModal
            isOpen={isCreateGrandchildModalOpen}
            onClose={() => {
              setIsCreateGrandchildModalOpen(false);
              setGrandchildFormData({
                display_name: "",
                description: "",
                strength_node_id: "",
                references: [],
              });
            }}
            onSubmit={async (data) => {
              await handleCreateGrandchild(data);
            }}
            strengthId={selectedChild?.node_id || ""}
            strengthName={getChildName(selectedChild)}
            mode="create"
          />
          <DeleteRiskDialog
            isOpen={isDeleteGrandchildDialogOpen}
            onClose={() => setIsDeleteGrandchildDialogOpen(false)}
            onConfirm={handleDeleteGrandchild}
            riskName={getGrandchildName(selectedGrandchild)}
          />
        </>
      )}
      {mode === "weaknesses" && (
        <>
          <OpportunityModal
            isOpen={isCreateGrandchildModalOpen}
            onClose={() => {
              setIsCreateGrandchildModalOpen(false);
              setGrandchildFormData({
                display_name: "",
                description: "",
                weakness_node_id: "",
                references: [],
              });
            }}
            onSubmit={async (data) => {
              await handleCreateGrandchild(data);
            }}
            weaknessId={selectedChild?.node_id || ""}
            weaknessName={getChildName(selectedChild)}
            mode="create"
          />
          <DeleteOpportunityDialog
            isOpen={isDeleteGrandchildDialogOpen}
            onClose={() => setIsDeleteGrandchildDialogOpen(false)}
            onConfirm={handleDeleteGrandchild}
            opportunityName={getGrandchildName(selectedGrandchild)}
          />
        </>
      )}

      {/* Create/Edit Tactic Modal */}
      <TacticModal
        isOpen={isCreateTacticModalOpen}
        onClose={() => {
          setIsCreateTacticModalOpen(false);
          setSelectedTactic(null);
        }}
        onSubmit={async (data) => {
          if (selectedTactic) {
            await handleUpdateTactic(data);
          } else {
            await handleCreateTactic(data);
          }
        }}
        competitorId={selectedCompetitor?.node_id || ""}
        competitorName={selectedCompetitor?.display_name || ""}
        initialData={selectedTactic || undefined}
        mode={selectedTactic ? "edit" : "create"}
      />

      {/* Delete Tactic Dialog */}
      <DeleteTacticDialog
        isOpen={isDeleteTacticDialogOpen}
        onClose={() => {
          setIsDeleteTacticDialogOpen(false);
          setSelectedTactic(null);
        }}
        onConfirm={handleDeleteTactic}
        tacticName={selectedTactic?.display_name || ""}
      />

      {/* Create/Edit Value Proposition Modal (for substitute products and competitors) */}
      <ValuePropositionModal
        isOpen={isCreateVPModalOpen}
        onClose={() => {
          setIsCreateVPModalOpen(false);
          setSelectedValueProposition(null);
        }}
        onSubmit={async (data) => {
          if (selectedValueProposition) {
            await handleUpdateValueProposition(data);
          } else {
            await handleCreateValueProposition(data);
          }
        }}
        parentNodeId={valuePropositionFormData.parent_node_id}
        parentNodeType={valuePropositionFormData.parent_node_type}
        parentDisplayName={
          contextMenuType === "competitor"
            ? selectedCompetitor?.display_name || ""
            : (selectedChild as SubstituteProduct)?.product_name || ""
        }
        initialData={selectedValueProposition || undefined}
        mode={selectedValueProposition ? "edit" : "create"}
      />

      {/* Delete Value Proposition Dialog */}
      <DeleteValuePropositionDialog
        isOpen={isDeleteVPDialogOpen}
        onClose={() => {
          setIsDeleteVPDialogOpen(false);
          setSelectedValueProposition(null);
        }}
        onConfirm={handleDeleteValueProposition}
        valuePropositionName={selectedValueProposition?.display_name || ""}
      />

      {/* Link Product Dialog */}
      <Dialog
        open={isLinkProductDialogOpen}
        onOpenChange={setIsLinkProductDialogOpen}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Link Product to Substitute</DialogTitle>
            <DialogDescription>
              Select which of your products may be substituted by this
              competitor's offering.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {isLoadingLinkDialogProducts ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : linkDialogProducts.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No available products to link. All products are already linked
                or you have no products yet.
              </p>
            ) : (
              <>
                <Label>Select Product</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={selectedProductToLink?.node_id || ""}
                  onChange={(e) => {
                    const product = linkDialogProducts.find(
                      (p) => p.node_id === e.target.value,
                    );
                    setSelectedProductToLink(product || null);
                  }}
                >
                  <option value="">-- Select Product --</option>
                  {linkDialogProducts.map((product) => (
                    <option key={product.node_id} value={product.node_id}>
                      {product.product_name}
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
                setIsLinkProductDialogOpen(false);
                setSelectedProductToLink(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleLinkProduct}
              disabled={!selectedProductToLink || linkProductMutation.isPending}
            >
              {linkProductMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Linking...
                </>
              ) : (
                "Link Product"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Context Menu Side Sheet - Single unified sheet */}
      {isContextMenuOpen && (
        <KnowledgeGraphSideSheet
          open={true}
          onOpenChange={(open) => {
            if (
              !open &&
              (isCreateTacticModalOpen ||
                isDeleteTacticDialogOpen ||
                isCreateVPModalOpen ||
                isDeleteVPDialogOpen)
            ) {
              return;
            }

            if (!open && isEditing) {
              toast({
                title: "Unsaved Changes",
                description: "Please save or cancel your changes first",
                variant: "destructive",
              });
              return;
            }

            setIsContextMenuOpen(open);
            if (!open) {
              setIsEditing(false);
            }
          }}
          title={
            contextMenuType === "competitor"
              ? "Competitor"
              : contextMenuType === "child"
                ? childLabel
                : contextMenuType === "grandchild" &&
                    mode === "substitute-products"
                  ? (selectedGrandchild as Product)?.product_name || "Product"
                  : grandchildLabel
          }
          icon={
            contextMenuType === "competitor"
              ? Users
              : contextMenuType === "child"
                ? mode === "strengths"
                  ? ThumbsUp
                  : mode === "weaknesses"
                    ? ThumbsDown
                    : Package
                : mode === "strengths"
                  ? ShieldAlert
                  : Star
          }
          isEditing={isEditing}
          onSave={
            contextMenuType === "competitor"
              ? handleUpdateCompetitor
              : contextMenuType === "child"
                ? handleUpdateChild
                : handleUpdateGrandchild
          }
          onCancel={() => {
            setIsEditing(false);
            if (contextMenuType === "competitor" && selectedCompetitor) {
              setFormData({
                display_name: selectedCompetitor.display_name,
                description: selectedCompetitor.description,
              });
            } else if (contextMenuType === "child" && selectedChild) {
              if (mode === "substitute-products") {
                const subProduct = selectedChild as SubstituteProduct;
                setFormData({
                  display_name: "",
                  description: subProduct.description,
                  product_name: subProduct.product_name,
                  product_detail_page: subProduct.product_detail_page || "",
                });
              } else {
                const child = selectedChild as
                  | CompetitorStrength
                  | CompetitorWeakness;
                setFormData({
                  display_name: child.display_name,
                  description: child.description,
                });
              }
            } else if (contextMenuType === "grandchild" && selectedGrandchild) {
              // Product grandchildren route through the navigate-to-edit
              // handler, so this branch only sees Risk | Opportunity.
              const grandchild = selectedGrandchild as Risk | Opportunity;
              setFormData({
                display_name: grandchild.display_name,
                description: grandchild.description,
              });
            }
          }}
          onEdit={
            contextMenuType === "grandchild" && mode === "substitute-products"
              ? handleNavigateToProductEdit
              : () => setIsEditing(true)
          }
          onDelete={
            contextMenuType === "grandchild" && mode === "substitute-products"
              ? handleUnlinkProduct
              : () => {
                  setIsContextMenuOpen(false);
                  if (contextMenuType === "competitor") {
                    setIsDeleteCompetitorDialogOpen(true);
                  } else if (contextMenuType === "child") {
                    setIsDeleteChildDialogOpen(true);
                  } else {
                    setIsDeleteGrandchildDialogOpen(true);
                  }
                }
          }
          deleteButtonLabel={
            contextMenuType === "grandchild" && mode === "substitute-products"
              ? "Unlink"
              : undefined
          }
          hasEditAccess={hasEditAccess}
          preventClose={isEditing}
        >
          {isEditing ? (
            <div className="space-y-4">
              <div>
                <Label htmlFor="context-edit-name">
                  {mode === "substitute-products" && contextMenuType === "child"
                    ? "Product Name:"
                    : "Name:"}
                </Label>
                <Input
                  id="context-edit-name"
                  value={
                    mode === "substitute-products" &&
                    contextMenuType === "child"
                      ? formData.product_name || ""
                      : formData.display_name
                  }
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      ...(mode === "substitute-products" &&
                      contextMenuType === "child"
                        ? { product_name: e.target.value }
                        : { display_name: e.target.value }),
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
              {mode === "substitute-products" &&
                contextMenuType === "child" && (
                  <div>
                    <Label htmlFor="context-edit-product-page">
                      Product Detail Page (Optional):
                    </Label>
                    <Input
                      id="context-edit-product-page"
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
                )}
            </div>
          ) : contextMenuType === "grandchild" &&
            mode === "substitute-products" ? (
            // Product view in substitute mode (read-only with navigation to edit)
            <div className="space-y-4">
              <div>
                <Label>Product Name</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  {(selectedGrandchild as Product)?.product_name}
                </p>
              </div>
              <div>
                <Label>Description</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  {(selectedGrandchild as Product)?.description}
                </p>
              </div>
              {(selectedGrandchild as Product)?.product_detail_page && (
                <div>
                  <Label>Product Page</Label>
                  <a
                    href={(selectedGrandchild as Product).product_detail_page}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline mt-1 block"
                  >
                    {(selectedGrandchild as Product).product_detail_page}
                  </a>
                </div>
              )}
              <div className="rounded-md bg-muted p-3 mt-4">
                <p className="text-xs text-muted-foreground">
                  This product may be substituted by the selected competitor
                  offering. Click "Unlink" to remove this relationship. Click
                  "Edit" to manage product details on the Products page.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="font-semibold">
                  {mode === "substitute-products" && contextMenuType === "child"
                    ? "Product Name:"
                    : "Name:"}
                </p>
                <p>
                  {contextMenuType === "competitor"
                    ? selectedCompetitor?.display_name
                    : contextMenuType === "child"
                      ? mode === "substitute-products"
                        ? (selectedChild as SubstituteProduct)?.product_name
                        : getChildName(selectedChild)
                      : getGrandchildName(selectedGrandchild)}
                </p>
              </div>
              <div>
                <p className="font-semibold">Description:</p>
                <p className="text-sm text-[var(--color-text-tertiary)]">
                  {contextMenuType === "competitor"
                    ? selectedCompetitor?.description
                    : contextMenuType === "child"
                      ? selectedChild?.description
                      : selectedGrandchild?.description}
                </p>
              </div>
              {mode === "substitute-products" &&
                contextMenuType === "child" &&
                (selectedChild as SubstituteProduct)?.product_detail_page && (
                  <div>
                    <p className="font-semibold">Product Detail Page:</p>
                    <a
                      href={
                        (selectedChild as SubstituteProduct).product_detail_page
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-800 underline break-all"
                    >
                      {(selectedChild as SubstituteProduct).product_detail_page}
                    </a>
                  </div>
                )}
            </div>
          )}

          {/* Tactics Section (for competitor context menu) */}
          {contextMenuType === "competitor" && !isEditing && (
            <SideSheetNestedList
              title="Marketing Tactics"
              tooltip="Specific tactics this competitor uses to bring products to market, such as social media campaigns, events, or advertising strategies."
              items={tactics}
              isLoading={isLoadingTactics}
              onAdd={() => {
                setTacticFormData({
                  display_name: "",
                  description: "",
                  competitor_node_id: selectedCompetitor?.node_id || "",
                  references: [],
                });
                setIsCreateTacticModalOpen(true);
              }}
              onEdit={(tactic) => {
                setSelectedTactic(tactic);
                setTacticFormData({
                  display_name: tactic.display_name,
                  description: tactic.description,
                  competitor_node_id: selectedCompetitor?.node_id || "",
                  references: tactic.references || [],
                });
                setIsCreateTacticModalOpen(true);
              }}
              onDelete={(tactic) => {
                setSelectedTactic(tactic);
                setIsDeleteTacticDialogOpen(true);
              }}
              hasEditAccess={hasEditAccess}
              isEditingParent={isEditing}
            />
          )}

          {/* Value Propositions Section (for competitor context menu) */}
          {contextMenuType === "competitor" && !isEditing && (
            <SideSheetNestedList
              title="Value Propositions"
              tooltip="Key reasons why customers might choose this competitor's offerings over yours."
              items={valuePropositions}
              isLoading={isLoadingVPs}
              onAdd={() => {
                setValuePropositionFormData({
                  display_name: "",
                  description: "",
                  parent_node_id: selectedCompetitor?.node_id || "",
                  parent_node_type: "Competitor",
                  references: [],
                });
                setIsCreateVPModalOpen(true);
              }}
              onEdit={(vp) => {
                setSelectedValueProposition(vp);
                setValuePropositionFormData({
                  display_name: vp.display_name,
                  description: vp.description,
                  parent_node_id: selectedCompetitor?.node_id || "",
                  parent_node_type: "Competitor",
                  references: vp.references || [],
                });
                setIsCreateVPModalOpen(true);
              }}
              onDelete={(vp) => {
                setSelectedValueProposition(vp);
                setValuePropositionFormData({
                  ...valuePropositionFormData,
                  parent_node_id: selectedCompetitor?.node_id || "",
                  parent_node_type: "Competitor",
                });
                setIsDeleteVPDialogOpen(true);
              }}
              hasEditAccess={hasEditAccess}
              isEditingParent={isEditing}
            />
          )}

          {/* Keywords Section (for competitor context menu) */}
          {contextMenuType === "competitor" &&
            selectedCompetitor &&
            !isEditing && (
              <CompetitorKeywordsSection
                competitorNodeId={selectedCompetitor.node_id}
                hasEditAccess={hasEditAccess}
              />
            )}

          {/* Value Propositions Section (for substitute products) */}
          {mode === "substitute-products" &&
            contextMenuType === "child" &&
            !isEditing && (
              <SideSheetNestedList
                title="Value Propositions"
                tooltip="Key reasons why customers might choose this substitute product over your offerings."
                items={valuePropositions}
                isLoading={isLoadingVPs}
                onAdd={() => {
                  setValuePropositionFormData({
                    display_name: "",
                    description: "",
                    parent_node_id: selectedChild?.node_id || "",
                    parent_node_type: "SubstituteProduct",
                    references: [],
                  });
                  setIsCreateVPModalOpen(true);
                }}
                onEdit={(vp) => {
                  setSelectedValueProposition(vp);
                  setValuePropositionFormData({
                    display_name: vp.display_name,
                    description: vp.description,
                    parent_node_id: selectedChild?.node_id || "",
                    parent_node_type: "SubstituteProduct",
                    references: vp.references || [],
                  });
                  setIsCreateVPModalOpen(true);
                }}
                onDelete={(vp) => {
                  setSelectedValueProposition(vp);
                  setValuePropositionFormData({
                    ...valuePropositionFormData,
                    parent_node_id: selectedChild?.node_id || "",
                  });
                  setIsDeleteVPDialogOpen(true);
                }}
                hasEditAccess={hasEditAccess}
                isEditingParent={isEditing}
              />
            )}
        </KnowledgeGraphSideSheet>
      )}
    </>
  );
};
